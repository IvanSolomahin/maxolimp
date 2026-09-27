const api = '/api/olympiads';
const $ = selector => document.querySelector(selector);
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const storageKey = 'onboarding-live-v1';
const favoritesKey = 'olympiad-favorites-local-v1';
const saved = JSON.parse(localStorage.getItem(storageKey) || '{}');
const state = {step:0, university:'', direction:'', ...saved, subject:''};
// Step 2 used to be the subject picker; results now occupy that step.
if (state.step === 3) state.step = 2;
const names = {university:new Map(), direction:new Map(), subject:new Map()};
const favorites = new Set(JSON.parse(localStorage.getItem(favoritesKey) || '[]'));
let activeBenefit = 'all';
let recommendations = [];
let requestId = 0;
let searchTimer;

async function getJson(path) {
  const response = await fetch(`${api}${path}`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function save() { localStorage.setItem(storageKey, JSON.stringify(state)); }

function choice(item, field) {
  const id = String(item.id);
  const note = field === 'university' ? (item.cities || []).join(' · ') : field === 'direction' ? item.code : '';
  return `<label class="choice-card"><input type="radio" name="${field}" value="${escapeHtml(id)}" ${state[field] === id ? 'checked' : ''}><span class="choice-body"><span><span class="choice-title">${escapeHtml(item.name)}</span>${note ? `<span class="choice-note">${escapeHtml(note)}</span>` : ''}</span><span class="radio-dot"></span></span></label>`;
}

async function loadChoices(field, search = '') {
  const container = $(`[data-options="${field}"]`);
  const empty = $(`[data-empty="${field}"]`);
  const current = ++requestId;
  container.textContent = 'Загрузка…';
  empty.hidden = true;
  try {
    let path;
    if (field === 'university') path = `/universities?q=${encodeURIComponent(search)}&size=100`;
    else if (field === 'direction') path = `/universities/${encodeURIComponent(state.university)}/programs?q=${encodeURIComponent(search)}&size=100`;
    else path = '/subjects?size=100';
    const data = await getJson(path);
    if (current !== requestId) return;
    data.items.forEach(item => names[field].set(String(item.id), item.name));
    container.innerHTML = data.items.map(item => choice(item, field)).join('');
    empty.textContent = field === 'university' ? 'Вузы не найдены' : field === 'direction' ? 'Направления не найдены' : 'Предметы не найдены';
    empty.hidden = data.items.length !== 0;
    if (data.total > data.items.length) {
      const note = document.createElement('p');
      note.className = 'choice-note';
      note.textContent = field === 'subject' ? 'Показаны первые 100 предметов' : 'Уточните поиск, чтобы увидеть другие варианты';
      container.append(note);
    }
  } catch {
    if (current !== requestId) return;
    container.textContent = '';
    empty.textContent = 'Не удалось загрузить данные. Повторите поиск.';
    empty.hidden = false;
  }
}

function showStep(step) {
  state.step = Math.max(0, Math.min(2, step));
  save();
  document.querySelectorAll('[data-step]').forEach(view => { const active = Number(view.dataset.step) === state.step; view.hidden = !active; view.setAttribute('aria-hidden', String(!active)); });
  $('#back-button').hidden = state.step === 0;
  $('#appbar-title').textContent = state.step === 2 ? 'Результаты' : 'Подбор олимпиад';
  $('#bottom-action').hidden = state.step === 2;
  $('#primary-action').textContent = 'Продолжить';
  $('#primary-action').disabled = state.step === 0 ? !state.university : state.step === 1 ? !state.direction : false;
  if (state.step === 0) loadChoices('university', $('#university-search').value.trim());
  if (state.step === 1) loadChoices('direction', $('#direction-search').value.trim());
  if (state.step === 2) loadRecommendations();
  $('.content').scrollTop = 0;
}

function benefitLabel(type) {
  if (type === 'bvi' || type === 'no entrance exams') return 'БВИ';
  if (type === '100 points') return '100 баллов';
  if (type === 'additional_points') return 'Дополнительные баллы';
  return type || 'Не указана';
}

function renderResults(total) {
  $('#criteria-main').textContent = `${names.university.get(state.university) || 'Вуз'} · ${names.direction.get(state.direction) || 'Направление'}`;
  $('#criteria-sub').textContent = state.subject ? `Предмет: ${names.subject.get(state.subject) || 'выбранный'}` : 'Любой профиль олимпиады';
  $('#result-count').textContent = `${total} вариантов`;
  $('#results-list').innerHTML = recommendations.map(item => `
    <article class="olympiad-card">
      <div class="card-head"><div><p class="card-kicker">${escapeHtml(item.subject.name)}</p><h2>${escapeHtml(item.name)}</h2></div><button class="icon-btn favorite" type="button" data-favorite="${item.id}" aria-label="${favorites.has(item.id) ? 'Убрать из избранного' : 'Добавить в избранное'}" aria-pressed="${favorites.has(item.id)}">♡</button></div>
      <div class="card-facts"><div class="fact-row"><span class="fact-label">Сложность</span><span class="fact-value">${escapeHtml(item.complexity)} из 5</span></div><div class="fact-row"><span class="fact-label">Льгота</span><span class="fact-value">${escapeHtml(benefitLabel(item.benefit.type))}</span></div></div>
      <div class="card-foot"><p>Условия льготы уточняйте в правилах приёма вуза.</p><button class="places-btn" type="button" data-places="${item.id}">Этапы и площадки</button></div>
    </article>`).join('');
  $('#empty-results').hidden = recommendations.length !== 0;
  $('#more-results').hidden = recommendations.length >= total || total === 0;
}

async function loadRecommendations(append = false) {
  const current = ++requestId;
  const page = append ? Math.floor(recommendations.length / 100) + 1 : 1;
  if (!append) { recommendations = []; $('#results-list').textContent = 'Загрузка…'; }
  $('#more-results').disabled = true;
  const params = new URLSearchParams({university_id:state.university, program_id:state.direction, size:'100', page:String(page)});
  if (state.subject) params.set('subject_id', state.subject);
  if (activeBenefit === 'bvi') params.set('benefit_type', 'bvi');
  if (activeBenefit === '100') params.set('benefit_type', '100 points');
  try {
    const data = await getJson(`/olympiads/recommendations?${params}`);
    if (current !== requestId) return;
    recommendations = append ? [...recommendations, ...data.items] : data.items;
    renderResults(data.total);
  } catch {
    if (current !== requestId) return;
    $('#results-list').textContent = '';
    $('#empty-results').textContent = 'Не удалось загрузить олимпиады. Повторите запрос.';
    $('#empty-results').hidden = false;
    $('#more-results').hidden = true;
  } finally {
    if (current === requestId) $('#more-results').disabled = false;
  }
}

document.querySelectorAll('[data-options]').forEach(container => container.addEventListener('change', event => {
  const input = event.target.closest('input[type="radio"]');
  if (!input) return;
  state[input.name] = input.value;
  if (input.name === 'university') { state.direction = ''; state.subject = ''; $('#direction-search').value = ''; }
  if (input.name === 'direction') state.subject = '';
  save();
  $('#primary-action').disabled = state.step === 0 ? !state.university : state.step === 1 ? !state.direction : false;
}));
document.querySelectorAll('[data-search]').forEach(input => input.addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => loadChoices(input.dataset.search, input.value.trim()), 300);
}));
$('#primary-action').addEventListener('click', () => { if (state.step === 0 && state.university) showStep(1); else if (state.step === 1 && state.direction) showStep(2); });
$('#back-button').addEventListener('click', () => showStep(state.step - 1));
$('#edit-criteria').addEventListener('click', () => showStep(0));
document.querySelectorAll('[data-benefit]').forEach(button => button.addEventListener('click', () => {
  activeBenefit = button.dataset.benefit;
  document.querySelectorAll('[data-benefit]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
  loadRecommendations();
}));
$('#more-results').addEventListener('click', () => loadRecommendations(true));
$('#results-list').addEventListener('click', async event => {
  const favorite = event.target.closest('[data-favorite]');
  if (favorite) {
    const id = Number(favorite.dataset.favorite);
    favorites.has(id) ? favorites.delete(id) : favorites.add(id);
    localStorage.setItem(favoritesKey, JSON.stringify([...favorites]));
    renderResults(Number($('#result-count').textContent.split(' ')[0]));
    return;
  }
  const places = event.target.closest('[data-places]');
  if (!places) return;
  const id = Number(places.dataset.places);
  const item = recommendations.find(entry => entry.id === id);
  $('#sheet-title').textContent = item.name;
  $('#sheet-sub').textContent = 'Этапы олимпиады';
  $('#place-list').innerHTML = '<li>Загрузка…</li>';
  $('#places-dialog').showModal();
  try {
    const data = await getJson(`/olympiads/${id}/stages`);
    if (!$('#places-dialog').open) return;
    const list = $('#place-list');
    list.replaceChildren();
    if (!data.items.length) { const li = document.createElement('li'); li.textContent = 'Этапы пока не указаны'; list.append(li); }
    data.items.forEach(stage => {
      const li = document.createElement('li');
      li.textContent = `${stage.name} · ${stage.is_online ? 'онлайн' : stage.location || 'место уточняется'} · ${new Date(stage.start_date).toLocaleDateString('ru-RU')}`;
      list.append(li);
    });
  } catch { $('#place-list').textContent = 'Не удалось загрузить этапы'; }
});
$('#close-dialog').addEventListener('click', () => $('#places-dialog').close());
$('#places-dialog').addEventListener('click', event => { if (event.target === $('#places-dialog')) $('#places-dialog').close(); });
showStep(0);
