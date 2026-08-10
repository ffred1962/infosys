/**
 * Страница /crm/events — глобальный список событий по ВСЕМ фирмам (аналог
 * /crm/firms/{id}/events, только без привязки к одной фирме — см.
 * js/firm_events.js). Просмотр, добавление и корректировка доступны прямо
 * здесь любому авторизованному пользователю; переиспользуются те же JSON API
 * /api/firm/{firm_id}/events[/{event_id}], что и на странице событий одной
 * фирмы — firm_id просто берётся из выбранной (при добавлении) или уже
 * известной по строке (при редактировании) фирмы, а не из URL страницы.
 */

const tableBody = document.getElementById("eventsBody");

if (tableBody) {
  const errorContainer = document.getElementById("eventsError");
  const newFirmSelect = document.getElementById("eventNewFirm");
  const newChannelSelect = document.getElementById("eventNewChannel");
  const newDescriptionInput = document.getElementById("eventNewDescription");
  const addBtn = document.getElementById("eventAddBtn");
  const firmsWithChannels = window.FIRMS_WITH_CHANNELS || [];

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
    return response.json();
  }

  function formatDate(isoString) {
    // created приходит от API как ISO-строка — приводим к тому же виду
    // "YYYY-MM-DD HH:MM", что и серверный strftime при первой отрисовке.
    const d = new Date(isoString);
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function findFirm(firmId) {
    return firmsWithChannels.find((f) => f.id === firmId);
  }

  // --- Каскадный выбор "фирма -> её канал" в форме добавления нового события ---

  function resetNewChannelSelect(message) {
    newChannelSelect.innerHTML = "";
    const option = document.createElement("option");
    option.value = "";
    option.textContent = message;
    newChannelSelect.appendChild(option);
    newChannelSelect.disabled = true;
  }

  if (newFirmSelect) {
    newFirmSelect.addEventListener("change", () => {
      const firmId = Number(newFirmSelect.value);
      if (!firmId) {
        resetNewChannelSelect("— сначала выберите фирму —");
        return;
      }
      const firm = findFirm(firmId);
      const channels = firm ? firm.channels : [];
      if (!channels.length) {
        resetNewChannelSelect("— у фирмы нет каналов связи —");
        return;
      }
      newChannelSelect.disabled = false;
      newChannelSelect.innerHTML = "";
      channels.forEach((ch) => {
        const option = document.createElement("option");
        option.value = ch.id;
        option.textContent = ch.label;
        newChannelSelect.appendChild(option);
      });
    });
  }

  // --- Таблица: строки существующих событий (просмотр + инлайн-редактирование) ---

  function buildRow(event) {
    // DOM API (не innerHTML с интерполяцией строки) — та же причина, что и в
    // остальных AJAX-таблицах проекта: описание/названия не должны
    // трактоваться как разметка.
    const row = document.createElement("tr");
    row.dataset.eventRowId = event.id;
    row.dataset.firmId = event.firm_id;

    const firmCell = document.createElement("td");
    firmCell.textContent = event.firm_name;

    const cityCell = document.createElement("td");
    cityCell.textContent = event.city_name;

    const channelCell = document.createElement("td");
    const channelSelect = document.createElement("select");
    channelSelect.className = "form-select form-select-sm event-channel-select";
    const firm = findFirm(event.firm_id);
    (firm ? firm.channels : []).forEach((ch) => {
      const option = document.createElement("option");
      option.value = ch.id;
      option.textContent = ch.label;
      if (ch.id === event.channel_id) option.selected = true;
      channelSelect.appendChild(option);
    });
    channelCell.appendChild(channelSelect);

    const dateCell = document.createElement("td");
    dateCell.textContent = formatDate(event.created);

    const authorCell = document.createElement("td");
    authorCell.textContent = event.author_fullname;

    const descriptionCell = document.createElement("td");
    const descriptionInput = document.createElement("input");
    descriptionInput.type = "text";
    descriptionInput.className = "form-control form-control-sm event-description-input";
    descriptionInput.value = event.description;
    descriptionInput.required = true;
    descriptionCell.appendChild(descriptionInput);

    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.className = "btn btn-sm btn-outline-primary event-save-btn";
    saveBtn.title = "Сохранить";
    saveBtn.setAttribute("aria-label", "Сохранить событие");
    saveBtn.innerHTML = '<i class="bi bi-check-lg"></i>';
    const actionsCell = document.createElement("td");
    actionsCell.className = "text-end";
    actionsCell.appendChild(saveBtn);

    row.append(firmCell, cityCell, channelCell, dateCell, authorCell, descriptionCell, actionsCell);
    return row;
  }

  async function saveRow(row) {
    clearError();
    const eventRowId = row.dataset.eventRowId;
    const firmId = row.dataset.firmId;
    const payload = {
      channel_id: Number(row.querySelector(".event-channel-select").value),
      description: row.querySelector(".event-description-input").value.trim(),
    };

    if (!payload.channel_id) {
      showError("Выберите канал связи.");
      return;
    }
    if (!payload.description) {
      showError("Описание не может быть пустым.");
      return;
    }

    // Фирма/город при редактировании не меняются (канал можно сменить только
    // в пределах той же фирмы — см. api/firm.py:edit_firm_event) и ответ API
    // их не содержит (FirmEventOut) — берём как есть из уже отрисованной строки.
    const firmName = row.children[0].textContent;
    const cityName = row.children[1].textContent;

    try {
      const updated = await apiRequest(`/api/firm/${firmId}/events/${eventRowId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const newRow = buildRow({
        ...updated,
        firm_id: Number(firmId),
        firm_name: firmName,
        city_name: cityName,
      });
      row.replaceWith(newRow);
    } catch (error) {
      showError(error.message);
    }
  }

  async function addEvent() {
    clearError();
    const firmId = Number(newFirmSelect.value);
    const payload = {
      channel_id: Number(newChannelSelect.value),
      description: newDescriptionInput.value.trim(),
    };

    if (!firmId) {
      showError("Выберите фирму.");
      return;
    }
    if (!payload.channel_id) {
      showError("Выберите канал связи.");
      return;
    }
    if (!payload.description) {
      showError("Описание не может быть пустым.");
      return;
    }

    try {
      await apiRequest(`/api/firm/${firmId}/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      // Новое событие всегда самое свежее — должно оказаться на первой странице
      // сортировки "новые сверху"; проще и надёжнее перезапросить страницу
      // целиком (как js/firm_events.js после добавления), чем пересчитывать
      // пагинацию на клиенте.
      window.location.reload();
    } catch (error) {
      showError(error.message);
    }
  }

  tableBody.addEventListener("click", (event) => {
    const row = event.target.closest("tr");
    if (!row) return;
    if (event.target.closest(".event-save-btn")) {
      saveRow(row);
    }
  });

  if (addBtn) {
    addBtn.addEventListener("click", addEvent);
  }
}
