/**
 * Управление списком баг-репортов на /admin/bugs через JSON API /api/admin/bug.
 */

const API_BASE = "/api/admin/bug";

const tableBody = document.getElementById("bugsBody");
const errorContainer = document.getElementById("bugsError");

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

async function toggleBug(row) {
  clearError();
  const bugId = row.dataset.bugId;

  try {
    const updated = await apiRequest(`${API_BASE}/${bugId}/toggle-open`, { method: "PATCH" });
    const badge = row.querySelector(".bug-status-badge");
    badge.textContent = updated.isopen ? "Открыт" : "Закрыт";
    badge.classList.toggle("text-bg-warning", updated.isopen);
    badge.classList.toggle("text-bg-success", !updated.isopen);
  } catch (error) {
    showError(error.message);
  }
}

async function deleteBug(row) {
  clearError();
  const bugId = row.dataset.bugId;

  try {
    await apiRequest(`${API_BASE}/${bugId}`, { method: "DELETE" });
    row.remove();
  } catch (error) {
    showError(error.message);
  }
}

tableBody.addEventListener("click", (event) => {
  const row = event.target.closest("tr");
  if (!row) return;

  if (event.target.closest(".bug-toggle-btn")) {
    toggleBug(row);
  } else if (event.target.closest(".bug-delete-btn")) {
    deleteBug(row);
  }
});
