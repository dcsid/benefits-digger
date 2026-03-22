const scopeSelect = document.querySelector("#scope");
const stateSelect = document.querySelector("#state-code");
const explorerForm = document.querySelector("#explorer-form");
const explorerQuery = document.querySelector("#explorer-query");
const explorerDescription = document.querySelector("#explorer-description");
const explorerInsight = document.querySelector("#explorer-insight");
const explorerResults = document.querySelector("#explorer-results");

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

function renderInsight(payload) {
  const interpretation = payload.interpretation || {};
  const categories = interpretation.applied_categories || [];
  const searchTerms = interpretation.search_terms || [];
  const methodLabel = interpretation.llm_used ? t("explorer.methodGemini") : t("explorer.methodHeuristic");
  const summary = categories.length || interpretation.applied_state_code || searchTerms.length
    ? t("explorer.localizedSummary")
    : t("explorer.browseSummary");

  explorerInsight.classList.remove("hidden");
  explorerInsight.classList.add("explorer-insight");
  explorerInsight.innerHTML = `
    <div class="row spread">
      <h3>${t("explorer.interpretationTitle")}</h3>
      <span class="pill">${escapeHtml(methodLabel)}</span>
    </div>
    <p class="meta">${escapeHtml(summary)}</p>
    ${
      categories.length
        ? `<div><strong>${t("explorer.needAreas")}</strong><div class="explorer-chip-row">${categories
            .map((category) => `<span class="pill">${escapeHtml(getCategoryLabel(category.key || category.label))}</span>`)
            .join("")}</div></div>`
        : ""
    }
    ${
      interpretation.applied_state_code
        ? `<p class="meta"><strong>${t("explorer.stateLabel")}</strong> ${escapeHtml(interpretation.applied_state_code)}</p>`
        : ""
    }
    ${
      searchTerms.length
        ? `<p class="meta"><strong>${t("explorer.searchTerms")}</strong> ${escapeHtml(searchTerms.join(", "))}</p>`
        : ""
    }
  `;
}

function renderExplorer(payload) {
  state.latestExplorerPayload = payload;
  const programs = payload.programs || [];
  renderInsight(payload);

  explorerResults.classList.remove("empty");
  explorerResults.innerHTML = programs.length
    ? programs
        .map(
          (program) => `
            <article class="mini-card explorer-item">
              <div class="row spread">
                <h4>${escapeHtml(program.name)}</h4>
                <span class="pill">${t("explorer.score", { score: program.search_score })}</span>
              </div>
              <p class="meta">${escapeHtml(program.agency || t("card.unknownAgency"))} · ${escapeHtml(program.jurisdiction.name)}</p>
              <p>${escapeHtml(translateDynamicText(program.summary) || t("card.noSummary"))}</p>
              ${
                program.match_reasons?.length
                  ? `<ul class="search-reason-list">${program.match_reasons
                      .map((reason) => `<li>${escapeHtml(translateDynamicText(reason))}</li>`)
                      .join("")}</ul>`
                  : ""
              }
              ${
                program.apply_url
                  ? `<p><a href="${escapeHtml(program.apply_url)}" target="_blank" rel="noreferrer">${t("explorer.openOfficial")}</a></p>`
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
    : `<p class='meta'>${t("explorer.noMatch")}</p>`;
}

async function loadExplorer() {
  const payload = await getJson("/api/v1/explorer/search", {
    method: "POST",
    body: JSON.stringify({
      query: explorerQuery.value.trim(),
      description: explorerDescription.value.trim(),
      scope: scopeSelect.value,
      state_code: stateSelect.value || null,
      limit: 20,
      use_llm: true,
    }),
  });
  renderExplorer(payload);
}

explorerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = explorerQuery.value.trim();
  const description = explorerDescription.value.trim();
  if (!description && query.length > 0 && query.length < 2) {
    explorerResults.innerHTML = `<p class="meta">${t("explorer.minChars")}</p>`;
    return;
  }
  try {
    await loadExplorer();
  } catch (error) {
    explorerResults.innerHTML = `<p class="meta">${t("explorer.failed", { error: error.message })}</p>`;
  }
});

document.querySelector("#refresh-explorer").addEventListener("click", () => {
  loadExplorer().catch((error) => {
    explorerResults.innerHTML = `<p class="meta">${t("explorer.failed", { error: error.message })}</p>`;
  });
});

loadStates()
  .then(() => loadExplorer())
  .catch((error) => {
    explorerResults.innerHTML = `<p class="meta">${error.message}</p>`;
  });

document.addEventListener("localechange", () => {
  loadStates().catch((error) => {
    explorerResults.innerHTML = `<p class="meta">${error.message}</p>`;
  });
  if (state.latestExplorerPayload) {
    renderExplorer(state.latestExplorerPayload);
  } else {
    explorerResults.innerHTML = `<p class="meta">${t("explorer.empty")}</p>`;
  }
});
