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
  // Текст ошибки из ответа сервера: FastAPI отдаёт detail строкой (наши
  // HTTPException) или массивом объектов (422 валидации Pydantic), а прокси/
  // туннель на долгом запросе может вернуть вообще не JSON (HTML-страницу 504) —
  // в этом случае сервер при этом мог всё же дойти до конца и сохранить отчёт.
  async function readError(res, fallback) {
    let data = null;
    try {
      data = await res.json();
    } catch (e) {
      return `Ошибка ${res.status}. Если запрос шёл долго, анализ мог всё же завершиться на сервере — обновите страницу и откройте анкету заново.`;
    }
    const detail = data && data.detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg || JSON.stringify(item)).join("; ") || fallback;
    }
    return detail || fallback;
  }

  // Кнопка "Анализировать": POST /api/admin/partner_applications/{id}/analyze,
  // отчёт дописывается сервером в "Заметки проверки" и сразу сохраняется —
  // страницу не перезагружаем, просто подставляем новое значение в textarea
  // (статус/таблица от анализа не меняются). Текущее содержимое textarea уходит
  // на сервер вместе с запросом, чтобы не затереть несохранённые правки админа.
  modalBody.addEventListener("click", (event) => {
    const analyzeBtn = event.target.closest(".application-analyze");
    if (!analyzeBtn) {
      return;
    }
    const notes = modalBody.querySelector(".application-notes");
    const errorEl = modalBody.querySelector(".application-status-error");
    const saveBtn = modalBody.querySelector(".application-status-save");
    const statusSelect = modalBody.querySelector(".application-status-select");
    const originalLabel = analyzeBtn.innerHTML;
    errorEl.textContent = "";
    // Пока идёт анализ (минуты), карточку блокируем целиком: иначе набранное
    // в поле заметок после клика было бы затёрто ответом, а "Сохранить" с
    // перезагрузкой страницы оборвал бы ожидание результата.
    const lockable = [analyzeBtn, saveBtn, notes, statusSelect];
    lockable.forEach((el) => el && (el.disabled = true));
    analyzeBtn.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> Анализируем...';

    fetch(`/api/admin/partner_applications/${analyzeBtn.dataset.appId}/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        verification_notes: notes.value,
        last_changed_seen: analyzeBtn.dataset.lastChanged || null,
      }),
    })
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(await readError(res, "Не удалось выполнить анализ."));
        }
        return res.json();
      })
      .then((data) => {
        notes.value = data.verification_notes;
        notes.scrollTop = notes.scrollHeight;
        analyzeBtn.dataset.lastChanged = data.last_changed;
        // Карточка клонируется из серверного <template> при каждом открытии, а
        // он отрисован один раз при загрузке страницы — без этого повторное
        // открытие этой же анкеты показало бы заметки ДО анализа, и "Сохранить"
        // (или повторный анализ) затёрли бы уже записанный отчёт.
        const template = document.getElementById(`application-card-${analyzeBtn.dataset.appId}`);
        if (template) {
          const tplNotes = template.content.querySelector(".application-notes");
          if (tplNotes) {
            tplNotes.value = data.verification_notes;
            tplNotes.textContent = data.verification_notes;
          }
          const tplBtn = template.content.querySelector(".application-analyze");
          if (tplBtn) {
            tplBtn.dataset.lastChanged = data.last_changed;
          }
        }
      })
      .catch((err) => {
        // pre-wrap: при отказе сохранить сервер возвращает в тексте ошибки
        // сам (уже оплаченный) отчёт — его нужно видеть с переносами строк.
        errorEl.style.whiteSpace = "pre-wrap";
        errorEl.textContent = err.message;
      })
      .finally(() => {
        lockable.forEach((el) => el && (el.disabled = false));
        analyzeBtn.innerHTML = originalLabel;
      });
  });

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
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(await readError(res, "Не удалось сохранить статус."));
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
