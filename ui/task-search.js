const api = '/api/tasks';
const $ = selector => document.querySelector(selector);
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const list = $('#task-list');
const count = $('#results-count');
const empty = $('#empty-state');
const dialog = $('#filter-dialog');
const taskPage = $('#task-page');
const searchScreen = $('[data-od-id="task-search-screen"]');
const query = $('#task-query');
const favorites = new Set(JSON.parse(localStorage.getItem('task-favorites-v1') || '[]'));
const favoriteItems = new Map(JSON.parse(localStorage.getItem('task-favorite-items-v1') || '[]'));
const state = {subject:'math', q:'', sort:'relevance', grade:'', difficultyMin:'', difficultyMax:'', page:1, total:0, items:[], favoritesOnly:false};
let requestId = 0;
let debounce;

async function getJson(path, signal) {
  const response = await fetch(`${api}${path}`, {signal});
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function showError(message) {
  empty.hidden = false;
  $('#empty-title').textContent = 'Не удалось загрузить задачи';
  $('#empty-copy').textContent = message;
  $('#empty-action').textContent = 'Повторить';
  list.hidden = true;
  $('#load-more').hidden = true;
}

function render() {
  const items = state.favoritesOnly ? [...favoriteItems.values()] : state.items;
  list.innerHTML = items.map(item => `
    <article class="task-card" data-id="${escapeHtml(item.id)}">
      <div class="task-top"><span class="task-number">Задача</span><div class="task-actions">
        <button class="icon-btn" type="button" data-favorite="${escapeHtml(item.id)}" aria-label="${favorites.has(item.id) ? 'Убрать из избранного' : 'Добавить в избранное'}" aria-pressed="${favorites.has(item.id)}">♡</button>
      </div></div>
      <h3 class="task-title"><button class="text-btn" type="button" data-open="${escapeHtml(item.id)}">${escapeHtml(item.title)}</button></h3>
      <p class="task-fragment">${escapeHtml(item.snippet || '')}</p>
      <div class="task-meta"><span class="meta-item">${item.difficulty == null ? 'Сложность не указана' : `Сложность ${escapeHtml(item.difficulty)} из 10`}</span>
      ${item.solution_method ? `<span class="meta-item">${escapeHtml(item.solution_method.name)}</span>` : ''}</div>
    </article>`).join('');
  count.textContent = state.favoritesOnly ? `${items.length} в избранном` : `${state.total} задач`;
  list.hidden = items.length === 0;
  empty.hidden = items.length !== 0;
  if (!items.length) {
    $('#empty-title').textContent = state.favoritesOnly ? 'Избранных задач нет' : 'Задачи не найдены';
    $('#empty-copy').textContent = state.favoritesOnly ? 'Добавьте задачу кнопкой с сердцем.' : 'Попробуйте изменить запрос или фильтры.';
    $('#empty-action').textContent = 'Сбросить поиск';
  }
  $('#load-more').hidden = state.favoritesOnly || state.items.length >= state.total || state.total === 0;
  $('[data-od-id="favorites-button"]').setAttribute('aria-pressed', String(state.favoritesOnly));
  $('#filter-count').hidden = !(state.grade || state.difficultyMin || state.difficultyMax);
  $('#filter-count').textContent = [state.grade, state.difficultyMin, state.difficultyMax].filter(Boolean).length;
}

async function loadTasks(append = false) {
  const current = ++requestId;
  if (!append) { state.page = 1; state.items = []; list.innerHTML = ''; }
  const params = new URLSearchParams({subject:state.subject, sort:state.sort, page:String(state.page), size:'20'});
  if (state.q.trim()) params.set('q', state.q.trim());
  if (state.grade) params.set('grade', state.grade);
  if (state.difficultyMin) params.set('difficulty_min', state.difficultyMin);
  if (state.difficultyMax) params.set('difficulty_max', state.difficultyMax);
  count.textContent = 'Загрузка…';
  $('#load-more').disabled = true;
  try {
    const data = await getJson(`/tasks?${params}`);
    if (current !== requestId) return;
    state.total = data.total;
    state.items = append ? [...state.items, ...data.items] : data.items;
    render();
  } catch (error) {
    if (current !== requestId) return;
    showError('Проверьте соединение и повторите запрос.');
  } finally {
    if (current === requestId) $('#load-more').disabled = false;
  }
}

async function openTask(id) {
  const taskUrl = `/tasks/${encodeURIComponent(id)}`;
  if (location.pathname !== taskUrl) history.pushState({taskId: id}, '', taskUrl);
  showTaskPage();
  $('#detail-title').textContent = 'Загрузка задачи…';
  $('#detail-statement').textContent = '';
  $('#detail-statement').classList.add('task-loading');
  $('#detail-meta').textContent = '';
  $('#detail-source').hidden = true;
  try {
    const task = await getJson(`/tasks/${encodeURIComponent(id)}`);
    if (location.pathname !== taskUrl) return;
    $('#detail-title').textContent = task.title;
    $('#detail-statement').textContent = task.statement || 'Условие не указано';
    $('#detail-statement').classList.remove('task-loading');
    $('#detail-meta').textContent = [task.subject === 'math' ? 'Математика' : task.subject === 'physics' ? 'Физика' : '', task.grade ? `${task.grade} класс` : '', task.source?.year, task.source?.stage, task.source?.number].filter(Boolean).join(' · ');
    if (task.source?.url && /^https?:\/\//i.test(task.source.url)) {
      $('#detail-source').href = task.source.url;
      $('#detail-source').hidden = false;
    }
  } catch {
    if (location.pathname !== taskUrl) return;
    $('#detail-title').textContent = 'Не удалось загрузить задачу';
    $('#detail-statement').textContent = 'Закройте окно и попробуйте снова.';
    $('#detail-statement').classList.remove('task-loading');
  }
}

function showTaskPage() {
  searchScreen.hidden = true;
  taskPage.hidden = false;
  window.scrollTo(0, 0);
}

function showSearchPage() {
  taskPage.hidden = true;
  searchScreen.hidden = false;
}

function routeFromLocation() {
  const match = location.pathname.match(/^\/tasks\/([^/]+)\/?$/);
  if (match) openTask(decodeURIComponent(match[1]));
  else showSearchPage();
}

query.addEventListener('input', () => {
  state.q = query.value;
  $('[data-od-id="clear-search"]').hidden = !state.q;
  clearTimeout(debounce);
  debounce = setTimeout(() => loadTasks(), 300);
});
$('[data-od-id="clear-search"]').addEventListener('click', () => { query.value = ''; state.q = ''; $('[data-od-id="clear-search"]').hidden = true; loadTasks(); });
$('#subject-select').addEventListener('change', event => { state.subject = event.target.value; loadTasks(); });
$('#sort-select').addEventListener('change', event => { state.sort = event.target.value; loadTasks(); });
$('[data-od-id="favorites-button"]').addEventListener('click', () => { state.favoritesOnly = !state.favoritesOnly; render(); });
$('[data-od-id="open-filters"]').addEventListener('click', () => { $('#grade-filter').value = state.grade; $('#difficulty-min').value = state.difficultyMin; $('#difficulty-max').value = state.difficultyMax; dialog.showModal(); });
$('[data-od-id="close-filters"]').addEventListener('click', () => dialog.close());
$('[data-od-id="reset-filters"]').addEventListener('click', () => { $('#grade-filter').value = ''; $('#difficulty-min').value = ''; $('#difficulty-max').value = ''; });
$('[data-od-id="apply-filters"]').addEventListener('click', () => {
  const min = $('#difficulty-min').value, max = $('#difficulty-max').value;
  if (min && max && Number(min) > Number(max)) { $('#difficulty-min').setCustomValidity('Минимум больше максимума'); $('#difficulty-min').reportValidity(); return; }
  $('#difficulty-min').setCustomValidity('');
  state.grade = $('#grade-filter').value;
  state.difficultyMin = min;
  state.difficultyMax = max;
  dialog.close();
  loadTasks();
});
$('#empty-action').addEventListener('click', () => { state.q = ''; state.grade = ''; state.difficultyMin = ''; state.difficultyMax = ''; state.favoritesOnly = false; query.value = ''; loadTasks(); });
$('#load-more').addEventListener('click', () => { state.page += 1; loadTasks(true); });
list.addEventListener('click', event => {
  const fav = event.target.closest('[data-favorite]');
  if (fav) {
    const id = fav.dataset.favorite;
    if (favorites.has(id)) { favorites.delete(id); favoriteItems.delete(id); }
    else { favorites.add(id); favoriteItems.set(id, state.items.find(item => item.id === id) || favoriteItems.get(id)); }
    localStorage.setItem('task-favorites-v1', JSON.stringify([...favorites]));
    localStorage.setItem('task-favorite-items-v1', JSON.stringify([...favoriteItems]));
    render();
    return;
  }
  const open = event.target.closest('[data-open]');
  if (open) openTask(open.dataset.open);
});
$('#task-back').addEventListener('click', () => {
  if (history.state?.taskId) history.back();
  else { history.pushState({}, '', '/'); showSearchPage(); }
});
window.addEventListener('popstate', routeFromLocation);
routeFromLocation();
if (!/^\/tasks\/[^/]+\/?$/.test(location.pathname)) loadTasks();
