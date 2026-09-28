const TRACKED = [
  {
    subject: "Информатика",
    name: "Высшая проба",
    benefit: "БВИ",
    total: 200,
    done: 46,
    href: "./olympiad-after-onboarding.html",
  },
  {
    subject: "Математика",
    name: "Физтех",
    benefit: "100 баллов",
    total: 150,
    done: 12,
    href: "./olympiad-task-search.html",
  },
];

const list = document.getElementById("tracked-list");

if (TRACKED.length === 0) {
  list.innerHTML =
    '<p class="empty-state">Пока нет плана подготовки. Начните с подбора олимпиады.</p>';
} else {
  list.innerHTML = TRACKED.map((o) => {
    const pct = Math.round((o.done / o.total) * 100);
    return `
        <article class="olympiad-card">
          <div class="card-top"><span class="subject-tag">${o.subject}</span><span class="benefit-tag">${o.benefit}</span></div>
          <h3>${o.name}</h3>
          <div class="progress-meta"><span>Решено заданий</span><strong>${o.done} / ${o.total}</strong></div>
          <div class="progress-track" role="progressbar" aria-label="Прогресс: ${o.name}" aria-valuenow="${o.done}" aria-valuemin="0" aria-valuemax="${o.total}"><div class="progress-value" style="width:${pct}%"></div></div>
          <div class="card-foot"><p>${pct}% пути пройдено</p><a class="go-btn" href="${o.href}">Продолжить →</a></div>
        </article>`;
  }).join("");
}
