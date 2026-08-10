/**
 * Динамическое управление таблицей типов каналов на /admin/channeltype
 * через JSON API /api/admin/channeltype (без перезагрузки страницы).
 */

const API_BASE = "/api/admin/channeltype";

const tableBody = document.getElementById("channeltypeBody");
const errorContainer = document.getElementById("channeltypeError");
const newNameInput = document.getElementById("channeltypeNewName");
const newActiveInput = document.getElementById("channeltypeNewActive");
const newInputInput = document.getElementById("channeltypeNewInput");
const newOutputInput = document.getElementById("channeltypeNewOutput");
const newIconInput = document.getElementById("channeltypeNewIcon");
const addBtn = document.getElementById("channeltypeAddBtn");

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

function buildRow(channelType) {
  // DOM API (не innerHTML с интерполяцией строки) — то же обоснование, что и
  // в taskstatus.js/city.js/firm_type.js/unit.js: название/путь к иконке не
  // должны трактоваться как разметка.
  const row = document.createElement("tr");
  row.dataset.channelTypeId = channelType.id;

  const iconCell = document.createElement("td");
  const iconImg = document.createElement("img");
  iconImg.className = "channeltype-icon-preview";
  iconImg.width = 28;
  iconImg.height = 28;
  iconImg.alt = "";
  iconImg.src = channelType.icon_url;
  iconCell.appendChild(iconImg);

  const nameCell = document.createElement("td");
  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.className = "form-control form-control-sm channeltype-name-input";
  nameInput.value = channelType.name;
  nameInput.required = true;
  nameCell.appendChild(nameInput);

  function checkboxCell(className, checked) {
    const cell = document.createElement("td");
    cell.className = "text-center";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.className = `form-check-input ${className}`;
    input.checked = checked;
    cell.appendChild(input);
    return cell;
  }

  const activeCell = checkboxCell("channeltype-active-input", channelType.is_active);
  const inputCell = checkboxCell("channeltype-input-input", channelType.is_input);
  const outputCell = checkboxCell("channeltype-output-input", channelType.is_output);

  const iconUrlCell = document.createElement("td");
  const iconUrlInput = document.createElement("input");
  iconUrlInput.type = "text";
  iconUrlInput.className = "form-control form-control-sm channeltype-icon-input";
  iconUrlInput.value = channelType.icon_url;
  iconUrlInput.required = true;
  iconUrlCell.appendChild(iconUrlInput);

  const saveBtn = document.createElement("button");
  saveBtn.type = "button";
  saveBtn.className = "btn btn-sm btn-outline-primary channeltype-save-btn";
  saveBtn.title = "Сохранить";
  saveBtn.setAttribute("aria-label", `Сохранить тип канала ${channelType.name}`);
  saveBtn.innerHTML = '<i class="bi bi-check-lg"></i>';

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "btn btn-sm btn-outline-danger channeltype-delete-btn";
  deleteBtn.title = "Удалить";
  deleteBtn.setAttribute("aria-label", `Удалить тип канала ${channelType.name}`);
  deleteBtn.innerHTML = '<i class="bi bi-trash"></i>';

  const actionsWrapper = document.createElement("div");
  actionsWrapper.className = "d-flex gap-1 justify-content-end";
  actionsWrapper.append(saveBtn, deleteBtn);
  const actionsCell = document.createElement("td");
  actionsCell.className = "text-end";
  actionsCell.appendChild(actionsWrapper);

  row.append(iconCell, nameCell, activeCell, inputCell, outputCell, iconUrlCell, actionsCell);
  return row;
}

function readPayloadFromRow(row) {
  return {
    name: row.querySelector(".channeltype-name-input").value.trim(),
    is_active: row.querySelector(".channeltype-active-input").checked,
    is_input: row.querySelector(".channeltype-input-input").checked,
    is_output: row.querySelector(".channeltype-output-input").checked,
    icon_url: row.querySelector(".channeltype-icon-input").value.trim(),
  };
}

async function saveRow(row) {
  clearError();
  const channelTypeId = row.dataset.channelTypeId;
  const payload = readPayloadFromRow(row);

  if (!payload.name) {
    showError("Название не может быть пустым.");
    return;
  }
  if (!payload.icon_url) {
    showError("Путь к иконке не может быть пустым.");
    return;
  }

  try {
    const updated = await apiRequest(`${API_BASE}/${channelTypeId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    row.querySelector(".channeltype-name-input").value = updated.name;
    row.querySelector(".channeltype-icon-input").value = updated.icon_url;
    row.querySelector(".channeltype-icon-preview").src = updated.icon_url;
  } catch (error) {
    showError(error.message);
  }
}

async function deleteRow(row) {
  clearError();
  const channelTypeId = row.dataset.channelTypeId;

  try {
    await apiRequest(`${API_BASE}/${channelTypeId}`, { method: "DELETE" });
    row.remove();
  } catch (error) {
    showError(error.message);
  }
}

async function addChannelType() {
  clearError();
  const payload = {
    name: newNameInput.value.trim(),
    is_active: newActiveInput.checked,
    is_input: newInputInput.checked,
    is_output: newOutputInput.checked,
    icon_url: newIconInput.value.trim(),
  };

  if (!payload.name) {
    showError("Название не может быть пустым.");
    return;
  }
  if (!payload.icon_url) {
    showError("Путь к иконке не может быть пустым.");
    return;
  }

  try {
    const created = await apiRequest(API_BASE, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    tableBody.appendChild(buildRow(created));
    newNameInput.value = "";
    newIconInput.value = "";
    newActiveInput.checked = true;
    newInputInput.checked = true;
    newOutputInput.checked = true;
  } catch (error) {
    showError(error.message);
  }
}

tableBody.addEventListener("click", (event) => {
  const row = event.target.closest("tr");
  if (!row) return;

  if (event.target.closest(".channeltype-save-btn")) {
    saveRow(row);
  } else if (event.target.closest(".channeltype-delete-btn")) {
    deleteRow(row);
  }
});

addBtn.addEventListener("click", addChannelType);
