const resultCount = document.querySelector("#result-count");
const federalResults = document.querySelector("#federal-results");
const stateResults = document.querySelector("#state-results");
const federalResultsColumn = document.querySelector("#federal-results-column");
const stateResultsColumn = document.querySelector("#state-results-column");
const resultsGrid = document.querySelector("#results-grid");
const noSession = document.querySelector("#no-session");
const redoScreeningButton = document.querySelector("#redo-screening");

function syncResultScrollSpacer(container) {
  if (!container) return;

  const existing = container.querySelector(":scope > .result-scroll-spacer");
  if (existing) existing.remove();

  const cards = [...container.querySelectorAll(":scope > .card")];
  if (!cards.length) return;

  // Keep at least one viewport worth of trailing space so late cards can still align to top.
  const spacerHeight = Math.max(24, container.clientHeight);
  if (spacerHeight <= 0) return;

  const spacer = document.createElement("div");
  spacer.className = "result-scroll-spacer";
  spacer.style.height = `${spacerHeight}px`;
  spacer.setAttribute("aria-hidden", "true");
  container.appendChild(spacer);
}

function syncAllResultScrollSpacers() {
  syncResultScrollSpacer(federalResults);
  syncResultScrollSpacer(stateResults);
}

function getResultCardAnchors(container, cards) {
  const maxTop = Math.max(0, container.scrollHeight - container.clientHeight);
  return cards.map((card) => Math.max(0, Math.min(card.offsetTop, maxTop)));
}

function nearestAnchorIndex(anchors, top) {
  if (!anchors.length) return -1;
  return anchors.reduce((best, anchor, index) => {
    const bestDistance = Math.abs(anchors[best] - top);
    const distance = Math.abs(anchor - top);
    return distance < bestDistance ? index : best;
  }, 0);
}

function syncArrowIndex(container) {
  if (!container) return;
  const cards = [...container.querySelectorAll(":scope > .card")];
  if (!cards.length) {
    delete container.dataset.arrowIndex;
    return;
  }
  const anchors = getResultCardAnchors(container, cards);
  const index = nearestAnchorIndex(anchors, container.scrollTop);
  if (index >= 0) container.dataset.arrowIndex = String(index);
}

function scrollToResultCard(container, direction) {
  if (!container) return;

  const cards = [...container.querySelectorAll(":scope > .card")];
  if (!cards.length) {
    container.scrollBy({ top: direction === "down" ? 180 : -180, behavior: "smooth" });
    return;
  }

  const containerTop = container.getBoundingClientRect().top;
  const anchorLine = containerTop + 12;
  let currentIndex = cards.findIndex((card) => {
    const rect = card.getBoundingClientRect();
    return rect.top <= anchorLine && rect.bottom > anchorLine;
  });

  if (currentIndex === -1) {
    currentIndex = container.scrollTop <= 2 ? 0 : cards.length - 1;
  }

  const targetIndex = direction === "down"
    ? Math.min(cards.length - 1, currentIndex + 1)
    : Math.max(0, currentIndex - 1);
  const targetRect = cards[targetIndex].getBoundingClientRect();
  const targetTop = Math.max(0, container.scrollTop + (targetRect.top - containerTop));
  container.dataset.arrowIndex = String(targetIndex);
  container.scrollTo({ top: targetTop, behavior: "smooth" });
}

function redoScreening() {
  setSessionId(null);
  setActiveScope(null);
  state.currentQuestion = null;
  state.isScreeningFinished = false;
  state.latestPlan = null;
  state.latestResults = null;
  window.location.href = "/?redo=1";
}

function updateResultsLayout() {
  const federalOnly = isFederalOnlyScope();
  const stateOnly = isStateOnlyScope();
  if (federalResultsColumn) federalResultsColumn.classList.toggle("hidden", stateOnly);
  if (stateResultsColumn) stateResultsColumn.classList.toggle("hidden", federalOnly);
  if (resultsGrid) resultsGrid.classList.toggle("single-column", federalOnly || stateOnly);
}

function renderResults(payload) {
  state.latestResults = payload;
  updateResultsLayout();

  const federalOnly = isFederalOnlyScope();
  const stateOnly = isStateOnlyScope();
  const federalCount = stateOnly
    ? 0
    : payload.federal_results.filter((item) => item.eligibility_status !== "likely_ineligible").length;
  const stateCount = federalOnly
    ? 0
    : payload.state_results.filter((item) => item.eligibility_status !== "likely_ineligible").length;
  const totalMatches = federalCount + stateCount;
  resultCount.textContent = t("results.liveMatches", { count: totalMatches });

  if (!stateOnly) {
    federalResults.classList.remove("empty");
    federalResults.innerHTML = payload.federal_results.length
      ? payload.federal_results.map(renderResultCard).join("")
      : `<p class='meta'>${t("results.noFederal")}</p>`;
  }

  if (!federalOnly) {
    stateResults.classList.remove("empty");
    stateResults.innerHTML = payload.state_results.length
      ? payload.state_results.map(renderResultCard).join("")
      : `<p class='meta'>${t("results.noState")}</p>`;
  }

  syncAllResultScrollSpacers();
  if (!stateOnly) syncArrowIndex(federalResults);
  if (!federalOnly) syncArrowIndex(stateResults);
}

async function loadResults() {
  if (!state.sessionId) {
    noSession.classList.remove("hidden");
    noSession.innerHTML = `<p>${t("results.noSession")}</p>`;
    return;
  }
  const payload = await getJson(`/api/v1/sessions/${state.sessionId}/results`);
  renderResults(payload);
  restoreDocChecks();
}

document.querySelector("#export-results").addEventListener("click", () => {
  if (!state.sessionId) return;
  window.print();
});

document.querySelector("#download-pdf").addEventListener("click", () => {
  if (!state.sessionId || typeof html2pdf === "undefined") return;
  const element = document.querySelector("#results-grid");
  if (!element) return;
  const btn = document.querySelector("#download-pdf");
  setBusyButtonText(btn, true, t("results.generatingPdf"), t("results.downloadPdf"));
  btn.disabled = true;
  html2pdf()
    .set({
      margin: 10,
      filename: "benefits-report.pdf",
      image: { type: "jpeg", quality: 0.98 },
      html2canvas: { scale: 2, useCORS: true },
      jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
    })
    .from(element)
    .save()
    .then(() => {
      setBusyButtonText(btn, false, t("results.generatingPdf"), t("results.downloadPdf"));
      btn.disabled = false;
    });
});

  redoScreeningButton?.addEventListener("click", redoScreening);

  document.querySelectorAll(".result-nav-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const targetSelector = button.dataset.scrollTarget;
      const direction = button.dataset.scrollDirection === "up" ? "up" : "down";
      const container = targetSelector ? document.querySelector(targetSelector) : null;
      scrollToResultCard(container, direction);
    });
  });

  [federalResults, stateResults].forEach((container) => {
    if (!container) return;
    container.addEventListener("scroll", () => {
      window.clearTimeout(container._arrowSyncTimer);
      container._arrowSyncTimer = window.setTimeout(() => syncArrowIndex(container), 120);
    });
  });

/* ── Document checklist persistence ─────────────────────────── */

function getCheckedDocs() {
  try { return JSON.parse(localStorage.getItem("bd_checked_docs") || "{}"); } catch { return {}; }
}

function saveCheckedDocs(map) {
  localStorage.setItem("bd_checked_docs", JSON.stringify(map));
}

function restoreDocChecks() {
  const checked = getCheckedDocs();
  document.querySelectorAll(".doc-check").forEach((cb) => {
    const key = `${cb.dataset.program}::${cb.dataset.doc}`;
    if (checked[key]) {
      cb.checked = true;
      cb.closest(".checklist-item")?.classList.add("checked");
    }
  });
}

document.addEventListener("change", (e) => {
  if (!e.target.classList.contains("doc-check")) return;
  const cb = e.target;
  const key = `${cb.dataset.program}::${cb.dataset.doc}`;
  const checked = getCheckedDocs();
  if (cb.checked) {
    checked[key] = true;
    cb.closest(".checklist-item")?.classList.add("checked");
  } else {
    delete checked[key];
    cb.closest(".checklist-item")?.classList.remove("checked");
  }
  saveCheckedDocs(checked);
});

updateResultsLayout();
loadResults().catch((error) => {
  federalResults.innerHTML = `<p class="meta">${t("results.loadError", { error: error.message })}</p>`;
});

document.addEventListener("localechange", () => {
  if (state.latestResults) {
    renderResults(state.latestResults);
    restoreDocChecks();
  } else if (!state.sessionId) {
    noSession.innerHTML = `<p>${t("results.noSession")}</p>`;
  }
});

window.addEventListener("resize", () => {
  syncAllResultScrollSpacers();
});
