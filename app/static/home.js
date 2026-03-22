const scopeSelect = document.querySelector("#scope");
const stateSelect = document.querySelector("#state-code");
const stateValidation = document.querySelector("#state-validation");
const startScreeningPanel = document.querySelector("#start-screening-panel");
const breadthSlider = document.querySelector("#breadth-slider");
const breadthDescription = document.querySelector("#breadth-description");
const depthSlider = document.querySelector("#depth-slider");
const depthDescription = document.querySelector("#depth-description");
const startForm = document.querySelector("#start-form");
const questionForm = document.querySelector("#question-form");
const questionShell = document.querySelector("#question-shell");
const questionEmpty = document.querySelector("#question-empty");
const categoryList = document.querySelector("#category-list");
// const reviewTasksNode = document.querySelector("#review-tasks");
// const adminKeyInput = document.querySelector("#admin-key");
// const saveAdminKeyButton = document.querySelector("#save-admin-key");
// const clearAdminKeyButton = document.querySelector("#clear-admin-key");

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
  const selectedValue = stateSelect.value;
  const states = await getJson("/api/v1/jurisdictions/states");
  stateSelect.innerHTML = `<option value="">${escapeHtml(t("home.chooseState"))}</option>`;
  states.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.code;
    option.textContent = `${item.name} (${item.code})`;
    stateSelect.appendChild(option);
  });
  if (selectedValue) stateSelect.value = selectedValue;
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

function updateBreadthDescription() {
  const val = parseFloat(breadthSlider.value);
  const best = getBreadthDescriptor(val);
  const maxQ = estimateBreadthQuestionCount(val);
  breadthDescription.textContent = t("home.breadthApprox", { description: best.text, count: maxQ });
}

function updateDepthDescription() {
  const val = parseFloat(depthSlider.value);
  const best = getDepthDescriptor(val);
  depthDescription.textContent = t("home.depthApprox", { description: best.text });
}

function renderCategories() {
  const selected = new Set(selectedCategories());
  categoryList.innerHTML = categoryDefinitions
    .map(
      (category) => `
        <label class="category-option">
          <input type="checkbox" name="category" value="${category.value}" ${selected.has(category.value) ? "checked" : ""} />
          <span>${escapeHtml(getCategoryLabel(category.value))}</span>
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
  setScreeningFinished(!question);
  if (!question) {
    questionEmpty.textContent = t("home.noMoreQuestions");
    questionEmpty.classList.remove("hidden");
    questionForm.classList.add("hidden");
    return;
  }

  questionEmpty.classList.add("hidden");
  questionForm.classList.remove("hidden");

  const translatedPrompt = translateDynamicText(question.prompt);
  const translatedHintText = translateDynamicText(question.hint);
  const hint = translatedHintText ? `<p class="meta">${escapeHtml(translatedHintText)}</p>` : "";
  let inputMarkup = "";

  if (question.input_type === "radio" && question.options) {
    inputMarkup = question.options
      .map(
        (option) => `
          <label class="choice">
            <input type="radio" name="answer" value="${option.value}" required />
            <span>${escapeHtml(translateDynamicText(option.label))}</span>
          </label>
        `,
      )
      .join("");
  } else if (question.input_type === "select" && question.options) {
    inputMarkup = `
      <select name="answer" required>
        <option value="">${escapeHtml(t("home.chooseOne"))}</option>
        ${question.options
          .map((option) => `<option value="${option.value}">${escapeHtml(translateDynamicText(option.label))}</option>`)
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
        <span class="pill">${escapeHtml(t("home.sensitivity", { level: translateEnum("sensitivity", question.sensitivity_level, question.sensitivity_level) }))}</span>
      </div>
      <label>
        <strong>${escapeHtml(translatedPrompt)}</strong>
        ${hint}
        ${inputMarkup}
      </label>
    </div>
  `;
}

/* -- Review Queue – commented out for now --
function renderReviewTasks(tasks) {
  state.latestReviewTasks = tasks;
  reviewTasksNode.classList.remove("empty");
  reviewTasksNode.innerHTML = tasks.length
    ? tasks
        .map(
          (task) => `
          <article class="task">
            <div class="row spread">
              <strong>${escapeHtml(task.source_title || t("home.sourceLabel"))}</strong>
              <span class="pill">${escapeHtml(translateEnum("reviewStatus", task.status, task.status))}</span>
            </div>
            <p class="meta">${escapeHtml(t("home.reviewTaskMeta", {
              diffType: translateEnum("reviewDiff", task.diff_type, task.diff_type),
              score: task.materiality_score,
            }))}</p>
            <p><a href="${escapeHtml(task.source_url)}" target="_blank" rel="noreferrer">${escapeHtml(task.source_url)}</a></p>
          </article>
        `,
        )
        .join("")
    : t("home.noReviewTasks");
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
-- end Review Queue */

function resetApp() {
  setSessionId(null);
  setActiveScope(null);
  state.currentQuestion = null;
  state.latestPlan = null;
  setScreeningFinished(false);

  scopeSelect.value = "both";
  stateSelect.value = "";
  breadthSlider.value = 0.5;
  depthSlider.value = 0.5;
  setAllCategories(false);
  updateStateVisibility();
  updateBreadthDescription();
  updateDepthDescription();

  questionForm.classList.add("hidden");
  questionShell.innerHTML = "";
  questionEmpty.textContent = t("home.questionEmpty");
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
      setStatus(t("home.selectCategory"));
      return;
    }
    if (!scopeSelect.value) {
      setStatus(t("home.chooseScope"));
      scrollToTopOf(startScreeningPanel);
      scopeSelect.focus();
      return;
    }
    if (scopeSelect.value !== "federal" && !stateSelect.value) {
      const msg = t("home.chooseStateMsg");
      setStatus(msg);
      setStateValidation(msg);
      scrollToTopOf(startScreeningPanel);
      stateSelect.focus();
      return;
    }

    if (submitBtn) {
      setLoading(submitBtn, true);
      setBusyButtonText(submitBtn, true, t("home.searching"), t("home.apply"));
    }

    const hasState = scopeSelect.value !== "federal" && stateSelect.value;
    setStatus(hasState ? t("home.creatingSessionState") : t("home.creatingSession"));
    const payload = {
      scope: scopeSelect.value,
      state_code: stateSelect.value || null,
      categories,
      breadth_value: parseFloat(breadthSlider.value),
      depth_value: parseFloat(depthSlider.value),
    };
    setActiveScope(payload.scope);
    const session = await getJson("/api/v1/sessions", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setSessionId(session.session_id);
    renderQuestion(session.next_question);
    setStatus(t("home.sessionLive", { sessionId: state.sessionId }));
  } catch (error) {
    setStatus(t("home.sessionError", { error: error.message }));
  } finally {
    if (submitBtn) {
      setLoading(submitBtn, false);
      setBusyButtonText(submitBtn, false, t("home.searching"), t("home.apply"));
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
    setStatus(t("home.answerRequired"));
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
    setStatus(t("home.answerSaved"));
  } catch (error) {
    setStatus(t("home.answerError", { error: error.message }));
  } finally {
    if (submitBtn) setLoading(submitBtn, false);
  }
});

document.querySelector("#show-results").addEventListener("click", () => {
  window.location.href = "/results";
});

document.querySelector("#select-all-categories").addEventListener("click", () => setAllCategories(true));
document.querySelector("#clear-categories").addEventListener("click", () => setAllCategories(false));
scopeSelect.addEventListener("change", updateStateVisibility);
stateSelect.addEventListener("change", () => {
  if (stateSelect.value) setStateValidation("");
});
breadthSlider.addEventListener("input", updateBreadthDescription);
depthSlider.addEventListener("input", updateDepthDescription);

document.querySelector("#reset-button").addEventListener("click", resetApp);

document.addEventListener("localechange", () => {
  renderCategories();
  updateBreadthDescription();
  updateDepthDescription();
  loadStates().catch((error) => setStatus(error.message));
  if (state.currentQuestion) {
    renderQuestion(state.currentQuestion);
  } else if (state.isScreeningFinished) {
    questionEmpty.textContent = t("home.noMoreQuestions");
  } else {
    questionEmpty.textContent = t("home.questionEmpty");
  }
  /* -- Review Queue locale update commented out --
  if (state.latestReviewTasks) {
    renderReviewTasks(state.latestReviewTasks);
  } else if (reviewTasksNode.classList.contains("empty")) {
    reviewTasksNode.textContent = t("home.noReviewTasks");
  }
  */
});

renderCategories();
loadStates()
  .catch((error) => setStatus(error.message));
updateStateVisibility();
updateBreadthDescription();
updateDepthDescription();
