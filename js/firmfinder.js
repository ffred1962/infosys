/**
 * Страница /crm/firm_finder — кнопка ПОИСК запускает POST /api/firm/search
 * (реальный веб-поиск на стороне Claude API) и рисует найденные фирмы в таблице.
 */

const firmFinderForm = document.getElementById("firmFinderForm");

if (firmFinderForm) {
  const citySelect = document.getElementById("firmFinderCity");
  const firmTypeSelect = document.getElementById("firmFinderFirmType");
  const searchBtn = document.getElementById("firmFinderSearchBtn");
  const errorContainer = document.getElementById("firmFinderError");
  const resultsSection = document.getElementById("firmFinderResults");
  const resultsBody = document.getElementById("firmFinderResultsBody");
  const resultsEmpty = document.getElementById("firmFinderResultsEmpty");

  function formatErrorDetail(detail) {
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
    }
    return detail || "Не удалось выполнить поиск.";
  }

  function showError(message) {
    errorContainer.textContent = message;
    errorContainer.classList.remove("d-none");
  }

  function clearError() {
    errorContainer.classList.add("d-none");
    errorContainer.textContent = "";
  }

  function buildResultRow(firm) {
    const tr = document.createElement("tr");

    const nameTd = document.createElement("td");
    nameTd.textContent = firm.name;
    tr.appendChild(nameTd);

    const phoneTd = document.createElement("td");
    phoneTd.textContent = firm.phone || "—";
    tr.appendChild(phoneTd);

    const websiteTd = document.createElement("td");
    if (firm.website && /^https?:\/\//i.test(firm.website)) {
      // Схема проверяется явно: firm.website приходит из ответа Claude API
      // (не наш контролируемый ввод), нельзя присваивать href без проверки —
      // иначе возможна ссылка вида javascript:...
      const link = document.createElement("a");
      link.href = firm.website;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = firm.website;
      websiteTd.appendChild(link);
    } else {
      websiteTd.textContent = firm.website || "—";
    }
    tr.appendChild(websiteTd);

    const addressTd = document.createElement("td");
    addressTd.textContent = firm.address || "—";
    tr.appendChild(addressTd);

    const sourceTd = document.createElement("td");
    sourceTd.textContent = firm.source || "—";
    tr.appendChild(sourceTd);

    const notesTd = document.createElement("td");
    notesTd.textContent = firm.notes || "—";
    tr.appendChild(notesTd);

    return tr;
  }

  searchBtn.addEventListener("click", async () => {
    clearError();
    resultsSection.classList.add("d-none");
    resultsBody.replaceChildren();

    const cityId = citySelect.value;
    const typeId = firmTypeSelect.value;
    if (!cityId || !typeId) {
      showError("Выберите город и тип фирмы.");
      return;
    }

    const originalLabel = searchBtn.innerHTML;
    searchBtn.disabled = true;
    searchBtn.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> Идёт поиск...';

    try {
      const response = await fetch("/api/firm/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ city_id: Number(cityId), type_id: Number(typeId) }),
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

      const firms = await response.json();
      resultsSection.classList.remove("d-none");
      if (firms.length === 0) {
        resultsEmpty.classList.remove("d-none");
      } else {
        resultsEmpty.classList.add("d-none");
        firms.forEach((firm) => resultsBody.appendChild(buildResultRow(firm)));
      }
    } catch (error) {
      showError(error.message);
    } finally {
      searchBtn.disabled = false;
      searchBtn.innerHTML = originalLabel;
    }
  });
}
