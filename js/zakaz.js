/**
 * /crm/zakaz — клик по названию фирмы в строке заказа открывает read-only
 * карточку анкеты контрагента в общей модалке. Контент каждой (уникальной)
 * анкеты заранее отрисован сервером в <template id="zakaz-anketa-card-{id}">
 * (см. templates/crm/zakaz.html) — JS только клонирует нужный шаблон в
 * модалку, без innerHTML/строковой интерполяции пользовательских данных (та
 * же техника, что и js/partner_applications.js).
 */

const zakazAnketaModalEl = document.getElementById("zakazAnketaModal");

if (zakazAnketaModalEl) {
  const zakazAnketaModal = new bootstrap.Modal(zakazAnketaModalEl);
  const modalBody = document.getElementById("zakazAnketaModalBody");

  document.querySelectorAll(".zakaz-anketa-link").forEach((link) => {
    link.addEventListener("click", () => {
      const template = document.getElementById(`zakaz-anketa-card-${link.dataset.anketaId}`);
      if (!template) {
        return;
      }
      modalBody.textContent = "";
      modalBody.appendChild(template.content.cloneNode(true));
      zakazAnketaModal.show();
    });
  });
}

/**
 * Кнопка "Анализ" — GET /api/zakaz/analysis с ТЕМИ ЖЕ параметрами фильтра,
 * что уже стоят в адресной строке текущей страницы (без page — анализ не
 * пагинируется, смотрит на всю отфильтрованную выборку целиком), рендерит
 * найденные аномалии в модалку. Контент строится через createElement/
 * textContent, никогда innerHTML — firm_name/delivery_addr приходят из БД
 * (в т.ч. из анкет, заполненных сторонними людьми), это не доверенный ввод.
 */
const zakazAnalysisBtn = document.getElementById("zakazAnalysisBtn");

if (zakazAnalysisBtn) {
  const analysisModalEl = document.getElementById("zakazAnalysisModal");
  const analysisModal = new bootstrap.Modal(analysisModalEl);
  const errorBox = document.getElementById("zakazAnalysisError");
  const content = document.getElementById("zakazAnalysisContent");

  function currentFilterQuery() {
    const params = new URLSearchParams(window.location.search);
    params.delete("page");
    return params.toString();
  }

  // showFirm=false для категорий, сгруппированных по фирме (group_by="firm")
  // — имя фирмы уже стоит заголовком группы, повторять его в каждой строке
  // избыточно. showFirm=true только для group_by="address" (категория
  // "Один адрес — разные фирмы"), где само название фирмы в каждой строке —
  // и есть суть аномалии.
  function buildOrdersTable(orders, showFirm) {
    const table = document.createElement("table");
    table.className = "table table-sm table-bordered mb-0";

    const columns = showFirm
      ? ["№ заказа", "Дата", "Фирма", "Город", "Адрес доставки"]
      : ["№ заказа", "Дата", "Город", "Адрес доставки"];

    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    columns.forEach((label) => {
      const th = document.createElement("th");
      th.textContent = label;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);

    const tbody = document.createElement("tbody");
    orders.forEach((order) => {
      const tr = document.createElement("tr");
      const values = showFirm
        ? [order.num, order.ord_date, order.firm_name, order.city_name, order.delivery_addr]
        : [order.num, order.ord_date, order.city_name, order.delivery_addr];
      values.forEach((value) => {
        const td = document.createElement("td");
        td.textContent = value || "—";
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);

    return table;
  }

  function buildCategory(category) {
    const card = document.createElement("div");
    card.className = "card mb-3";

    const header = document.createElement("div");
    header.className = "card-header d-flex justify-content-between align-items-center";

    const titleWrap = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = category.label;
    titleWrap.appendChild(title);
    const desc = document.createElement("div");
    desc.className = "text-secondary small";
    desc.textContent = category.description;
    titleWrap.appendChild(desc);
    header.appendChild(titleWrap);

    const badge = document.createElement("span");
    badge.className = "badge text-bg-warning";
    badge.textContent = `${category.order_count} зак.`;
    header.appendChild(badge);

    card.appendChild(header);

    const body = document.createElement("div");
    body.className = "card-body";

    category.groups.forEach((group, index) => {
      if (index > 0) {
        body.appendChild(document.createElement("hr"));
      }
      const groupTitle = document.createElement("div");
      groupTitle.className = "fw-semibold mb-1";
      groupTitle.textContent = group.subtitle ? `${group.title} — ${group.subtitle}` : group.title;
      body.appendChild(groupTitle);

      const tableWrap = document.createElement("div");
      tableWrap.className = "table-responsive mb-2";
      tableWrap.appendChild(buildOrdersTable(group.orders, category.group_by === "address"));
      body.appendChild(tableWrap);
    });

    card.appendChild(body);
    return card;
  }

  zakazAnalysisBtn.addEventListener("click", async () => {
    errorBox.classList.add("d-none");
    errorBox.textContent = "";
    content.textContent = "";

    const originalLabel = zakazAnalysisBtn.innerHTML;
    zakazAnalysisBtn.disabled = true;
    zakazAnalysisBtn.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> Анализируем...';

    try {
      const response = await fetch(`/api/zakaz/analysis?${currentFilterQuery()}`);
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

      const report = await response.json();
      const summary = document.createElement("p");
      summary.className = "text-secondary";
      summary.textContent = `Проверено заказов (по текущему фильтру): ${report.total_orders}`;
      content.appendChild(summary);

      if (report.categories.length === 0) {
        const ok = document.createElement("div");
        ok.className = "alert alert-success mb-0";
        ok.textContent = "Аномалий не найдено.";
        content.appendChild(ok);
      } else {
        report.categories.forEach((category) => content.appendChild(buildCategory(category)));
      }

      analysisModal.show();
    } catch (error) {
      errorBox.textContent = error.message;
      errorBox.classList.remove("d-none");
      analysisModal.show();
    } finally {
      zakazAnalysisBtn.disabled = false;
      zakazAnalysisBtn.innerHTML = originalLabel;
    }
  });
}
