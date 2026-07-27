/**
 * Страница /crm/firms/{id}/prices — кнопка "Скачать прайс" запускает
 * POST /api/firm/{id}/download_price (ИИ-агент заходит на сайт фирмы и
 * скачивает актуальные цены на двери). Запрос реально может идти несколько
 * минут (веб-поиск на стороне Claude API), поэтому кнопка на время запроса
 * отключается и показывает спиннер — тот же паттерн, что и js/firmfinder.js.
 */

const downloadBtn = document.getElementById("firmPriceDownloadBtn");

if (downloadBtn) {
  const errorContainer = document.getElementById("firmPriceDownloadError");
  const successContainer = document.getElementById("firmPriceDownloadSuccess");

  function formatErrorDetail(detail) {
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
    }
    return detail || "Не удалось скачать прайс.";
  }

  function showError(message) {
    errorContainer.textContent = message;
    errorContainer.classList.remove("d-none");
  }

  function clearMessages() {
    errorContainer.classList.add("d-none");
    errorContainer.textContent = "";
    successContainer.classList.add("d-none");
    successContainer.textContent = "";
  }

  downloadBtn.addEventListener("click", async () => {
    clearMessages();

    const firmId = downloadBtn.dataset.firmId;
    const originalLabel = downloadBtn.innerHTML;
    downloadBtn.disabled = true;
    downloadBtn.innerHTML =
      '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> Скачивание прайса...';

    try {
      const response = await fetch(`/api/firm/${firmId}/download_price`, {
        method: "POST",
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

      const result = await response.json();
      successContainer.textContent = `Прайс скачан: ${result.item_count} товар(ов). Обновляем список...`;
      successContainer.classList.remove("d-none");
      window.location.reload();
    } catch (error) {
      showError(error.message);
      downloadBtn.disabled = false;
      downloadBtn.innerHTML = originalLabel;
    }
  });
}
