/**
 * Динамическое управление таблицей констант на /admin/constants
 * через JSON API /api/admin/constants (без перезагрузки страницы).
 * Удаление констант не предусмотрено — только создание и редактирование.
 */

const API_BASE = "/api/admin/constants";

const tableBody = document.getElementById("constantBody");
const errorContainer = document.getElementById("constantError");
const newNameInput = document.getElementById("constantNewName");
const newValueInput = document.getElementById("constantNewValue");
const addBtn = document.getElementById("constantAddBtn");

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

function formatUpdated(isoString) {
  // Строковый срез, а не new Date(...)/getUTC* — значение naive-UTC без смещения
  // в конце строки браузер распарсил бы как локальное время (см. js/tasks.js).
  return isoString.slice(0, 16).replace("T", " ");
}

function buildRow(constant) {
  // DOM API (не innerHTML с интерполяцией строки), чтобы название/значение
  // константы не могли быть интерпретированы как разметка (XSS).
  const row = document.createElement("tr");
  row.dataset.constantId = constant.id;

  const idCell = document.createElement("td");
  idCell.textContent = constant.id;

  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.className = "form-control form-control-sm constant-name-input";
  nameInput.value = constant.name;
  nameInput.required = true;
  const nameCell = document.createElement("td");
  nameCell.appendChild(nameInput);

  const valueInput = document.createElement("input");
  valueInput.type = "text";
  valueInput.className = "form-control form-control-sm constant-value-input";
  valueInput.value = constant.value;
  valueInput.required = true;
  const valueCell = document.createElement("td");
  valueCell.appendChild(valueInput);

  const updatedCell = document.createElement("td");
  updatedCell.className = "constant-updated";
  updatedCell.textContent = formatUpdated(constant.updated);

  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.className = "btn btn-sm btn-outline-primary constant-save-btn";
  saveBtn.title = "Сохранить";
  saveBtn.setAttribute("aria-label", `Сохранить константу ${constant.name}`);
  saveBtn.innerHTML = '<i class="bi bi-check-lg"></i>';

  const actionsCell = document.createElement("td");
  actionsCell.className = "text-end";
  actionsCell.appendChild(saveBtn);

  row.append(idCell, nameCell, valueCell, updatedCell, actionsCell);
  return row;
}

async function saveRow(row) {
  clearError();
  const constantId = row.dataset.constantId;
  const nameInput = row.querySelector(".constant-name-input");
  const valueInput = row.querySelector(".constant-value-input");
  const name = nameInput.value.trim();
  const value = valueInput.value.trim();

  if (!name) {
    showError("Название не может быть пустым.");
    return;
  }
  if (!value) {
    showError("Значение не может быть пустым.");
    return;
  }

  try {
    const updated = await apiRequest(`${API_BASE}/${constantId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, value }),
    });
    nameInput.value = updated.name;
    valueInput.value = updated.value;
    row.querySelector(".constant-updated").textContent = formatUpdated(updated.updated);
  } catch (error) {
    showError(error.message);
  }
}

async function addConstant() {
  clearError();
  const name = newNameInput.value.trim();
  const value = newValueInput.value.trim();

  if (!name) {
    showError("Название не может быть пустым.");
    return;
  }
  if (!value) {
    showError("Значение не может быть пустым.");
    return;
  }

  try {
    const created = await apiRequest(API_BASE, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, value }),
    });
    tableBody.appendChild(buildRow(created));
    newNameInput.value = "";
    newValueInput.value = "";
  } catch (error) {
    showError(error.message);
  }
}

tableBody.addEventListener("click", (event) => {
  const row = event.target.closest("tr");
  if (!row) return;

  if (event.target.closest(".constant-save-btn")) {
    saveRow(row);
  }
});

addBtn.addEventListener("click", addConstant);
