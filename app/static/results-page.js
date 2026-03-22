const resultCount = document.querySelector("#result-count");
const federalResults = document.querySelector("#federal-results");
const stateResults = document.querySelector("#state-results");
const stateResultsColumn = document.querySelector("#state-results-column");
const resultsGrid = document.querySelector("#results-grid");
const noSession = document.querySelector("#no-session");
const redoScreeningButton = document.querySelector("#redo-screening");

function scrollToResultCard(container, direction) {
  if (!container) return;

  const cards = [...container.querySelectorAll(":scope > .card")];
  if (!cards.length) {
    container.scrollBy({ top: direction === "down" ? 180 : -180, behavior: "smooth" });
    return;
  }

  const currentTop = container.scrollTop;
  const offsets = cards.map((card) => card.offsetTop);
  const closestIndex = offsets.reduce((bestIndex, offset, index) => {
    const bestDistance = Math.abs(offsets[bestIndex] - currentTop);
    const distance = Math.abs(offset - currentTop);
    return distance < bestDistance ? index : bestIndex;
  }, 0);

  const targetIndex = direction === "down"
    ? Math.min(cards.length - 1, closestIndex + 1)
    : Math.max(0, closestIndex - 1);

  container.scrollTo({ top: Math.max(0, offsets[targetIndex]), behavior: "smooth" });
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
  if (stateResultsColumn) stateResultsColumn.classList.toggle("hidden", federalOnly);
  if (resultsGrid) resultsGrid.classList.toggle("single-column", federalOnly);
}

function renderResults(payload) {
  state.latestResults = payload;
  updateResultsLayout();

  const federalOnly = isFederalOnlyScope();
  const federalCount = payload.federal_results.filter((item) => item.eligibility_status !== "likely_ineligible").length;
  const stateCount = federalOnly
    ? 0
    : payload.state_results.filter((item) => item.eligibility_status !== "likely_ineligible").length;
  const totalMatches = federalCount + stateCount;
  resultCount.textContent = t("results.liveMatches", { count: totalMatches });

  federalResults.classList.remove("empty");
  if (!federalOnly) stateResults.classList.remove("empty");
  federalResults.innerHTML = payload.federal_results.length
    ? payload.federal_results.map(renderResultCard).join("")
    : `<p class='meta'>${t("results.noFederal")}</p>`;

  if (federalOnly) {
    stateResults.innerHTML = state.isScreeningFinished
      ? `<p class='meta'>${t("results.federalOnlyFinished")}</p>`
      : `<p class='meta'>${t("results.federalOnlyHidden")}</p>`;
    return;
  }

  stateResults.innerHTML = payload.state_results.length
    ? payload.state_results.map(renderResultCard).join("")
    : `<p class='meta'>${t("results.noState")}</p>`;
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
