document.addEventListener("DOMContentLoaded", () => {
  // ----------------------
  // LOGIN HANDLING
  // ----------------------
  const loginScreen = document.getElementById("login-screen");
  const appContent = document.getElementById("app-content");
  const loginBtn = document.getElementById("login-btn");
  const loginUser = document.getElementById("login-username");
  const loginPass = document.getElementById("login-password");

  let detectors = []; // isso deve ser preenchido da mesma forma que o select atual

  function filterDetectorsByAntipattern() {
    const ap = document.getElementById("antipattern-select").value;
    const detectorSelect = document.getElementById("detector-select");

    detectorSelect.innerHTML = "";

    const filtered = detectors.filter(d => d.name_ap === ap);

    filtered.forEach(det => {
      const opt = document.createElement("option");
      opt.value = det.name;

      if (det.api_url && det.api_url.trim() !== "") {
        opt.textContent = `${det.name} (API: ${det.api_url})`;
      } else {
        opt.textContent = det.name;
      }

      detectorSelect.appendChild(opt);
    });

    if (filtered.length === 0) {
      detectorSelect.innerHTML = `<option disabled>No detector available for selected anti-pattern</option>`;
    }
  }

  document.getElementById("antipattern-select")
    .addEventListener("change", filterDetectorsByAntipattern);

  // Oculta tudo imediatamente
  loginScreen.style.display = "none";
  appContent.style.display = "none";

  function showApp() {
    loginScreen.style.display = "none";
    appContent.style.display = "block";
  }

  function showLogin() {
    appContent.style.display = "none";
    loginScreen.style.display = "flex";
  }

  // Se já tiver token →  pula o login sem piscar
  if (localStorage.getItem("auth_token")) {
    showApp();
  } else {
    showLogin();
  }

  loginBtn.addEventListener("click", async () => {
    const res = await fetch("/api/v1/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: loginUser.value,
        password: loginPass.value
      })
    });

    const data = await res.json();

    if (data.success) {
      localStorage.setItem("auth_token", data.token);
      localStorage.setItem("auth_role", data.role);
      showApp();
    } else {
      alert("Invalid username or password.");
    }
  });

  const logoutBtn = document.getElementById("logout-btn");

  logoutBtn.addEventListener("click", () => {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("auth_role");
    appContent.style.display = "none";
    loginScreen.style.display = "flex"; // volta a tela
    loginUser.value = "";
    loginPass.value = "";
  });

  const sourceSelect = document.getElementById("source-select");
  const detectorSelect = document.getElementById("detector-select");
  const resultOutput = document.getElementById("result-output");
  const sourceHistorySelect = document.getElementById("history-filter-source");
  const detectorHistorySelect = document.getElementById("history-filter-detector");

  // Campos do form de adicionar Source
  const addSourceBtn = document.getElementById("add-source-btn");
  const newSourceName = document.getElementById("new-source-name");
  const newSourceFile = document.getElementById("new-source-file");
  const newSourceApi = document.getElementById("new-source-api");

  // Campos do form de adicionar Detector
  const addDetectorBtn = document.getElementById("add-detector-btn");
  const newAPName = document.getElementById("antipattern-name");
  const newDetectorName = document.getElementById("new-detector-name");
  const newDetectorApi = document.getElementById("new-detector-api");

  const startDateInput = document.getElementById("history-start-date");
  const endDateInput = document.getElementById("history-end-date");

  const d = new Date();
  d.setHours(d.getHours() - 3);
  iso = d.toISOString().slice(0, 16);

  startDateInput.value = iso;
  endDateInput.value = iso;

  // Botão de run
  const runBtn = document.getElementById("run-btn");

  // Botão de history
  const historyRefreshBtn = document.getElementById("history-refresh-btn");

  historyRefreshBtn.addEventListener("click", async () => {
    loadHistoryFromAPI();
  });

  const autoRunBtn = document.getElementById("auto-run-btn");
  const intervalInput = document.getElementById("interval-seconds");
  let autoRunInterval = null;
  let autoRunBuffer = [];
  let flag = false;

  autoRunBtn.addEventListener("click", async () => {
    flag = true;
    // Se já está em execução → parar
    if (autoRunInterval) {
      clearInterval(autoRunInterval);
      autoRunInterval = null;

      autoRunBtn.textContent = "⏱️ Start Polling";
      autoRunBtn.classList.remove("btn-danger");
      autoRunBtn.classList.add("btn-outline-primary");

      if (autoRunBuffer.length > 0) {
        const selectedSources = Array.from(sourceSelect.selectedOptions).map(opt => opt.value);
        const selectedDetectors = Array.from(detectorSelect.selectedOptions).map(opt => opt.value);

        // ---- Enviar tudo acumulado ao parar ----
        const res = await fetch("/api/v1/runs/autorun", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source_name: selectedSources[0], data: autoRunBuffer, detector: selectedDetectors[0] })
        });

        const result = await res.json();
        renderDetectionResult(result);
        autoRunBuffer = []; // limpa após envio;
      }

      return;
    }

    // Se não está rodando → iniciar
    const intervalSeconds = parseInt(intervalInput.value);
    //if (isNaN(intervalSeconds) || intervalSeconds < 1) {
    if (isNaN(intervalSeconds)) {
      alert("Please enter a valid interval (in seconds).");
      return;
    }

    async function collectData() {
      const selectedSources = Array.from(sourceSelect.selectedOptions).map(opt => opt.value);
      const selectedDetectors = Array.from(detectorSelect.selectedOptions).map(opt => opt.value);

      const res = await fetch("/api/v1/runs/collect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sources: selectedSources, detectors: selectedDetectors })
      });

      const result = await res.json();

      result.forEach(exec => {
        autoRunBuffer.push(...exec); // espalha os elementos no vetor final
      });

      // Apagar apos o teste sintetico
      if(flag) {
        const res1 = await fetch("/api/v1/runs/autorun", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source_name: selectedSources[0], data: autoRunBuffer, detector: selectedDetectors[0] })
        });

        const result1 = await res1.json();
        renderDetectionResult(result1);
      }
    }

    await collectData(); // coleta primeiro imediatamente
    autoRunInterval = setInterval(collectData, intervalSeconds * 1000);

    autoRunBtn.textContent = "⏹️ Stop Polling";
    autoRunBtn.classList.remove("btn-outline-primary");
    autoRunBtn.classList.add("btn-danger");
  });


  // ---------------------------
  // Funções de load
  // ---------------------------
  async function loadSources() {
    const res = await fetch("/api/v1/sources/list");
    const data = await res.json();
    sourceSelect.innerHTML = "";
    sourceHistorySelect.innerHTML = "";
    data.sources.forEach(src => {
      const opt = document.createElement("option");
      opt.value = src;
      opt.textContent = src;
      sourceSelect.appendChild(opt);

      const opt2 = document.createElement("option");
      opt2.value = src;
      opt2.textContent = src;
      sourceHistorySelect.appendChild(opt2);
    });
  }

  async function loadDetectors() {
    const res = await fetch("/api/v1/detectors/list");
    const data = await res.json();
    detectorHistorySelect.innerHTML = "";
    data.detectors.forEach(det => {
      const opt2 = document.createElement("option");
      opt2.value = det.name;
      opt2.textContent = det.name_ap + " - " + det.name;
      detectorHistorySelect.appendChild(opt2);
    });

    detectors = data.detectors

    const select = document.getElementById("antipattern-select");
    const uniqueAPs = [...new Set(detectors.map(d => d.name_ap))];

    select.innerHTML = `<option value="">-- Select anti-pattern --</option>`;
    uniqueAPs.forEach(ap => {
      const opt = document.createElement("option");
      opt.value = ap;
      opt.textContent = ap;
      select.appendChild(opt);
    });
  }

  // Carrega listas na inicialização
  loadSources();
  loadDetectors();

  // ---------------------------
  // Adicionar nova fonte
  // ---------------------------
  addSourceBtn.addEventListener("click", async () => {
    name = newSourceName.value
    api = newSourceApi.value
    file = newSourceFile.files[0]

    payload = {}

    if (!name) {
      alert("Please provide a source name.");
      return;
    }

    payload.name = name

    if (api) {
      payload.api_url = api;
      payload.json_data = null;
    } else if (file) {
      const text = await file.text();
      let parsed;
      try {
        parsed = JSON.parse(text);
      } catch (err) {
        alert("Invalid JSON file.");
        return;
      }
      payload.json_data = parsed;
      payload.api_url = null;
    } else {
      alert("Please provide either a JSON file or an API URL.");
      return;
    }

    const res = await fetch("/api/v1/sources/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      alert("Source added successfully!");
      newSourceName.value = "";
      newSourceFile.value = "";
      newSourceApi.value = "";
      loadSources();
    } else {
      alert("Error adding source.");
    }
  });

  // ---------------------------
  // Adicionar novo detector
  // ---------------------------
  addDetectorBtn.addEventListener("click", async () => {
    if (!newAPName.value || !newDetectorName.value || !newDetectorApi.value) {
      alert("Please provide both a detector name and an API URL.");
      return;
    }

    const payload = {
      antipattern: newAPName.value,
      name: newDetectorName.value,
      api_url: newDetectorApi.value
    };

    const res = await fetch("/api/v1/detectors/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      alert("Detector added successfully!");
      newAPName.value = "";
      newDetectorName.value = "";
      newDetectorApi.value = "";
      loadDetectors();
    } else {
      alert("Error adding detector.");
    }
  });

  // ---------------------------
  // Run detector
  // ---------------------------
  runBtn.addEventListener("click", async () => {
    const selectedSources = Array.from(sourceSelect.selectedOptions).map(opt => opt.value);
    const selectedDetectors = Array.from(detectorSelect.selectedOptions).map(opt => opt.value);

    const res = await fetch("/api/v1/runs/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sources: selectedSources, detectors: selectedDetectors })
    });

    const data = await res.json();
    //resultOutput.textContent = JSON.stringify(data, null, 2);
    renderDetectionResult(data);
  });

  const clearDbBtn = document.getElementById("clear-db-btn");

  clearDbBtn.addEventListener("click", async () => {
    if (!confirm("⚠️ This will delete all sources and detectors. Continue?")) return;

    const res = await fetch("/api/v1/admin/clear", { method: "DELETE" });
    const data = await res.json();

    alert(data.message);
    await loadSources();
    await loadDetectors();
  });

  sourceSelect.addEventListener("keydown", async (e) => {
    if (e.key === "Delete") {
      const selected = Array.from(sourceSelect.selectedOptions).map(opt => opt.value);
      if (!selected.length) return;

      if (!confirm(`⚠️ Delete selected sources: ${selected.join(", ")}?`)) return;

      const res = await fetch("/api/v1/admin/sources", {
        method: "DELETE", // ou DELETE se preferir
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ names: selected })
      });

      const data = await res.json();
      alert(data.message);
      await loadSources();
    }
  });

  // Função para deletar detectores
  detectorSelect.addEventListener("keydown", async (e) => {
    if (e.key === "Delete") {
      const selected = Array.from(detectorSelect.selectedOptions).map(opt => opt.value);
      if (!selected.length) return;

      if (!confirm(`⚠️ Delete selected detectors: ${selected.join(", ")}?`)) return;

      const res = await fetch("/api/v1/admin/detectors", {
        method: "DELETE", // ou DELETE
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ names: selected })
      });

      const data = await res.json();
      alert(data.message);
      await loadDetectors();
    }
  });

  sourceSelect.addEventListener("dblclick", async () => {
    const selectedOptions = Array.from(sourceSelect.selectedOptions);
    if (selectedOptions.length !== 1) {
      alert("Please select a single source to see details.");
      return;
    }
    const name = selectedOptions[0].value;

    const res = await fetch(`/api/v1/sources/get?name=${encodeURIComponent(name)}`);
    if (!res.ok) {
      alert("Error fetching source details.");
      return;
    }
    const data = await res.json();
    alert("Source details:\n" + JSON.stringify(data, null, 2));
  });

  detectorSelect.addEventListener("dblclick", async () => {
    const selectedOptions = Array.from(detectorSelect.selectedOptions);
    if (selectedOptions.length !== 1) {
      alert("Please select a single detector to see details.");
      return;
    }
    const name = selectedOptions[0].value;

    const res = await fetch(`/api/v1/detectors/get?name=${encodeURIComponent(name)}`);
    if (!res.ok) {
      alert("Error fetching detector details.");
      return;
    }
    const data = await res.json();
    alert("Detector details:\n" + JSON.stringify(data, null, 2));
  });

  let stackedHistoryChart = null;

  function createOrUpdateHistoryChart(execs) {
    const source = execs.source;
    const detector = execs.detector;
    const history = execs.history;

    const labels = history.map(e =>
      new Date(e.timestamp).toLocaleString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
      })
    );

    const detectedData = history.map(e => e.detected);
    const remainingData = history.map(e => e.total - e.detected);

    // 🔥 Se já existir, destruir antes
    if (stackedHistoryChart) {
      stackedHistoryChart.destroy();
    }

    stackedHistoryChart = new Chart(document.getElementById("stackedBarHistory"), {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Detected",
            data: detectedData,
            backgroundColor: "#F28B82",
            stack: "stack1"
          },
          {
            label: "Passed",
            data: remainingData,
            backgroundColor: "#A7E0A5",
            stack: "stack1"
          }
        ]
      },
      options: {
        responsive: true,
        onClick: (event, elements) => {
          if (!elements.length) return;
          const index = elements[0].index;
          showHistoryDetails(source, detector, history[index]);
        },
        scales: {
          x: { stacked: true },
          y: { stacked: true, beginAtZero: true }
        }
      }
    });
  }

  function showHistoryDetails(source, detector, run) {
    const container2 = document.getElementById('visual-output2');
    container2.innerHTML = ""; // limpa conteúdo anterior

    const card = document.createElement("div");
    card.className = "card mb-3 shadow-sm";

    card.innerHTML = `
            <div class="card-body">
                <h5 class="card-title">${detector.name_ap}</h5>
                <p><strong>Source:</strong> ${source.name}</p>
                <p><strong>Detector:</strong> ${detector.name}</p>
                <p><strong>Analyzed:</strong> ${run.total} | <strong>Detected:</strong> ${run.detected}</p>
                <p><strong>Execution Time:</strong> ${run.execution_time} ms</p>

<button class="btn btn-outline-primary btn-sm" 
        data-bs-toggle="collapse"
        data-bs-target="#details-${run.id}">
    Show details
</button>

                <div id="details-${run.id}" class="collapse mt-3">
                <div class="table-responsive">
    <table class="table table-bordered table-sm">
        <thead>
            <tr>
                ${Object.keys(run.result[0]).map(key => `
                    <th>${key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</th>
                `).join('')}
            </tr>
        </thead>
        <tbody>
            ${run.result.map(entry => `
                <tr>
                    ${Object.keys(entry).map(key => `
                        <td>
${(() => {
        const value = entry[key];

        // boolean
        if (typeof value === "boolean") {
          return value ? "✅ Yes" : "❌ No";
        }

        // array
        if (Array.isArray(value)) {

          // array of objects → create nested table
          if (value.length > 0 && typeof value[0] === "object") {
            return `
                <table class="table table-bordered table-sm mt-2">
                    <thead>
                        <tr>
                            ${Object.keys(value[0]).map(subKey => `
                                <th>${subKey.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</th>
                            `).join('')}
                        </tr>
                    </thead>
                    <tbody>
                        ${value.map(inner => `
                            <tr>
                                ${Object.keys(inner).map(subKey => `<td>${inner[subKey]}</td>`).join('')}
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            `;
          }

          // array simples → join
          return value.join(", ");
        }

        // objeto simples → mostrar formatado
        if (typeof value === "object" && value !== null) {
          return `<pre class='small code-block'>${JSON.stringify(value, null, 2)}</pre>`;
        }

        // default
        return value ?? "";
      })()}
</td>
                    `).join('')}
                </tr>
            `).join('')}
        </tbody>
    </table>
    </div>
</div>
            </div>
        `;

    container2.appendChild(card);
  }

  async function loadHistoryFromAPI() {
    const source = sourceHistorySelect.value;
    const detector = detectorHistorySelect.value;

    const start = startDateInput.value;
    const end = endDateInput.value;

    if (!source || !detector) return;

    let url = `/api/v1/runs/history?source=${encodeURIComponent(source)}&detector=${encodeURIComponent(detector)}`;
    if (start) url += `&start=${encodeURIComponent(start)}`;
    if (end) url += `&end=${encodeURIComponent(end)}`;

    const res = await fetch(url);
    const execs = await res.json();

    createOrUpdateHistoryChart(execs);
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && loginScreen.style.display !== "none") {
      loginBtn.click();
    }
  });

  function renderDetectionResult(data) {

    const container = document.getElementById('visual-output');
    container.innerHTML = ""; // limpa conteúdo anterior

    data.forEach((item, index) => {

      const card = document.createElement("div");
      card.className = "card mb-3 shadow-sm";

      card.innerHTML = `
            <div class="card-body">
                <h5 class="card-title">${item.ap}</h5>
                <p><strong>Source:</strong> ${item.source}</p>
                <p><strong>Detector:</strong> ${item.detector}</p>
                <p><strong>Analyzed:</strong> ${item.analyzed} | <strong>Detected:</strong> ${item.detected}</p>
                <p><strong>Execution Time:</strong> ${item.execution_time_ms} ms</p>

<button class="btn btn-outline-primary btn-sm" 
        data-bs-toggle="collapse"
        data-bs-target="#details-${index}">
    Show details
</button>

                <div id="details-${index}" class="collapse mt-3">
                <div class="table-responsive">
    <table class="table table-bordered table-sm">
        <thead>
            <tr>
                ${Object.keys(item.data[0]).map(key => `
                    <th>${key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</th>
                `).join('')}
            </tr>
        </thead>
        <tbody>
            ${item.data.map(entry => `
                <tr>
                    ${Object.keys(entry).map(key => `
                        <td>
${(() => {
          const value = entry[key];

          // boolean
          if (typeof value === "boolean") {
            return value ? "✅ Yes" : "❌ No";
          }

          // array
          if (Array.isArray(value)) {

            // array of objects → create nested table
            if (value.length > 0 && typeof value[0] === "object") {
              return `
                <table class="table table-bordered table-sm mt-2">
                    <thead>
                        <tr>
                            ${Object.keys(value[0]).map(subKey => `
                                <th>${subKey.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</th>
                            `).join('')}
                        </tr>
                    </thead>
                    <tbody>
                        ${value.map(inner => `
                            <tr>
                                ${Object.keys(inner).map(subKey => `<td>${inner[subKey]}</td>`).join('')}
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
                </div>
            `;
            }

            // array simples → join
            return value.join(", ");
          }

          // objeto simples → mostrar formatado
          if (typeof value === "object" && value !== null) {
            return `<pre class='small code-block'>${JSON.stringify(value, null, 2)}</pre>`;
          }

          // default
          return value ?? "";
        })()}
</td>
                    `).join('')}
                </tr>
            `).join('')}
        </tbody>
    </table>
</div>
            </div>
        `;

      container.appendChild(card);
    });
  }
});

