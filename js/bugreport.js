/**
 * Модальное окно баг-репорта (иконка "жучок" в шапке) — POST на /api/bug.
 * Модалка отсутствует в DOM на страницах login/setup (topbar там скрыт),
 * поэтому все обращения к элементам ниже защищены проверкой на null.
 */

const bugModalEl = document.getElementById("bugReportModal");

if (bugModalEl) {
  const bugDescriptionInput = document.getElementById("bugReportDescription");
  const bugSaveBtn = document.getElementById("bugReportSaveBtn");
  const bugErrorContainer = document.getElementById("bugReportError");
  const bugSuccessContainer = document.getElementById("bugReportSuccess");
  const bugModal = new bootstrap.Modal(bugModalEl);

  function clearBugMessages() {
    bugErrorContainer.classList.add("d-none");
    bugErrorContainer.textContent = "";
    bugSuccessContainer.classList.add("d-none");
    bugSuccessContainer.textContent = "";
  }

  function showBugError(message) {
    bugSuccessContainer.classList.add("d-none");
    bugErrorContainer.textContent = message;
    bugErrorContainer.classList.remove("d-none");
  }

  bugModalEl.addEventListener("show.bs.modal", () => {
    clearBugMessages();
    bugDescriptionInput.value = "";
  });

  bugSaveBtn.addEventListener("click", async () => {
    clearBugMessages();
    const title = bugDescriptionInput.value.trim();

    if (!title) {
      showBugError("Опишите ошибку перед сохранением.");
      return;
    }

    bugSaveBtn.disabled = true;
    try {
      const response = await fetch("/api/bug", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title }),
      });

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

      bugSuccessContainer.textContent = "Спасибо! Баг-репорт отправлен.";
      bugSuccessContainer.classList.remove("d-none");
      bugDescriptionInput.value = "";
      setTimeout(() => bugModal.hide(), 1200);
    } catch (error) {
      showBugError(error.message);
    } finally {
      bugSaveBtn.disabled = false;
    }
  });
}
