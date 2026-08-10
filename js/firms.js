/**
 * Страница /crm/firms — карточка фирмы (клик по названию) и кнопка "+" для
 * ручного добавления. Одна и та же модалка используется для создания,
 * редактирования и просмотра (форма отключается, если data-can-edit="false").
 */

const firmModalEl = document.getElementById("firmModal");

if (firmModalEl) {
  const firmModal = new bootstrap.Modal(firmModalEl);
  const errorContainer = document.getElementById("firmsError");
  const modalErrorContainer = document.getElementById("firmModalError");
  const modalLabel = document.getElementById("firmModalLabel");
  const saveBtn = document.getElementById("firmModalSaveBtn");
  const pricesLink = document.getElementById("firmModalPricesLink");
  const commentsLink = document.getElementById("firmModalCommentsLink");
  const channelsLink = document.getElementById("firmModalChannelsLink");
  const eventsLink = document.getElementById("firmModalEventsLink");

  const idInput = document.getElementById("firmModalId");
  const creationDateEl = document.getElementById("firmModalCreationDate");
  const nameInput = document.getElementById("firmModalName");
  const citySelect = document.getElementById("firmModalCity");
  const typeSelect = document.getElementById("firmModalType");
  const phoneInput = document.getElementById("firmModalPhone");
  const websiteInput = document.getElementById("firmModalWebsite");
  const addressInput = document.getElementById("firmModalAddress");
  const sourceInput = document.getElementById("firmModalSource");
  const notesInput = document.getElementById("firmModalNotes");
  const ratingInput = document.getElementById("firmModalRating");

  const formFields = [nameInput, citySelect, typeSelect, phoneInput, websiteInput, addressInput, sourceInput, notesInput, ratingInput];

  function formatErrorDetail(detail) {
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
    }
    return detail || "Не удалось сохранить фирму.";
  }

  function clearPageError() {
    errorContainer.classList.add("d-none");
    errorContainer.textContent = "";
  }

  function showPageError(message) {
    errorContainer.textContent = message;
    errorContainer.classList.remove("d-none");
  }

  function clearModalError() {
    modalErrorContainer.classList.add("d-none");
    modalErrorContainer.textContent = "";
  }

  function showModalError(message) {
    modalErrorContainer.textContent = message;
    modalErrorContainer.classList.remove("d-none");
  }

  function setFieldsEnabled(enabled) {
    formFields.forEach((field) => {
      field.disabled = !enabled;
    });
    saveBtn.classList.toggle("d-none", !enabled);
  }

  function resetFields() {
    idInput.value = "";
    nameInput.value = "";
    citySelect.selectedIndex = 0;
    typeSelect.selectedIndex = 0;
    phoneInput.value = "";
    websiteInput.value = "";
    addressInput.value = "";
    sourceInput.value = "";
    notesInput.value = "";
    ratingInput.value = "5";
  }

  function openCreateModal() {
    clearModalError();
    resetFields();
    setFieldsEnabled(true);
    modalLabel.textContent = "Новая фирма";
    // Даты создания у ещё не сохранённой фирмы просто нет.
    creationDateEl.classList.add("d-none");
    pricesLink.classList.add("d-none");
    commentsLink.classList.add("d-none");
    channelsLink.classList.add("d-none");
    eventsLink.classList.add("d-none");
    firmModal.show();
  }

  function openCardModal(link) {
    clearModalError();
    idInput.value = link.dataset.id;
    nameInput.value = link.dataset.name;
    citySelect.value = link.dataset.cityId;
    typeSelect.value = link.dataset.typeId;
    phoneInput.value = link.dataset.phone;
    websiteInput.value = link.dataset.website;
    addressInput.value = link.dataset.address;
    sourceInput.value = link.dataset.source;
    notesInput.value = link.dataset.notes;
    ratingInput.value = link.dataset.rating;
    // Только для чтения — не форм-поле, никогда не входит в payload сохранения.
    creationDateEl.textContent = `Добавлена: ${link.dataset.creationDate}`;
    creationDateEl.classList.remove("d-none");

    const canEdit = link.dataset.canEdit === "true";
    setFieldsEnabled(canEdit);
    modalLabel.textContent = canEdit ? "Фирма" : "Просмотр фирмы";
    const returnTo = window.location.pathname + window.location.search;
    pricesLink.href = `/crm/firms/${link.dataset.id}/prices?return_to=${encodeURIComponent(returnTo)}`;
    pricesLink.classList.remove("d-none");
    commentsLink.href = `/crm/firms/${link.dataset.id}/comments?return_to=${encodeURIComponent(returnTo)}`;
    commentsLink.classList.remove("d-none");
    channelsLink.href = `/crm/firms/${link.dataset.id}/channels?return_to=${encodeURIComponent(returnTo)}`;
    channelsLink.classList.remove("d-none");
    eventsLink.href = `/crm/firms/${link.dataset.id}/events?return_to=${encodeURIComponent(returnTo)}`;
    eventsLink.classList.remove("d-none");
    firmModal.show();
  }

  document.getElementById("firmCreateBtn").addEventListener("click", openCreateModal);

  document.querySelectorAll(".firm-name-link").forEach((link) => {
    link.addEventListener("click", () => openCardModal(link));
  });

  // Возврат со страницы прайсов (/crm/firms/{id}/prices) — переоткрываем карточку
  // той же фирмы, если она есть на текущей странице/фильтре списка.
  const openFirmId = new URLSearchParams(window.location.search).get("open_firm_id");
  if (openFirmId) {
    const link = document.querySelector(`.firm-name-link[data-id="${openFirmId}"]`);
    // Сначала убираем open_firm_id из адресной строки — иначе openCardModal()
    // ниже посчитает его частью "текущей страницы" и зашьёт в return_to
    // ссылки "Прайсы", и он задвоится при повторном заходе на прайсы.
    const url = new URL(window.location.href);
    url.searchParams.delete("open_firm_id");
    window.history.replaceState({}, "", url);
    if (link) {
      openCardModal(link);
    }
  }

  saveBtn.addEventListener("click", async () => {
    clearModalError();
    clearPageError();

    const name = nameInput.value.trim();
    if (!name) {
      showModalError("Название не может быть пустым.");
      return;
    }
    if (!citySelect.value || !typeSelect.value) {
      showModalError("Выберите город и тип фирмы.");
      return;
    }
    const rating = Number(ratingInput.value);
    if (!Number.isInteger(rating) || rating < 0 || rating > 10) {
      showModalError("Рейтинг должен быть целым числом от 0 до 10.");
      return;
    }

    const payload = {
      city_id: Number(citySelect.value),
      type_id: Number(typeSelect.value),
      name,
      phone: phoneInput.value.trim() || null,
      website: websiteInput.value.trim() || null,
      address: addressInput.value.trim() || null,
      source: sourceInput.value.trim() || null,
      notes: notesInput.value.trim() || null,
      rating,
    };

    const firmId = idInput.value;
    const url = firmId ? `/api/firm/${firmId}` : "/api/firm";
    const method = firmId ? "PATCH" : "POST";

    saveBtn.disabled = true;
    try {
      const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
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

      // Изменение city_id/type_id могло вывести фирму за рамки текущего
      // фильтра/страницы — проще и надёжнее перезапросить страницу целиком,
      // чем пересчитывать пагинацию на клиенте.
      window.location.reload();
    } catch (error) {
      showModalError(error.message);
    } finally {
      saveBtn.disabled = false;
    }
  });
}
