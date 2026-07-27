/**
 * Динамическое управление таблицей единиц измерения на /admin/unit
 * через JSON API /api/admin/unit (без перезагрузки страницы).
 */

const API_BASE = "/api/admin/unit";

const tableBody = document.getElementById("unitBody");
const errorContainer = document.getElementById("unitError");
const newNameInput = document.getElementById("unitNewName");
const addBtn = document.getElementById("unitAddBtn");

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

function buildRow(unit) {
  // DOM API (не innerHTML с интерполяцией строки), чтобы название единицы
  // не могло быть интерпретировано как разметка (XSS через название).
  const row = document.createElement("tr");
  row.dataset.unitId = unit.id;

  const idCell = document.createElement("td");
  idCell.textContent = unit.id;

  const nameWrapper = document.createElement("div");
  nameWrapper.className = "d-flex gap-1";

  const input = document.createElement("input");
  input.type = "text";
  input.className = "form-control form-control-sm unit-name-input";
  input.value = unit.name;
  input.required = true;

  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.className = "btn btn-sm btn-outline-primary unit-save-btn";
  saveBtn.title = "Сохранить";
  saveBtn.setAttribute("aria-label", `Сохранить единицу ${unit.name}`);
  saveBtn.innerHTML = '<i class="bi bi-check-lg"></i>';

  nameWrapper.append(input, saveBtn);
  const nameCell = document.createElement("td");
  nameCell.appendChild(nameWrapper);

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "btn btn-sm btn-outline-danger unit-delete-btn";
  deleteBtn.title = "Удалить";
  deleteBtn.setAttribute("aria-label", `Удалить единицу ${unit.name}`);
  deleteBtn.innerHTML = '<i class="bi bi-trash"></i>';

  const actionsCell = document.createElement("td");
  actionsCell.className = "text-end";
  actionsCell.appendChild(deleteBtn);

  row.append(idCell, nameCell, actionsCell);
  return row;
}

async function saveRow(row) {
  clearError();
  const unitId = row.dataset.unitId;
  const input = row.querySelector(".unit-name-input");
  const name = input.value.trim();

  if (!name) {
    showError("Название не может быть пустым.");
    return;
  }

  try {
    const updated = await apiRequest(`${API_BASE}/${unitId}`, {
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
  const unitId = row.dataset.unitId;

  try {
    await apiRequest(`${API_BASE}/${unitId}`, { method: "DELETE" });
    row.remove();
  } catch (error) {
    showError(error.message);
  }
}

async function addUnit() {
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

  if (event.target.closest(".unit-save-btn")) {
    saveRow(row);
  } else if (event.target.closest(".unit-delete-btn")) {
    deleteRow(row);
  }
});

addBtn.addEventListener("click", addUnit);
