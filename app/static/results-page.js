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
}

document.querySelector("#export-results").addEventListener("click", () => {
  if (!state.sessionId) return;
  window.print();
});

updateResultsLayout();
loadResults().catch((error) => {
  federalResults.innerHTML = `<p class="meta">Could not load results: ${error.message}</p>`;
});
