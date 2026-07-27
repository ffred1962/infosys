/**
 * Управление списком уведомлений на /admin/notifications через JSON API /api/admin/notification.
 */

const API_BASE = "/api/admin/notification";

const tableBody = document.getElementById("notificationsBody");
const errorContainer = document.getElementById("notificationsError");

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

async function toggleNotification(row) {
  clearError();
  const notificationId = row.dataset.notificationId;

  try {
    const updated = await apiRequest(`${API_BASE}/${notificationId}/toggle-viewed`, {
      method: "PATCH",
    });
    const badge = row.querySelector(".notification-status-badge");
    badge.textContent = updated.viewed ? "Да" : "Нет";
    badge.classList.toggle("text-bg-secondary", updated.viewed);
    badge.classList.toggle("text-bg-primary", !updated.viewed);
  } catch (error) {
    showError(error.message);
  }
}

async function deleteNotification(row) {
  clearError();
  const notificationId = row.dataset.notificationId;

  try {
    await apiRequest(`${API_BASE}/${notificationId}`, { method: "DELETE" });
    row.remove();
  } catch (error) {
    showError(error.message);
  }
}

tableBody.addEventListener("click", (event) => {
  const row = event.target.closest("tr");
  if (!row) return;

  if (event.target.closest(".notification-toggle-btn")) {
    toggleNotification(row);
  } else if (event.target.closest(".notification-delete-btn")) {
    deleteNotification(row);
  }
});
