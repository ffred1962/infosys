/**
 * Динамическое управление таблицей типов фирм на /admin/firmtype
 * через JSON API /api/admin/firmtype (без перезагрузки страницы).
 */

const API_BASE = "/api/admin/firmtype";

const tableBody = document.getElementById("firmtypeBody");
const errorContainer = document.getElementById("firmtypeError");
const newNameInput = document.getElementById("firmtypeNewName");
const addBtn = document.getElementById("firmtypeAddBtn");

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

function buildRow(firmType) {
  // DOM API (не innerHTML с интерполяцией строки), чтобы название типа фирмы
  // не могло быть интерпретировано как разметка (XSS через название).
  const row = document.createElement("tr");
  row.dataset.firmTypeId = firmType.id;

  const idCell = document.createElement("td");
  idCell.textContent = firmType.id;

  const nameWrapper = document.createElement("div");
  nameWrapper.className = "d-flex gap-1";

  const input = document.createElement("input");
  input.type = "text";
  input.className = "form-control form-control-sm firmtype-name-input";
  input.value = firmType.name;
  input.required = true;

  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.className = "btn btn-sm btn-outline-primary firmtype-save-btn";
  saveBtn.title = "Сохранить";
  saveBtn.setAttribute("aria-label", `Сохранить тип фирмы ${firmType.name}`);
  saveBtn.innerHTML = '<i class="bi bi-check-lg"></i>';

  nameWrapper.append(input, saveBtn);
  const nameCell = document.createElement("td");
  nameCell.appendChild(nameWrapper);

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "btn btn-sm btn-outline-danger firmtype-delete-btn";
  deleteBtn.title = "Удалить";
  deleteBtn.setAttribute("aria-label", `Удалить тип фирмы ${firmType.name}`);
  deleteBtn.innerHTML = '<i class="bi bi-trash"></i>';

  const actionsCell = document.createElement("td");
  actionsCell.className = "text-end";
  actionsCell.appendChild(deleteBtn);

  row.append(idCell, nameCell, actionsCell);
  return row;
}

async function saveRow(row) {
  clearError();
  const firmTypeId = row.dataset.firmTypeId;
  const input = row.querySelector(".firmtype-name-input");
  const name = input.value.trim();

  if (!name) {
    showError("Название не может быть пустым.");
    return;
  }

  try {
    const updated = await apiRequest(`${API_BASE}/${firmTypeId}`, {
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
  const firmTypeId = row.dataset.firmTypeId;

  try {
    await apiRequest(`${API_BASE}/${firmTypeId}`, { method: "DELETE" });
    row.remove();
  } catch (error) {
    showError(error.message);
  }
}

async function addFirmType() {
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

  if (event.target.closest(".firmtype-save-btn")) {
    saveRow(row);
  } else if (event.target.closest(".firmtype-delete-btn")) {
    deleteRow(row);
  }
});

addBtn.addEventListener("click", addFirmType);
