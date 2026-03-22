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
const adminKeyInput = document.querySelector("#admin-key");
const saveAdminKeyButton = document.querySelector("#save-admin-key");
const clearAdminKeyButton = document.querySelector("#clear-admin-key");

const lifeIntakeDescription = document.querySelector("#life-intake-description");
const lifeIntakeAnalyzeButton = document.querySelector("#life-intake-analyze");
const lifeIntakeClearButton = document.querySelector("#life-intake-clear");
const lifeIntakeStatus = document.querySelector("#life-intake-status");
const lifeIntakeOutput = document.querySelector("#life-intake-output");
const lifeIntakeSummary = document.querySelector("#life-intake-summary");
const lifeIntakeScope = document.querySelector("#life-intake-scope");
const lifeIntakeState = document.querySelector("#life-intake-state");
const lifeIntakeCategories = document.querySelector("#life-intake-categories");
const lifeIntakeFacts = document.querySelector("#life-intake-facts");
const lifeIntakeMissing = document.querySelector("#life-intake-missing");
const lifeIntakeApplyButton = document.querySelector("#life-intake-apply");
const lifeIntakeStartButton = document.querySelector("#life-intake-start");
const lifeChatLauncher = document.querySelector("#life-chat-launcher");
const lifeChatPopover = document.querySelector("#life-chat-popover");
const lifeChatCloseButton = document.querySelector("#life-chat-close");
const lifeChatEmpty = document.querySelector("#life-chat-empty");
const lifeChatbox = document.querySelector("#life-chatbox");
const lifeChatMessages = document.querySelector("#life-chat-messages");
const lifeChatForm = document.querySelector("#life-chat-form");
const lifeChatInput = document.querySelector("#life-chat-input");

const intakeState = {
  description: "",
  payload: null,
  messages: [],
  pendingQuestionKey: null,
  chatOpen: false,
  autoOpenedProbeKey: null,
};

function saveAdminKeyFromInput() {
  if (!adminKeyInput) return;
  setAdminKey(adminKeyInput.value);
  setStatus(adminKeyInput.value.trim() ? t("home.adminSaved") : t("home.adminCleared"));
}

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

function setLifeIntakeStatus(message = "") {
  if (!lifeIntakeStatus) return;
  lifeIntakeStatus.textContent = message;
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
  return [...document.querySelectorAll('input[name="category"]:checked')].map((box) => box.value);
}

function setSelectedCategories(values = []) {
  const selected = new Set(values);
  document.querySelectorAll('input[name="category"]').forEach((input) => {
    input.checked = selected.has(input.value);
  });
}

function updateStateVisibility() {
  const scope = scopeSelect.value;
  stateSelect.closest("label").style.display = scope === "federal" ? "none" : "grid";
  if (scope === "federal") setStateValidation("");
}

function estimateDepthQuestionCount(depthValue) {
  const v = Math.max(0, Math.min(1, depthValue));
  if (v <= 0.5) {
    const ratio = v / 0.5;
    return Math.round(4 + (10 - 4) * ratio);
  }
  const ratio = (v - 0.5) / 0.5;
  return Math.round(10 + (24 - 10) * ratio);
}

function updateDepthDescription() {
  const val = parseFloat(depthSlider.value);
  let best = depthDescriptions[0];
  for (const descriptor of depthDescriptions) {
    if (Math.abs(descriptor.at - val) < Math.abs(best.at - val)) best = descriptor;
  }
  const descriptor = getDepthDescriptor(best.at);
  const maxQ = estimateDepthQuestionCount(val);
  depthDescription.textContent = t("home.breadthApprox", { description: descriptor.text, count: maxQ });

  depthPills.forEach((pill) => {
    const pillValue = parseFloat(pill.dataset.depthValue || "0");
    const isActive = Math.abs(pillValue - best.at) < 0.001;
    pill.classList.toggle("active", isActive);
    pill.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
}

function renderCategories() {
  const selected = new Set(selectedCategories());
  categoryList.innerHTML = categoryDefinitions
    .map(
      (category) => `
        <label class="category-option">
          <input type="checkbox" name="category" value="${category.value}" ${selected.has(category.value) ? "checked" : ""} />
          <span class="category-icon" aria-hidden="true">${category.icon || "•"}</span>
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
            <input type="radio" name="answer" value="${escapeHtml(option.value)}" required />
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
          .map((option) => `<option value="${escapeHtml(option.value)}">${escapeHtml(translateDynamicText(option.label))}</option>`)
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

function scopeLabel(scope) {
  const key = `intake.scope.${scope}`;
  const translated = t(key);
  return translated !== key ? translated : scope;
}

function factLabel(fact) {
  const key = `intake.fact.${fact.key}`;
  const translated = t(key);
  return translated !== key ? translated : (fact.label || fact.key);
}

function resetLifeChat() {
  intakeState.messages = [];
  intakeState.pendingQuestionKey = null;
  intakeState.autoOpenedProbeKey = null;
  if (lifeChatMessages) lifeChatMessages.innerHTML = "";
}

function setLifeChatOpen(open, { focusInput = false } = {}) {
  intakeState.chatOpen = Boolean(open) && Boolean(intakeState.payload);
  if (lifeChatPopover) lifeChatPopover.classList.toggle("hidden", !intakeState.chatOpen);
  if (lifeChatLauncher) {
    lifeChatLauncher.setAttribute("aria-expanded", intakeState.chatOpen ? "true" : "false");
  }
  if (focusInput && intakeState.chatOpen && lifeChatInput) {
    requestAnimationFrame(() => lifeChatInput.focus());
  }
}

function renderLifeChat() {
  if (!lifeChatbox || !lifeChatEmpty || !lifeChatMessages || !lifeChatLauncher) return;
  const hasPayload = Boolean(intakeState.payload);
  lifeChatLauncher.classList.toggle("hidden", !hasPayload);
  lifeChatLauncher.classList.toggle("has-probe", Boolean(intakeState.payload?.next_probe));
  lifeChatEmpty.classList.toggle("hidden", hasPayload);
  lifeChatbox.classList.toggle("hidden", !hasPayload);
  if (!hasPayload) {
    setLifeChatOpen(false);
    return;
  }

  lifeChatMessages.innerHTML = intakeState.messages
    .map((message) => {
      const roleClass = message.role === "assistant" ? "assistant" : "user";
      return `<div class="chat-bubble ${roleClass}">${escapeHtml(message.content)}</div>`;
    })
    .join("");
  lifeChatMessages.scrollTop = lifeChatMessages.scrollHeight;

  const probeKey = intakeState.payload?.next_probe?.key || null;
  if (probeKey && intakeState.autoOpenedProbeKey !== probeKey) {
    intakeState.autoOpenedProbeKey = probeKey;
    setLifeChatOpen(true, { focusInput: true });
  }
}

function renderLifeIntake(payload) {
  intakeState.payload = payload;
  intakeState.pendingQuestionKey = payload.next_probe?.key || null;
  lifeIntakeOutput.classList.toggle("hidden", !payload);
  if (!payload) {
    lifeIntakeSummary.textContent = "";
    lifeIntakeScope.textContent = "";
    lifeIntakeState.textContent = "";
    lifeIntakeCategories.innerHTML = "";
    lifeIntakeFacts.innerHTML = "";
    lifeIntakeMissing.innerHTML = "";
    renderLifeChat();
    return;
  }

  lifeIntakeSummary.textContent = payload.summary || "";
  lifeIntakeScope.textContent = scopeLabel(payload.suggested_scope || "federal");
  lifeIntakeState.textContent = payload.applied_state_code || t("home.chooseState");

  lifeIntakeCategories.innerHTML = (payload.suggested_categories || []).length
    ? payload.suggested_categories
        .map((category) => `<span class="chip">${escapeHtml(getCategoryLabel(category.key) || category.label)}</span>`)
        .join("")
    : `<span class="meta">${escapeHtml(t("home.lifeNoCategories"))}</span>`;

  lifeIntakeFacts.innerHTML = (payload.structured_facts || []).length
    ? payload.structured_facts
        .map((fact) => `<span class="chip"><strong>${escapeHtml(factLabel(fact))}:</strong> ${escapeHtml(fact.value_label)}</span>`)
        .join("")
    : `<span class="meta">${escapeHtml(t("home.lifeNoFacts"))}</span>`;

  lifeIntakeMissing.innerHTML = (payload.follow_up_questions || []).length
    ? payload.follow_up_questions
        .map((question) => `<li><strong>${escapeHtml(question.prompt)}</strong> <span class="meta">${escapeHtml(question.reason)}</span></li>`)
        .join("")
    : `<li>${escapeHtml(t("home.lifeNoMissing"))}</li>`;

  renderLifeChat();
}

function clearLifeIntake() {
  intakeState.description = "";
  intakeState.payload = null;
  intakeState.pendingQuestionKey = null;
  intakeState.chatOpen = false;
  lifeIntakeDescription.value = "";
  lifeChatInput.value = "";
  setLifeIntakeStatus("");
  resetLifeChat();
  renderLifeIntake(null);
}

function applyIntakeSuggestionsToForm() {
  if (!intakeState.payload) return;
  scopeSelect.value = intakeState.payload.suggested_scope || "federal";
  if (intakeState.payload.applied_state_code) {
    stateSelect.value = intakeState.payload.applied_state_code;
  }
  const categoryKeys = (intakeState.payload.suggested_categories || []).map((category) => category.key);
  setSelectedCategories(categoryKeys);
  updateStateVisibility();
  setStateValidation("");
  setStatus(t("home.lifeApplyDone"));
  scrollToTopOf(startScreeningPanel);
}

function buildSessionPayload({ scope, stateCode, categories }) {
  return {
    scope,
    state_code: stateCode || null,
    categories,
    depth_value: parseFloat(depthSlider.value),
  };
}

async function startScreeningFlow(payload, prefillAnswers = {}) {
  const submitBtn = startForm.querySelector("button[type='submit']");
  try {
    setStateValidation("");
    if (!payload.categories?.length) {
      setStatus(t("home.selectCategory"));
      return;
    }
    if (!payload.scope) {
      setStatus(t("home.chooseScope"));
      return;
    }
    if (payload.scope !== "federal" && !payload.state_code) {
      const msg = t("home.chooseStateMsg");
      setStatus(msg);
      setStateValidation(msg);
      return;
    }

    if (submitBtn) {
      setLoading(submitBtn, true);
      setBusyButtonText(submitBtn, true, t("home.searching"), t("home.apply"));
    }

    setActiveScope(payload.scope);
    setStatus(payload.scope === "federal" ? t("home.creatingSession") : t("home.creatingSessionState"));
    const session = await getJson("/api/v1/sessions", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    setSessionId(session.session_id);
    let envelope = session;
    const filteredPrefills = Object.fromEntries(
      Object.entries(prefillAnswers || {}).filter(([, value]) => value !== null && value !== ""),
    );
    if (Object.keys(filteredPrefills).length) {
      envelope = await getJson(`/api/v1/sessions/${session.session_id}/answers`, {
        method: "POST",
        body: JSON.stringify({ answers: filteredPrefills }),
      });
    }

    renderQuestion(envelope.next_question);
    setStatus(t("home.sessionLive", { sessionId: state.sessionId }));
    if (intakeState.payload) {
      setLifeIntakeStatus(t("home.lifeStarted"));
    }
  } catch (error) {
    setStatus(t("home.sessionError", { error: error.message }));
  } finally {
    if (submitBtn) {
      setLoading(submitBtn, false);
      setBusyButtonText(submitBtn, false, t("home.searching"), t("home.apply"));
    }
  }
}

async function analyzeLifeIntake() {
  const description = (lifeIntakeDescription.value || "").trim();
  if (!description) {
    setLifeIntakeStatus(t("home.lifeDescriptionRequired"));
    return;
  }

  try {
    intakeState.description = description;
    resetLifeChat();
    setLoading(lifeIntakeAnalyzeButton, true);
    setLifeIntakeStatus(t("home.lifeAnalyzing"));
    const payload = await getJson("/api/v1/intake/interpret", {
      method: "POST",
      body: JSON.stringify({
        description,
        scope: scopeSelect.value || null,
        state_code: stateSelect.value || null,
        categories: selectedCategories(),
        use_llm: true,
      }),
    });
    intakeState.messages = payload.chat_reply ? [{ role: "assistant", content: payload.chat_reply }] : [];
    renderLifeIntake(payload);
    setLifeIntakeStatus(t("home.lifeAnalyzed"));
  } catch (error) {
    setLifeIntakeStatus(t("home.lifeInterpretError", { error: error.message }));
  } finally {
    setLoading(lifeIntakeAnalyzeButton, false);
  }
}

async function sendLifeProbe(message) {
  if (!intakeState.payload) return;
  const trimmed = message.trim();
  if (!trimmed) return;

  try {
    intakeState.messages.push({ role: "user", content: trimmed });
    renderLifeChat();
    setLoading(lifeChatForm.querySelector("button[type='submit']"), true);
    const payload = await getJson("/api/v1/intake/probe", {
      method: "POST",
      body: JSON.stringify({
        description: intakeState.description,
        scope: intakeState.payload.suggested_scope,
        state_code: intakeState.payload.applied_state_code,
        categories: (intakeState.payload.suggested_categories || []).map((category) => category.key),
        current_facts: intakeState.payload.current_facts || {},
        pending_question_key: intakeState.pendingQuestionKey,
        messages: intakeState.messages,
        use_llm: true,
      }),
    });
  if (payload.chat_reply) {
      intakeState.messages.push({ role: "assistant", content: payload.chat_reply });
    }
    renderLifeIntake(payload);
    setLifeIntakeStatus(t("home.lifeProbeUpdated"));
  } catch (error) {
    setLifeIntakeStatus(t("home.lifeProbeError", { error: error.message }));
  } finally {
    lifeChatInput.value = "";
    setLoading(lifeChatForm.querySelector("button[type='submit']"), false);
  }
}

function resetApp() {
  setSessionId(null);
  setActiveScope(null);
  state.currentQuestion = null;
  state.latestPlan = null;
  setScreeningFinished(false);

  scopeSelect.value = "both";
  stateSelect.value = "";
  depthSlider.value = "0.5";
  setAllCategories(false);
  updateStateVisibility();
  updateDepthDescription();

  questionForm.classList.add("hidden");
  questionShell.innerHTML = "";
  questionEmpty.textContent = t("home.questionEmpty");
  questionEmpty.classList.remove("hidden");

  setStatus("");
}

startForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await startScreeningFlow(
    buildSessionPayload({
      scope: scopeSelect.value,
      stateCode: stateSelect.value,
      categories: selectedCategories(),
    }),
  );
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

lifeIntakeAnalyzeButton?.addEventListener("click", analyzeLifeIntake);
lifeIntakeClearButton?.addEventListener("click", clearLifeIntake);
lifeIntakeApplyButton?.addEventListener("click", applyIntakeSuggestionsToForm);
lifeIntakeStartButton?.addEventListener("click", async () => {
  if (!intakeState.payload) return;
  applyIntakeSuggestionsToForm();
  await startScreeningFlow(
    buildSessionPayload({
      scope: intakeState.payload.suggested_scope,
      stateCode: intakeState.payload.applied_state_code,
      categories: (intakeState.payload.suggested_categories || []).map((category) => category.key),
    }),
    intakeState.payload.prefill_answers || {},
  );
});

lifeChatForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  await sendLifeProbe(lifeChatInput.value || "");
});

lifeChatLauncher?.addEventListener("click", () => {
  setLifeChatOpen(!intakeState.chatOpen, { focusInput: !intakeState.chatOpen });
});

lifeChatCloseButton?.addEventListener("click", () => {
  setLifeChatOpen(false);
});

document.querySelector("#show-results").addEventListener("click", () => {
  window.location.href = "/results";
});

document.querySelector("#select-all-categories").addEventListener("click", () => setAllCategories(true));
document.querySelector("#clear-categories").addEventListener("click", () => setAllCategories(false));
document.querySelector("#reset-button").addEventListener("click", resetApp);

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

document.addEventListener("localechange", () => {
  renderCategories();
  updateDepthDescription();
  loadStates().catch((error) => setStatus(error.message));
  renderLifeIntake(intakeState.payload);
  if (state.currentQuestion) {
    renderQuestion(state.currentQuestion);
  } else if (state.isScreeningFinished) {
    questionEmpty.textContent = t("home.noMoreQuestions");
  } else {
    questionEmpty.textContent = t("home.questionEmpty");
  }
});

renderCategories();
loadStates().catch((error) => setStatus(error.message));
updateStateVisibility();
updateDepthDescription();
renderLifeIntake(null);
