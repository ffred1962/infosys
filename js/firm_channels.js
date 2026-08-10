/**
 * Страница /crm/firms/{id}/channels — как /admin/channeltype, инлайн-редактирование
 * прямо в таблице через JSON API /api/firm/{id}/channels/... (без перезагрузки
 * страницы). Только рендерится, если у текущего пользователя есть право
 * редактировать эту фирму (can_edit) — иначе tbody не несёт data-can-edit="true"
 * и большинство обработчиков ниже просто не находят своих элементов управления.
 */

const tableBody = document.getElementById("firmChannelBody");

if (tableBody && tableBody.dataset.canEdit === "true") {
  const firmId = tableBody.dataset.firmId;
  const API_BASE = `/api/firm/${firmId}/channels`;
  const errorContainer = document.getElementById("firmChannelError");
  const newTypeSelect = document.getElementById("firmChannelNewType");
  const newAddressInput = document.getElementById("firmChannelNewAddress");
  const newDescriptionInput = document.getElementById("firmChannelNewDescription");
  const addBtn = document.getElementById("firmChannelAddBtn");

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

  function formatDate(isoString) {
    // date_added приходит от API как ISO-строка — приводим к тому же виду
    // "YYYY-MM-DD HH:MM", что и серверный strftime при первой отрисовке.
    const d = new Date(isoString);
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function buildRow(channel) {
    // DOM API (не innerHTML с интерполяцией строки) — та же причина, что и
    // в channel_type.js/firms.js: адрес/описание не должны трактоваться как разметка.
    const row = document.createElement("tr");
    row.dataset.channelRowId = channel.id;
    // Тип канала больше не редактируется инлайн в таблице (задаётся только при
    // создании) — сохраняем его здесь просто чтобы отправить неизменным
    // обратно в payload при сохранении адреса/описания (API требует channel_id
    // в теле запроса даже когда он не меняется).
    row.dataset.channelTypeId = channel.channel_id;

    const iconCell = document.createElement("td");
    const iconImg = document.createElement("img");
    iconImg.width = 24;
    iconImg.height = 24;
    iconImg.alt = channel.channel_name;
    iconImg.title = channel.channel_name;
    iconImg.src = channel.icon_url;
    iconCell.appendChild(iconImg);

    const addressCell = document.createElement("td");
    const addressInput = document.createElement("input");
    addressInput.type = "text";
    addressInput.className = "form-control form-control-sm firm-channel-address-input";
    addressInput.value = channel.address;
    addressInput.required = true;
    addressCell.appendChild(addressInput);

    const descriptionCell = document.createElement("td");
    const descriptionInput = document.createElement("input");
    descriptionInput.type = "text";
    descriptionInput.className = "form-control form-control-sm firm-channel-description-input";
    descriptionInput.value = channel.description || "";
    descriptionCell.appendChild(descriptionInput);

    const dateCell = document.createElement("td");
    dateCell.textContent = formatDate(channel.date_added);

    const saveBtn = document.createElement("button");
    saveBtn.type = "button";
    saveBtn.className = "btn btn-sm btn-outline-primary firm-channel-save-btn";
    saveBtn.title = "Сохранить";
    saveBtn.setAttribute("aria-label", "Сохранить канал связи");
    saveBtn.innerHTML = '<i class="bi bi-check-lg"></i>';

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "btn btn-sm btn-outline-danger firm-channel-delete-btn";
    deleteBtn.title = "Удалить";
    deleteBtn.setAttribute("aria-label", "Удалить канал связи");
    deleteBtn.innerHTML = '<i class="bi bi-trash"></i>';

    const actionsWrapper = document.createElement("div");
    actionsWrapper.className = "d-flex gap-1 justify-content-end";
    actionsWrapper.append(saveBtn, deleteBtn);
    const actionsCell = document.createElement("td");
    actionsCell.className = "text-end";
    actionsCell.appendChild(actionsWrapper);

    row.append(iconCell, addressCell, descriptionCell, dateCell, actionsCell);
    return row;
  }

  function readPayloadFromRow(row) {
    return {
      // Тип канала больше не редактируется инлайн — берём как есть из dataset
      // (проставлен при первой отрисовке строки, см. buildRow()/шаблон).
      channel_id: Number(row.dataset.channelTypeId),
      address: row.querySelector(".firm-channel-address-input").value.trim(),
      description: row.querySelector(".firm-channel-description-input").value.trim() || null,
    };
  }

  async function saveRow(row) {
    clearError();
    const channelRowId = row.dataset.channelRowId;
    const payload = readPayloadFromRow(row);

    if (!payload.address) {
      showError("Адрес не может быть пустым.");
      return;
    }

    try {
      const updated = await apiRequest(`${API_BASE}/${channelRowId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const newRow = buildRow(updated);
      row.replaceWith(newRow);
    } catch (error) {
      showError(error.message);
    }
  }

  async function deleteRow(row) {
    clearError();
    const channelRowId = row.dataset.channelRowId;

    try {
      await apiRequest(`${API_BASE}/${channelRowId}`, { method: "DELETE" });
      row.remove();
    } catch (error) {
      showError(error.message);
    }
  }

  async function addChannel() {
    clearError();
    const payload = {
      channel_id: Number(newTypeSelect.value),
      address: newAddressInput.value.trim(),
      description: newDescriptionInput.value.trim() || null,
    };

    if (!payload.channel_id) {
      showError("Выберите тип канала.");
      return;
    }
    if (!payload.address) {
      showError("Адрес не может быть пустым.");
      return;
    }

    try {
      const created = await apiRequest(API_BASE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      tableBody.appendChild(buildRow(created));
      newAddressInput.value = "";
      newDescriptionInput.value = "";
    } catch (error) {
      showError(error.message);
    }
  }

  tableBody.addEventListener("click", (event) => {
    const row = event.target.closest("tr");
    if (!row) return;

    if (event.target.closest(".firm-channel-save-btn")) {
      saveRow(row);
    } else if (event.target.closest(".firm-channel-delete-btn")) {
      deleteRow(row);
    }
  });

  if (addBtn) {
    addBtn.addEventListener("click", addChannel);
  }
}
