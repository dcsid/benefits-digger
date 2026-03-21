const state = {
  sessionId: null,
  currentQuestion: null,
  latestPlan: null,
};

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
const depthDescriptions = {
  quick:
    "Quick asks fewer questions, avoids aggressive follow-ups for as long as it can, and stops early once it has a light screen.",
  standard:
    "Standard asks a balanced number of questions and starts pulling in more detailed follow-ups after the basics.",
  deep:
    "Deep is more aggressive: it keeps going longer and starts medium and high-sensitivity follow-ups much earlier to tighten the match.",
};
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

const scopeSelect = document.querySelector("#scope");
const stateSelect = document.querySelector("#state-code");
const depthSelect = document.querySelector("#depth-mode");
const depthDescription = document.querySelector("#depth-description");
const startForm = document.querySelector("#start-form");
const questionForm = document.querySelector("#question-form");
const questionShell = document.querySelector("#question-shell");
const questionEmpty = document.querySelector("#question-empty");
const resultCount = document.querySelector("#result-count");
const federalResults = document.querySelector("#federal-results");
const stateResults = document.querySelector("#state-results");
const statusNode = document.querySelector("#status");
const reviewTasks = document.querySelector("#review-tasks");
const categoryList = document.querySelector("#category-list");
const planShell = document.querySelector("#plan-shell");
const planEmpty = document.querySelector("#plan-empty");
const planDepthPill = document.querySelector("#plan-depth-pill");
const overviewMetrics = document.querySelector("#overview-metrics");
const benefitStack = document.querySelector("#benefit-stack");
const missingFacts = document.querySelector("#missing-facts");
const actionPlan = document.querySelector("#action-plan");
const sourceHub = document.querySelector("#source-hub");
const planningNotes = document.querySelector("#planning-notes");
const scenarioPresetsNode = document.querySelector("#scenario-presets");
const scenarioResults = document.querySelector("#scenario-results");
const explorerForm = document.querySelector("#explorer-form");
const explorerQuery = document.querySelector("#explorer-query");
const explorerResults = document.querySelector("#explorer-results");

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
  statusNode.textContent = message;
}

async function loadStates() {
  const states = await getJson("/api/v1/jurisdictions/states");
  stateSelect.innerHTML = '<option value="">Choose a state</option>';
  states.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.code;
    option.textContent = `${item.name} (${item.code})`;
    stateSelect.appendChild(option);
  });
}

function selectedCategories() {
  const boxes = [...document.querySelectorAll('input[name="category"]:checked')];
  return boxes.map((box) => box.value);
}

function updateStateVisibility() {
  const scope = scopeSelect.value;
  stateSelect.closest("label").style.display = scope === "federal" ? "none" : "grid";
}

function updateDepthDescription() {
  depthDescription.textContent = depthDescriptions[depthSelect.value] || depthDescriptions.standard;
}

function renderCategories() {
  categoryList.innerHTML = categoryDefinitions
    .map(
      (category) => `
        <label class="category-option">
          <input type="checkbox" name="category" value="${category.value}" />
          <span>${category.label}</span>
        </label>
      `,
    )
    .join("");
}

function setAllCategories(checked) {
  document.querySelectorAll('input[name="category"]').forEach((input) => {
    input.checked = checked;
  });
}

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

function renderQuestion(question) {
  state.currentQuestion = question;
  if (!question) {
    questionEmpty.textContent = "No more questions queued. Results are ready.";
    questionEmpty.classList.remove("hidden");
    questionForm.classList.add("hidden");
    return;
  }

  questionEmpty.classList.add("hidden");
  questionForm.classList.remove("hidden");

  const hint = question.hint ? `<p class="meta">${question.hint}</p>` : "";
  let inputMarkup = "";

  if (question.input_type === "radio" && question.options) {
    inputMarkup = question.options
      .map(
        (option) => `
          <label class="choice">
            <input type="radio" name="answer" value="${option.value}" required />
            <span>${option.label}</span>
          </label>
        `,
      )
      .join("");
  } else if (question.input_type === "select" && question.options) {
    inputMarkup = `
      <select name="answer" required>
        <option value="">Choose one</option>
        ${question.options
          .map((option) => `<option value="${option.value}">${option.label}</option>`)
          .join("")}
      </select>
    `;
  } else if (question.input_type === "date") {
    inputMarkup = '<input type="date" name="answer" required />';
  } else if (question.input_type === "number" || question.input_type === "currency") {
    inputMarkup = '<input type="number" name="answer" step="0.01" required />';
  } else {
    inputMarkup = '<input type="text" name="answer" required />';
  }

  questionShell.innerHTML = `
    <div class="stack">
      <div>
        <span class="pill">${question.sensitivity_level} sensitivity</span>
      </div>
      <label>
        <strong>${question.prompt}</strong>
        ${hint}
        ${inputMarkup}
      </label>
    </div>
  `;
}

function statusLabel(status) {
  return status.replaceAll("_", " ");
}

function renderResultCard(item) {
  const reasons = item.matched_reasons.length
    ? `<ul class="reason-list">${item.matched_reasons.map((reason) => `<li>${reason}</li>`).join("")}</ul>`
    : "<p class='meta'>No matched reasons yet.</p>";
  const missing = item.missing_facts.length
    ? `<ul class="reason-list">${item.missing_facts.map((fact) => `<li>${fact}</li>`).join("")}</ul>`
    : "<p class='meta'>No missing facts for this current pass.</p>";
  const dataSources = item.data_gathered_from.length
    ? `<ul class="source-list">${item.data_gathered_from
        .map(
          (source) =>
            `<li><a href="${source.url}" target="_blank" rel="noreferrer">${source.title}</a>${
              source.last_verified_at ? ` · verified ${source.last_verified_at}` : ""
            }</li>`,
        )
        .join("")}</ul>`
    : "<p class='meta'>No official government sources attached.</p>";
  const howToGet = item.how_to_get_benefit.length
    ? `<ul class="source-list">${item.how_to_get_benefit
        .map((step) => `<li><a href="${step.url}" target="_blank" rel="noreferrer">${step.label}</a></li>`)
        .join("")}</ul>`
    : "<p class='meta'>No official application path is available for this result yet.</p>";
  const applicationLink = item.apply_url
    ? `<a href="${item.apply_url}" target="_blank" rel="noreferrer">Open official government page</a>`
    : "<span class='meta'>Use the official sources below.</span>";

  return `
    <article class="card">
      <header>
        <div>
          <h3>${item.program_name}</h3>
          <p class="meta">${item.agency || "Unknown agency"} · ${item.jurisdiction.name}</p>
        </div>
        <span class="badge ${item.eligibility_status}">${statusLabel(item.eligibility_status)}</span>
      </header>
      <p>${item.summary || "No summary available."}</p>
      <div class="stack">
        <div>
          <div class="row spread">
            <strong>Confidence</strong>
            <span>${item.decision_certainty}/100</span>
          </div>
          <div class="meter"><span style="width: ${item.decision_certainty}%"></span></div>
        </div>
        <div>
          <strong>Amount</strong>
          <p class="meta">${item.estimated_amount.display}</p>
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

function renderResults(payload) {
  const totalMatches =
    payload.federal_results.filter((item) => item.eligibility_status !== "likely_ineligible").length +
    payload.state_results.filter((item) => item.eligibility_status !== "likely_ineligible").length;
  resultCount.textContent = `${totalMatches} live matches`;

  federalResults.classList.remove("empty");
  stateResults.classList.remove("empty");
  federalResults.innerHTML = payload.federal_results.length
    ? payload.federal_results.map(renderResultCard).join("")
    : "No federal results for the current answers.";
  stateResults.innerHTML = payload.state_results.length
    ? payload.state_results.map(renderResultCard).join("")
    : "No state results for the current answers.";
}

function renderPlan(plan) {
  state.latestPlan = plan;
  if (!plan) {
    planShell.classList.add("hidden");
    planEmpty.classList.remove("hidden");
    planDepthPill.textContent = "No active session";
    return;
  }

  planShell.classList.remove("hidden");
  planEmpty.classList.add("hidden");
  planDepthPill.textContent = `${plan.profile.depth_mode} depth`;

  const metrics = [
    { label: "Likely programs", value: plan.overview.likely_programs },
    { label: "Possible programs", value: plan.overview.possible_programs },
    { label: "Answered questions", value: plan.overview.answered_questions },
    { label: "Average rule coverage", value: `${plan.overview.average_rule_coverage}%` },
  ];

  overviewMetrics.innerHTML = metrics
    .map(
      (metric) => `
        <article class="metric-card">
          <span>${metric.label}</span>
          <strong>${metric.value}</strong>
        </article>
      `,
    )
    .join("");

  benefitStack.innerHTML = plan.benefit_stack.length
    ? plan.benefit_stack
        .map(
          (item) => `
            <article class="mini-card">
              <h4>${item.label}</h4>
              <p class="meta">${item.likely_programs} likely · ${item.possible_programs} possible</p>
              <p>${item.top_programs.join(", ") || "No top programs yet."}</p>
            </article>
          `,
        )
        .join("")
    : "<p class='meta'>No benefit stack yet.</p>";

  missingFacts.innerHTML = plan.top_missing_facts.length
    ? plan.top_missing_facts
        .map(
          (item) => `
            <article class="mini-card">
              <h4>${item.label}</h4>
              <p class="meta">Affects ${item.program_count} program match${item.program_count === 1 ? "" : "es"}.</p>
            </article>
          `,
        )
        .join("")
    : "<p class='meta'>No missing-fact hotspots right now.</p>";

  actionPlan.innerHTML = plan.action_plan.length
    ? plan.action_plan
        .map(
          (step) => `
            <article class="mini-card">
              <h4>${step.program_name}</h4>
              <p class="meta">${statusLabel(step.eligibility_status)} · confidence ${step.confidence}/100</p>
              <p><a href="${step.url}" target="_blank" rel="noreferrer">${step.step_label}</a></p>
            </article>
          `,
        )
        .join("")
    : "<p class='meta'>No action steps yet.</p>";

  sourceHub.innerHTML = plan.official_source_hub.length
    ? plan.official_source_hub
        .map(
          (item) => `
            <article class="mini-card">
              <a href="${item.url}" target="_blank" rel="noreferrer">${item.label}</a>
            </article>
          `,
        )
        .join("")
    : "<p class='meta'>No official source hub yet.</p>";

  planningNotes.innerHTML = plan.planning_notes.length
    ? plan.planning_notes
        .map((note) => `<article class="mini-card"><p>${note}</p></article>`)
        .join("")
    : "<p class='meta'>Planning notes will appear after your session has results.</p>";
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
              <h3>${comparison.name}</h3>
              <p class="meta">${comparison.description || "Scenario comparison"}</p>
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
                      .map((item) => `<li>${item.program_name} · ${statusLabel(item.after_status)}</li>`)
                      .join("")}</ul>`
                  : "<p class='meta'>No new positive matches in this scenario.</p>"
              }
            </div>
            <div>
              <h4>Improved programs</h4>
              ${
                comparison.improved_programs.length
                  ? `<ul class="reason-list">${comparison.improved_programs
                      .map((item) => `<li>${item.program_name} · ${statusLabel(item.before_status)} to ${statusLabel(item.after_status)}</li>`)
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

function renderExplorer(programs) {
  explorerResults.classList.remove("empty");
  explorerResults.innerHTML = programs.length
    ? programs
        .map(
          (program) => `
            <article class="mini-card explorer-item">
              <h4>${program.name}</h4>
              <p class="meta">${program.agency || "Unknown agency"} · ${program.jurisdiction.name}</p>
              <p>${program.summary || "No summary available."}</p>
              ${
                program.apply_url
                  ? `<p><a href="${program.apply_url}" target="_blank" rel="noreferrer">Open official government page</a></p>`
                  : ""
              }
              ${
                program.data_gathered_from.length
                  ? `<ul class="source-list">${program.data_gathered_from
                      .map((source) => `<li><a href="${source.url}" target="_blank" rel="noreferrer">${source.title}</a></li>`)
                      .join("")}</ul>`
                  : ""
              }
            </article>
          `,
        )
        .join("")
    : "No programs matched this search.";
}

function renderReviewTasks(tasks) {
  reviewTasks.classList.remove("empty");
  reviewTasks.innerHTML = tasks.length
    ? tasks
        .map(
          (task) => `
          <article class="task">
            <div class="row spread">
              <strong>${task.source_title || "Source"}</strong>
              <span class="pill">${task.status}</span>
            </div>
            <p class="meta">${task.diff_type} · materiality ${task.materiality_score}</p>
            <p><a href="${task.source_url}" target="_blank" rel="noreferrer">${task.source_url}</a></p>
          </article>
        `,
        )
        .join("")
    : "No review tasks yet.";
}

async function loadResults() {
  if (!state.sessionId) return;
  const payload = await getJson(`/api/v1/sessions/${state.sessionId}/results`);
  renderResults(payload);
}

async function loadPlan() {
  if (!state.sessionId) {
    renderPlan(null);
    return;
  }
  const payload = await getJson(`/api/v1/sessions/${state.sessionId}/plan`);
  renderPlan(payload);
}

async function loadReviewTasks() {
  const tasks = await getJson("/api/v1/admin/review-tasks");
  renderReviewTasks(tasks);
}

async function loadExplorer() {
  const categories = selectedCategories();
  const params = new URLSearchParams({
    query: explorerQuery.value.trim(),
    scope: scopeSelect.value,
    limit: "20",
  });
  if (stateSelect.value) params.set("state_code", stateSelect.value);
  if (categories.length) params.set("categories", categories.join(","));
  const payload = await getJson(`/api/v1/programs?${params.toString()}`);
  renderExplorer(payload);
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

startForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const categories = selectedCategories();
    if (!categories.length) {
      setStatus("Select at least one category before applying your selections.");
      return;
    }
    setStatus("Creating session...");
    const payload = {
      scope: scopeSelect.value,
      state_code: stateSelect.value || null,
      categories,
      depth_mode: depthSelect.value,
    };
    const session = await getJson("/api/v1/sessions", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.sessionId = session.session_id;
    renderQuestion(session.next_question);
    await loadResults();
    await loadPlan();
    await loadExplorer();
    setStatus(`Session ${state.sessionId} is live.`);
  } catch (error) {
    setStatus(`Could not start session: ${error.message}`);
  }
});

questionForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.sessionId || !state.currentQuestion) return;
  const formData = new FormData(questionForm);
  const value = formData.get("answer");
  if (value === null || value === "") {
    setStatus("Please choose an answer before continuing.");
    return;
  }
  try {
    const payload = await getJson(`/api/v1/sessions/${state.sessionId}/answers`, {
      method: "POST",
      body: JSON.stringify({
        answers: {
          [state.currentQuestion.key]: value,
        },
      }),
    });
    renderQuestion(payload.next_question);
    await loadResults();
    await loadPlan();
    setStatus(`Saved answer for ${state.currentQuestion.key}.`);
  } catch (error) {
    setStatus(`Could not save answer: ${error.message}`);
  }
});

document.querySelector("#show-results").addEventListener("click", async () => {
  try {
    await loadResults();
    await loadPlan();
    setStatus("Results refreshed.");
  } catch (error) {
    setStatus(`Could not refresh results: ${error.message}`);
  }
});

document.querySelector("#sync-button").addEventListener("click", async () => {
  try {
    setStatus("Refreshing official sources...");
    const payload = await getJson("/api/v1/admin/sync", { method: "POST" });
    renderReviewTasks(payload.review_tasks || []);
    await loadResults();
    await loadPlan();
    await loadExplorer();
    setStatus("Official sources refreshed.");
  } catch (error) {
    setStatus(`Sync failed: ${error.message}`);
  }
});

document.querySelector("#refresh-review").addEventListener("click", loadReviewTasks);
document.querySelector("#refresh-explorer").addEventListener("click", loadExplorer);
document.querySelector("#select-all-categories").addEventListener("click", () => setAllCategories(true));
document.querySelector("#clear-categories").addEventListener("click", () => setAllCategories(false));
scopeSelect.addEventListener("change", updateStateVisibility);
depthSelect.addEventListener("change", updateDepthDescription);
explorerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await loadExplorer();
  } catch (error) {
    setStatus(`Explorer failed: ${error.message}`);
  }
});
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

renderCategories();
renderScenarioPresets();
loadStates()
  .then(async () => {
    await loadReviewTasks();
    await loadExplorer();
  })
  .catch((error) => setStatus(error.message));
updateStateVisibility();
updateDepthDescription();
renderPlan(null);
