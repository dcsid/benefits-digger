const scopeSelect = document.querySelector("#scope");
const stateSelect = document.querySelector("#state-code");
const stateValidation = document.querySelector("#state-validation");
const startScreeningPanel = document.querySelector("#start-screening-panel");
const setupView = document.querySelector("#setup-view");
const questionView = document.querySelector("#question-view");
const sessionSummary = document.querySelector("#session-summary");
const editSetupButton = document.querySelector("#edit-setup");
const depthSlider = document.querySelector("#depth-slider");
const depthPills = [...document.querySelectorAll(".depth-pill")];
const depthDescription = document.querySelector("#depth-description");
const startForm = document.querySelector("#start-form");
const questionForm = document.querySelector("#question-form");
const questionShell = document.querySelector("#question-shell");
const questionEmpty = document.querySelector("#question-empty");
const questionCompleteActions = document.querySelector("#question-complete-actions");
const backQuestionButton = document.querySelector("#back-question");
const backQuestionCompleteButton = document.querySelector("#back-question-complete");
const categoryList = document.querySelector("#category-list");
const lifeChatLauncher = document.querySelector("#life-chat-launcher");
const lifeChatPopover = document.querySelector("#life-chat-popover");
const lifeChatHeader = document.querySelector(".life-chat-header");
const lifeChatCloseButton = document.querySelector("#life-chat-close");
const lifeChatbox = document.querySelector("#life-chatbox");
const lifeChatMessages = document.querySelector("#life-chat-messages");
const lifeChatSuggestions = document.querySelector("#life-chat-suggestions");
const lifeChatForm = document.querySelector("#life-chat-form");
const lifeChatInput = document.querySelector("#life-chat-input");
const lifeChatSendButton = document.querySelector("#life-chat-send");
const lifeChatAssistantStatus = document.querySelector("#life-chat-assistant-status");

let questionTrail = [];
let questionCursor = -1;
let answerMap = {};
const intakeState = {
  description: "",
  payload: null,
  messages: [],
  pendingQuestionKey: null,
  chatOpen: false,
  autoOpenedProbeKey: null,
  isProbeLoading: false,
};

function syncSharedZoboState() {
  if (typeof window.syncZoboSharedState !== "function") return;
  window.syncZoboSharedState({
    description: intakeState.description,
    payload: intakeState.payload,
    messages: intakeState.messages,
    pendingQuestionKey: intakeState.pendingQuestionKey,
    chatOpen: intakeState.chatOpen,
    autoOpenedProbeKey: intakeState.autoOpenedProbeKey,
  });
}

function syncBackButtons() {
  const canGoBackInForm = !state.isScreeningFinished && questionCursor > 0;
  const canGoBackFromComplete = state.isScreeningFinished && questionTrail.length > 0;
  if (backQuestionButton) backQuestionButton.disabled = !canGoBackInForm;
  if (backQuestionCompleteButton) backQuestionCompleteButton.disabled = !canGoBackFromComplete;
}

function restoreCurrentAnswer(question) {
  if (!question) return;
  const stored = answerMap[question.key];
  if (stored === undefined || stored === null) return;

  const radioNodes = [...questionShell.querySelectorAll('input[type="radio"][name="answer"]')];
  if (radioNodes.length) {
    radioNodes.forEach((input) => {
      input.checked = `${input.value}` === `${stored}`;
    });
    return;
  }

  const field = questionShell.querySelector('[name="answer"]');
  if (field) field.value = stored;
}

function pruneAnswersToTrail() {
  const keep = new Set(questionTrail.map((question) => question.key));
  Object.keys(answerMap).forEach((key) => {
    if (!keep.has(key)) delete answerMap[key];
  });
}

function goBackOneQuestion() {
  if (!questionTrail.length) return;

  if (state.isScreeningFinished) {
    questionCursor = questionTrail.length - 1;
    renderQuestion(questionTrail[questionCursor]);
    return;
  }

  if (questionCursor <= 0) return;
  questionCursor -= 1;
  renderQuestion(questionTrail[questionCursor]);
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
  setStatus(message);
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

function updateDepthDescription() {
  const val = parseFloat(depthSlider.value);
  let best = depthDescriptions[0];
  for (const d of depthDescriptions) {
    if (Math.abs(d.at - val) < Math.abs(best.at - val)) best = d;
  }
  const maxQ = estimateDepthQuestionCount(val);
  const descriptor = getDepthDescriptor(best.at);
  depthDescription.textContent = t("home.breadthApprox", { description: descriptor.text, count: maxQ });

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

function updateButtonTextForState() {
  const submitBtn = document.querySelector("#start-form button[type='submit']");
  if (!submitBtn) return;
  
  const scope = scopeSelect.value;
  const stateCode = stateSelect.value;
  
  let buttonText = "Start My Screening";
  
  // Try to get localized version
  const localizedStart = t("home.startScreening");
  if (localizedStart && !localizedStart.includes("home.")) {
    buttonText = localizedStart;
  }
  
  // If state is selected and not federal-only, personalize
  if (stateCode && scope !== "federal") {
    const stateOption = stateSelect.options[stateSelect.selectedIndex];
    if (stateOption) {
      const stateName = stateOption.textContent.split('(')[0].trim();
      buttonText = `Find ${stateName} Benefits`;
    }
  }
  
  submitBtn.textContent = buttonText;
}

function renderCategories() {
  const selected = new Set(selectedCategories());
  categoryList.innerHTML = categoryDefinitions
    .map(
      (category) => {
        const label = getCategoryLabel(category.value) || category.label;
        return `
        <label class="category-option">
          <input type="checkbox" name="category" value="${category.value}" ${selected.has(category.value) ? "checked" : ""} />
          <span class="category-icon" aria-hidden="true">${category.icon || "•"}</span>
          <span>${escapeHtml(label)}</span>
        </label>
      `;
      },
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
    questionCompleteActions?.classList.remove("hidden");
    syncBackButtons();
    return;
  }

  questionEmpty.classList.add("hidden");
  questionForm.classList.remove("hidden");
  questionCompleteActions?.classList.add("hidden");

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
  restoreCurrentAnswer(question);
  syncBackButtons();
}

function getLifeAssistantName() {
  return t("home.lifeAssistantName");
}

function getLifeChatWelcomeMessage() {
  return t("home.lifeChatWelcome");
}

function getLifeChatStatusText() {
  if (!intakeState.payload) return t("home.lifeChatStatusEmpty");
  if (intakeState.isProbeLoading) return t("home.lifeChatStatusThinking");
  const noMeaningfulSummary = !intakeState.payload.summary;
  const noCategories = !(intakeState.payload.suggested_categories || []).length;
  const noFacts = !(intakeState.payload.structured_facts || []).length;
  if (noMeaningfulSummary && noCategories && noFacts) return t("home.lifeChatStatusWaitingDetails");
  if (intakeState.payload?.next_probe) return t("home.lifeChatStatusReady");
  return t("home.lifeChatStatusDone");
}

function getLifeChatPlaceholder() {
  const probe = intakeState.payload?.next_probe;
  if (!probe) return t("home.lifeChatPlaceholder");
  if (probe.input_type === "yes_no") return t("home.lifeChatPlaceholderYesNo");
  if (probe.input_type === "state") return t("home.lifeChatPlaceholderState");
  return t("home.lifeChatPlaceholder");
}

function buildLifeChatSuggestions() {
  const probe = intakeState.payload?.next_probe;
  if (!probe || intakeState.isProbeLoading) return [];

  if (probe.input_type === "yes_no" && Array.isArray(probe.options)) {
    return probe.options.map((option) => ({
      value: option.value,
      label: translateDynamicText(option.label),
    }));
  }

  if (probe.input_type === "state") {
    const suggestions = [];
    const knownState = intakeState.payload?.applied_state_code || stateSelect?.value || "";
    if (knownState) {
      suggestions.push({ value: knownState, label: knownState });
    }
    return suggestions;
  }

  return [];
}

function syncLifePayloadToForm() {
  if (!intakeState.payload) return;
  scopeSelect.value = intakeState.payload.suggested_scope || "federal";
  if (intakeState.payload.applied_state_code) {
    stateSelect.value = intakeState.payload.applied_state_code;
  }
  const categoryKeys = (intakeState.payload.suggested_categories || []).map((category) => category.key);
  setAllCategories(false);
  document.querySelectorAll('input[name="category"]').forEach((input) => {
    input.checked = categoryKeys.includes(input.value);
  });
  updateStateVisibility();
  updateButtonTextForState();
  updateSessionSummary();
  setStateValidation("");
}

function resetLifeChat() {
  intakeState.messages = [];
  intakeState.pendingQuestionKey = null;
  intakeState.autoOpenedProbeKey = null;
  intakeState.isProbeLoading = false;
  if (lifeChatMessages) lifeChatMessages.innerHTML = "";
  syncSharedZoboState();
}

function setLifeChatOpen(open, { focusInput = false } = {}) {
  intakeState.chatOpen = Boolean(open);
  if (lifeChatPopover) lifeChatPopover.classList.toggle("hidden", !intakeState.chatOpen);
  if (lifeChatLauncher) {
    lifeChatLauncher.setAttribute("aria-expanded", intakeState.chatOpen ? "true" : "false");
  }
  syncSharedZoboState();
  if (focusInput && intakeState.chatOpen && lifeChatInput) {
    requestAnimationFrame(() => lifeChatInput.focus());
  }
}

function closeLifeChat() {
  setLifeChatOpen(false);
}

function renderLifeChat() {
  if (!lifeChatbox || !lifeChatMessages || !lifeChatLauncher) return;
  const hasPayload = Boolean(intakeState.payload);
  lifeChatLauncher.classList.toggle("has-probe", Boolean(intakeState.payload?.next_probe));
  lifeChatbox.classList.remove("hidden");
  if (lifeChatAssistantStatus) {
    lifeChatAssistantStatus.textContent = getLifeChatStatusText();
  }

  lifeChatMessages.innerHTML = intakeState.messages
    .map((message) => {
      const roleClass = message.role === "assistant" ? "assistant" : "user";
      const author = message.role === "assistant" ? getLifeAssistantName() : t("home.lifeChatUserLabel");
      const avatarText = message.role === "assistant" ? "ZO" : ((author || "Y").trim().charAt(0).toUpperCase() || "Y");
      return `
        <article class="chat-entry ${roleClass}">
          <div class="chat-entry-meta">
            <span class="chat-avatar ${roleClass}" aria-hidden="true">${escapeHtml(avatarText)}</span>
            <span class="chat-author">${escapeHtml(author)}</span>
          </div>
          <div class="chat-bubble ${roleClass}">${escapeHtml(message.content)}</div>
        </article>
      `;
    })
    .join("");

  if (!intakeState.messages.length && !intakeState.isProbeLoading) {
    lifeChatMessages.innerHTML = `
      <article class="chat-entry assistant welcome">
        <div class="chat-entry-meta">
          <span class="chat-avatar assistant" aria-hidden="true">ZO</span>
          <span class="chat-author">${escapeHtml(getLifeAssistantName())}</span>
        </div>
        <div class="chat-bubble assistant">${escapeHtml(getLifeChatWelcomeMessage())}</div>
      </article>
    `;
  }

  if (intakeState.isProbeLoading) {
    lifeChatMessages.innerHTML += `
      <article class="chat-entry assistant">
        <div class="chat-entry-meta">
          <span class="chat-avatar assistant" aria-hidden="true">ZO</span>
          <span class="chat-author">${escapeHtml(getLifeAssistantName())}</span>
        </div>
        <div class="chat-bubble assistant typing" aria-label="${escapeHtml(t("home.lifeChatStatusThinking"))}">
          <span></span><span></span><span></span>
        </div>
      </article>
    `;
  }
  lifeChatMessages.scrollTop = lifeChatMessages.scrollHeight;

  const suggestions = buildLifeChatSuggestions();
  if (lifeChatSuggestions) {
    if (suggestions.length) {
      lifeChatSuggestions.classList.remove("hidden");
      lifeChatSuggestions.innerHTML = `
        <span class="life-chat-suggestions-label">${escapeHtml(t("home.lifeChatQuickReplies"))}</span>
        ${suggestions
          .map(
            (suggestion) => `
              <button
                type="button"
                class="life-chat-suggestion"
                data-life-chat-suggestion="${escapeHtml(suggestion.value)}"
              >${escapeHtml(suggestion.label)}</button>
            `,
          )
          .join("")}
      `;
    } else {
      lifeChatSuggestions.classList.add("hidden");
      lifeChatSuggestions.innerHTML = "";
    }
  }

  if (lifeChatInput) {
    lifeChatInput.placeholder = getLifeChatPlaceholder();
    lifeChatInput.disabled = intakeState.isProbeLoading;
  }
  if (lifeChatSendButton) {
    setBusyButtonText(lifeChatSendButton, intakeState.isProbeLoading, t("home.lifeChatSending"), t("home.lifeChatSend"));
    lifeChatSendButton.disabled = intakeState.isProbeLoading;
  }

  const probeKey = intakeState.payload?.next_probe?.key || null;
  if (hasPayload && probeKey && intakeState.autoOpenedProbeKey !== probeKey) {
    intakeState.autoOpenedProbeKey = probeKey;
    setLifeChatOpen(true, { focusInput: true });
  }
  syncSharedZoboState();
}

function renderLifeIntake(payload) {
  intakeState.payload = payload;
  intakeState.pendingQuestionKey = payload?.next_probe?.key || null;
  if (payload) {
    syncLifePayloadToForm();
  }
  renderLifeChat();
}

function clearLifeIntake() {
  intakeState.description = "";
  intakeState.payload = null;
  intakeState.pendingQuestionKey = null;
  closeLifeChat();
  resetLifeChat();
  if (lifeChatInput) lifeChatInput.value = "";
  if (typeof window.clearZoboSharedState === "function") {
    window.clearZoboSharedState();
  }
  renderLifeIntake(null);
}

async function interpretLifeChat(description) {
  const trimmed = (description || "").trim();
  if (!trimmed) {
    setLifeIntakeStatus(t("home.lifeDescriptionRequired"));
    return;
  }

  try {
    intakeState.description = trimmed;
    resetLifeChat();
    intakeState.messages = [{ role: "user", content: trimmed }];
    intakeState.isProbeLoading = true;
    setLifeChatOpen(true);
    renderLifeChat();
    setLifeIntakeStatus(t("home.lifeAnalyzing"));
    const payload = await getJson("/api/v1/intake/interpret", {
      method: "POST",
      body: JSON.stringify({
        description: trimmed,
        scope: scopeSelect.value || null,
        state_code: stateSelect.value || null,
        categories: selectedCategories(),
        use_llm: true,
      }),
    });
    if (payload.chat_reply) {
      intakeState.messages.push({ role: "assistant", content: payload.chat_reply });
    }
    intakeState.isProbeLoading = false;
    renderLifeIntake(payload);
    setLifeIntakeStatus(t("home.lifeAnalyzed"));
  } catch (error) {
    intakeState.isProbeLoading = false;
    renderLifeChat();
    setLifeIntakeStatus(t("home.lifeInterpretError", { error: error.message }));
  } finally {
    if (lifeChatInput) lifeChatInput.value = "";
  }
}

async function sendLifeProbe(message) {
  if (!intakeState.payload) {
    const trimmed = (message || "").trim();
    if (!trimmed) return;
    await interpretLifeChat(trimmed);
    return;
  }

  const trimmed = message.trim();
  if (!trimmed) return;

  try {
    intakeState.messages.push({ role: "user", content: trimmed });
    intakeState.isProbeLoading = true;
    renderLifeChat();
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
    intakeState.isProbeLoading = false;
    renderLifeIntake(payload);
    setLifeIntakeStatus(t("home.lifeProbeUpdated"));
  } catch (error) {
    intakeState.isProbeLoading = false;
    renderLifeChat();
    setLifeIntakeStatus(t("home.lifeProbeError", { error: error.message }));
  } finally {
    if (lifeChatInput) lifeChatInput.value = "";
    if (intakeState.chatOpen && lifeChatInput) {
      requestAnimationFrame(() => lifeChatInput.focus());
    }
  }
}

function showQuestionView() {
  setupView?.classList.add("hidden");
  questionView?.classList.remove("hidden");
}

function showSetupView() {
  questionView?.classList.add("hidden");
  setupView?.classList.remove("hidden");
  scrollToTopOf(startScreeningPanel);
}

function updateSessionSummary() {
  if (!sessionSummary) return;
  const scopeText = scopeSelect.options[scopeSelect.selectedIndex]?.textContent || "Federal and state";
  const stateText = stateSelect.value
    ? stateSelect.options[stateSelect.selectedIndex]?.textContent || stateSelect.value
    : "No state filter";
  const depthText = getDepthDescriptor(parseFloat(depthSlider.value)).label;
  const categoryCount = selectedCategories().length;
  sessionSummary.textContent = `Currently searching: ${scopeText} | ${stateText} | ${depthText} depth | ${categoryCount} categories.`;
}

function resetApp() {
  setSessionId(null);
  setActiveScope(null);
  state.currentQuestion = null;
  state.latestPlan = null;
  setScreeningFinished(false);
  questionTrail = [];
  questionCursor = -1;
  answerMap = {};

  scopeSelect.value = "both";
  stateSelect.value = "";
  depthSlider.value = "0.5";
  setAllCategories(false);
  updateStateVisibility();
  updateDepthDescription();
  updateButtonTextForState();
  updateSessionSummary();

  questionForm.classList.add("hidden");
  questionShell.innerHTML = "";
  questionEmpty.textContent = t("home.questionEmpty");
  questionEmpty.classList.remove("hidden");
  questionCompleteActions?.classList.add("hidden");
  syncBackButtons();
  showSetupView();

  clearLifeIntake();
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
    showLoadingOverlay(hasState ? t("home.creatingSessionState") : t("home.creatingSession"));
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
    let envelope = session;
    const filteredPrefills = Object.fromEntries(
      Object.entries(intakeState.payload?.prefill_answers || {}).filter(([, value]) => value !== null && value !== ""),
    );
    if (Object.keys(filteredPrefills).length) {
      envelope = await getJson(`/api/v1/sessions/${session.session_id}/answers`, {
        method: "POST",
        body: JSON.stringify({ answers: filteredPrefills }),
      });
    }
    questionTrail = envelope.next_question ? [envelope.next_question] : [];
    questionCursor = envelope.next_question ? 0 : -1;
    answerMap = {};
    renderQuestion(envelope.next_question);
    updateSessionSummary();
    showQuestionView();
    setStatus(t("home.sessionLive", { sessionId: state.sessionId }));
  } catch (error) {
    setStatus(t("home.sessionError", { error: error.message }));
  } finally {
    hideLoadingOverlay();
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
    const currentQuestion = questionTrail[questionCursor] || state.currentQuestion;
    answerMap[currentQuestion.key] = value;

    questionTrail = questionTrail.slice(0, questionCursor + 1);
    pruneAnswersToTrail();

    const payload = await getJson(`/api/v1/sessions/${state.sessionId}/answers`, {
      method: "POST",
      body: JSON.stringify({
        answers: answerMap,
        replace_answers: true,
      }),
    });

    if (payload.next_question) {
      questionTrail.push(payload.next_question);
      questionCursor = questionTrail.length - 1;
    }

    renderQuestion(payload.next_question);
    setStatus(t("home.answerSaved"));
  } catch (error) {
    setStatus(t("home.answerError", { error: error.message }));
  } finally {
    if (submitBtn) setLoading(submitBtn, false);
  }
});

lifeChatForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (intakeState.isProbeLoading) return;
  await sendLifeProbe(lifeChatInput.value || "");
});

lifeChatSuggestions?.addEventListener("click", async (event) => {
  const target = event.target.closest("[data-life-chat-suggestion]");
  if (!target || intakeState.isProbeLoading) return;
  await sendLifeProbe(target.dataset.lifeChatSuggestion || "");
});

lifeChatLauncher?.addEventListener("click", () => {
  setLifeChatOpen(!intakeState.chatOpen, { focusInput: !intakeState.chatOpen });
});

lifeChatCloseButton?.addEventListener("click", (event) => {
  event.preventDefault();
  event.stopPropagation();
  closeLifeChat();
});

lifeChatHeader?.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof Element)) return;
  if (target.closest("#life-chat-close")) return;
  closeLifeChat();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && intakeState.chatOpen) {
    closeLifeChat();
  }
});

document.addEventListener("click", (event) => {
  if (!intakeState.chatOpen) return;
  const target = event.target;
  if (!(target instanceof Element)) return;
  if (target.closest("#life-chat-popover") || target.closest("#life-chat-launcher")) return;
  closeLifeChat();
});

function goToResultsPage() {
  window.location.href = "/results";
}

document.querySelector("#show-results")?.addEventListener("click", async () => {
  try {
    goToResultsPage();
  } catch (error) {
    setStatus(t("results.loadError", { error: error.message }));
  }
});

document.querySelector("#show-results-complete")?.addEventListener("click", async () => {
  try {
    goToResultsPage();
  } catch (error) {
    setStatus(t("results.loadError", { error: error.message }));
  }
});
backQuestionButton?.addEventListener("click", goBackOneQuestion);
backQuestionCompleteButton?.addEventListener("click", goBackOneQuestion);
document.querySelector("#select-all-categories").addEventListener("click", () => setAllCategories(true));
document.querySelector("#clear-categories").addEventListener("click", () => setAllCategories(false));
scopeSelect.addEventListener("change", () => {
  updateStateVisibility();
  updateButtonTextForState();
});
stateSelect.addEventListener("change", () => {
  if (stateSelect.value) setStateValidation("");
  updateButtonTextForState();
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
editSetupButton?.addEventListener("click", showSetupView);

document.querySelector("#reset-button").addEventListener("click", resetApp);

document.addEventListener("localechange", () => {
  renderCategories();
  updateDepthDescription();
  updateButtonTextForState();
  updateSessionSummary();
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
updateButtonTextForState();
updateSessionSummary();
renderLifeIntake(null);

const params = new URLSearchParams(window.location.search);
if (params.get("redo") === "1") {
  resetApp();
  params.delete("redo");
  const query = params.toString();
  window.history.replaceState({}, "", query ? `/?${query}` : "/");
} else {
  syncBackButtons();
}
