const planShell = document.querySelector("#plan-shell");
const planEmpty = document.querySelector("#plan-empty");
const planDepthPill = document.querySelector("#plan-depth-pill");
const overviewMetrics = document.querySelector("#overview-metrics");
const benefitStack = document.querySelector("#benefit-stack");
const missingFacts = document.querySelector("#missing-facts");
const actionPlan = document.querySelector("#action-plan");
const sourceHub = document.querySelector("#source-hub");
const planningNotes = document.querySelector("#planning-notes");

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

async function loadPlan() {
  if (!state.sessionId) {
    planEmpty.innerHTML = 'No active session. <a href="/">Start a screening</a> first.';
    renderPlan(null);
    return;
  }
  const payload = await getJson(`/api/v1/sessions/${state.sessionId}/plan`);
  renderPlan(payload);
}

loadPlan().catch((error) => {
  planEmpty.textContent = `Could not load plan: ${error.message}`;
});
