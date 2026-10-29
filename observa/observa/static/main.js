document.addEventListener("DOMContentLoaded", () => {
  // ----------------------
  // LOGIN HANDLING
  // ----------------------
  const loginScreen = document.getElementById("login-screen");
  const appContent = document.getElementById("app-content");
  const loginBtn = document.getElementById("login-btn");
  const loginEmail = document.getElementById("login-email");
  const loginPass = document.getElementById("login-password");
  const passwordVisibilityBtn = document.getElementById("toggle-password-visibility");
  const passwordVisibilityLabel = passwordVisibilityBtn.querySelector(".visually-hidden");
  const currentUsernameLabel = document.getElementById("current-username");
  const accountUsernameLabel = document.getElementById("account-username");
  const accountRoleLabel = document.getElementById("account-role");
  let currentUser = null;

  passwordVisibilityBtn.addEventListener("click", () => {
    const isPasswordVisible = loginPass.type === "text";
    loginPass.type = isPasswordVisible ? "password" : "text";
    passwordVisibilityBtn.setAttribute("aria-pressed", String(!isPasswordVisible));
    const label = isPasswordVisible ? "Mostrar senha" : "Ocultar senha";
    passwordVisibilityBtn.setAttribute("aria-label", label);
    passwordVisibilityLabel.textContent = label;
  });

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

  function clearSession() {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("auth_role");
    currentUser = null;
    currentUsernameLabel.textContent = "";
    accountUsernameLabel.textContent = "";
    accountRoleLabel.textContent = "";
  }

  async function apiFetch(url, options = {}) {
    const headers = new Headers(options.headers || {});
    const token = localStorage.getItem("auth_token");
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const response = await fetch(url, { ...options, headers });
    if (response.status === 401) {
      clearSession();
      showLogin();
    }
    return response;
  }

  function applyRole(role) {
    const canManageCatalog = role === "admin" || role === "operator";
    const isAdmin = role === "admin";
    const isExecutor = role === "executor";

    document.getElementById("source-registration-controls").hidden = !canManageCatalog;
    document.getElementById("detector-registration-controls").hidden = !canManageCatalog;
    document.getElementById("clear-db-btn").hidden = !isAdmin;
    document.getElementById("user-management-section").hidden = !isAdmin;
    document.querySelector('[data-bs-target="#tab-history"]').closest("li").hidden = isExecutor;
    document.getElementById("tab-history").hidden = isExecutor;
  }

  function updateAccountMenu(user) {
    const roleLabels = {
      admin: "Admin",
      operator: "Operador",
      executor: "Executor"
    };
    currentUser = { id: user.id, username: user.username, role: user.role };
    currentUsernameLabel.textContent = user.username;
    accountUsernameLabel.textContent = user.username;
    accountRoleLabel.textContent = roleLabels[user.role] || user.role;
  }

  async function activateUser(user) {
    updateAccountMenu(user);
    localStorage.setItem("auth_role", user.role);
    applyRole(user.role);
    showApp();
    await loadSources();
    await loadDetectors();
    if (user.role === "admin") await loadUsers();
  }

  async function restoreSession() {
    if (!localStorage.getItem("auth_token")) {
      showLogin();
      return;
    }

    const response = await apiFetch("/api/v1/admin/me");
    if (!response.ok) {
      clearSession();
      showLogin();
      return;
    }
    await activateUser(await response.json());
  }

  loginBtn.addEventListener("click", async () => {
    const res = await fetch("/api/v1/admin/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: loginEmail.value,
        password: loginPass.value
      })
    });

    const data = await res.json();
    if (res.ok && data.success) {
      localStorage.setItem("auth_token", data.token);
      await activateUser(data);
    } else {
      alert("Invalid email or password.");
    }
  });

  const logoutBtn = document.getElementById("logout-btn");

  logoutBtn.addEventListener("click", () => {
    clearSession();
    showLogin();
    loginEmail.value = "";
    loginPass.value = "";
  });

  const sourceSelect = document.getElementById("source-select");
  const detectorSelect = document.getElementById("detector-select");
  const resultOutput = document.getElementById("result-output");
  const sourceHistorySelect = document.getElementById("history-filter-source");
  const detectorHistorySelect = document.getElementById("history-filter-detector");
  const userList = document.getElementById("user-list");
  const newUserName = document.getElementById("new-user-name");
  const newUserEmail = document.getElementById("new-user-email");
  const newUserRole = document.getElementById("new-user-role");
  const createUserBtn = document.getElementById("create-user-btn");
  newUserName.maxLength = 128;
  const passwordResetModal = document.getElementById("password-reset-modal");
  const resetPasswordInput = document.getElementById("reset-user-password");
  const confirmResetPasswordInput = document.getElementById("confirm-reset-user-password");
  const passwordConfirmationMessage = document.getElementById("password-confirmation-message");
  const saveUserPasswordBtn = document.getElementById("save-user-password-btn");
  let passwordResetUserId = null;

  function updatePasswordRequirements() {
    const password = resetPasswordInput.value;
    const checks = {
      length: Array.from(password).length >= 9,
      uppercase: /[A-Z]/.test(password),
      lowercase: /[a-z]/.test(password),
      number: /[0-9]/.test(password),
      special: /[^A-Za-z0-9\s]/.test(password)
    };

    Object.entries(checks).forEach(([rule, isValid]) => {
      const item = passwordResetModal.querySelector(`[data-password-rule="${rule}"]`);
      item.classList.toggle("is-valid", password.length > 0 && isValid);
      item.classList.toggle("is-invalid", password.length > 0 && !isValid);
      item.querySelector("span").textContent = isValid ? "✓" : "○";
    });

    const confirmationMatches = password.length > 0
      && password === confirmResetPasswordInput.value;
    passwordConfirmationMessage.textContent = confirmResetPasswordInput.value
      ? confirmationMatches ? "Passwords match." : "Passwords do not match."
      : "";
    passwordConfirmationMessage.className = confirmationMatches
      ? "small mt-2 text-success"
      : "small mt-2 text-danger";
    saveUserPasswordBtn.disabled = !Object.values(checks).every(Boolean) || !confirmationMatches;
  }

  [resetPasswordInput, confirmResetPasswordInput].forEach(input => {
    input.addEventListener("input", updatePasswordRequirements);
  });

  passwordResetModal.addEventListener("hidden.bs.modal", () => {
    passwordResetUserId = null;
    resetPasswordInput.value = "";
    confirmResetPasswordInput.value = "";
    passwordConfirmationMessage.textContent = "";
    passwordConfirmationMessage.className = "small mt-2";
    updatePasswordRequirements();
  });

  saveUserPasswordBtn.addEventListener("click", async () => {
    if (!passwordResetUserId || saveUserPasswordBtn.disabled) return;

    saveUserPasswordBtn.disabled = true;
    const response = await apiFetch(
      `/api/v1/admin/users/${passwordResetUserId}/password`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: resetPasswordInput.value })
      }
    );
    const data = await response.json();
    if (!response.ok) {
      alert(data.detail || "Unable to update user password.");
      updatePasswordRequirements();
      return;
    }

    bootstrap.Modal.getOrCreateInstance(passwordResetModal).hide();
    alert("Password updated successfully.");
  });

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
        const res = await apiFetch("/api/v1/runs/autorun", {
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

      const res = await apiFetch("/api/v1/runs/collect", {
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
        const res1 = await apiFetch("/api/v1/runs/autorun", {
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
    const res = await apiFetch("/api/v1/sources/list");
    if (!res.ok) return;
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
    const res = await apiFetch("/api/v1/detectors/list");
    if (!res.ok) return;
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

  async function loadUsers() {
    const response = await apiFetch("/api/v1/admin/users");
    if (!response.ok) return;

    const data = await response.json();
    userList.replaceChildren();
    data.users.forEach(user => {
      const row = document.createElement("tr");
      const usernameCell = document.createElement("td");
      const usernameInput = document.createElement("input");
      usernameInput.type = "text";
      usernameInput.className = "form-control form-control-sm";
      usernameInput.value = user.username;
      usernameInput.maxLength = 128;
      usernameInput.autocomplete = "off";
      usernameCell.appendChild(usernameInput);

      const emailCell = document.createElement("td");
      const emailInput = document.createElement("input");
      emailInput.type = "email";
      emailInput.className = "form-control form-control-sm";
      emailInput.value = user.email;
      emailInput.maxLength = 254;
      emailInput.autocomplete = "off";
      emailCell.appendChild(emailInput);

      const roleCell = document.createElement("td");
      const roleSelect = document.createElement("select");
      roleSelect.className = "form-select form-select-sm";
      [["admin", "Admin"], ["operator", "Operador"], ["executor", "Executor"]]
        .forEach(([value, label]) => {
          const option = document.createElement("option");
          option.value = value;
          option.textContent = label;
          option.selected = user.role === value;
          roleSelect.appendChild(option);
        });
      roleCell.appendChild(roleSelect);

      const activeCell = document.createElement("td");
      const activeCheckbox = document.createElement("input");
      activeCheckbox.type = "checkbox";
      activeCheckbox.className = "form-check-input";
      activeCheckbox.checked = user.is_active;
      activeCell.appendChild(activeCheckbox);

      const actionsCell = document.createElement("td");
      const saveButton = document.createElement("button");
      saveButton.type = "button";
      saveButton.className = "btn btn-sm btn-outline-primary me-2";
      saveButton.textContent = "Save";
      saveButton.addEventListener("click", async () => {
        const updatedUsername = usernameInput.value.trim();
        const updatedEmail = emailInput.value.trim().toLowerCase();
        const result = await apiFetch(`/api/v1/admin/users/${user.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            username: updatedUsername,
            email: updatedEmail,
            role: roleSelect.value,
            is_active: activeCheckbox.checked
          })
        });
        if (!result.ok) {
          const error = await result.json();
          alert(error.detail || "Unable to update user.");
          return;
        }

        if (currentUser?.id === user.id) {
          updateAccountMenu({
            id: currentUser.id,
            username: updatedUsername,
            role: currentUser.role
          });
        }
        await loadUsers();
      });

      const resetPasswordButton = document.createElement("button");
      resetPasswordButton.type = "button";
      resetPasswordButton.className = "btn btn-sm btn-outline-secondary me-2";
      resetPasswordButton.textContent = "Change password";
      resetPasswordButton.addEventListener("click", () => {
        passwordResetUserId = user.id;
        document.getElementById("password-reset-title").textContent =
          `Change password for ${user.username}`;
        resetPasswordInput.value = "";
        confirmResetPasswordInput.value = "";
        updatePasswordRequirements();
        bootstrap.Modal.getOrCreateInstance(passwordResetModal).show();
      });

      const deleteButton = document.createElement("button");
      deleteButton.type = "button";
      deleteButton.className = "btn btn-sm btn-outline-danger";
      deleteButton.textContent = "Delete";
      deleteButton.addEventListener("click", async () => {
        if (!confirm(`Delete user '${user.username}'?`)) return;
        const result = await apiFetch(`/api/v1/admin/users/${user.id}`, {
          method: "DELETE"
        });
        if (!result.ok) {
          const error = await result.json();
          alert(error.detail || "Unable to delete user.");
          return;
        }
        await loadUsers();
      });

      actionsCell.append(saveButton, resetPasswordButton, deleteButton);
      row.append(usernameCell, emailCell, roleCell, activeCell, actionsCell);
      userList.appendChild(row);
    });
  }

  createUserBtn.addEventListener("click", async () => {
    const username = newUserName.value.trim();
    const email = newUserEmail.value.trim().toLowerCase();
    if (!username || !email) {
      alert("Enter a username and email address.");
      return;
    }

    const response = await apiFetch("/api/v1/admin/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, email, role: newUserRole.value })
    });
    const data = await response.json();
    if (!response.ok) {
      alert(data.detail || "Unable to create user.");
      return;
    }

    alert(`User: ${data.user.username}\nRole: ${data.user.role}\nInitial password: ${data.initial_password}\n\nSave this password now. It will not be shown again.`);
    newUserName.value = "";
    newUserEmail.value = "";
    await loadUsers();
  });

  void restoreSession();

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

    const res = await apiFetch("/api/v1/sources/register", {
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

    const res = await apiFetch("/api/v1/detectors/register", {
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

    const res = await apiFetch("/api/v1/runs/execute", {
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

    const res = await apiFetch("/api/v1/admin/clear", { method: "DELETE" });
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

      const res = await apiFetch("/api/v1/admin/sources", {
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

      const res = await apiFetch("/api/v1/admin/detectors", {
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

    const res = await apiFetch(`/api/v1/sources/get?name=${encodeURIComponent(name)}`);
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

    const res = await apiFetch(`/api/v1/detectors/get?name=${encodeURIComponent(name)}`);
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

    const res = await apiFetch(url);
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
