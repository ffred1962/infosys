/**
 * Страница /crm/firms/{id}/comments — форма "Добавить" отправляет
 * POST /api/firm/{id}/comments, после успеха страница перезагружается (тот же
 * приём, что и "Скачать прайс" на /crm/firms/{id}/prices, см. js/firm_prices.js) —
 * список уже отсортирован сервером по added desc, перезагрузка проще и надёжнее
 * ручного построения новой строки на клиенте.
 */

const commentForm = document.getElementById("firmCommentForm");

if (commentForm) {
  const errorContainer = document.getElementById("firmCommentError");
  const textInput = document.getElementById("firmCommentText");
  const submitBtn = document.getElementById("firmCommentSubmitBtn");

  function formatErrorDetail(detail) {
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
    }
    return detail || "Не удалось добавить примечание.";
  }

  function showError(message) {
    errorContainer.textContent = message;
    errorContainer.classList.remove("d-none");
  }

  function clearError() {
    errorContainer.classList.add("d-none");
    errorContainer.textContent = "";
  }

  commentForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearError();

    const comment = textInput.value.trim();
    if (!comment) {
      showError("Примечание не может быть пустым.");
      return;
    }

    const firmId = commentForm.dataset.firmId;
    submitBtn.disabled = true;
    try {
      const response = await fetch(`/api/firm/${firmId}/comments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ comment }),
      });

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

      window.location.reload();
    } catch (error) {
      showError(error.message);
      submitBtn.disabled = false;
    }
  });
}
