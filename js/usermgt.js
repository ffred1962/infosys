/**
 * /admin/usermgt — карточка пользователя (клик по email) в общей модалке.
 * Контент каждой карточки заранее отрисован сервером в <template id="user-card-{id}">
 * (см. templates/admin/usermgt.html) — JS только клонирует нужный шаблон в модалку,
 * без innerHTML/строковой интерполяции пользовательских данных.
 */

const userCardModalEl = document.getElementById("userCardModal");

if (userCardModalEl) {
  const userCardModal = new bootstrap.Modal(userCardModalEl);
  const modalBody = document.getElementById("userCardModalBody");
  const modalLabel = document.getElementById("userCardModalLabel");

  function wirePasswordToggle(root) {
    const btn = root.querySelector(".user-toggle-password-btn");
    const section = root.querySelector(".user-password-section");
    if (btn && section) {
      btn.addEventListener("click", () => section.classList.toggle("d-none"));
    }
  }

  function openUserModal(userId, email, errorMessage) {
    const template = document.getElementById(`user-card-${userId}`);
    if (!template) {
      return;
    }
    modalBody.textContent = "";
    const clone = template.content.cloneNode(true);
    if (errorMessage) {
      const errorEl = clone.querySelector(".user-card-error");
      if (errorEl) {
        errorEl.textContent = errorMessage;
        errorEl.classList.remove("d-none");
      }
    }
    modalBody.appendChild(clone);
    wirePasswordToggle(modalBody);
    modalLabel.textContent = email || "Пользователь";
    userCardModal.show();
  }

  document.querySelectorAll(".user-email-link").forEach((link) => {
    link.addEventListener("click", () => openUserModal(link.dataset.userId, link.dataset.email, null));
  });

  // Возврат после редактирования/смены пароля/ролей — переоткрываем карточку того
  // же пользователя (см. views/admin/usermgt.py:_redirect_to_user), при ошибке
  // валидации показываем её прямо в карточке.
  if (window.OPEN_USER_ID) {
    const link = document.querySelector(`.user-email-link[data-user-id="${window.OPEN_USER_ID}"]`);
    if (link) {
      openUserModal(window.OPEN_USER_ID, link.dataset.email, window.OPEN_USER_ERROR);
    }
    const url = new URL(window.location.href);
    url.searchParams.delete("open_user_id");
    url.searchParams.delete("user_error");
    window.history.replaceState({}, "", url);
  }
}
