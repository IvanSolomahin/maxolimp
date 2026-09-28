const API = "/api/olympiads/communities";
const onlineList = document.getElementById("online-list");
const clubList = document.getElementById("club-list");
const onlineSubject = document.getElementById("online-subject");
const clubSubject = document.getElementById("club-subject");
const clubCity = document.getElementById("club-city");
const message = document.getElementById("community-message");
const dialog = document.getElementById("club-dialog");
const map = L.map("community-map", {
    attributionControl: false // Полностью скрывает нижнюю панель с копирайтом
}).setView([59.9386, 30.3141], 11);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
}).addTo(map);
const markers = L.layerGroup().addTo(map);
let clubs = [];

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

async function api(path, options) {
  const response = await fetch(`${API}${path}`, options);
  if (!response.ok) throw new Error(`Ошибка сервера (${response.status})`);
  return response.status === 204 ? null : response.json();
}

async function loadOptions() {
  const data = await api("/options");
  for (const subject of data.subjects) {
    for (const select of [onlineSubject, clubSubject]) {
      const option = document.createElement("option");
      option.value = subject;
      option.textContent = subject;
      select.append(option);
    }
  }
  for (const city of data.cities) {
    const option = document.createElement("option");
    option.value = city;
    option.textContent = city;
    clubCity.append(option);
  }
}

async function loadOnline() {
  onlineList.innerHTML = '<p class="community-message">Загружаем чаты…</p>';
  try {
    const query = onlineSubject.value ? `?subject=${encodeURIComponent(onlineSubject.value)}` : "";
    const { items } = await api(`/online${query}`);
    onlineList.innerHTML = items.length ? items.map((chat) => `
      <article class="community-card">
        <div class="community-icon">${esc(chat.platform.slice(0, 2).toUpperCase())}</div>
        <div class="community-body"><strong>${esc(chat.name)}</strong>
          <span>${esc(chat.subject)} · ${esc(chat.platform)}${chat.description ? ` · ${esc(chat.description)}` : ""}</span></div>
        <a class="join-btn" href="${esc(chat.url)}" target="_blank" rel="noopener noreferrer">Открыть</a>
      </article>`).join("") : '<p class="community-message">Чатов по этому предмету пока нет.</p>';
  } catch (error) {
    onlineList.innerHTML = `<p class="community-message">${esc(error.message)}. Не удалось загрузить список чатов.</p>`;
  }
}

function openClub(club) {
  document.getElementById("sheet-title").textContent = club.name || "Кружок";
  document.getElementById("sheet-sub").textContent = club.address || "Адрес не указан";
  const facts = [
    ["Предмет", club.subject], ["Статус", club.status],
    ["Расстояние", club.distance_km == null ? null : `${club.distance_km} км`], ["Информация", club.note],
  ].filter(([, value]) => value);
  document.getElementById("sheet-facts").innerHTML = facts.map(([label, value]) =>
    `<li><span>${esc(label)}</span><span>${esc(value)}</span></li>`).join("");
  const join = dialog.querySelector(".sheet-actions");
  join.innerHTML = club.source
    ? `<a class="join-btn" style="width:100%;justify-content:center;min-height:48px" href="${esc(club.source)}" target="_blank" rel="noopener noreferrer">Перейти к источнику</a>`
    : "";
  dialog.showModal();
}

function renderClubs(items) {
  clubs = items;
  markers.clearLayers();
  for (const club of items) {
    if (club.latitude == null || club.longitude == null) continue;
    const marker = L.marker([club.latitude, club.longitude]).addTo(markers);
    marker.bindTooltip(esc(club.name || "Кружок"));
    marker.on("click", () => openClub(club));
  }
  clubList.innerHTML = items.length ? items.map((club, index) => `
    <article class="club-card"><div class="club-top"><h3>${esc(club.name || "Кружок")}</h3>
      ${club.distance_km == null ? "" : `<span class="club-dist">${club.distance_km} км</span>`}</div>
      <p class="club-addr">${esc(club.address || "Адрес не указан")}</p>
      <div class="club-foot"><button class="detail-link" type="button" data-detail="${index}">Подробнее</button></div></article>`).join("")
    : '<p class="community-message">По выбранным фильтрам кружков не найдено.</p>';
  clubList.querySelectorAll("[data-detail]").forEach((button) =>
    button.addEventListener("click", () => openClub(clubs[Number(button.dataset.detail)])));
}

async function loadClubs(location = null) {
  message.textContent = "Загружаем кружки…";
  const params = new URLSearchParams({ city: clubCity.value || "Санкт-Петербург" });
  if (clubSubject.value) params.set("subject", clubSubject.value);
  if (location) { params.set("lat", location.lat); params.set("lon", location.lon); }
  try {
    const { items } = await api(`/clubs?${params}`);
    renderClubs(items);
    message.textContent = items.length ? `Найдено кружков: ${items.length}` : "Кружков по выбранным фильтрам не найдено.";
    if (items.length && !location) {
      const points = items.filter((club) => club.latitude != null && club.longitude != null)
        .map((club) => [club.latitude, club.longitude]);
      if (points.length) map.fitBounds(points, { padding: [24, 24], maxZoom: 13 });
    }
  } catch (error) {
    renderClubs([]);
    message.textContent = `${error.message}. Не удалось загрузить кружки.`;
  }
}

document.getElementById("mode-toggle").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-mode]");
  if (!button) return;
  document.querySelectorAll("#mode-toggle button").forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
  const isOnline = button.dataset.mode === "online";
  document.getElementById("online-view").hidden = !isOnline;
  document.getElementById("offline-view").hidden = isOnline;
  if (!isOnline) setTimeout(() => map.invalidateSize(), 0);
});
onlineSubject.addEventListener("change", loadOnline);
clubSubject.addEventListener("change", () => loadClubs());
clubCity.addEventListener("change", () => loadClubs());
document.getElementById("nearby-button").addEventListener("click", () => {
  if (!navigator.geolocation) { message.textContent = "Браузер не поддерживает геолокацию."; return; }
  message.textContent = "Определяем местоположение…";
  navigator.geolocation.getCurrentPosition(
    ({ coords }) => { map.setView([coords.latitude, coords.longitude], 12); loadClubs(coords); },
    () => { message.textContent = "Не удалось получить местоположение. Разрешите доступ к геолокации."; },
    { enableHighAccuracy: true, timeout: 10000 },
  );
});
document.getElementById("close-dialog").addEventListener("click", () => dialog.close());

(async () => {
  try { await loadOptions(); } catch (error) { message.textContent = error.message; }
  await Promise.all([loadOnline(), loadClubs()]);
})();
