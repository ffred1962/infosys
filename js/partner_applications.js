/**
 * /admin/partner_applications — просмотр анкеты (клик по компании/имени) в
 * общей модалке. Контент каждой анкеты заранее отрисован сервером в
 * <template id="application-card-{id}"> (см. templates/admin/partner_applications.html)
 * — JS только клонирует нужный шаблон в модалку, без innerHTML/строковой
 * интерполяции пользовательских данных (та же техника, что и js/usermgt.js).
 * Только просмотр — редактирования здесь нет.
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
}
