const state = {
  sessionId: null,
  currentQuestion: null,
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

const scopeSelect = document.querySelector("#scope");
const stateSelect = document.querySelector("#state-code");
const depthSelect = document.querySelector("#depth-mode");
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
  const sources = item.sources.length
    ? `<ul class="source-list">${item.sources
        .map(
          (source) =>
            `<li><a href="${source.url}" target="_blank" rel="noreferrer">${source.title}</a>${
              source.last_verified_at ? ` · verified ${source.last_verified_at}` : ""
            }</li>`,
        )
        .join("")}</ul>`
    : "<p class='meta'>No sources attached.</p>";

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
          <strong>Sources</strong>
          ${sources}
        </div>
        <div class="row">
          <a href="${item.apply_url}" target="_blank" rel="noreferrer">Open application page</a>
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

async function loadReviewTasks() {
  const tasks = await getJson("/api/v1/admin/review-tasks");
  renderReviewTasks(tasks);
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
    setStatus(`Saved answer for ${state.currentQuestion.key}.`);
  } catch (error) {
    setStatus(`Could not save answer: ${error.message}`);
  }
});

document.querySelector("#show-results").addEventListener("click", async () => {
  try {
    await loadResults();
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
    setStatus("Official sources refreshed.");
  } catch (error) {
    setStatus(`Sync failed: ${error.message}`);
  }
});

document.querySelector("#refresh-review").addEventListener("click", loadReviewTasks);
document.querySelector("#select-all-categories").addEventListener("click", () => setAllCategories(true));
document.querySelector("#clear-categories").addEventListener("click", () => setAllCategories(false));
scopeSelect.addEventListener("change", updateStateVisibility);

renderCategories();
loadStates().then(loadReviewTasks).catch((error) => setStatus(error.message));
updateStateVisibility();
