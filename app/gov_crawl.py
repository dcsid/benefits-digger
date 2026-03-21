from __future__ import annotations

import json
import logging
import re
from collections import deque
from typing import Any, Iterable, Optional
from urllib.parse import urljoin, urlparse

import httpx

from app.catalog import hash_content, is_official_government_url, strip_html
from app.config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()

TITLE_RE = re.compile(r"<title[^>]*>(?P<title>.*?)</title>", re.IGNORECASE | re.DOTALL)
META_DESCRIPTION_RE = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](?P<description>[^"\']+)["\']',
    re.IGNORECASE,
)
LINK_RE = re.compile(
    r'<a[^>]+href=["\'](?P<href>[^"\']+)["\'][^>]*>(?P<label>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)

GENERIC_BENEFIT_KEYWORDS = {
    "apply",
    "assistance",
    "benefit",
    "benefits",
    "eligibility",
    "help",
    "program",
    "services",
    "support",
}

CATEGORY_KEYWORDS = {
    "children_families": {"child", "children", "family", "pregnancy", "parent"},
    "death": {"burial", "death", "funeral", "survivor"},
    "disabilities": {"disability", "disabled", "impairment", "ssi", "ssdi"},
    "disasters": {"disaster", "emergency", "fema", "fire", "flood"},
    "education": {"education", "school", "student", "tuition"},
    "food": {"food", "nutrition", "snap", "wic"},
    "health": {"health", "medical", "medicaid", "medicare"},
    "housing_utilities": {"housing", "rent", "shelter", "utility", "voucher"},
    "jobs_unemployment": {"employment", "job", "unemployment", "workforce"},
    "military_veterans": {"military", "veteran", "va"},
    "retirement_seniors": {"retirement", "senior", "social security"},
    "welfare_cash_assistance": {"assistance", "cash", "tanf", "welfare"},
    "general": {"benefits", "program", "services"},
}


def category_keyword_hints(categories: Optional[Iterable[str]] = None) -> list[str]:
    hints = set(GENERIC_BENEFIT_KEYWORDS)
    for category in categories or []:
        hints.update(CATEGORY_KEYWORDS.get(category, {str(category).lower()}))
    return sorted(hints)


def _normalized_host(url: str) -> str:
    return (urlparse(url).netloc or "").lower().split(":")[0]


def _same_site(seed_host: str, url: str) -> bool:
    host = _normalized_host(url)
    if not host:
        return False
    return host == seed_host or host.endswith(f".{seed_host}") or seed_host.endswith(f".{host}")


def _extract_title(payload_text: str) -> str:
    match = TITLE_RE.search(payload_text or "")
    return strip_html(match.group("title")) if match else ""


def _extract_description(payload_text: str) -> str:
    match = META_DESCRIPTION_RE.search(payload_text or "")
    if match:
        return strip_html(match.group("description"))
    return ""


def _extract_excerpt(payload_text: str) -> str:
    description = _extract_description(payload_text)
    if description:
        return description[:800]
    return strip_html(payload_text)[:800]


def _keyword_score(text: str, keyword_hints: Iterable[str]) -> int:
    normalized = (text or "").lower()
    score = 0
    for keyword in keyword_hints:
        if keyword.lower() in normalized:
            score += 1
    return score


def _extract_links(base_url: str, payload_text: str, *, seed_host: str, keyword_hints: list[str]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    for match in LINK_RE.finditer(payload_text or ""):
        href = (match.group("href") or "").strip()
        if not href or href.startswith("#") or href.lower().startswith("javascript:") or href.lower().startswith("mailto:"):
            continue
        absolute_url = urljoin(base_url, href)
        if absolute_url in seen or not is_official_government_url(absolute_url) or not _same_site(seed_host, absolute_url):
            continue
        label = strip_html(match.group("label"))
        score = _keyword_score(f"{absolute_url} {label}", keyword_hints)
        if score <= 0 and "/benefit" not in absolute_url.lower() and "/program" not in absolute_url.lower():
            continue
        candidates.append({"url": absolute_url, "label": label, "score": str(score)})
        seen.add(absolute_url)
    candidates.sort(key=lambda item: (int(item["score"]), len(item["url"])), reverse=True)
    return candidates


def crawl_official_site(
    seed_url: str,
    *,
    timeout_seconds: float,
    max_pages: int,
    max_depth: int,
    keyword_hints: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    if not is_official_government_url(seed_url):
        return []

    hints = keyword_hints or sorted(GENERIC_BENEFIT_KEYWORDS)
    pages: list[dict[str, Any]] = []
    visited: set[str] = set()
    queue = deque([(seed_url, 0, None)])
    seed_host = _normalized_host(seed_url)

    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        while queue and len(pages) < max_pages:
            candidate_url, depth, discovered_from = queue.popleft()
            if candidate_url in visited:
                continue
            visited.add(candidate_url)
            try:
                response = client.get(candidate_url)
                response.raise_for_status()
            except Exception as exc:
                logger.debug("Skipping crawl URL %s: %s", candidate_url, exc)
                continue

            final_url = str(response.url)
            if not is_official_government_url(final_url) or not _same_site(seed_host, final_url):
                continue

            content_type = (response.headers.get("content-type") or "text/html").split(";")[0].strip()
            if "html" not in content_type and not content_type.startswith("text/"):
                continue

            payload_text = response.text
            title = _extract_title(payload_text) or final_url
            excerpt = _extract_excerpt(payload_text)
            if not excerpt:
                continue

            pages.append(
                {
                    "url": final_url,
                    "title": title[:200],
                    "excerpt": excerpt,
                    "depth": depth,
                    "discovered_from": discovered_from,
                    "content_hash": hash_content(payload_text),
                    "content_type": content_type,
                    "raw_excerpt": payload_text[:5000],
                }
            )

            if depth >= max_depth:
                continue

            for link in _extract_links(final_url, payload_text, seed_host=seed_host, keyword_hints=hints):
                if link["url"] not in visited:
                    queue.append((link["url"], depth + 1, final_url))

    return pages


def _heuristic_relevance_score(page: dict[str, Any], *, context_title: str, categories: list[str]) -> int:
    text = " ".join(
        [
            str(page.get("title") or ""),
            str(page.get("excerpt") or ""),
            str(page.get("url") or ""),
            str(context_title or ""),
        ]
    ).lower()
    score = _keyword_score(text, category_keyword_hints(categories))
    title_tokens = [token for token in re.findall(r"[a-z0-9]+", context_title.lower()) if len(token) > 3]
    for token in title_tokens:
        if token in text:
            score += 2
    if "/apply" in text or "eligibility" in text:
        score += 2
    return score


def filter_relevant_pages(
    pages: list[dict[str, Any]],
    *,
    context_title: str,
    jurisdiction_name: str,
    categories: Optional[list[str]] = None,
    max_results: int = 4,
) -> list[dict[str, Any]]:
    if not pages:
        return []

    categories = list(categories or [])
    heuristic_ranked = sorted(
        pages,
        key=lambda page: (
            _heuristic_relevance_score(page, context_title=context_title, categories=categories),
            -int(page.get("depth", 0)),
        ),
        reverse=True,
    )

    if not settings.gemini_api_key or len(pages) <= 1:
        return heuristic_ranked[:max_results]

    try:
        from google import genai

        client = genai.Client(api_key=settings.gemini_api_key)
        prompt = f"""You are filtering a crawl of official government pages for a benefits product.

Return ONLY JSON with this shape:
{{
  "selected_urls": ["https://..."]
}}

Select up to {max_results} URLs that are most relevant for official benefit information.

Context:
- Program or agency: {context_title}
- Jurisdiction: {jurisdiction_name}
- Categories: {json.dumps(categories)}

Rules:
- Only pick from the provided URLs.
- Prefer pages that explain eligibility, applications, benefits, or official program details.
- Avoid generic navigation, press, careers, or unrelated services pages.

Candidates:
{json.dumps([{"url": page["url"], "title": page["title"], "excerpt": page["excerpt"]} for page in pages], ensure_ascii=True)}
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "temperature": 0.1,
            },
        )
        payload = json.loads(response.text.strip())
        selected_urls = set(payload.get("selected_urls", []))
        if not selected_urls:
            return heuristic_ranked[:max_results]
        selected_pages = [page for page in heuristic_ranked if page["url"] in selected_urls]
        return selected_pages[:max_results] or heuristic_ranked[:max_results]
    except Exception as exc:  # pragma: no cover - external API fallback
        logger.warning("Gemini crawl filtering failed, using heuristic fallback: %s", exc)
        return heuristic_ranked[:max_results]
