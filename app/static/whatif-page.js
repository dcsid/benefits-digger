const scenarioPresetsNode = document.querySelector("#scenario-presets");
const scenarioResults = document.querySelector("#scenario-results");
const noSession = document.querySelector("#no-session");

function renderScenarioPresets() {
  scenarioPresetsNode.innerHTML = scenarioPresets
    .map(
      (preset, index) => {
        const display = getScenarioPresetDisplay(preset);
        return `
        <button type="button" class="scenario-button" data-scenario-index="${index}">
          <strong>${escapeHtml(display.name)}</strong>
          <span class="meta">${escapeHtml(display.description)}</span>
        </button>
      `;
      },
    )
    .join("");
}

function renderScenarioComparison(payload) {
  state.latestScenarioComparison = payload;
  if (!payload.comparisons.length) {
    scenarioResults.classList.add("empty");
    scenarioResults.textContent = t("whatif.noResult");
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
              <p class="meta">${escapeHtml(comparison.description || t("whatif.scenarioCompare"))}</p>
            </div>
          </header>
          <div class="metric-grid">
            <article class="metric-card">
              <span>${t("whatif.likelyDelta")}</span>
              <strong>${comparison.summary.likely_delta > 0 ? "+" : ""}${comparison.summary.likely_delta}</strong>
            </article>
            <article class="metric-card">
              <span>${t("whatif.possibleDelta")}</span>
              <strong>${comparison.summary.possible_delta > 0 ? "+" : ""}${comparison.summary.possible_delta}</strong>
            </article>
            <article class="metric-card">
              <span>${t("whatif.federalDelta")}</span>
              <strong>${comparison.summary.federal_delta > 0 ? "+" : ""}${comparison.summary.federal_delta}</strong>
            </article>
            <article class="metric-card">
              <span>${t("whatif.stateDelta")}</span>
              <strong>${comparison.summary.state_delta > 0 ? "+" : ""}${comparison.summary.state_delta}</strong>
            </article>
          </div>
          <div class="results-grid planner-grid">
            <div>
              <h4>${t("whatif.newPrograms")}</h4>
              ${
                comparison.gained_programs.length
                  ? `<ul class="reason-list">${comparison.gained_programs
                      .map((item) => `<li>${escapeHtml(item.program_name)} · ${statusLabel(item.after_status)}</li>`)
                      .join("")}</ul>`
                  : `<p class='meta'>${t("whatif.noNewMatches")}</p>`
              }
            </div>
            <div>
              <h4>${t("whatif.improvedPrograms")}</h4>
              ${
                comparison.improved_programs.length
                  ? `<ul class="reason-list">${comparison.improved_programs
                      .map((item) => `<li>${escapeHtml(item.program_name)} · ${statusLabel(item.before_status)} ${t("whatif.toStatus")} ${statusLabel(item.after_status)}</li>`)
                      .join("")}</ul>`
                  : `<p class='meta'>${t("whatif.noImprovements")}</p>`
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
    setStatus(t("whatif.startFirst"));
    return;
  }
  const preset = scenarioPresets[index];
  const display = getScenarioPresetDisplay(preset);
  const payload = await getJson(`/api/v1/sessions/${state.sessionId}/compare`, {
    method: "POST",
    body: JSON.stringify({
      scenarios: [
        {
          name: display.name,
          description: display.description,
          answers: preset.answers,
        },
      ],
    }),
  });
  renderScenarioComparison(payload);
}

scenarioPresetsNode.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-scenario-index]");
  if (!button) return;
  try {
    await runScenario(button.dataset.scenarioIndex);
    setStatus(t("whatif.updated"));
  } catch (error) {
    setStatus(t("whatif.failed", { error: error.message }));
  }
});

if (!state.sessionId) {
  noSession.classList.remove("hidden");
  noSession.innerHTML = `<p>${t("whatif.noSession")}</p>`;
}
renderScenarioPresets();

document.addEventListener("localechange", () => {
  renderScenarioPresets();
  if (state.latestScenarioComparison) {
    renderScenarioComparison(state.latestScenarioComparison);
  } else {
    scenarioResults.textContent = t("whatif.startThenRun");
  }
  if (!state.sessionId) {
    noSession.innerHTML = `<p>${t("whatif.noSession")}</p>`;
  }
});
