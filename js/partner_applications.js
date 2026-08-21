/**
 * /admin/partner_applications — просмотр анкеты (клик по компании/имени) в
 * общей модалке. Контент каждой анкеты заранее отрисован сервером в
 * <template id="application-card-{id}"> (см. templates/admin/partner_applications.html)
 * — JS только клонирует нужный шаблон в модалку, без innerHTML/строковой
 * интерполяции пользовательских данных (та же техника, что и js/usermgt.js).
 * Просмотр read-only, кроме одного действия — блока "Проверка" (статус +
 * заметки + кнопка "Сохранить" внутри самого шаблона, одним PATCH-запросом).
 */

const applicationModalEl = document.getElementById("applicationModal");

if (applicationModalEl) {
  const applicationModal = new bootstrap.Modal(applicationModalEl);
  const modalBody = document.getElementById("applicationModalBody");

  document.querySelectorAll(".application-link").forEach((link) => {
    link.addEventListener("click", () => {
      const template = document.getElementById(`application-card-${link.dataset.appId}`);
      if (!template) {
        return;
      }
      modalBody.textContent = "";
      modalBody.appendChild(template.content.cloneNode(true));
      applicationModal.show();
    });
  });

  // Делегирование клика на modalBody — кнопка появляется в DOM только после
  // клонирования шаблона выше, обычный addEventListener на неё в момент
  // загрузки страницы ничего бы не поймал.
  modalBody.addEventListener("click", (event) => {
    const btn = event.target.closest(".application-status-save");
    if (!btn) {
      return;
    }
    const select = modalBody.querySelector(".application-status-select");
    const notes = modalBody.querySelector(".application-notes");
    const errorEl = modalBody.querySelector(".application-status-error");
    const appId = btn.dataset.appId;
    errorEl.textContent = "";
    btn.disabled = true;

    fetch(`/api/admin/partner_applications/${appId}/review`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status_id: Number(select.value), verification_notes: notes.value }),
    })
      .then((res) => {
        if (!res.ok) {
          return res.json().then((data) => {
            throw new Error(data.detail || "Не удалось сохранить статус.");
          });
        }
        // Таблица в фоне тоже показывает статус — проще перезагрузить
        // страницу (та же логика, что и у "Скачать прайс"/firm_comments),
        // чем дублировать обновление и модалки, и строки таблицы вручную.
        window.location.reload();
      })
      .catch((err) => {
        btn.disabled = false;
        errorEl.textContent = err.message;
      });
  });
}
