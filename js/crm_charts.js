/**
 * Графики на странице /crm: "выданные мной" / "выданные мне" по статусам задач.
 * Чистый CSS-рендер (ширина задаётся сервером через data-pct), JS только
 * анимирует появление баров и переключает вид "график/таблица".
 */

function animateBars() {
  document.querySelectorAll(".crm-charts .bar-fill").forEach((el) => {
    const pct = el.dataset.pct || "0";
    requestAnimationFrame(() => {
      el.style.width = `${pct}%`;
    });
  });
}

function wireTableToggles() {
  document.querySelectorAll(".chart-table-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.chart;
      const view = document.getElementById(`${key}-chart-view`);
      const table = document.getElementById(`${key}-chart-table`);
      if (!view || !table) return;

      const showingTable = !table.classList.contains("d-none");
      view.classList.toggle("d-none", !showingTable);
      table.classList.toggle("d-none", showingTable);
      btn.textContent = showingTable ? "Таблица" : "График";
    });
  });
}

animateBars();
wireTableToggles();
