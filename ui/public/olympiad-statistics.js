const series = {
  week: {
    label: "за последние 7 дней",
    days: ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
    values: [2, 1, 3, 0, 2, 1, 3],
    total: 12,
  },
  month: {
    label: "за последние 30 дней",
    days: ["1", "5", "10", "15", "20", "25", "30"],
    values: [4, 2, 7, 3, 5, 8, 6],
    total: 35,
  },
  year: {
    label: "за последние 12 месяцев",
    days: ["Окт", "Дек", "Фев", "Апр", "Июн", "Авг", "Сен"],
    values: [4, 6, 3, 8, 5, 11, 12],
    total: 49,
  },
};
function showPeriod(k) {
  const s = series[k];
  document.getElementById("period-count").textContent = s.total;
  document.getElementById("chart-count").textContent = s.total;
  document.getElementById("period-caption").textContent = s.label;
  document.querySelector(".chart-total strong").nextSibling.textContent =
    " за " + (k === "week" ? "неделю" : k === "month" ? "месяц" : "год");
  const max = Math.max(...s.values);
  document.getElementById("chart").innerHTML = s.values
    .map(
      (v, i) =>
        `<div class="bar-wrap"><div class="bar" style="--h:${Math.max(5, Math.round((v / max) * 100))}%" title="${v} задач"></div><span class="bar-label">${s.days[i]}</span></div>`,
    )
    .join("");
  document
    .querySelectorAll("[data-period]")
    .forEach((b) =>
      b.setAttribute("aria-pressed", String(b.dataset.period === k)),
    );
}
document
  .querySelectorAll("[data-period]")
  .forEach((b) =>
    b.addEventListener("click", () => showPeriod(b.dataset.period)),
  );
showPeriod("week");
const solved = JSON.parse(localStorage.getItem("maxolimp-solved") || "[]");
if (solved.length) {
  document.getElementById("all-count").textContent = 28 + solved.length;
  const list = document.getElementById("solved-list");
  solved.forEach((name) =>
    list.insertAdjacentHTML(
      "afterbegin",
      `<div class="row"><span class="rank">✓</span><div class="row-copy"><p class="row-title"></p><p class="row-sub">Отмечено вами</p></div></div>`,
    ),
  );
  [...list.querySelectorAll(".row:first-child .row-title")].forEach(
    (el, i) => (el.textContent = solved[i]),
  );
}
