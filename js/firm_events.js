/**
 * Страница /crm/firms/{id}/events — таблица событий по каналам связи фирмы,
 * постранично (обычная серверная пагинация через ?page=, как /admin/login_info),
 * с инлайн-редактированием строк через JSON API /api/firm/{id}/events/{event_id}
 * (без перезагрузки страницы — как js/firm_channels.js). Доступно любому
 * авторизованному пользователю, без ограничения владельцем/админом фирмы.
 * Удаления нет — только просмотр, добавление и корректировка.
 */

const tableBody = document.getElementById("firmEventBody");

if (tableBody) {
  const firmId = tableBody.dataset.firmId;
  const API_BASE = `/api/firm/${firmId}/events`;
  const errorContainer = document.getElementById("firmEventError");
  const newChannelSelect = document.getElementById("firmEventNewChannel");
  const newDescriptionInput = document.getElementById("firmEventNewDescription");
  const addBtn = document.getElementById("firmEventAddBtn");
  const firmChannels = window.FIRM_CHANNELS || [];

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

  function buildRow(event) {
    // DOM API (не innerHTML с интерполяцией строки) — та же причина, что и в
    // firm_channels.js/firms.js: описание не должно трактоваться как разметка.
    const row = document.createElement("tr");
    row.dataset.eventRowId = event.id;

    const channelCell = document.createElement("td");
    const channelSelect = document.createElement("select");
    channelSelect.className = "form-select form-select-sm firm-event-channel-select";
    firmChannels.forEach((ch) => {
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
    descriptionInput.className = "form-control form-control-sm firm-event-description-input";
    descriptionInput.value = event.description;
    descriptionInput.required = true;
    descriptionCell.appendChild(descriptionInput);

    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.className = "btn btn-sm btn-outline-primary firm-event-save-btn";
    saveBtn.title = "Сохранить";
    saveBtn.setAttribute("aria-label", "Сохранить событие");
    saveBtn.innerHTML = '<i class="bi bi-check-lg"></i>';
    const actionsCell = document.createElement("td");
    actionsCell.className = "text-end";
    actionsCell.appendChild(saveBtn);

    row.append(channelCell, dateCell, authorCell, descriptionCell, actionsCell);
    return row;
  }

  async function saveRow(row) {
    clearError();
    const eventRowId = row.dataset.eventRowId;
    const payload = {
      channel_id: Number(row.querySelector(".firm-event-channel-select").value),
      description: row.querySelector(".firm-event-description-input").value.trim(),
    };

    if (!payload.description) {
      showError("Описание не может быть пустым.");
      return;
    }

    try {
      const updated = await apiRequest(`${API_BASE}/${eventRowId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      row.replaceWith(buildRow(updated));
    } catch (error) {
      showError(error.message);
    }
  }

  async function addEvent() {
    clearError();
    const payload = {
      channel_id: Number(newChannelSelect.value),
      description: newDescriptionInput.value.trim(),
    };

    if (!payload.channel_id) {
      showError("Выберите канал связи.");
      return;
    }
    if (!payload.description) {
      showError("Описание не может быть пустым.");
      return;
    }

    try {
      await apiRequest(API_BASE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      // Новое событие всегда самое свежее — должно оказаться на первой странице
      // сортировки "новые сверху"; проще и надёжнее перезапросить страницу
      // целиком (как js/firm_comments.js после добавления), чем пересчитывать
      // пагинацию на клиенте.
      window.location.reload();
    } catch (error) {
      showError(error.message);
    }
  }

  tableBody.addEventListener("click", (event) => {
    const row = event.target.closest("tr");
    if (!row) return;
    if (event.target.closest(".firm-event-save-btn")) {
      saveRow(row);
    }
  });

  if (addBtn) {
    addBtn.addEventListener("click", addEvent);
  }
}
