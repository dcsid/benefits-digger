const state = {
  sessionId: localStorage.getItem("bd_session_id") || null,
  currentQuestion: null,
  latestPlan: null,
  latestResults: null,
  latestScenarioComparison: null,
  latestExplorerPayload: null,
  latestReviewTasks: null,
  activeScope: localStorage.getItem("bd_active_scope") || null,
  adminKey: sessionStorage.getItem("bd_admin_key") || "",
  isScreeningFinished: localStorage.getItem("bd_screening_finished") === "1",
};

/* ── i18n translation system ─────────────────────────────────── */

let _locale = localStorage.getItem("bd_locale") || "en";
let _strings = {};

async function loadLocale(locale) {
  try {
    const res = await fetch(`/static/locales/${locale}.json`);
    if (!res.ok) throw new Error(`Locale ${locale} not found`);
    _strings = await res.json();
    _locale = locale;
    localStorage.setItem("bd_locale", locale);
    document.documentElement.lang = locale;
    applyI18n();
    const langSelect = document.querySelector("#lang-select");
    if (langSelect) langSelect.value = _locale;
    document.dispatchEvent(new CustomEvent("localechange", { detail: { locale: _locale } }));
  } catch {
    if (locale !== "en") await loadLocale("en");
  }
}

function t(key, params = {}) {
  let s = _strings[key] || key;
  for (const [k, v] of Object.entries(params)) {
    s = s.replace(`{${k}}`, v);
  }
  return s;
}

function applyI18n() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.dataset.i18n;
    const translated = t(key);
    if (translated !== key) {
      if (el.dataset.i18nAttr) {
        el.setAttribute(el.dataset.i18nAttr, translated);
        if (el.dataset.i18nAttr === "placeholder") {
          el.placeholder = translated;
        } else if (el.dataset.i18nAttr === "title") {
          el.title = translated;
        }
      } else {
        el.innerHTML = translated;
      }
    }
  });
}

function getLocale() { return _locale; }

/* Auto-load locale on page load */
loadLocale(_locale);

function setSessionId(id) {
  state.sessionId = id;
  if (id) localStorage.setItem("bd_session_id", id);
  else localStorage.removeItem("bd_session_id");
}

function setActiveScope(scope) {
  state.activeScope = scope;
  if (scope) localStorage.setItem("bd_active_scope", scope);
  else localStorage.removeItem("bd_active_scope");
}

function getAdminKey() {
  return state.adminKey || sessionStorage.getItem("bd_admin_key") || "";
}

function setAdminKey(key) {
  const normalized = (key || "").trim();
  state.adminKey = normalized;
  if (normalized) sessionStorage.setItem("bd_admin_key", normalized);
  else sessionStorage.removeItem("bd_admin_key");
}

function setScreeningFinished(finished) {
  state.isScreeningFinished = finished;
  if (finished) localStorage.setItem("bd_screening_finished", "1");
  else localStorage.removeItem("bd_screening_finished");
  updateResultsNavVisibility();
}

function updateResultsNavVisibility() {
  const navResults = document.querySelector("#nav-results");
  if (!navResults) return;
  if (state.isScreeningFinished) navResults.classList.remove("hidden");
  else navResults.classList.add("hidden");
}

const categoryDefinitions = [
  { value: "children_families", label: "Children and families", labelKey: "category.children_families", icon: "👨‍👩‍👧" },
  { value: "death", label: "Death", labelKey: "category.death", icon: "🕊️" },
  { value: "disabilities", label: "Disabilities", labelKey: "category.disabilities", icon: "♿" },
  { value: "disasters", label: "Disasters", labelKey: "category.disasters", icon: "🌪️" },
  { value: "education", label: "Education", labelKey: "category.education", icon: "🎓" },
  { value: "food", label: "Food", labelKey: "category.food", icon: "🍎" },
  { value: "health", label: "Health", labelKey: "category.health", icon: "🩺" },
  { value: "housing_utilities", label: "Housing and utilities", labelKey: "category.housing_utilities", icon: "🏠" },
  { value: "jobs_unemployment", label: "Jobs and unemployment", labelKey: "category.jobs_unemployment", icon: "💼" },
  { value: "military_veterans", label: "Military and veterans", labelKey: "category.military_veterans", icon: "🎖️" },
  { value: "retirement_seniors", label: "Retirement and seniors", labelKey: "category.retirement_seniors", icon: "👵" },
  { value: "welfare_cash_assistance", label: "Welfare and cash assistance", labelKey: "category.welfare_cash_assistance", icon: "💵" },
];

const breadthDescriptions = [
  { at: 0.0, labelKey: "home.breadthFocused", textKey: "breadth.focused" },
  { at: 0.5, labelKey: "home.breadthBalanced", textKey: "breadth.balanced" },
  { at: 1.0, labelKey: "home.breadthBroad", textKey: "breadth.broad" },
];

const depthDescriptions = [
  { at: 0.0, labelKey: "home.depthLight", textKey: "depth.light" },
  { at: 0.5, labelKey: "home.depthStandard", textKey: "depth.standard" },
  { at: 1.0, labelKey: "home.depthDetailed", textKey: "depth.detailed" },
];

const scenarioPresets = [
  {
    nameKey: "scenario.limitedIncome",
    descriptionKey: "scenario.limitedIncomeDesc",
    answers: { applicant_income: "Yes" },
  },
  {
    nameKey: "scenario.disability",
    descriptionKey: "scenario.disabilityDesc",
    answers: { applicant_disability: "Yes", applicant_ability_to_work: "Yes" },
  },
  {
    nameKey: "scenario.military",
    descriptionKey: "scenario.militaryDesc",
    answers: { applicant_served_in_active_military: "Yes", applicant_service_disability: "Yes" },
  },
  {
    nameKey: "scenario.familyDeath",
    descriptionKey: "scenario.familyDeathDesc",
    answers: {
      applicant_dolo: "Yes",
      deceased_died_of_COVID: "Yes",
      deceased_death_location_is_US: "Yes",
      deceased_date_of_death: "2021-01-15",
    },
  },
];

function getCategoryLabel(value) {
  return t(`category.${value}`);
}

function getBreadthDescriptor(value) {
  const val = Number.isFinite(value) ? value : 0.5;
  let best = breadthDescriptions[0];
  for (const descriptor of breadthDescriptions) {
    if (Math.abs(descriptor.at - val) < Math.abs(best.at - val)) best = descriptor;
  }
  return {
    label: t(best.labelKey),
    text: t(best.textKey),
  };
}

function getDepthDescriptor(value) {
  const val = Number.isFinite(value) ? value : 0.5;
  let best = depthDescriptions[0];
  for (const descriptor of depthDescriptions) {
    if (Math.abs(descriptor.at - val) < Math.abs(best.at - val)) best = descriptor;
  }
  return {
    label: t(best.labelKey),
    text: t(best.textKey),
  };
}

function estimateBreadthQuestionCount(value) {
  const anchors = [
    { at: 0.0, count: 4 },
    { at: 0.5, count: 10 },
    { at: 1.0, count: 24 },
  ];
  const val = Math.max(0, Math.min(1, Number.isFinite(value) ? value : 0.5));
  let lower = anchors[0];
  let upper = anchors[anchors.length - 1];
  for (const anchor of anchors) {
    if (anchor.at <= val) lower = anchor;
    if (anchor.at >= val) {
      upper = anchor;
      break;
    }
  }
  if (lower.at === upper.at) return lower.count;
  const ratio = (val - lower.at) / (upper.at - lower.at);
  return Math.round(lower.count + (upper.count - lower.count) * ratio);
}

function getScenarioPresetDisplay(preset) {
  return {
    name: t(preset.nameKey),
    description: t(preset.descriptionKey),
  };
}

function translateEnum(prefix, value, fallback = "") {
  const key = `${prefix}.${value}`;
  const translated = t(key);
  return translated !== key ? translated : (fallback || value);
}

function translateDynamicText(text) {
  if (!text) return text;
  const exactMap = {
    "What is your date of birth?": "dynamic.question.dob",
    "For example: 1990-01-20": "dynamic.hint.dobExample",
    "Did you ever work and pay U.S. Social Security taxes?": "dynamic.question.paidIntoSS",
    "Do you have limited income and resources?": "dynamic.question.limitedIncome",
    "This is a broad screening question, not a final determination.": "dynamic.hint.limitedIncome",
    "Do you have a disability or qualifying illness?": "dynamic.question.disability",
    "Are you unable to work for a year or more because of your disability?": "dynamic.question.unableToWork",
    "Did you serve in the active military, naval, or air service?": "dynamic.question.activeMilitary",
    "Was your disability caused or made worse by your active-duty military service?": "dynamic.question.serviceDisabilityDetailed",
    "Did you recently experience the death of an immediate family member?": "dynamic.question.familyDeathDetailed",
    "What was the date of death?": "dynamic.question.dateOfDeath",
    "If you do not know the exact date, enter an approximate one.": "dynamic.hint.dateOfDeath",
    "Was the person's death COVID-19 related?": "dynamic.question.covidDeath",
    "Did the person die in the U.S.?": "dynamic.question.deathInUs",
    "Including Puerto Rico and U.S. territories.": "dynamic.hint.deathInUs",
    "What is your approximate annual household income?": "dynamic.question.householdIncome",
    "For reference, the 2024 federal poverty level is $15,060/year for a single-person household. Many programs use 130–200% of this threshold.": "dynamic.hint.householdIncome",
    "What type of disability or condition do you have?": "dynamic.question.disabilityType",
    "Select all that apply. Under SSA rules, a qualifying disability must significantly limit your ability to perform basic work activities.": "dynamic.hint.disabilityType",
    "How many months has your condition prevented you from working?": "dynamic.question.monthsUnableToWork",
    "SSDI requires inability to engage in substantial gainful activity for at least 12 consecutive months (42 U.S.C. § 423(d)(1)(A)).": "dynamic.hint.monthsUnableToWork",
    "What is your approximate age?": "dynamic.question.approxAge",
    "A rough age is enough for a quick check.": "dynamic.hint.approxAge",
    "What is your exact date of birth?": "dynamic.question.exactDob",
    "Full retirement age varies: 66 for those born 1943–1954, increasing to 67 for those born 1960 or later (42 U.S.C. § 416(l)).": "dynamic.hint.exactDob",
    "Are you a military veteran?": "dynamic.question.militaryVeteran",
    "VA benefits require active duty service. Reserve/National Guard service may qualify if activated under federal orders (38 U.S.C. § 101(2)).": "dynamic.hint.activeMilitary",
    "Was your disability related to military service?": "dynamic.question.serviceDisabilitySimple",
    "VA disability compensation requires a service-connected condition with a disability rating of at least 10% (38 U.S.C. § 1110).": "dynamic.hint.serviceDisabilityDetailed",
    "Did you recently lose a family member?": "dynamic.question.familyDeathSimple",
    "Survivor benefits eligibility depends on your relationship to the deceased and their work history (42 U.S.C. § 402).": "dynamic.hint.familyDeathDetailed",
    "Which state or territory do you want state benefits for?": "dynamic.question.stateCode",
    "State benefits vary by state and are kept separate from federal matches.": "dynamic.hint.stateCode",
    "Yes": "dynamic.option.yes",
    "No": "dynamic.option.no",
    "Physical disability": "dynamic.option.physicalDisability",
    "Cognitive or intellectual disability": "dynamic.option.cognitiveDisability",
    "Sensory disability (vision/hearing)": "dynamic.option.sensoryDisability",
    "Mental health condition": "dynamic.option.mentalHealth",
    "Chronic illness": "dynamic.option.chronicIllness",
    "None of the above": "dynamic.option.noneOfTheAbove",
    "Monthly retirement income for people who worked and paid Social Security taxes.": "dynamic.summary.retirement",
    "Monthly disability benefits for people who paid into Social Security and cannot work due to disability.": "dynamic.summary.ssdi",
    "Monthly support for older adults and people with disabilities who have limited income and resources.": "dynamic.summary.ssi",
    "Tax-free monthly payments for veterans whose disability was caused or worsened by active-duty service.": "dynamic.summary.vaDisability",
    "Monthly Social Security payments for eligible family members after a worker dies.": "dynamic.summary.survivor",
    "Financial help for funeral or burial costs for someone who died of COVID-19 in the U.S.": "dynamic.summary.funeral",
    "You worked and paid Social Security taxes.": "dynamic.reason.paidIntoSS",
    "You are at least retirement age.": "dynamic.reason.retirementAge",
    "You have limited income and resources.": "dynamic.reason.limitedIncome",
    "You have a disability or qualifying illness.": "dynamic.reason.disability",
    "You cannot work for a year or more because of your disability.": "dynamic.reason.unableToWork",
    "You served in the active military.": "dynamic.reason.activeMilitary",
    "Your disability was caused or worsened by active-duty service.": "dynamic.reason.serviceDisability",
    "You recently experienced the death of a family member.": "dynamic.reason.familyDeath",
    "The deceased's death was COVID-19 related.": "dynamic.reason.covidDeath",
    "The deceased died in the U.S.": "dynamic.reason.diedInUs",
    "The deceased died after May 20, 2020.": "dynamic.reason.afterDate",
    "Up to $943/month for individuals, $1,415/month for couples (2024 rates).": "dynamic.amount.ssi",
    "Monthly amount depends on work history and claiming age.": "dynamic.amount.retirement",
    "Monthly amount depends on work history.": "dynamic.amount.ssdi",
    "Amount depends on disability rating and dependents.": "dynamic.amount.vaDisability",
    "Monthly amount depends on the worker's record and your relationship.": "dynamic.amount.survivor",
    "Reimbursement amount depends on eligible funeral expenses.": "dynamic.amount.funeral",
    "Social Security card or number": "dynamic.document.ssnCard",
    "Your 9-digit SSN": "dynamic.document.ssnCardDesc",
    "Proof of age": "dynamic.document.proofOfAge",
    "Birth certificate or passport": "dynamic.document.proofOfAgeDesc",
    "W-2 forms or self-employment tax returns": "dynamic.document.w2",
    "Most recent year's earnings records": "dynamic.document.w2RecentDesc",
    "Earnings records for the current and prior year": "dynamic.document.w2CurrentPriorDesc",
    "Bank account information": "dynamic.document.bankInfo",
    "For direct deposit of benefits": "dynamic.document.bankInfoDesc",
    "Medical records": "dynamic.document.medicalRecords",
    "Documentation of your disability from doctors, hospitals, or clinics": "dynamic.document.medicalRecordsDesc",
    "Proof of income and resources": "dynamic.document.incomeResources",
    "Pay stubs, bank statements, or benefit award letters": "dynamic.document.incomeResourcesDesc",
    "Documentation of your disability": "dynamic.document.disabilityDocsDesc",
    "Proof of living arrangement": "dynamic.document.livingArrangement",
    "Lease, mortgage statement, or letter from landlord": "dynamic.document.livingArrangementDesc",
    "Proof of citizenship or immigration status": "dynamic.document.citizenship",
    "Birth certificate, passport, or immigration documents": "dynamic.document.citizenshipDesc",
    "DD-214 (discharge papers)": "dynamic.document.dd214",
    "Certificate of Release or Discharge from Active Duty": "dynamic.document.dd214Desc",
    "Evidence linking your disability to military service": "dynamic.document.serviceEvidenceDesc",
    "VA Form 21-526EZ": "dynamic.document.vaForm",
    "Application for Disability Compensation": "dynamic.document.vaFormDesc",
    "Deceased's Social Security number": "dynamic.document.deceasedSsn",
    "The worker's SSN": "dynamic.document.deceasedSsnDesc",
    "Death certificate": "dynamic.document.deathCertificate",
    "Certified copy of the death certificate": "dynamic.document.deathCertificateDesc",
    "Proof of relationship": "dynamic.document.relationshipProof",
    "Marriage certificate, birth certificate, or adoption papers": "dynamic.document.relationshipProofDesc",
    "Must attribute the death to COVID-19": "dynamic.document.covidDeathCertificateDesc",
    "Funeral expense receipts": "dynamic.document.funeralReceipts",
    "Itemized receipts or contracts from funeral providers": "dynamic.document.funeralReceiptsDesc",
    "Proof of U.S. residency": "dynamic.document.usResidency",
    "For the person who incurred the funeral expenses": "dynamic.document.usResidencyDesc",
    "FEMA application number": "dynamic.document.femaAppNumber",
    "If you previously applied for other FEMA assistance": "dynamic.document.femaAppNumberDesc",
    "Start on the official state social services website.": "server.step.startState",
    "Use the state's official benefit tools or program pages to choose the benefit you need.": "server.step.useStateTools",
    "Follow the state's official instructions for documents, local office contact, or online submission.": "server.step.followStateInstructions",
    "Review the official government eligibility source used for this match.": "server.step.reviewEligibility",
    "Open the official government page to start or continue the application.": "server.step.openOfficial",
    "Use the same official page for required documents, status checks, or agency contact details.": "server.step.useSamePage",
    "Choose a state to unlock official state benefit pathways.": "server.note.chooseState",
  };
  if (exactMap[text]) return t(exactMap[text]);

  let match = text.match(/^You already have (\d+) strong match(es)? to pursue on official government sites\.$/);
  if (match) {
    const count = match[1];
    return t("server.note.strongMatches", { count, plural: count === "1" ? "" : "s" });
  }

  match = text.match(/^You have (\d+) possible match(es)?; answering a few more questions should tighten these\.$/);
  if (match) {
    const count = match[1];
    return t("server.note.possibleMatches", { count, plural: count === "1" ? "" : "s" });
  }

  match = text.match(/^The biggest information gap right now is: (.+)\.$/);
  if (match) {
    return t("server.note.biggestGap", { label: match[1] });
  }

  return text;
}

function escapeHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function setBusyButtonText(button, isBusy, busyText, idleText) {
  if (!button) return;
  button.textContent = isBusy ? busyText : idleText;
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
  const explicitHeaders = options.headers instanceof Headers
    ? Object.fromEntries(options.headers.entries())
    : (options.headers || {});
  const headers = {
    "Content-Type": "application/json",
    ...explicitHeaders,
  };
  const adminKey = getAdminKey();
  if (adminKey && !headers["X-Admin-Key"]) {
    headers["X-Admin-Key"] = adminKey;
  }
  const response = await fetch(url, {
    ...options,
    headers,
  });
  if (!response.ok) {
    let message = "";
    try {
      const payload = await response.json();
      message = payload?.detail || "";
    } catch (error) {
      message = await response.text();
    }
    if (response.status === 401 && url.includes("/api/v1/admin/")) {
      throw new Error(
        getAdminKey()
          ? t("admin.invalidKey")
          : t("admin.requiredKey"),
      );
    }
    throw new Error(message || t("errors.requestFailed", { status: response.status }));
  }
  return response.json();
}

function setStatus(message) {
  const node = document.querySelector("#status");
  if (node) node.textContent = message;
}

function showLoadingOverlay(message) {
  const overlay = document.getElementById("loading-overlay");
  const msg = document.getElementById("loading-message");
  if (msg) msg.textContent = message || "Loading...";
  if (overlay) overlay.classList.remove("hidden");
}

function hideLoadingOverlay() {
  const overlay = document.getElementById("loading-overlay");
  if (overlay) overlay.classList.add("hidden");
}

function scrollToTopOf(node) {
  if (!node) return;
  const top = node.getBoundingClientRect().top + window.scrollY - 8;
  window.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
}

function isFederalOnlyScope() {
  return state.activeScope === "federal";
}

function statusLabel(status) {
  return translateEnum("status", status, status.replaceAll("_", " "));
}

function renderResultCard(item) {
  const reasons = item.matched_reasons.length
    ? `<ul class="reason-list">${item.matched_reasons.map((reason) => `<li>${escapeHtml(translateDynamicText(reason))}</li>`).join("")}</ul>`
    : `<p class='meta'>${t("card.noMatchedReasons")}</p>`;
  const missing = item.missing_facts.length
    ? `<ul class="reason-list">${item.missing_facts.map((fact) => `<li>${escapeHtml(translateDynamicText(fact))}</li>`).join("")}</ul>`
    : `<p class='meta'>${t("card.noMissingFacts")}</p>`;
  const dataSources = item.data_gathered_from.length
    ? `<ul class="source-list">${item.data_gathered_from
        .map(
          (source) =>
            `<li><a href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">${escapeHtml(source.title)}</a>${
              source.last_verified_at ? ` · ${escapeHtml(t("card.verified", { date: source.last_verified_at }))}` : ""
            }</li>`,
        )
        .join("")}</ul>`
    : `<p class='meta'>${t("card.noSources")}</p>`;
  const howToGet = item.how_to_get_benefit.length
    ? `<ul class="source-list">${item.how_to_get_benefit
        .map((step) => `<li><a href="${escapeHtml(step.url)}" target="_blank" rel="noreferrer">${escapeHtml(step.label)}</a></li>`)
        .join("")}</ul>`
    : `<p class='meta'>${t("card.noApplicationPath")}</p>`;
  const documents = (item.documents && item.documents.length)
    ? `<ul class="checklist">${item.documents.map((doc) =>
        `<li class="checklist-item">
          <label><input type="checkbox" class="doc-check" data-program="${escapeHtml(item.program_slug)}" data-doc="${escapeHtml(doc.name)}">
          <strong>${escapeHtml(translateDynamicText(doc.name))}</strong> <span class="badge-doc ${escapeHtml(doc.type)}">${escapeHtml(translateEnum("docType", doc.type, doc.type))}</span></label>
          ${doc.description ? `<p class="meta">${escapeHtml(translateDynamicText(doc.description))}</p>` : ""}
        </li>`).join("")}</ul>`
    : `<p class='meta'>${t("card.noDocuments")}</p>`;

  const applicationLink = item.apply_url
    ? `<a href="${escapeHtml(item.apply_url)}" target="_blank" rel="noreferrer">${t("card.openOfficial")}</a>`
    : `<span class='meta'>${t("card.useSourcesBelow")}</span>`;

  const certainty = item.decision_certainty ?? 0;
  const amountObj = item.estimated_amount || {};
  const amountDisplay = amountObj.display ?? t("card.notAvailable");
  const amountCalculated = amountObj.calculated ? t("card.amountEstimated") : "";
  const certaintyLabel = (key) => translateEnum("certainty", key, key.replace(/_/g, " "));
  const translatedHowToGet = item.how_to_get_benefit.map((step) => ({
    ...step,
    label: translateDynamicText(step.label),
  }));

  return `
    <article class="card">
      <header>
        <div>
          <h3>${escapeHtml(item.program_name)}</h3>
          <p class="meta">${escapeHtml(item.agency || t("card.unknownAgency"))} · ${escapeHtml(item.jurisdiction.name)}</p>
        </div>
        <span class="badge ${escapeHtml(item.eligibility_status)}">${statusLabel(item.eligibility_status)}</span>
      </header>
      <p>${escapeHtml(translateDynamicText(item.summary) || t("card.noSummary"))}</p>
      <div class="stack">
        <div>
          <div class="row spread" style="cursor:pointer" onclick="this.parentElement.querySelector('.certainty-breakdown').classList.toggle('open')">
            <strong>${t("card.confidence")} <span class="meta" style="font-weight:normal;font-size:0.82rem">${t("card.clickExpand")}</span></strong>
            <span>${certainty}/100</span>
          </div>
          <div class="meter"><span style="width: ${certainty}%"></span></div>
          <div class="certainty-breakdown">
            ${item.certainty_breakdown ? Object.entries(item.certainty_breakdown).map(([key, val]) => `
              <div class="certainty-row">
                <span>${escapeHtml(certaintyLabel(key))}</span>
                <div class="mini-meter"><span style="width: ${val ?? 0}%"></span></div>
                <span>${val ?? 0}</span>
              </div>
            `).join("") : `<p class='meta'>${t("card.noBreakdown")}</p>`}
        </div>
        <div>
          <strong>${t("card.amount")}${amountCalculated}</strong>
          <p class="meta">${escapeHtml(amountDisplay)}</p>
        </div>
        <div>
          <strong>${t("card.whyMatched")}</strong>
          ${reasons}
        </div>
        <div>
          <strong>${t("card.missingFacts")}</strong>
          ${missing}
        </div>
        <div>
          <div class="row spread" style="cursor:pointer" onclick="this.parentElement.querySelector('.documents-section').classList.toggle('open')">
            <strong>${t("card.documentsNeeded")} <span class="meta" style="font-weight:normal;font-size:0.82rem">${t("card.clickExpand")}</span></strong>
          </div>
          <div class="documents-section">${documents}</div>
        </div>
        <div>
          <strong>${t("card.dataGathered")}</strong>
          ${dataSources}
        </div>
        <div class="row">
          <strong>${t("card.howToGet")}</strong>
        </div>
        <div>
          ${translatedHowToGet.length
            ? `<ul class="source-list">${translatedHowToGet
                .map((step) => `<li><a href="${escapeHtml(step.url)}" target="_blank" rel="noreferrer">${escapeHtml(step.label)}</a></li>`)
                .join("")}</ul>`
            : howToGet}
        </div>
        <div class="row">
          ${applicationLink}
        </div>
      </div>
    </article>
  `;
}

// Show/hide Results nav link based on screening state on every page load
updateResultsNavVisibility();

const ZOBO_STORAGE_KEY = "bd_zobo_state";

function defaultZoboState() {
  return {
    description: "",
    payload: null,
    messages: [],
    pendingQuestionKey: null,
    chatOpen: false,
    autoOpenedProbeKey: null,
    isProbeLoading: false,
  };
}

function readPersistedZoboState() {
  try {
    const raw = sessionStorage.getItem(ZOBO_STORAGE_KEY);
    if (!raw) return defaultZoboState();
    const parsed = JSON.parse(raw);
    return {
      ...defaultZoboState(),
      ...parsed,
      messages: Array.isArray(parsed?.messages) ? parsed.messages : [],
    };
  } catch {
    return defaultZoboState();
  }
}

function persistZoboState(snapshot) {
  const normalized = {
    ...defaultZoboState(),
    ...snapshot,
    isProbeLoading: false,
  };
  sessionStorage.setItem(ZOBO_STORAGE_KEY, JSON.stringify(normalized));
}

window.syncZoboSharedState = function syncZoboSharedState(snapshot) {
  persistZoboState(snapshot);
};

window.clearZoboSharedState = function clearZoboSharedState() {
  sessionStorage.removeItem(ZOBO_STORAGE_KEY);
};

function isHomePage() {
  return window.location.pathname === "/";
}

function countResultsByStatus(payload, status) {
  if (!payload) return 0;
  const all = [...(payload.federal_results || []), ...(payload.state_results || [])];
  return all.filter((item) => item.eligibility_status === status).length;
}

async function hydrateZoboSessionContext() {
  if (!state.sessionId) return;
  if (!state.latestPlan) {
    try {
      state.latestPlan = await getJson(`/api/v1/sessions/${state.sessionId}/plan`);
    } catch {
      // Leave session context best-effort.
    }
  }
  if (window.location.pathname === "/results" && !state.latestResults) {
    try {
      state.latestResults = await getJson(`/api/v1/sessions/${state.sessionId}/results`);
    } catch {
      // Leave session context best-effort.
    }
  }
}

function getZoboScopeFromContext(zoboState) {
  return (
    state.activeScope ||
    zoboState.payload?.suggested_scope ||
    state.latestPlan?.profile?.scope ||
    "both"
  );
}

function getZoboStateCodeFromContext(zoboState) {
  return (
    zoboState.payload?.applied_state_code ||
    zoboState.payload?.current_facts?.state_code ||
    state.latestPlan?.profile?.state_code ||
    null
  );
}

function getZoboCategoriesFromContext(zoboState) {
  const merged = [
    ...((zoboState.payload?.suggested_categories || []).map((item) => item.key)),
    ...((state.latestPlan?.profile?.selected_categories || []).map((item) => item.key)),
  ];
  return [...new Set(merged.filter(Boolean))];
}

function buildZoboContextFacts(zoboState) {
  const facts = {
    ...(zoboState.payload?.current_facts || {}),
    current_page: window.location.pathname,
  };
  if (state.sessionId) facts.active_session = true;
  if (state.activeScope) facts.session_scope = state.activeScope;

  const plan = state.latestPlan;
  if (plan?.profile?.state_code) facts.state_code = facts.state_code || plan.profile.state_code;
  if (plan?.overview?.answered_questions != null) facts.answered_questions = plan.overview.answered_questions;
  if (plan?.overview?.likely_programs != null) facts.current_likely_matches = plan.overview.likely_programs;
  if (plan?.overview?.possible_programs != null) facts.current_possible_matches = plan.overview.possible_programs;
  if (Array.isArray(plan?.top_missing_facts) && plan.top_missing_facts.length) {
    facts.current_top_missing_fact = plan.top_missing_facts[0].label;
  }

  const results = state.latestResults;
  if (results) {
    facts.current_likely_matches = countResultsByStatus(results, "likely_eligible");
    facts.current_possible_matches = countResultsByStatus(results, "possibly_eligible");
  }

  return facts;
}

function getZoboAssistantName() {
  return t("home.lifeAssistantName");
}

function getZoboWelcomeMessage() {
  return state.sessionId ? t("home.lifeChatWelcomeSession") : t("home.lifeChatWelcome");
}

function getZoboStatusText(zoboState) {
  if (!zoboState.payload) return t("home.lifeChatStatusEmpty");
  if (zoboState.isProbeLoading) return t("home.lifeChatStatusThinking");
  if (zoboState.payload?.next_probe) return t("home.lifeChatStatusReady");
  return t("home.lifeChatStatusDone");
}

function getZoboPlaceholder(zoboState) {
  const probe = zoboState.payload?.next_probe;
  if (!probe) return t("home.lifeChatPlaceholder");
  if (probe.input_type === "yes_no") return t("home.lifeChatPlaceholderYesNo");
  if (probe.input_type === "state") return t("home.lifeChatPlaceholderState");
  return t("home.lifeChatPlaceholder");
}

function buildZoboSuggestions(zoboState) {
  const probe = zoboState.payload?.next_probe;
  if (!probe || zoboState.isProbeLoading) return [];
  if (probe.input_type === "yes_no" && Array.isArray(probe.options)) {
    return probe.options.map((option) => ({
      value: option.value,
      label: translateDynamicText(option.label),
    }));
  }
  if (probe.input_type === "state") {
    const knownState = getZoboStateCodeFromContext(zoboState);
    return knownState ? [{ value: knownState, label: knownState }] : [];
  }
  return [];
}

function normalizeZoboNavigationAction(action) {
  if (!action || !action.href) return null;
  if (action.href === "#start-screening-panel" || action.href === "action:start_screening") {
    return { ...action, href: "/" };
  }
  return action;
}

function ensureSitewideZoboMarkup() {
  if (isHomePage()) return null;
  let launcher = document.querySelector("#sitewide-zobo-launcher");
  if (launcher) {
    return {
      launcher,
      popover: document.querySelector("#sitewide-zobo-popover"),
      header: document.querySelector("#sitewide-zobo-popover .life-chat-header"),
      closeButton: document.querySelector("#sitewide-zobo-close"),
      messages: document.querySelector("#sitewide-zobo-messages"),
      suggestions: document.querySelector("#sitewide-zobo-suggestions"),
      actions: document.querySelector("#sitewide-zobo-actions"),
      form: document.querySelector("#sitewide-zobo-form"),
      input: document.querySelector("#sitewide-zobo-input"),
      sendButton: document.querySelector("#sitewide-zobo-send"),
      assistantStatus: document.querySelector("#sitewide-zobo-status"),
    };
  }

  const host = document.querySelector("main.layout") || document.body;
  host.insertAdjacentHTML(
    "beforeend",
    `
      <button
        type="button"
        id="sitewide-zobo-launcher"
        class="life-chat-launcher"
        aria-controls="sitewide-zobo-popover"
        aria-expanded="false"
        aria-label="${escapeHtml(t("home.lifeChatLauncherLabel"))}"
      >
        <span class="life-chat-launcher-core" aria-hidden="true">
          <span class="life-chat-bot-icon">
            <span class="life-chat-bot-face"></span>
          </span>
        </span>
      </button>

      <section id="sitewide-zobo-popover" class="life-chat-popover hidden" aria-live="polite">
        <div class="life-chat-header">
          <div class="life-chat-assistant">
            <div class="life-chat-avatar" aria-hidden="true">
              <span class="life-chat-bot-icon">
                <span class="life-chat-bot-face"></span>
              </span>
            </div>
            <div class="stack life-chat-header-copy">
              <strong>${escapeHtml(getZoboAssistantName())}</strong>
              <p class="meta">${escapeHtml(t("home.lifeChatHint"))}</p>
              <span id="sitewide-zobo-status" class="life-chat-status"></span>
            </div>
          </div>
          <button
            type="button"
            id="sitewide-zobo-close"
            class="ghost life-chat-close"
            aria-label="${escapeHtml(t("home.lifeChatClose"))}"
          >
            <span class="life-chat-close-mark" aria-hidden="true">−</span>
            <span>${escapeHtml(t("home.lifeChatMinimize"))}</span>
          </button>
        </div>
        <div class="life-chatbox">
          <div id="sitewide-zobo-messages" class="life-chat-messages"></div>
          <div id="sitewide-zobo-suggestions" class="life-chat-suggestions hidden"></div>
          <div id="sitewide-zobo-actions" class="life-chat-actions hidden"></div>
          <form id="sitewide-zobo-form" class="life-chat-form">
            <label class="sr-only" for="sitewide-zobo-input">${escapeHtml(t("home.lifeChatInputLabel"))}</label>
            <input
              id="sitewide-zobo-input"
              type="text"
              placeholder="${escapeHtml(t("home.lifeChatPlaceholder"))}"
            />
            <button type="submit" id="sitewide-zobo-send">${escapeHtml(t("home.lifeChatSend"))}</button>
          </form>
        </div>
      </section>
    `,
  );

  launcher = document.querySelector("#sitewide-zobo-launcher");
  return ensureSitewideZoboMarkup();
}

function renderSitewideZobo(zoboState) {
  const nodes = ensureSitewideZoboMarkup();
  if (!nodes) return;

  nodes.launcher.classList.toggle("has-probe", Boolean(zoboState.payload?.next_probe));
  nodes.launcher.setAttribute("aria-expanded", zoboState.chatOpen ? "true" : "false");
  nodes.popover.classList.toggle("hidden", !zoboState.chatOpen);
  if (nodes.assistantStatus) nodes.assistantStatus.textContent = getZoboStatusText(zoboState);

  if (!zoboState.messages.length && !zoboState.isProbeLoading) {
    nodes.messages.innerHTML = `
      <article class="chat-entry assistant welcome">
        <div class="chat-entry-meta">
          <span class="chat-avatar assistant" aria-hidden="true">ZO</span>
          <span class="chat-author">${escapeHtml(getZoboAssistantName())}</span>
        </div>
        <div class="chat-bubble assistant">${escapeHtml(getZoboWelcomeMessage())}</div>
      </article>
    `;
  } else {
    nodes.messages.innerHTML = zoboState.messages
      .map((message) => {
        const roleClass = message.role === "assistant" ? "assistant" : "user";
        const author = message.role === "assistant" ? getZoboAssistantName() : t("home.lifeChatUserLabel");
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
  }

  if (zoboState.isProbeLoading) {
    nodes.messages.innerHTML += `
      <article class="chat-entry assistant">
        <div class="chat-entry-meta">
          <span class="chat-avatar assistant" aria-hidden="true">ZO</span>
          <span class="chat-author">${escapeHtml(getZoboAssistantName())}</span>
        </div>
        <div class="chat-bubble assistant typing" aria-label="${escapeHtml(t("home.lifeChatStatusThinking"))}">
          <span></span><span></span><span></span>
        </div>
      </article>
    `;
  }
  nodes.messages.scrollTop = nodes.messages.scrollHeight;

  const suggestions = buildZoboSuggestions(zoboState);
  if (suggestions.length) {
    nodes.suggestions.classList.remove("hidden");
    nodes.suggestions.innerHTML = `
      <span class="life-chat-suggestions-label">${escapeHtml(t("home.lifeChatQuickReplies"))}</span>
      ${suggestions
        .map(
          (suggestion) => `
            <button
              type="button"
              class="life-chat-suggestion"
              data-sitewide-zobo-suggestion="${escapeHtml(suggestion.value)}"
            >${escapeHtml(suggestion.label)}</button>
          `,
        )
        .join("")}
    `;
  } else {
    nodes.suggestions.classList.add("hidden");
    nodes.suggestions.innerHTML = "";
  }

  const actions = (zoboState.payload?.navigation_actions || [])
    .map(normalizeZoboNavigationAction)
    .filter(Boolean);
  if (actions.length) {
    nodes.actions.classList.remove("hidden");
    nodes.actions.innerHTML = `
      <span class="life-chat-suggestions-label">${escapeHtml(t("home.lifeChatNavigate"))}</span>
      <div class="life-chat-action-list">
        ${actions
          .map(
            (action) => `
              <a class="life-chat-action-link" href="${escapeHtml(action.href)}">${escapeHtml(translateDynamicText(action.label || action.key || action.href))}</a>
            `,
          )
          .join("")}
      </div>
    `;
  } else {
    nodes.actions.classList.add("hidden");
    nodes.actions.innerHTML = "";
  }

  nodes.input.placeholder = getZoboPlaceholder(zoboState);
  nodes.input.disabled = zoboState.isProbeLoading;
  setBusyButtonText(nodes.sendButton, zoboState.isProbeLoading, t("home.lifeChatSending"), t("home.lifeChatSend"));
  nodes.sendButton.disabled = zoboState.isProbeLoading;

  const probeKey = zoboState.payload?.next_probe?.key || null;
  if (probeKey && zoboState.autoOpenedProbeKey !== probeKey) {
    zoboState.autoOpenedProbeKey = probeKey;
    zoboState.chatOpen = true;
    requestAnimationFrame(() => nodes.input.focus());
  }

  persistZoboState(zoboState);
}

function initializeSitewideZobo() {
  if (isHomePage()) return;
  const nodes = ensureSitewideZoboMarkup();
  if (!nodes || nodes.popover.dataset.initialized === "true") {
    if (nodes) renderSitewideZobo(readPersistedZoboState());
    return;
  }
  nodes.popover.dataset.initialized = "true";

  const zoboState = readPersistedZoboState();
  renderSitewideZobo(zoboState);

  async function interpret(message) {
    const trimmed = (message || "").trim();
    if (!trimmed) {
      setStatus(t("home.lifeDescriptionRequired"));
      return;
    }
    try {
      zoboState.description = trimmed;
      zoboState.messages = [{ role: "user", content: trimmed }];
      zoboState.isProbeLoading = true;
      zoboState.chatOpen = true;
      renderSitewideZobo(zoboState);
      await hydrateZoboSessionContext();
      const payload = await getJson("/api/v1/intake/interpret", {
        method: "POST",
        body: JSON.stringify({
          description: trimmed,
          scope: getZoboScopeFromContext(zoboState),
          state_code: getZoboStateCodeFromContext(zoboState),
          categories: getZoboCategoriesFromContext(zoboState),
          current_facts: buildZoboContextFacts(zoboState),
          use_llm: true,
        }),
      });
      if (payload.chat_reply) {
        zoboState.messages.push({ role: "assistant", content: payload.chat_reply });
      }
      zoboState.payload = payload;
      zoboState.pendingQuestionKey = payload?.next_probe?.key || null;
      zoboState.isProbeLoading = false;
      renderSitewideZobo(zoboState);
      setStatus(t("home.lifeAnalyzed"));
    } catch (error) {
      zoboState.isProbeLoading = false;
      renderSitewideZobo(zoboState);
      setStatus(t("home.lifeInterpretError", { error: error.message }));
    } finally {
      nodes.input.value = "";
    }
  }

  async function probe(message) {
    const trimmed = (message || "").trim();
    if (!trimmed) return;
    if (!zoboState.payload) {
      await interpret(trimmed);
      return;
    }
    try {
      zoboState.messages.push({ role: "user", content: trimmed });
      zoboState.isProbeLoading = true;
      renderSitewideZobo(zoboState);
      await hydrateZoboSessionContext();
      const payload = await getJson("/api/v1/intake/probe", {
        method: "POST",
        body: JSON.stringify({
          description: zoboState.description,
          scope: getZoboScopeFromContext(zoboState),
          state_code: getZoboStateCodeFromContext(zoboState),
          categories: getZoboCategoriesFromContext(zoboState),
          current_facts: buildZoboContextFacts(zoboState),
          pending_question_key: zoboState.pendingQuestionKey,
          messages: zoboState.messages,
          use_llm: true,
        }),
      });
      if (payload.chat_reply) {
        zoboState.messages.push({ role: "assistant", content: payload.chat_reply });
      }
      zoboState.payload = payload;
      zoboState.pendingQuestionKey = payload?.next_probe?.key || null;
      zoboState.isProbeLoading = false;
      renderSitewideZobo(zoboState);
      setStatus(t("home.lifeProbeUpdated"));
    } catch (error) {
      zoboState.isProbeLoading = false;
      renderSitewideZobo(zoboState);
      setStatus(t("home.lifeProbeError", { error: error.message }));
    } finally {
      nodes.input.value = "";
      if (zoboState.chatOpen) {
        requestAnimationFrame(() => nodes.input.focus());
      }
    }
  }

  nodes.form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (zoboState.isProbeLoading) return;
    await probe(nodes.input.value || "");
  });

  nodes.suggestions.addEventListener("click", async (event) => {
    const target = event.target.closest("[data-sitewide-zobo-suggestion]");
    if (!target || zoboState.isProbeLoading) return;
    await probe(target.dataset.sitewideZoboSuggestion || "");
  });

  nodes.launcher.addEventListener("click", () => {
    zoboState.chatOpen = !zoboState.chatOpen;
    renderSitewideZobo(zoboState);
    if (zoboState.chatOpen) {
      requestAnimationFrame(() => nodes.input.focus());
    }
  });

  nodes.closeButton.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    zoboState.chatOpen = false;
    renderSitewideZobo(zoboState);
  });

  nodes.header.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    if (target.closest("#sitewide-zobo-close")) return;
    zoboState.chatOpen = false;
    renderSitewideZobo(zoboState);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && zoboState.chatOpen) {
      zoboState.chatOpen = false;
      renderSitewideZobo(zoboState);
    }
  });

  document.addEventListener("click", (event) => {
    if (!zoboState.chatOpen) return;
    const target = event.target;
    if (!(target instanceof Element)) return;
    if (target.closest("#sitewide-zobo-popover") || target.closest("#sitewide-zobo-launcher")) return;
    zoboState.chatOpen = false;
    renderSitewideZobo(zoboState);
  });

  document.addEventListener("localechange", () => {
    renderSitewideZobo(zoboState);
  });
}

initializeSitewideZobo();
