const scenarioPresetsNode = document.querySelector("#scenario-presets");
const scenarioResults = document.querySelector("#scenario-results");
const noSession = document.querySelector("#no-session");

function renderScenarioPresets() {
  scenarioPresetsNode.innerHTML = scenarioPresets
    .map(
      (preset, index) => `
        <button type="button" class="scenario-button" data-scenario-index="${index}">
          <strong>${preset.name}</strong>
          <span class="meta">${preset.description}</span>
        </button>
      `,
    )
    .join("");
}

function renderScenarioComparison(payload) {
  if (!payload.comparisons.length) {
    scenarioResults.classList.add("empty");
    scenarioResults.textContent = "No scenario result returned.";
    return;
  }
  scenarioResults.classList.remove("empty");
  scenarioResults.innerHTML = payload.comparisons
    .map(
      (comparison) => `
        <article class="card">
          <header>
            <div>
              <h3>${escapeHtml(comparison.name)}</h3>
              <p class="meta">${escapeHtml(comparison.description || "Scenario comparison")}</p>
            </div>
          </header>
          <div class="metric-grid">
            <article class="metric-card">
              <span>Likely delta</span>
              <strong>${comparison.summary.likely_delta > 0 ? "+" : ""}${comparison.summary.likely_delta}</strong>
            </article>
            <article class="metric-card">
              <span>Possible delta</span>
              <strong>${comparison.summary.possible_delta > 0 ? "+" : ""}${comparison.summary.possible_delta}</strong>
            </article>
            <article class="metric-card">
              <span>Federal delta</span>
              <strong>${comparison.summary.federal_delta > 0 ? "+" : ""}${comparison.summary.federal_delta}</strong>
            </article>
            <article class="metric-card">
              <span>State delta</span>
              <strong>${comparison.summary.state_delta > 0 ? "+" : ""}${comparison.summary.state_delta}</strong>
            </article>
          </div>
          <div class="results-grid planner-grid">
            <div>
              <h4>New or unlocked programs</h4>
              ${
                comparison.gained_programs.length
                  ? `<ul class="reason-list">${comparison.gained_programs
                      .map((item) => `<li>${escapeHtml(item.program_name)} · ${statusLabel(item.after_status)}</li>`)
                      .join("")}</ul>`
                  : "<p class='meta'>No new positive matches in this scenario.</p>"
              }
            </div>
            <div>
              <h4>Improved programs</h4>
              ${
                comparison.improved_programs.length
                  ? `<ul class="reason-list">${comparison.improved_programs
                      .map((item) => `<li>${escapeHtml(item.program_name)} · ${statusLabel(item.before_status)} to ${statusLabel(item.after_status)}</li>`)
                      .join("")}</ul>`
                  : "<p class='meta'>No status improvements in this scenario.</p>"
              }
            </div>
          </div>
        </article>
      `,
    )
    .join("");
}

async function runScenario(index) {
  if (!state.sessionId) {
    setStatus("Start a session before running scenarios.");
    return;
  }
  const preset = scenarioPresets[index];
  const payload = await getJson(`/api/v1/sessions/${state.sessionId}/compare`, {
    method: "POST",
    body: JSON.stringify({ scenarios: [preset] }),
  });
  renderScenarioComparison(payload);
}

scenarioPresetsNode.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-scenario-index]");
  if (!button) return;
  try {
    await runScenario(button.dataset.scenarioIndex);
    setStatus("Scenario comparison updated.");
  } catch (error) {
    setStatus(`Scenario compare failed: ${error.message}`);
  }
});

if (!state.sessionId) {
  noSession.classList.remove("hidden");
}
renderScenarioPresets();
