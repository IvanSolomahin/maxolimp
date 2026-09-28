const ONLINE = [
  {
    icon: "TG",
    name: "Олимпиадная информатика",
    platform: "Telegram · чат",
    members: "18 400 участников",
    joined: false,
  },
  {
    icon: "TG",
    name: "Высшая проба — вопросы",
    platform: "Telegram · чат",
    members: "6 100 участников",
    joined: true,
  },
  {
    icon: "DС",
    name: "Соревновательное программирование",
    platform: "Discord · сервер",
    members: "9 800 участников",
    joined: false,
  },
  {
    icon: "VK",
    name: "Абитуриенту ВШЭ",
    platform: "VK · группа",
    members: "54 000 участников",
    joined: false,
  },
  {
    icon: "TG",
    name: "Математические олимпиады",
    platform: "Telegram · канал",
    members: "22 700 подписчиков",
    joined: false,
  },
];

const CLUBS = [
  {
    name: "Кружок по информатике при лицее №239",
    dist: "1.2 км",
    addr: "Санкт-Петербург, Приморский р-н",
    schedule: "Вт, Чт · 18:00",
    level: "Начинающие и продвинутые",
  },
  {
    name: "Матклуб «Вектор»",
    dist: "2.8 км",
    addr: "Санкт-Петербург, Выборгский р-н",
    schedule: "Сб · 12:00",
    level: "Средний и высокий уровень",
  },
  {
    name: "Клуб олимпиадной информатики ИТМО",
    dist: "3.4 км",
    addr: "Санкт-Петербург, центр города",
    schedule: "Ср · 19:00",
    level: "Высшая лига",
  },
  {
    name: "Кружок «Юный программист»",
    dist: "4.1 км",
    addr: "Санкт-Петербург, Московский р-н",
    schedule: "Пн, Пт · 17:30",
    level: "Начинающие",
  },
];

const onlineList = document.getElementById("online-list");
const clubList = document.getElementById("club-list");
const dialog = document.getElementById("club-dialog");
const toggle = document.getElementById("mode-toggle");
const onlineView = document.getElementById("online-view");
const offlineView = document.getElementById("offline-view");

function renderOnline() {
  onlineList.innerHTML = ONLINE.map(
    (c, i) => `
        <div class="community-card">
          <div class="community-icon">${c.icon}</div>
          <div class="community-body">
            <strong>${c.name}</strong>
            <span>${c.platform} · ${c.members}</span>
          </div>
          <button class="join-btn ${c.joined ? "joined" : ""}" type="button" data-join="${i}">${c.joined ? "Вы в чате" : "Вступить"}</button>
        </div>`,
  ).join("");

  onlineList.querySelectorAll("[data-join]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const i = Number(btn.dataset.join);
      ONLINE[i].joined = !ONLINE[i].joined;
      renderOnline();
    });
  });
}

function renderClubs() {
  clubList.innerHTML = CLUBS.map(
    (c, i) => `
        <article class="club-card">
          <div class="club-top"><h3>${c.name}</h3><span class="club-dist">${c.dist}</span></div>
          <p class="club-addr">${c.addr}</p>
          <div class="club-foot"><button class="detail-link" type="button" data-club-detail="${i}">Подробнее</button></div>
        </article>`,
  ).join("");

  clubList.querySelectorAll("[data-club-detail]").forEach((btn) => {
    btn.addEventListener("click", () =>
      openClub(CLUBS[Number(btn.dataset.clubDetail)]),
    );
  });
}

function openClub(club) {
  document.getElementById("sheet-title").textContent = club.name;
  document.getElementById("sheet-sub").textContent = club.addr;
  document.getElementById("sheet-facts").innerHTML = `
        <li><span>Расстояние</span><span>${club.dist}</span></li>
        <li><span>Расписание</span><span>${club.schedule}</span></li>
        <li><span>Уровень</span><span>${club.level}</span></li>`;
  dialog.showModal();
}

document.querySelectorAll(".map-pin[data-club]").forEach((pin) => {
  pin.addEventListener("click", () =>
    openClub(CLUBS[Number(pin.dataset.club)]),
  );
});

document
  .getElementById("close-dialog")
  .addEventListener("click", () => dialog.close());

toggle.addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-mode]");
  if (!btn) return;
  toggle
    .querySelectorAll("button")
    .forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
  const isOnline = btn.dataset.mode === "online";
  onlineView.hidden = !isOnline;
  offlineView.hidden = isOnline;
});

renderOnline();
renderClubs();
