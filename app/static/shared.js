const state = {
  sessionId: localStorage.getItem("bd_session_id") || null,
  currentQuestion: null,
  latestPlan: null,
  activeScope: localStorage.getItem("bd_active_scope") || null,
  isScreeningFinished: false,
};

function setSessionId(id) {
  state.sessionId = id;
  if (id) localStorage.setItem("bd_session_id", id);
  else localStorage.removeItem("bd_session_id");
}

function setActiveScope(scope) {
  state.activeScope = scope;
  if (scope) localStorage.setItem("bd_active_scope", scope);
  else localStorage.removeItem("bd_active_scope");
}

const categoryDefinitions = [
  { value: "children_families", label: "Children and families" },
  { value: "death", label: "Death" },
  { value: "disabilities", label: "Disabilities" },
  { value: "disasters", label: "Disasters" },
  { value: "education", label: "Education" },
  { value: "food", label: "Food" },
  { value: "health", label: "Health" },
  { value: "housing_utilities", label: "Housing and utilities" },
  { value: "jobs_unemployment", label: "Jobs and unemployment" },
  { value: "military_veterans", label: "Military and veterans" },
  { value: "retirement_seniors", label: "Retirement and seniors" },
  { value: "welfare_cash_assistance", label: "Welfare and cash assistance" },
];

const depthDescriptions = [
  { at: 0.0, label: "Quick", text: "Quick asks fewer, simpler questions and stops early once it has a light screen." },
  { at: 0.5, label: "Standard", text: "Standard asks a balanced number of questions with moderate detail." },
  { at: 1.0, label: "Deep", text: "Deep asks more specific questions with legal references and keeps going longer to tighten the match." },
];

const scenarioPresets = [
  {
    name: "If I had limited income and resources",
    description: "Useful for cash-assistance or SSI-style planning.",
    answers: { applicant_income: "Yes" },
  },
  {
    name: "If I had a qualifying disability",
    description: "Tests disability-related pathways and work-limitation rules.",
    answers: { applicant_disability: "Yes", applicant_ability_to_work: "Yes" },
  },
  {
    name: "If I had active-duty military service",
    description: "Checks whether service history opens veteran benefits.",
    answers: { applicant_served_in_active_military: "Yes", applicant_service_disability: "Yes" },
  },
  {
    name: "If I had a recent family death event",
    description: "Explores survivor and funeral assistance pathways.",
    answers: {
      applicant_dolo: "Yes",
      deceased_died_of_COVID: "Yes",
      deceased_death_location_is_US: "Yes",
      deceased_date_of_death: "2021-01-15",
    },
  },
];

function escapeHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function setBusyButtonText(button, isBusy, busyText, idleText) {
  if (!button) return;
  button.textContent = isBusy ? busyText : idleText;
}

function setLoading(el, isLoading) {
  if (isLoading) {
    el.classList.add("loading");
    if (el.tagName === "BUTTON") el.disabled = true;
  } else {
    el.classList.remove("loading");
    if (el.tagName === "BUTTON") el.disabled = false;
  }
}

let debounceTimer = null;
function debounce(fn, ms = 300) {
  return (...args) => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => fn(...args), ms);
  };
}

async function getJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const payload = await response.text();
    throw new Error(payload || `Request failed with ${response.status}`);
  }
  return response.json();
}

function setStatus(message) {
  const node = document.querySelector("#status");
  if (node) node.textContent = message;
}

function scrollToTopOf(node) {
  if (!node) return;
  const top = node.getBoundingClientRect().top + window.scrollY - 8;
  window.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
}

function isFederalOnlyScope() {
  return state.activeScope === "federal";
}

function statusLabel(status) {
  return status.replaceAll("_", " ");
}

function renderResultCard(item) {
  const reasons = item.matched_reasons.length
    ? `<ul class="reason-list">${item.matched_reasons.map((reason) => `<li>${escapeHtml(reason)}</li>`).join("")}</ul>`
    : "<p class='meta'>No matched reasons yet.</p>";
  const missing = item.missing_facts.length
    ? `<ul class="reason-list">${item.missing_facts.map((fact) => `<li>${escapeHtml(fact)}</li>`).join("")}</ul>`
    : "<p class='meta'>No missing facts for this current pass.</p>";
  const dataSources = item.data_gathered_from.length
    ? `<ul class="source-list">${item.data_gathered_from
        .map(
          (source) =>
            `<li><a href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">${escapeHtml(source.title)}</a>${
              source.last_verified_at ? ` · verified ${escapeHtml(source.last_verified_at)}` : ""
            }</li>`,
        )
        .join("")}</ul>`
    : "<p class='meta'>No official government sources attached.</p>";
  const howToGet = item.how_to_get_benefit.length
    ? `<ul class="source-list">${item.how_to_get_benefit
        .map((step) => `<li><a href="${escapeHtml(step.url)}" target="_blank" rel="noreferrer">${escapeHtml(step.label)}</a></li>`)
        .join("")}</ul>`
    : "<p class='meta'>No official application path is available for this result yet.</p>";
  const applicationLink = item.apply_url
    ? `<a href="${escapeHtml(item.apply_url)}" target="_blank" rel="noreferrer">Open official government page</a>`
    : "<span class='meta'>Use the official sources below.</span>";

  const certainty = item.decision_certainty ?? 0;
  const amountDisplay = item.estimated_amount?.display ?? "Not available";

  return `
    <article class="card">
      <header>
        <div>
          <h3>${escapeHtml(item.program_name)}</h3>
          <p class="meta">${escapeHtml(item.agency || "Unknown agency")} · ${escapeHtml(item.jurisdiction.name)}</p>
        </div>
        <span class="badge ${escapeHtml(item.eligibility_status)}">${statusLabel(item.eligibility_status)}</span>
      </header>
      <p>${escapeHtml(item.summary || "No summary available.")}</p>
      <div class="stack">
        <div>
          <div class="row spread" style="cursor:pointer" onclick="this.parentElement.querySelector('.certainty-breakdown').classList.toggle('open')">
            <strong>Confidence <span class="meta" style="font-weight:normal;font-size:0.82rem">(click to expand)</span></strong>
            <span>${certainty}/100</span>
          </div>
          <div class="meter"><span style="width: ${certainty}%"></span></div>
          <div class="certainty-breakdown">
            ${item.certainty_breakdown ? Object.entries(item.certainty_breakdown).map(([key, val]) => `
              <div class="certainty-row">
                <span>${escapeHtml(key.replace(/_/g, " "))}</span>
                <div class="mini-meter"><span style="width: ${val ?? 0}%"></span></div>
                <span>${val ?? 0}</span>
              </div>
            `).join("") : "<p class='meta'>No breakdown available.</p>"}
        </div>
        <div>
          <strong>Amount</strong>
          <p class="meta">${escapeHtml(amountDisplay)}</p>
        </div>
        <div>
          <strong>Why it matched</strong>
          ${reasons}
        </div>
        <div>
          <strong>What is still missing</strong>
          ${missing}
        </div>
        <div>
          <strong>Data gathered from official government websites</strong>
          ${dataSources}
        </div>
        <div class="row">
          <strong>How to get this benefit</strong>
        </div>
        <div>
          ${howToGet}
        </div>
        <div class="row">
          ${applicationLink}
        </div>
      </div>
    </article>
  `;
}
