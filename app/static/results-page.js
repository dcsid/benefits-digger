const resultCount = document.querySelector("#result-count");
const federalResults = document.querySelector("#federal-results");
const stateResults = document.querySelector("#state-results");
const stateResultsColumn = document.querySelector("#state-results-column");
const resultsGrid = document.querySelector("#results-grid");
const noSession = document.querySelector("#no-session");

function updateResultsLayout() {
  const federalOnly = isFederalOnlyScope();
  if (stateResultsColumn) stateResultsColumn.classList.toggle("hidden", federalOnly);
  if (resultsGrid) resultsGrid.classList.toggle("single-column", federalOnly);
}

function renderResults(payload) {
  updateResultsLayout();

  const federalOnly = isFederalOnlyScope();
  const federalCount = payload.federal_results.filter((item) => item.eligibility_status !== "likely_ineligible").length;
  const stateCount = federalOnly
    ? 0
    : payload.state_results.filter((item) => item.eligibility_status !== "likely_ineligible").length;
  const totalMatches = federalCount + stateCount;
  resultCount.textContent = `${totalMatches} live matches`;

  federalResults.classList.remove("empty");
  if (!federalOnly) stateResults.classList.remove("empty");
  federalResults.innerHTML = payload.federal_results.length
    ? payload.federal_results.map(renderResultCard).join("")
    : "<p class='meta'>No federal results yet. Answer more questions to improve matches.</p>";

  if (federalOnly) {
    stateResults.innerHTML = state.isScreeningFinished
      ? "<p class='meta'>This is a federal-only session, so no state results are shown.</p>"
      : "<p class='meta'>State results are hidden while Federal only scope is selected.</p>";
    return;
  }

  stateResults.innerHTML = payload.state_results.length
    ? payload.state_results.map(renderResultCard).join("")
    : "<p class='meta'>No state results yet. Answer more questions to improve matches.</p>";
}

async function loadResults() {
  if (!state.sessionId) {
    noSession.classList.remove("hidden");
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
  setBusyButtonText(btn, true, "Generating...", "Download PDF");
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
      setBusyButtonText(btn, false, "Generating...", "Download PDF");
      btn.disabled = false;
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
  federalResults.innerHTML = `<p class="meta">Could not load results: ${error.message}</p>`;
});
