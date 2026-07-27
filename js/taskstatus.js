/**
 * Динамическое управление таблицей статусов задач на /admin/taskstatus
 * через JSON API /api/admin/taskstatus (без перезагрузки страницы).
 */

const API_BASE = "/api/admin/taskstatus";

const tableBody = document.getElementById("taskstatusBody");
const errorContainer = document.getElementById("taskstatusError");
const newNameInput = document.getElementById("taskstatusNewName");
const addBtn = document.getElementById("taskstatusAddBtn");

function showError(message) {
  errorContainer.textContent = message;
  errorContainer.classList.remove("d-none");
}

function clearError() {
  errorContainer.textContent = "";
  errorContainer.classList.add("d-none");
}

async function apiRequest(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = `Ошибка сервера: ${response.statusText}`;
    try {
      const data = await response.json();
      detail = data.detail || detail;
    } catch (e) {
      // тело ответа не JSON — оставляем сообщение по умолчанию
    }
    throw new Error(detail);
  }
  if (response.status === 204) {
    return null;
  }
  return response.json();
}

function buildRow(status) {
  // DOM API (не innerHTML с интерполяцией строки), чтобы имя статуса
  // не могло быть интерпретировано как разметка (XSS через название статуса).
  const row = document.createElement("tr");
  row.dataset.statusId = status.id;

  const idCell = document.createElement("td");
  idCell.textContent = status.id;

  const nameWrapper = document.createElement("div");
  nameWrapper.className = "d-flex gap-1";

  const input = document.createElement("input");
  input.type = "text";
  input.className = "form-control form-control-sm taskstatus-name-input";
  input.value = status.name;
  input.required = true;

  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.className = "btn btn-sm btn-outline-primary taskstatus-save-btn";
  saveBtn.title = "Сохранить";
  saveBtn.setAttribute("aria-label", `Сохранить статус ${status.name}`);
  saveBtn.innerHTML = '<i class="bi bi-check-lg"></i>';

  nameWrapper.append(input, saveBtn);
  const nameCell = document.createElement("td");
  nameCell.appendChild(nameWrapper);

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "btn btn-sm btn-outline-danger taskstatus-delete-btn";
  deleteBtn.title = "Удалить";
  deleteBtn.setAttribute("aria-label", `Удалить статус ${status.name}`);
  deleteBtn.innerHTML = '<i class="bi bi-trash"></i>';

  const actionsCell = document.createElement("td");
  actionsCell.className = "text-end";
  actionsCell.appendChild(deleteBtn);

  row.append(idCell, nameCell, actionsCell);
  return row;
}

async function saveRow(row) {
  clearError();
  const statusId = row.dataset.statusId;
  const input = row.querySelector(".taskstatus-name-input");
  const name = input.value.trim();

  if (!name) {
    showError("Название не может быть пустым.");
    return;
  }

  try {
    const updated = await apiRequest(`${API_BASE}/${statusId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    input.value = updated.name;
  } catch (error) {
    showError(error.message);
  }
}

async function deleteRow(row) {
  clearError();
  const statusId = row.dataset.statusId;

  try {
    await apiRequest(`${API_BASE}/${statusId}`, { method: "DELETE" });
    row.remove();
  } catch (error) {
    showError(error.message);
  }
}

async function addStatus() {
  clearError();
  const name = newNameInput.value.trim();

  if (!name) {
    showError("Название не может быть пустым.");
    return;
  }

  try {
    const created = await apiRequest(API_BASE, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    tableBody.appendChild(buildRow(created));
    newNameInput.value = "";
  } catch (error) {
    showError(error.message);
  }
}

tableBody.addEventListener("click", (event) => {
  const row = event.target.closest("tr");
  if (!row) return;

  if (event.target.closest(".taskstatus-save-btn")) {
    saveRow(row);
  } else if (event.target.closest(".taskstatus-delete-btn")) {
    deleteRow(row);
  }
});

addBtn.addEventListener("click", addStatus);
