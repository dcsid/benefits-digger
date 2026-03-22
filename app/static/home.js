const scopeSelect = document.querySelector("#scope");
const stateSelect = document.querySelector("#state-code");
const stateValidation = document.querySelector("#state-validation");
const startScreeningPanel = document.querySelector("#start-screening-panel");
const depthSlider = document.querySelector("#depth-slider");
const depthPills = [...document.querySelectorAll(".depth-pill")];
const depthDescription = document.querySelector("#depth-description");
const startForm = document.querySelector("#start-form");
const questionForm = document.querySelector("#question-form");
const questionShell = document.querySelector("#question-shell");
const questionEmpty = document.querySelector("#question-empty");
const categoryList = document.querySelector("#category-list");
const reviewTasksNode = document.querySelector("#review-tasks");
const adminKeyInput = document.querySelector("#admin-key");
const saveAdminKeyButton = document.querySelector("#save-admin-key");
const clearAdminKeyButton = document.querySelector("#clear-admin-key");

function setStateValidation(message = "") {
  if (!stateValidation || !stateSelect) return;
  if (!message) {
    stateValidation.textContent = "";
    stateValidation.classList.add("hidden");
    stateSelect.classList.remove("input-error");
    stateSelect.removeAttribute("aria-invalid");
    return;
  }

  stateValidation.textContent = message;
  stateValidation.classList.remove("hidden");
  stateSelect.classList.add("input-error");
  stateSelect.setAttribute("aria-invalid", "true");
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
  if (scope === "federal") setStateValidation("");
}

function updateDepthDescription() {
  const val = parseFloat(depthSlider.value);
  let best = depthDescriptions[0];
  for (const d of depthDescriptions) {
    if (Math.abs(d.at - val) < Math.abs(best.at - val)) best = d;
  }
  const maxQ = estimateDepthQuestionCount(val);
  depthDescription.textContent = `${best.text} (~${maxQ} questions)`;

  depthPills.forEach((pill) => {
    const pillValue = parseFloat(pill.dataset.depthValue || "0");
    const isActive = Math.abs(pillValue - best.at) < 0.001;
    pill.classList.toggle("active", isActive);
    pill.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
}

function estimateDepthQuestionCount(depthValue) {
  // Keep this consistent with backend DEPTH_ANCHORS interpolation.
  const v = Math.max(0, Math.min(1, depthValue));
  if (v <= 0.5) {
    const t = v / 0.5;
    return Math.round(4 + (10 - 4) * t);
  }
  const t = (v - 0.5) / 0.5;
  return Math.round(10 + (24 - 10) * t);
}

function renderCategories() {
  categoryList.innerHTML = categoryDefinitions
    .map(
      (category) => `
        <label class="category-option">
          <input type="checkbox" name="category" value="${category.value}" />
          <span class="category-icon" aria-hidden="true">${category.icon || "•"}</span>
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
  state.isScreeningFinished = !question;
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

function renderReviewTasks(tasks) {
  reviewTasksNode.classList.remove("empty");
  reviewTasksNode.innerHTML = tasks.length
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

async function loadReviewTasks() {
  try {
    const tasks = await getJson("/api/v1/admin/review-tasks");
    renderReviewTasks(tasks);
  } catch (error) {
    reviewTasksNode.classList.add("empty");
    reviewTasksNode.textContent = error.message;
    throw error;
  }
}

function syncAdminKeyInput() {
  if (!adminKeyInput) return;
  adminKeyInput.value = getAdminKey();
}

function saveAdminKeyFromInput() {
  if (!adminKeyInput) return;
  setAdminKey(adminKeyInput.value);
  adminKeyInput.value = getAdminKey();
  setStatus(getAdminKey() ? "Admin key saved for this browser tab." : "Admin key cleared.");
}

function resetApp() {
  setSessionId(null);
  setActiveScope(null);
  state.currentQuestion = null;
  state.latestPlan = null;
  state.isScreeningFinished = false;

  scopeSelect.value = "both";
  stateSelect.value = "";
  depthSlider.value = "0.5";
  setAllCategories(false);
  updateStateVisibility();
  updateDepthDescription();

  questionForm.classList.add("hidden");
  questionShell.innerHTML = "";
  questionEmpty.textContent = "Start a session to begin the screener.";
  questionEmpty.classList.remove("hidden");

  setStatus("");
}

startForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitBtn = startForm.querySelector("button[type='submit']");
  if (submitBtn && submitBtn.disabled) return;
  try {
    setStateValidation("");
    const categories = selectedCategories();
    if (!categories.length) {
      setStatus("Select at least one category before applying your selections.");
      return;
    }
    if (!scopeSelect.value) {
      setStatus("Choose a screening scope before starting your session.");
      scrollToTopOf(startScreeningPanel);
      scopeSelect.focus();
      return;
    }
    if (scopeSelect.value !== "federal" && !stateSelect.value) {
      const msg = "Please choose a state before starting state or combined screening.";
      setStatus(msg);
      setStateValidation(msg);
      scrollToTopOf(startScreeningPanel);
      stateSelect.focus();
      return;
    }

    if (submitBtn) {
      setLoading(submitBtn, true);
      setBusyButtonText(submitBtn, true, "Searching...", "Apply selections");
    }

    const hasState = scopeSelect.value !== "federal" && stateSelect.value;
    setStatus(hasState ? "Creating session and loading state benefits..." : "Creating session...");
    const payload = {
      scope: scopeSelect.value,
      state_code: stateSelect.value || null,
      categories,
      depth_value: parseFloat(depthSlider.value),
    };
    setActiveScope(payload.scope);
    const session = await getJson("/api/v1/sessions", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setSessionId(session.session_id);
    renderQuestion(session.next_question);
    setStatus(`Session ${state.sessionId} is live.`);
  } catch (error) {
    setStatus(`Could not start session: ${error.message}`);
  } finally {
    if (submitBtn) {
      setLoading(submitBtn, false);
      setBusyButtonText(submitBtn, false, "Searching...", "Apply selections");
    }
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
    setStatus(`Saved answer for ${state.currentQuestion.key}.`);
  } catch (error) {
    setStatus(`Could not save answer: ${error.message}`);
  } finally {
    if (submitBtn) setLoading(submitBtn, false);
  }
});

document.querySelector("#show-results").addEventListener("click", async () => {
  try {
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
    setStatus(
      `Official sources refreshed. Crawled ${payload.crawled_programs || 0} program sites and added ${payload.crawl_sources_added || 0} direct government page sources.`,
    );
  } catch (error) {
    setStatus(`Sync failed: ${error.message}`);
  }
});

document.querySelector("#refresh-review").addEventListener("click", loadReviewTasks);
document.querySelector("#select-all-categories").addEventListener("click", () => setAllCategories(true));
document.querySelector("#clear-categories").addEventListener("click", () => setAllCategories(false));
scopeSelect.addEventListener("change", updateStateVisibility);
stateSelect.addEventListener("change", () => {
  if (stateSelect.value) setStateValidation("");
});
depthSlider.addEventListener("input", updateDepthDescription);
depthPills.forEach((pill) => {
  pill.addEventListener("click", () => {
    const target = pill.dataset.depthValue;
    if (target == null) return;
    depthSlider.value = target;
    updateDepthDescription();
  });
});
saveAdminKeyButton?.addEventListener("click", saveAdminKeyFromInput);
clearAdminKeyButton?.addEventListener("click", () => {
  if (!adminKeyInput) return;
  adminKeyInput.value = "";
  saveAdminKeyFromInput();
});
adminKeyInput?.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    saveAdminKeyFromInput();
  }
});

document.querySelector("#reset-button").addEventListener("click", resetApp);

renderCategories();
syncAdminKeyInput();
loadStates()
  .then(() => loadReviewTasks())
  .catch((error) => setStatus(error.message));
updateStateVisibility();
updateDepthDescription();
