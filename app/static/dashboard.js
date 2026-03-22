const planShell = document.querySelector("#plan-shell");
const planEmpty = document.querySelector("#plan-empty");
const planDepthPill = document.querySelector("#plan-depth-pill");
const overviewMetrics = document.querySelector("#overview-metrics");
const benefitStack = document.querySelector("#benefit-stack");
const missingFacts = document.querySelector("#missing-facts");
const actionPlan = document.querySelector("#action-plan");
const sourceHub = document.querySelector("#source-hub");
const planningNotes = document.querySelector("#planning-notes");
const documentChecklist = document.querySelector("#document-checklist");

function renderPlan(plan) {
  state.latestPlan = plan;
  if (!plan) {
    planShell.classList.add("hidden");
    planEmpty.classList.remove("hidden");
    planDepthPill.textContent = t("dashboard.noSession");
    return;
  }

  planShell.classList.remove("hidden");
  planEmpty.classList.add("hidden");
  const breadthValue = plan.profile.breadth_value ?? 0.5;
  const dv = plan.profile.depth_value ?? 0.5;
  const breadthLabel = getBreadthDescriptor(breadthValue).label;
  const depthLabel = getDepthDescriptor(dv).label;
  planDepthPill.textContent = t("dashboard.controlsPill", {
    breadthLabel,
    breadthPercent: Math.round(breadthValue * 100),
    depthLabel,
    depthPercent: Math.round(dv * 100),
  });

  const estMonthly = plan.overview.estimated_monthly_total;
  const metrics = [
    { label: t("dashboard.likelyPrograms"), value: plan.overview.likely_programs },
    { label: t("dashboard.possiblePrograms"), value: plan.overview.possible_programs },
    { label: t("dashboard.answeredQuestions"), value: plan.overview.answered_questions },
    { label: t("dashboard.avgRuleCoverage"), value: `${plan.overview.average_rule_coverage}%` },
  ];
  if (estMonthly > 0) {
    metrics.push({ label: t("dashboard.estMonthly"), value: `$${estMonthly.toLocaleString()}` });
  }

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
              <h4>${escapeHtml(translateEnum("category", item.category, item.label))}</h4>
              <p class="meta">${item.likely_programs} ${escapeHtml(t("dashboard.likely"))} · ${item.possible_programs} ${escapeHtml(t("dashboard.possible"))}</p>
              <p>${item.top_programs.map(escapeHtml).join(", ") || t("dashboard.noTopPrograms")}</p>
            </article>
          `,
        )
        .join("")
    : `<p class='meta'>${t("dashboard.noBenefitStack")}</p>`;

  missingFacts.innerHTML = plan.top_missing_facts.length
    ? plan.top_missing_facts
        .map(
          (item) => `
            <article class="mini-card">
              <h4>${escapeHtml(item.label)}</h4>
              <p class="meta">${escapeHtml(t("dashboard.affects", { count: item.program_count }))}</p>
            </article>
          `,
        )
        .join("")
    : `<p class='meta'>${t("dashboard.noMissingFacts")}</p>`;

  actionPlan.innerHTML = plan.action_plan.length
    ? plan.action_plan
        .map(
          (step) => `
            <article class="mini-card">
              <h4>${escapeHtml(step.program_name)}</h4>
              <p class="meta">${statusLabel(step.eligibility_status)} · ${escapeHtml(t("dashboard.confidence", { value: step.confidence }))}</p>
              <p><a href="${escapeHtml(step.url)}" target="_blank" rel="noreferrer">${escapeHtml(translateDynamicText(step.step_label))}</a></p>
            </article>
          `,
        )
        .join("")
    : `<p class='meta'>${t("dashboard.noActions")}</p>`;

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
    : `<p class='meta'>${t("dashboard.noSourceHub")}</p>`;

  const docs = plan.document_checklist || [];
  documentChecklist.innerHTML = docs.length
    ? `<ul class="checklist">${docs.map((doc) =>
        `<li class="checklist-item">
          <label><input type="checkbox" class="doc-check" data-program="plan" data-doc="${escapeHtml(doc.name)}">
          <strong>${escapeHtml(doc.name)}</strong> <span class="badge-doc ${escapeHtml(doc.type)}">${escapeHtml(translateEnum("docType", doc.type, doc.type))}</span></label>
          ${doc.description ? `<p class="meta">${escapeHtml(translateDynamicText(doc.description))}</p>` : ""}
          <p class="meta">${escapeHtml(t("dashboard.neededFor", { programs: doc.programs.map(escapeHtml).join(", ") }))}</p>
        </li>`).join("")}</ul>`
    : `<p class='meta'>${t("dashboard.noDocuments")}</p>`;

  planningNotes.innerHTML = plan.planning_notes.length
    ? plan.planning_notes
        .map((note) => `<article class="mini-card"><p>${escapeHtml(translateDynamicText(note))}</p></article>`)
        .join("")
    : `<p class='meta'>${t("dashboard.noPlanningNotes")}</p>`;
}

async function loadPlan() {
  if (!state.sessionId) {
    planEmpty.innerHTML = t("dashboard.noSessionLink");
    renderPlan(null);
    return;
  }
  const payload = await getJson(`/api/v1/sessions/${state.sessionId}/plan`);
  renderPlan(payload);
}

document.querySelector("#download-pdf").addEventListener("click", () => {
  if (!state.sessionId || typeof html2pdf === "undefined") return;
  const element = planShell;
  if (!element) return;
  const btn = document.querySelector("#download-pdf");
  setBusyButtonText(btn, true, t("dashboard.generatingPdf"), t("dashboard.downloadPdf"));
  btn.disabled = true;
  html2pdf()
    .set({
      margin: 10,
      filename: "benefits-dashboard.pdf",
      image: { type: "jpeg", quality: 0.98 },
      html2canvas: { scale: 2, useCORS: true },
      jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
    })
    .from(element)
    .save()
    .then(() => {
      setBusyButtonText(btn, false, t("dashboard.generatingPdf"), t("dashboard.downloadPdf"));
      btn.disabled = false;
    });
});

loadPlan().catch((error) => {
  planEmpty.textContent = t("dashboard.loadError", { error: error.message });
});

document.addEventListener("localechange", () => {
  if (state.latestPlan) {
    renderPlan(state.latestPlan);
  } else if (!state.sessionId) {
    planEmpty.innerHTML = t("dashboard.noSessionLink");
    renderPlan(null);
  }
});
