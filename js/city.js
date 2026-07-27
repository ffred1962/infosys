/**
 * Динамическое управление таблицей городов на /admin/city
 * через JSON API /api/admin/city (без перезагрузки страницы).
 */

const API_BASE = "/api/admin/city";

const tableBody = document.getElementById("cityBody");
const errorContainer = document.getElementById("cityError");
const newNameInput = document.getElementById("cityNewName");
const addBtn = document.getElementById("cityAddBtn");

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

function buildRow(city) {
  // DOM API (не innerHTML с интерполяцией строки), чтобы название города
  // не могло быть интерпретировано как разметка (XSS через название).
  const row = document.createElement("tr");
  row.dataset.cityId = city.id;

  const idCell = document.createElement("td");
  idCell.textContent = city.id;

  const nameWrapper = document.createElement("div");
  nameWrapper.className = "d-flex gap-1";

  const input = document.createElement("input");
  input.type = "text";
  input.className = "form-control form-control-sm city-name-input";
  input.value = city.name;
  input.required = true;

  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.className = "btn btn-sm btn-outline-primary city-save-btn";
  saveBtn.title = "Сохранить";
  saveBtn.setAttribute("aria-label", `Сохранить город ${city.name}`);
  saveBtn.innerHTML = '<i class="bi bi-check-lg"></i>';

  nameWrapper.append(input, saveBtn);
  const nameCell = document.createElement("td");
  nameCell.appendChild(nameWrapper);

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "btn btn-sm btn-outline-danger city-delete-btn";
  deleteBtn.title = "Удалить";
  deleteBtn.setAttribute("aria-label", `Удалить город ${city.name}`);
  deleteBtn.innerHTML = '<i class="bi bi-trash"></i>';

  const actionsCell = document.createElement("td");
  actionsCell.className = "text-end";
  actionsCell.appendChild(deleteBtn);

  row.append(idCell, nameCell, actionsCell);
  return row;
}

async function saveRow(row) {
  clearError();
  const cityId = row.dataset.cityId;
  const input = row.querySelector(".city-name-input");
  const name = input.value.trim();

  if (!name) {
    showError("Название не может быть пустым.");
    return;
  }

  try {
    const updated = await apiRequest(`${API_BASE}/${cityId}`, {
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
  const cityId = row.dataset.cityId;

  try {
    await apiRequest(`${API_BASE}/${cityId}`, { method: "DELETE" });
    row.remove();
  } catch (error) {
    showError(error.message);
  }
}

async function addCity() {
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

  if (event.target.closest(".city-save-btn")) {
    saveRow(row);
  } else if (event.target.closest(".city-delete-btn")) {
    deleteRow(row);
  }
});

addBtn.addEventListener("click", addCity);
