const scopeSelect = document.querySelector("#scope");
const stateSelect = document.querySelector("#state-code");
const explorerForm = document.querySelector("#explorer-form");
const explorerQuery = document.querySelector("#explorer-query");
const explorerResults = document.querySelector("#explorer-results");

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

async function loadExplorer() {
  const params = new URLSearchParams({
    query: explorerQuery.value.trim(),
    scope: scopeSelect.value,
    limit: "20",
  });
  if (stateSelect.value) params.set("state_code", stateSelect.value);
  const payload = await getJson(`/api/v1/programs?${params.toString()}`);
  renderExplorer(payload);
}

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
    explorerResults.innerHTML = `<p class="meta">Explorer failed: ${error.message}</p>`;
  }
});

document.querySelector("#refresh-explorer").addEventListener("click", () => {
  loadExplorer().catch((error) => {
    explorerResults.innerHTML = `<p class="meta">Explorer failed: ${error.message}</p>`;
  });
});

loadStates()
  .then(() => loadExplorer())
  .catch((error) => {
    explorerResults.innerHTML = `<p class="meta">${error.message}</p>`;
  });
