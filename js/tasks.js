/**
 * Страница /crm/tasks: две вкладки (выданные мной / выданные мне) через JSON API /api/task,
 * без перезагрузки страницы.
 */

const API_BASE = "/api/task";

const errorContainer = document.getElementById("tasksError");
const authoredBody = document.getElementById("authoredBody");
const assignedBody = document.getElementById("assignedBody");
const createBtn = document.getElementById("taskCreateBtn");
const authoredTabBtn = document.getElementById("authored-tab");

const taskModalEl = document.getElementById("taskModal");
const taskModal = new bootstrap.Modal(taskModalEl);
const modalError = document.getElementById("taskModalError");
const modalIdInput = document.getElementById("taskModalId");
const modalTitleLabel = document.getElementById("taskModalLabel");
const modalTitleInput = document.getElementById("taskModalTitle");
const modalDescriptionInput = document.getElementById("taskModalDescription");
const modalDueDateInput = document.getElementById("taskModalDueDate");
const modalAssigneeSelect = document.getElementById("taskModalAssignee");
const modalStatusSelect = document.getElementById("taskModalStatus");
const modalStatusGroup = document.getElementById("taskModalStatusGroup");
const modalSaveBtn = document.getElementById("taskModalSaveBtn");

const taskViewModalEl = document.getElementById("taskViewModal");
const taskViewModal = new bootstrap.Modal(taskViewModalEl);
const viewError = document.getElementById("taskViewError");
const viewIdInput = document.getElementById("taskViewId");
const viewAuthor = document.getElementById("taskViewAuthor");
const viewDueDate = document.getElementById("taskViewDueDate");
const viewDescription = document.getElementById("taskViewDescription");
const viewStatusSelect = document.getElementById("taskViewStatus");
const viewSaveBtn = document.getElementById("taskViewSaveBtn");

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function showError(message) {
  errorContainer.textContent = message;
  errorContainer.classList.remove("d-none");
}

function clearError() {
  errorContainer.textContent = "";
  errorContainer.classList.add("d-none");
}

function showModalError(message) {
  modalError.textContent = message;
  modalError.classList.remove("d-none");
}

function clearModalError() {
  modalError.textContent = "";
  modalError.classList.add("d-none");
}

function showViewError(message) {
  viewError.textContent = message;
  viewError.classList.remove("d-none");
}

function clearViewError() {
  viewError.textContent = "";
  viewError.classList.add("d-none");
}

function formatErrorDetail(detail) {
  // Pydantic-валидация (422) отдаёт detail как массив {loc, msg, ...},
  // а не строку — плоские HTTPException-ошибки уже строки.
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
  }
  return detail;
}

async function apiRequest(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = `Ошибка сервера: ${response.statusText}`;
    try {
      const data = await response.json();
      detail = formatErrorDetail(data.detail) || detail;
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

function buildAuthoredRow(task) {
  const row = document.createElement("tr");
  row.dataset.taskId = task.id;
  row.dataset.title = task.title;
  row.dataset.description = task.description || "";
  row.dataset.dueDate = task.due_date.slice(0, 10);
  row.dataset.assigneeId = task.assignee_id;
  row.dataset.statusId = task.status_id;

  const idCell = document.createElement("td");
  idCell.textContent = task.id;

  const titleCell = document.createElement("td");
  const titleLink = document.createElement("button");
  titleLink.type = "button";
  titleLink.className = "btn btn-link p-0 text-start task-title-link";
  titleLink.textContent = task.title;
  titleCell.appendChild(titleLink);

  const assigneeCell = document.createElement("td");
  assigneeCell.textContent = task.assignee_fullname;

  const dueDateCell = document.createElement("td");
  dueDateCell.textContent = task.due_date.slice(0, 10);

  const statusCell = document.createElement("td");
  const statusBadge = document.createElement("span");
  statusBadge.className = "badge text-bg-info task-status-badge";
  statusBadge.textContent = task.status_name;
  statusCell.appendChild(statusBadge);

  const completedCell = document.createElement("td");
  const completedBadge = document.createElement("span");
  completedBadge.className = `badge ${task.completed ? "text-bg-success" : "text-bg-secondary"} task-completed-badge`;
  completedBadge.textContent = task.completed ? "Да" : "Нет";
  completedCell.appendChild(completedBadge);

  const actionsCell = document.createElement("td");
  actionsCell.className = "text-end";
  const actionsWrapper = document.createElement("div");
  actionsWrapper.className = "d-flex gap-1 justify-content-end";

  const completeBtn = document.createElement("button");
  completeBtn.type = "button";
  completeBtn.className = "btn btn-sm btn-outline-success task-complete-btn";
  completeBtn.title = "Отметить выполнение";
  completeBtn.setAttribute("aria-label", `Отметить выполнение задачи ${task.id}`);
  completeBtn.innerHTML = '<i class="bi bi-check-lg"></i>';

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "btn btn-sm btn-outline-danger task-delete-btn";
  deleteBtn.title = "Удалить";
  deleteBtn.setAttribute("aria-label", `Удалить задачу ${task.id}`);
  deleteBtn.innerHTML = '<i class="bi bi-trash"></i>';

  actionsWrapper.append(completeBtn, deleteBtn);
  actionsCell.appendChild(actionsWrapper);

  row.append(idCell, titleCell, assigneeCell, dueDateCell, statusCell, completedCell, actionsCell);
  return row;
}

function updateAuthoredRow(row, task) {
  row.dataset.title = task.title;
  row.dataset.description = task.description || "";
  row.dataset.dueDate = task.due_date.slice(0, 10);
  row.dataset.assigneeId = task.assignee_id;
  row.dataset.statusId = task.status_id;

  row.children[1].querySelector(".task-title-link").textContent = task.title;
  row.children[2].textContent = task.assignee_fullname;
  row.children[3].textContent = task.due_date.slice(0, 10);
  row.querySelector(".task-status-badge").textContent = task.status_name;
}

function openCreateModal() {
  clearModalError();
  modalIdInput.value = "";
  modalTitleLabel.textContent = "Новая задача";
  modalTitleInput.value = "";
  modalDescriptionInput.value = "";
  modalDueDateInput.value = "";
  modalDueDateInput.min = todayIso();
  modalAssigneeSelect.selectedIndex = 0;
  modalStatusSelect.selectedIndex = 0;
  modalStatusGroup.classList.remove("d-none");
  taskModal.show();
}

function openEditModal(row) {
  clearModalError();
  modalIdInput.value = row.dataset.taskId;
  modalTitleLabel.textContent = "Редактировать задачу";
  modalTitleInput.value = row.dataset.title;
  modalDescriptionInput.value = row.dataset.description;
  modalDueDateInput.value = row.dataset.dueDate;
  modalDueDateInput.min = todayIso();
  modalAssigneeSelect.value = row.dataset.assigneeId;
  // Статус при редактировании автором не меняется (это делает исполнитель через
  // вкладку "Выданные мне"), поэтому поле скрываем и не отправляем его в PATCH.
  modalStatusGroup.classList.add("d-none");
  taskModal.show();
}

async function saveTask() {
  clearModalError();

  const title = modalTitleInput.value.trim();
  const dueDate = modalDueDateInput.value;
  const taskId = modalIdInput.value;

  if (!title) {
    showModalError("Название не может быть пустым.");
    return;
  }
  if (!dueDate) {
    showModalError("Укажите срок.");
    return;
  }
  if (!taskId && dueDate < todayIso()) {
    // Проверка только при создании — редактирование уже просроченной задачи
    // (без изменения срока) не должно блокироваться, см. api/task.py:TaskIn.
    showModalError("Срок выполнения не может быть раньше сегодняшнего дня.");
    return;
  }

  const payload = {
    title,
    description: modalDescriptionInput.value.trim() || null,
    due_date: dueDate,
    assignee_id: parseInt(modalAssigneeSelect.value, 10),
  };
  if (!taskId) {
    // status_id только при создании — при редактировании его меняет исполнитель, не автор
    payload.status_id = parseInt(modalStatusSelect.value, 10);
  }

  modalSaveBtn.disabled = true;
  try {
    if (taskId) {
      const updated = await apiRequest(`${API_BASE}/${taskId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const row = authoredBody.querySelector(`tr[data-task-id="${taskId}"]`);
      if (row) updateAuthoredRow(row, updated);
    } else {
      const created = await apiRequest(API_BASE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      authoredBody.appendChild(buildAuthoredRow(created));
    }
    taskModal.hide();
  } catch (error) {
    showModalError(error.message);
  } finally {
    modalSaveBtn.disabled = false;
  }
}

async function toggleComplete(row) {
  clearError();
  const taskId = row.dataset.taskId;
  try {
    const updated = await apiRequest(`${API_BASE}/${taskId}/complete`, { method: "PATCH" });
    const badge = row.querySelector(".task-completed-badge");
    badge.textContent = updated.completed ? "Да" : "Нет";
    badge.classList.toggle("text-bg-success", updated.completed);
    badge.classList.toggle("text-bg-secondary", !updated.completed);
  } catch (error) {
    showError(error.message);
  }
}

async function deleteTask(row) {
  clearError();
  const taskId = row.dataset.taskId;
  try {
    await apiRequest(`${API_BASE}/${taskId}`, { method: "DELETE" });
    row.remove();
  } catch (error) {
    showError(error.message);
  }
}

function openViewModal(row) {
  clearViewError();
  viewIdInput.value = row.dataset.taskId;
  viewAuthor.textContent = row.dataset.author;
  viewDueDate.textContent = row.dataset.dueDate;
  viewDescription.textContent = row.dataset.description || "—";
  viewStatusSelect.value = row.dataset.statusId;
  taskViewModal.show();
}

async function saveViewStatus() {
  clearViewError();
  const taskId = viewIdInput.value;

  viewSaveBtn.disabled = true;
  try {
    const updated = await apiRequest(`${API_BASE}/${taskId}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status_id: parseInt(viewStatusSelect.value, 10) }),
    });
    const row = assignedBody.querySelector(`tr[data-task-id="${taskId}"]`);
    if (row) {
      row.dataset.statusId = updated.status_id;
      row.querySelector(".task-status-badge").textContent = updated.status_name;
    }
    taskViewModal.hide();
  } catch (error) {
    showViewError(error.message);
  } finally {
    viewSaveBtn.disabled = false;
  }
}

createBtn.addEventListener("click", openCreateModal);
modalSaveBtn.addEventListener("click", saveTask);
viewSaveBtn.addEventListener("click", saveViewStatus);

// Кнопка "Новая задача" видна только на вкладке "Выданные мной" — на "Выданные мне"
// создавать задачи от чужого имени нельзя (это делает автор, см. api/task.py:create_task).
authoredTabBtn.addEventListener("shown.bs.tab", () => createBtn.classList.remove("d-none"));
authoredTabBtn.addEventListener("hidden.bs.tab", () => createBtn.classList.add("d-none"));

authoredBody.addEventListener("click", (event) => {
  const row = event.target.closest("tr");
  if (!row) return;

  if (event.target.closest(".task-title-link")) {
    openEditModal(row);
  } else if (event.target.closest(".task-complete-btn")) {
    toggleComplete(row);
  } else if (event.target.closest(".task-delete-btn")) {
    deleteTask(row);
  }
});

assignedBody.addEventListener("click", (event) => {
  const row = event.target.closest("tr");
  if (!row) return;

  if (event.target.closest(".task-title-link")) {
    openViewModal(row);
  }
});
