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

const lifeEventPresets = [
  {
    icon: "briefcase",
    title: "I just lost my job",
    description: "Unemployment, food assistance, and emergency help",
    scope: "both",
    depth_value: 0.5,
    categories: ["jobs_unemployment", "food", "welfare_cash_assistance", "housing_utilities"],
    prefilled_answers: {},
  },
  {
    icon: "heart",
    title: "A family member passed away",
    description: "Survivor benefits, funeral assistance, and support",
    scope: "both",
    depth_value: 0.5,
    categories: ["death", "welfare_cash_assistance"],
    prefilled_answers: { applicant_dolo: "Yes" },
  },
  {
    icon: "clock",
    title: "I'm turning 65",
    description: "Retirement, Medicare, Social Security, and senior programs",
    scope: "both",
    depth_value: 0.5,
    categories: ["retirement_seniors", "health"],
    prefilled_answers: {},
  },
  {
    icon: "baby",
    title: "I had a baby",
    description: "Family benefits, child care, WIC, and health coverage",
    scope: "both",
    depth_value: 0.5,
    categories: ["children_families", "health", "food"],
    prefilled_answers: {},
  },
  {
    icon: "shield",
    title: "I became disabled",
    description: "Disability benefits, SSI, SSDI, and medical assistance",
    scope: "both",
    depth_value: 1.0,
    categories: ["disabilities", "health", "welfare_cash_assistance"],
    prefilled_answers: { applicant_disability: "Yes" },
  },
  {
    icon: "star",
    title: "I served in the military",
    description: "Veterans benefits, pensions, VA health care",
    scope: "both",
    depth_value: 1.0,
    categories: ["military_veterans", "health", "housing_utilities"],
    prefilled_answers: { applicant_served_in_active_military: "Yes" },
  },
];

const scopeSelect = document.querySelector("#scope");
const stateSelect = document.querySelector("#state-code");
const depthSlider = document.querySelector("#depth-slider");
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

function escapeHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
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
  const val = parseFloat(depthSlider.value);
  let best = depthDescriptions[0];
  for (const d of depthDescriptions) {
    if (Math.abs(d.at - val) < Math.abs(best.at - val)) best = d;
  }
  const maxQ = Math.round(4 + val * 20);
  depthDescription.textContent = `${best.text} (~${maxQ} questions)`;
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

  const hint = question.hint ? `<p class="meta">${escapeHtml(question.hint)}</p>` : "";
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
        <span class="pill">${escapeHtml(question.sensitivity_level)} sensitivity</span>
      </div>
      <label>
        <strong>${escapeHtml(question.prompt)}</strong>
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

function renderResults(payload) {
  const totalMatches =
    payload.federal_results.filter((item) => item.eligibility_status !== "likely_ineligible").length +
    payload.state_results.filter((item) => item.eligibility_status !== "likely_ineligible").length;
  resultCount.textContent = `${totalMatches} live matches`;

  federalResults.classList.remove("empty");
  stateResults.classList.remove("empty");
  federalResults.innerHTML = payload.federal_results.length
    ? payload.federal_results.map(renderResultCard).join("")
    : "<p class='meta'>No federal results yet. Answer more questions to improve matches.</p>";
  stateResults.innerHTML = payload.state_results.length
    ? payload.state_results.map(renderResultCard).join("")
    : "<p class='meta'>No state results yet. Answer more questions to improve matches.</p>";
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
  const dv = plan.profile.depth_value ?? 0.5;
  const tierLabel = dv < 0.33 ? "quick" : dv < 0.67 ? "standard" : "deep";
  planDepthPill.textContent = `${tierLabel} depth (${Math.round(dv * 100)}%)`;

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
              <h4>${escapeHtml(item.label)}</h4>
              <p class="meta">${item.likely_programs} likely · ${item.possible_programs} possible</p>
              <p>${item.top_programs.map(escapeHtml).join(", ") || "No top programs yet."}</p>
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
              <h4>${escapeHtml(item.label)}</h4>
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
              <h4>${escapeHtml(step.program_name)}</h4>
              <p class="meta">${statusLabel(step.eligibility_status)} · confidence ${step.confidence}/100</p>
              <p><a href="${escapeHtml(step.url)}" target="_blank" rel="noreferrer">${escapeHtml(step.step_label)}</a></p>
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
              <a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer">${escapeHtml(item.label)}</a>
            </article>
          `,
        )
        .join("")
    : "<p class='meta'>No official source hub yet.</p>";

  planningNotes.innerHTML = plan.planning_notes.length
    ? plan.planning_notes
        .map((note) => `<article class="mini-card"><p>${escapeHtml(note)}</p></article>`)
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

function renderExplorer(programs) {
  explorerResults.classList.remove("empty");
  explorerResults.innerHTML = programs.length
    ? programs
        .map(
          (program) => `
            <article class="mini-card explorer-item">
              <h4>${escapeHtml(program.name)}</h4>
              <p class="meta">${escapeHtml(program.agency || "Unknown agency")} · ${escapeHtml(program.jurisdiction.name)}</p>
              <p>${escapeHtml(program.summary || "No summary available.")}</p>
              ${
                program.apply_url
                  ? `<p><a href="${escapeHtml(program.apply_url)}" target="_blank" rel="noreferrer">Open official government page</a></p>`
                  : ""
              }
              ${
                program.data_gathered_from.length
                  ? `<ul class="source-list">${program.data_gathered_from
                      .map((source) => `<li><a href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">${escapeHtml(source.title)}</a></li>`)
                      .join("")}</ul>`
                  : ""
              }
            </article>
          `,
        )
        .join("")
    : "<p class='meta'>No programs matched this search. Try broadening your query or categories.</p>";
}

function renderReviewTasks(tasks) {
  reviewTasks.classList.remove("empty");
  reviewTasks.innerHTML = tasks.length
    ? tasks
        .map(
          (task) => `
          <article class="task">
            <div class="row spread">
              <strong>${escapeHtml(task.source_title || "Source")}</strong>
              <span class="pill">${escapeHtml(task.status)}</span>
            </div>
            <p class="meta">${escapeHtml(task.diff_type)} · materiality ${task.materiality_score}</p>
            <p><a href="${escapeHtml(task.source_url)}" target="_blank" rel="noreferrer">${escapeHtml(task.source_url)}</a></p>
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
  const submitBtn = startForm.querySelector("button[type='submit']");
  if (submitBtn && submitBtn.disabled) return;
  try {
    const categories = selectedCategories();
    if (!categories.length) {
      setStatus("Select at least one category before applying your selections.");
      return;
    }
    if (scopeSelect.value !== "federal" && !stateSelect.value) {
      setStatus("Please select a state when using state or combined scope.");
      return;
    }
    if (submitBtn) setLoading(submitBtn, true);
    setStatus("Creating session...");
    const payload = {
      scope: scopeSelect.value,
      state_code: stateSelect.value || null,
      categories,
      depth_value: parseFloat(depthSlider.value),
    };
    const session = await getJson("/api/v1/sessions", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.sessionId = session.session_id;
    renderQuestion(session.next_question);
    await Promise.all([loadResults(), loadPlan(), loadExplorer()]);
    setStatus(`Session ${state.sessionId} is live.`);
  } catch (error) {
    setStatus(`Could not start session: ${error.message}`);
  } finally {
    if (submitBtn) setLoading(submitBtn, false);
  }
});

questionForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitBtn = questionForm.querySelector("button[type='submit']");
  if (submitBtn && submitBtn.disabled) return;
  if (!state.sessionId || !state.currentQuestion) return;
  const formData = new FormData(questionForm);
  const value = formData.get("answer");
  if (value === null || value.toString().trim() === "") {
    setStatus("Please choose an answer before continuing.");
    return;
  }
  try {
    if (submitBtn) setLoading(submitBtn, true);
    const payload = await getJson(`/api/v1/sessions/${state.sessionId}/answers`, {
      method: "POST",
      body: JSON.stringify({
        answers: {
          [state.currentQuestion.key]: value,
        },
      }),
    });
    renderQuestion(payload.next_question);
    await Promise.all([loadResults(), loadPlan()]);
    setStatus(`Saved answer for ${state.currentQuestion.key}.`);
  } catch (error) {
    setStatus(`Could not save answer: ${error.message}`);
  } finally {
    if (submitBtn) setLoading(submitBtn, false);
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
depthSlider.addEventListener("input", updateDepthDescription);
explorerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = explorerQuery.value.trim();
  if (query.length > 0 && query.length < 2) {
    setStatus("Enter at least 2 characters to search.");
    return;
  }
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

const lifeEventsNode = document.querySelector("#life-events");

const eventIcons = {
  briefcase: "\uD83D\uDCBC",
  heart: "\uD83D\uDDA4",
  clock: "\u23F0",
  baby: "\uD83D\uDC76",
  shield: "\u267F",
  star: "\u2B50",
};

function renderLifeEvents() {
  lifeEventsNode.innerHTML = lifeEventPresets
    .map(
      (event, index) => `
        <button type="button" class="life-event-card" data-life-event="${index}">
          <span class="event-icon">${eventIcons[event.icon] || ""}</span>
          <strong>${escapeHtml(event.title)}</strong>
          <span class="meta">${escapeHtml(event.description)}</span>
        </button>
      `,
    )
    .join("");
}

lifeEventsNode.addEventListener("click", async (event) => {
  const card = event.target.closest("[data-life-event]");
  if (!card || card.disabled) return;
  const preset = lifeEventPresets[card.dataset.lifeEvent];
  if (!preset) return;

  card.disabled = true;
  setLoading(card, true);

  try {
    scopeSelect.value = preset.scope;
    depthSlider.value = preset.depth_value;
    updateStateVisibility();
    updateDepthDescription();

    preset.categories.forEach((cat) => {
      const checkbox = document.querySelector(`input[name="category"][value="${cat}"]`);
      if (checkbox) checkbox.checked = true;
    });

    setStatus("Setting up your screening...");
    const payload = {
      scope: preset.scope,
      state_code: stateSelect.value || null,
      categories: preset.categories,
      depth_value: preset.depth_value,
    };

    if (payload.scope !== "federal" && !payload.state_code) {
      setLoading(card, false);
      setStatus("Please select a state first, then click a life event.");
      return;
    }

    const session = await getJson("/api/v1/sessions", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    state.sessionId = session.session_id;

    if (Object.keys(preset.prefilled_answers).length) {
      const updated = await getJson(`/api/v1/sessions/${state.sessionId}/answers`, {
        method: "POST",
        body: JSON.stringify({ answers: preset.prefilled_answers }),
      });
      renderQuestion(updated.next_question);
    } else {
      renderQuestion(session.next_question);
    }

    await Promise.all([loadResults(), loadPlan(), loadExplorer()]);
    setStatus(`Session started for "${preset.title}".`);
  } catch (error) {
    setStatus(`Could not start session: ${error.message}`);
  } finally {
    setLoading(card, false);
  }
});

function resetApp() {
  state.sessionId = null;
  state.currentQuestion = null;
  state.latestPlan = null;

  scopeSelect.value = "both";
  stateSelect.value = "";
  depthSlider.value = 0.5;
  setAllCategories(false);
  updateStateVisibility();
  updateDepthDescription();

  questionForm.classList.add("hidden");
  questionShell.innerHTML = "";
  questionEmpty.textContent = "Start a session to begin the screener.";
  questionEmpty.classList.remove("hidden");

  renderPlan(null);

  resultCount.textContent = "0 live matches";
  federalResults.innerHTML = "No federal results yet.";
  federalResults.classList.add("empty");
  stateResults.innerHTML = "No state results yet.";
  stateResults.classList.add("empty");

  scenarioResults.innerHTML = "Start a session, then run a scenario.";
  scenarioResults.classList.add("empty");

  explorerResults.innerHTML = "Use the explorer to browse the current official program catalog.";
  explorerResults.classList.add("empty");
  explorerQuery.value = "";

  setStatus("");
}

document.querySelector("#reset-button").addEventListener("click", resetApp);

document.querySelector("#export-results").addEventListener("click", () => {
  if (!state.sessionId) {
    setStatus("Start a session first to export results.");
    return;
  }
  window.print();
});

renderLifeEvents();
renderCategories();
renderScenarioPresets();
loadStates()
  .then(async () => {
    await Promise.all([loadReviewTasks(), loadExplorer()]);
  })
  .catch((error) => setStatus(error.message));
updateStateVisibility();
updateDepthDescription();
renderPlan(null);
