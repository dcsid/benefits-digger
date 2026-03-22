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
  button.disabled = true;
  setStatus("Running scenario…");
  try {
    await runScenario(button.dataset.scenarioIndex);
    setStatus(t("whatif.updated"));
  } catch (error) {
    setStatus(t("whatif.failed", { error: error.message }));
  } finally {
    button.disabled = false;
  }
});

/* ── Quick-start session form ── */

const whatifStartForm = document.querySelector("#whatif-start-form");
const whatifScope = document.querySelector("#whatif-scope");
const whatifStateLabel = document.querySelector("#whatif-state-label");
const whatifStateCode = document.querySelector("#whatif-state-code");
const whatifCategoriesContainer = document.querySelector("#whatif-categories");

async function loadWhatifStates() {
  if (!whatifStateCode) return;
  const states = await getJson("/api/v1/jurisdictions/states");
  whatifStateCode.innerHTML = `<option value="">${escapeHtml(t("home.chooseState"))}</option>`;
  states.forEach((item) => {
    const opt = document.createElement("option");
    opt.value = item.code;
    opt.textContent = `${item.name} (${item.code})`;
    whatifStateCode.appendChild(opt);
  });
}

function renderWhatifCategories() {
  if (!whatifCategoriesContainer) return;
  whatifCategoriesContainer.innerHTML = categoryDefinitions
    .map(
      (cat) => `
      <label class="category-option">
        <input type="checkbox" name="whatif-category" value="${cat.value}" checked />
        <span class="category-icon">${cat.icon || ""}</span>
        <span>${escapeHtml(getCategoryLabel(cat.value) || cat.label)}</span>
      </label>`,
    )
    .join("");
}

const whatifFormError = document.querySelector("#whatif-form-error");

function showFormError(msg) {
  if (whatifFormError) {
    whatifFormError.textContent = msg;
    whatifFormError.classList.remove("hidden");
  }
}
function clearFormError() {
  if (whatifFormError) {
    whatifFormError.textContent = "";
    whatifFormError.classList.add("hidden");
  }
}

whatifScope?.addEventListener("change", () => {
  if (whatifStateLabel) {
    const needsState = whatifScope.value !== "federal";
    whatifStateLabel.style.display = needsState ? "" : "none";
    if (needsState) loadWhatifStates().catch(() => {});
  }
});

whatifStartForm?.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearFormError();
  const scope = whatifScope.value;
  const stateCode = whatifStateCode?.value || "";
  const categories = [...document.querySelectorAll('input[name="whatif-category"]:checked')].map(
    (cb) => cb.value,
  );

  if (!categories.length) {
    showFormError(t("home.selectCategory"));
    return;
  }
  if (scope !== "federal" && !stateCode) {
    showFormError(t("home.chooseStateMsg"));
    return;
  }

  const submitBtn = whatifStartForm.querySelector('button[type="submit"]');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = "Creating session…";
  }

  try {
    const session = await getJson("/api/v1/sessions", {
      method: "POST",
      body: JSON.stringify({
        scope,
        state_code: stateCode || null,
        categories,
        depth_value: 0.5,
      }),
    });
    setSessionId(session.session_id);
    setActiveScope(scope);
    noSession.classList.add("hidden");
    setStatus(t("whatif.updated"));
  } catch (err) {
    showFormError(err.message || t("whatif.failed", { error: err.message }));
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = t("whatif.startSession");
    }
  }
});

document.querySelector("#whatif-select-all")?.addEventListener("click", () => {
  document.querySelectorAll('input[name="whatif-category"]').forEach((cb) => (cb.checked = true));
});
document.querySelector("#whatif-clear-all")?.addEventListener("click", () => {
  document.querySelectorAll('input[name="whatif-category"]').forEach((cb) => (cb.checked = false));
});

/* ── Initialization ── */

if (!state.sessionId) {
  noSession.classList.remove("hidden");
  loadWhatifStates().catch((err) => setStatus(err.message));
  renderWhatifCategories();
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
    renderWhatifCategories();
    loadWhatifStates().catch((err) => setStatus(err.message));
  }
});
