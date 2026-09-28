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
const state = {subject:'math', q:'', sort:'relevance', grade:'', olympiadId:'', olympiadName:'', difficultyMin:'', difficultyMax:'', classifiers:[], page:1, total:0, items:[]};
let olympiads = [];
let classifiers = [];
let classifiersStatus = 'Загрузка тегов…';
let filterClassifiers = new Set();
let classifierRequestId = 0;
let filterOlympiadId = '';
let filterOlympiadName = '';
let requestId = 0;
let detailRequestId = 0;
let debounce;
let openedTask = null;
let taskAlreadySolved = false;

function loginUrl() {
  return `./olympiad-auth.html?next=${encodeURIComponent(location.pathname + location.search)}`;
}

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
  const items = state.items;
  list.innerHTML = items.map(item => `
    <article class="task-card" data-id="${escapeHtml(item.id)}">
      <div class="task-top"><span class="task-number">${item.number ? `№ ${escapeHtml(item.number)}` : ''}</span>${item.difficulty == null ? '' : `<span class="difficulty-badge difficulty-${Number(item.difficulty) <= 3 ? 'easy' : Number(item.difficulty) <= 5 ? 'medium' : 'hard'}">Сложность ${escapeHtml(item.difficulty)}/10</span>`}</div>
      <a class="task-fragment task-link" href="/tasks/${encodeURIComponent(item.id)}" data-open="${escapeHtml(item.id)}">${escapeHtml(item.snippet || item.title || '')}</a>
      <div class="task-meta">${item.olympiad ? `<span class="meta-item" title="${escapeHtml(item.olympiad)}">${escapeHtml(item.olympiad_short_name || item.olympiad)}</span>` : ''}${item.solution_method ? `<span class="meta-item">${escapeHtml(item.solution_method.name)}</span>` : ''}</div>
    </article>`).join('');
  list.querySelectorAll('.task-card').forEach((card, index) => {
    taskMath.renderMathText(card.querySelector('.task-fragment'), items[index].snippet || items[index].title || '');
  });
  count.textContent = `${state.total} задач`;
  list.hidden = items.length === 0;
  empty.hidden = items.length !== 0;
  if (!items.length) {
    $('#empty-title').textContent = 'Задачи не найдены';
    $('#empty-copy').textContent = 'Попробуйте изменить запрос или фильтры.';
    $('#empty-action').textContent = 'Сбросить поиск';
  }
  $('#load-more').hidden = state.items.length >= state.total || state.total === 0;
  const filterCount = [state.grade, state.olympiadId, state.difficultyMin, state.difficultyMax].filter(Boolean).length + state.classifiers.length;
  $('#filter-count').hidden = !filterCount;
  $('#filter-count').textContent = filterCount;
  const activeFilters = $('#active-filters');
  activeFilters.replaceChildren();
  for (const classifier of state.classifiers) {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'filter-chip';
    chip.textContent = `${classifier} ×`;
    chip.setAttribute('aria-label', `Убрать тег ${classifier}`);
    chip.addEventListener('click', () => {
      state.classifiers = state.classifiers.filter(value => value !== classifier);
      loadTasks();
    });
    activeFilters.append(chip);
  }
  activeFilters.hidden = !state.classifiers.length;
}

async function loadTasks(append = false) {
  const current = ++requestId;
  if (!append) { state.page = 1; state.items = []; list.innerHTML = ''; }
  const params = new URLSearchParams({subject:state.subject, sort:state.sort, page:String(state.page), size:'20'});
  if (state.q.trim()) params.set('q', state.q.trim());
  if (state.olympiadId) params.set('olympiad_id', state.olympiadId);
  if (state.grade) params.set('grade', state.grade);
  if (state.difficultyMin) params.set('difficulty_min', state.difficultyMin);
  if (state.difficultyMax) params.set('difficulty_max', state.difficultyMax);
  for (const classifier of state.classifiers) params.append('classifiers', classifier);
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
  const current = ++detailRequestId;
  openedTask = null;
  taskAlreadySolved = false;
  const taskUrl = `/tasks/${encodeURIComponent(id)}`;
  if (location.pathname !== taskUrl) history.pushState({taskId: id}, '', taskUrl);
  showTaskPage();
  $('#detail-title').textContent = 'Загрузка задачи…';
  $('#detail-statement').textContent = '';
  $('#detail-statement').classList.add('task-loading');
  $('#detail-meta').textContent = '';
  $('#detail-source').hidden = true;
  $('#detail-solution-section').hidden = true;
  $('#detail-answer').hidden = true;
  $('#detail-answer-form').hidden = false;
  $('#detail-user-answer').value = '';
  $('#detail-user-answer').disabled = false;
  $('#detail-submit-answer').disabled = false;
  $('#detail-feedback').hidden = true;
  $('#detail-mark-solved').disabled = false;
  $('#detail-mark-solved').textContent = 'Отметить решённой';
  try {
    const task = await getJson(`/tasks/${encodeURIComponent(id)}`);
    if (current !== detailRequestId || location.pathname !== taskUrl) return;
    openedTask = task;
    taskMath.renderMathText($('#detail-title'), task.title);
    taskMath.renderMathText($('#detail-statement'), task.statement || 'Условие не указано');
    $('#detail-statement').classList.remove('task-loading');
    $('#detail-meta').textContent = [task.subject === 'math' ? 'Математика' : task.subject === 'physics' ? 'Физика' : '', task.grade ? `${task.grade} класс` : '', task.olympiads?.[0]?.short_name || task.olympiads?.[0]?.name, task.source?.year, task.source?.stage, task.source?.number ? `№ ${task.source.number}` : ''].filter(Boolean).join(' · ');
    if (task.source?.url && /^https?:\/\//i.test(task.source.url)) {
      $('#detail-source').href = task.source.url;
      $('#detail-source').hidden = false;
    }
    try {
      let progress = await fetch(`/api/progress/tasks/${encodeURIComponent(id)}`);
      if (progress.status === 401) {
        await window.maxUserReady;
        progress = await fetch(`/api/progress/tasks/${encodeURIComponent(id)}`);
      }
      if (current === detailRequestId && progress.ok) taskAlreadySolved = (await progress.json()).solved;
    } catch {
      // The task remains readable if the progress service is unavailable.
    }
  } catch {
    if (current !== detailRequestId || location.pathname !== taskUrl) return;
    $('#detail-title').textContent = 'Не удалось загрузить задачу';
    $('#detail-statement').textContent = 'Закройте окно и попробуйте снова.';
    $('#detail-statement').classList.remove('task-loading');
  }
}

async function revealOpenedTask() {
  if (!openedTask || !$('#detail-user-answer').value.trim()) return;
  $('#detail-user-answer').blur();
  const id = openedTask.id;
  const current = detailRequestId;
  $('#detail-user-answer').disabled = true;
  $('#detail-submit-answer').disabled = true;
  $('#detail-feedback').textContent = 'Ответ отправлен. Сверьте его с эталоном и решите, отмечать ли задачу.';
  $('#detail-feedback').hidden = false;
  $('#detail-solution-section').hidden = false;
  $('#detail-solution-title').textContent = openedTask.answer?.trim() || openedTask.has_solution ? 'Эталонные материалы' : 'Отметка о решении';
  $('#detail-answer').hidden = !openedTask.answer?.trim();
  if (openedTask.answer?.trim()) taskMath.renderMathText($('#detail-answer-text'), openedTask.answer);
  $('#detail-mark-solved').disabled = taskAlreadySolved;
  $('#detail-mark-solved').textContent = taskAlreadySolved ? 'Задача решена' : 'Отметить решённой';
  const solutionText = $('#detail-solution');
  if (!openedTask.has_solution) {
    solutionText.textContent = '';
    solutionText.hidden = true;
    return;
  }
  solutionText.hidden = false;
  solutionText.textContent = 'Загрузка решения…';
  try {
    const data = await getJson(`/tasks/${encodeURIComponent(id)}/solutions`);
    if (current !== detailRequestId) return;
    const solution = data.items?.find(item => item.is_verified || !item.is_generated);
    taskMath.renderMathText(solutionText, solution?.content?.trim() || 'Решение пока не добавлено.');
  } catch {
    if (current === detailRequestId) solutionText.textContent = 'Не удалось загрузить решение.';
  }
}

$('#detail-submit-answer').addEventListener('click', revealOpenedTask);
$('#detail-user-answer').addEventListener('keydown', event => {
  if (event.key === 'Enter') revealOpenedTask();
});
$('#detail-mark-solved').addEventListener('click', async () => {
  if (!openedTask || $('#detail-solution-section').hidden) return;
  const button = $('#detail-mark-solved');
  button.disabled = true;
  try {
    const response = await fetch(`/api/progress/tasks/${encodeURIComponent(openedTask.id)}/solved`, {method:'POST'});
    if (response.status === 401) { location.href = loginUrl(); return; }
    if (!response.ok) throw new Error();
    taskAlreadySolved = true;
    button.textContent = 'Задача решена';
  } catch {
    button.disabled = false;
    $('#detail-feedback').textContent = 'Не удалось сохранить решение. Попробуйте ещё раз.';
  }
});

function showTaskPage() {
  searchScreen.hidden = true;
  taskPage.hidden = false;
  window.scrollTo(0, 0);
}

function showSearchPage() {
  detailRequestId++;
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
$('#subject-select').addEventListener('change', event => { state.subject = event.target.value; state.classifiers = []; loadClassifiers(); loadTasks(); });
$('#sort-select').addEventListener('change', event => { state.sort = event.target.value; loadTasks(); });
$('[data-od-id="open-filters"]').addEventListener('click', () => { $('#grade-filter').value = state.grade; filterOlympiadId = state.olympiadId; filterOlympiadName = state.olympiadName; $('#olympiad-search').value = ''; $('#olympiad-options').hidden = true; updateOlympiadSelection(); $('#difficulty-min').value = state.difficultyMin; $('#difficulty-max').value = state.difficultyMax; filterClassifiers = new Set(state.classifiers); $('#classifier-search').value = ''; if (classifiersStatus === 'Не удалось загрузить теги.') loadClassifiers(); else renderClassifiers(); dialog.showModal(); });
$('[data-od-id="close-filters"]').addEventListener('click', () => dialog.close());
$('[data-od-id="reset-filters"]').addEventListener('click', () => { $('#grade-filter').value = ''; filterOlympiadId = ''; filterOlympiadName = ''; $('#olympiad-search').value = ''; $('#olympiad-options').hidden = true; updateOlympiadSelection(); $('#difficulty-min').value = ''; $('#difficulty-max').value = ''; filterClassifiers.clear(); renderClassifiers(); });
$('[data-od-id="apply-filters"]').addEventListener('click', () => {
  const min = $('#difficulty-min').value, max = $('#difficulty-max').value;
  if (min && max && Number(min) > Number(max)) { $('#difficulty-min').setCustomValidity('Минимум больше максимума'); $('#difficulty-min').reportValidity(); return; }
  $('#difficulty-min').setCustomValidity('');
  state.grade = $('#grade-filter').value;
  state.olympiadId = filterOlympiadId;
  state.olympiadName = filterOlympiadName;
  state.difficultyMin = min;
  state.difficultyMax = max;
  state.classifiers = [...filterClassifiers];
  dialog.close();
  loadTasks();
});
$('#empty-action').addEventListener('click', () => { state.q = ''; state.grade = ''; state.olympiadId = ''; state.olympiadName = ''; state.difficultyMin = ''; state.difficultyMax = ''; state.classifiers = []; query.value = ''; loadTasks(); });
$('#load-more').addEventListener('click', () => { state.page += 1; loadTasks(true); });
list.addEventListener('click', event => {
  const open = event.target.closest('[data-open]');
  if (open) {
    event.preventDefault();
    openTask(open.dataset.open);
  }
});
$('#task-back').addEventListener('click', () => {
  if (history.state?.taskId) history.back();
  else { history.pushState({}, '', '/'); showSearchPage(); }
});
window.addEventListener('popstate', routeFromLocation);
routeFromLocation();
if (!/^\/tasks\/[^/]+\/?$/.test(location.pathname)) loadTasks();
loadClassifiers();

function renderClassifiers(message = classifiersStatus) {
  const options = $('#classifier-options');
  options.replaceChildren();
  if (message) {
    const status = document.createElement('p');
    status.className = 'classifier-status';
    status.textContent = message;
    options.append(status);
    return;
  }
  const needle = $('#classifier-search').value.trim().toLocaleLowerCase('ru');
  const matching = classifiers.filter(value => value.toLocaleLowerCase('ru').includes(needle));
  matching.sort((a, b) => Number(filterClassifiers.has(b)) - Number(filterClassifiers.has(a)));
  for (const classifier of matching) {
    const label = document.createElement('label');
    label.className = 'classifier-option';
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.value = classifier;
    input.checked = filterClassifiers.has(classifier);
    const name = document.createElement('span');
    name.textContent = classifier;
    label.append(input, name);
    options.append(label);
  }
  if (!matching.length) {
    const status = document.createElement('p');
    status.className = 'classifier-status';
    status.textContent = needle ? 'Теги не найдены' : 'Для этого предмета тегов пока нет';
    options.append(status);
  }
}

async function loadClassifiers() {
  const current = ++classifierRequestId;
  classifiersStatus = 'Загрузка тегов…';
  renderClassifiers();
  try {
    const data = await getJson(`/tasks/classifiers?subject=${encodeURIComponent(state.subject)}`);
    if (current !== classifierRequestId) return;
    classifiers = data.items || [];
    classifiersStatus = '';
    renderClassifiers();
  } catch {
    if (current !== classifierRequestId) return;
    classifiers = [];
    classifiersStatus = 'Не удалось загрузить теги.';
    renderClassifiers();
  }
}

$('#classifier-search').addEventListener('input', () => renderClassifiers());
$('#classifier-options').addEventListener('change', event => {
  if (!event.target.matches('input[type="checkbox"]')) return;
  if (event.target.checked) filterClassifiers.add(event.target.value);
  else filterClassifiers.delete(event.target.value);
});

function updateOlympiadSelection() {
  const selection = $('#olympiad-selection');
  selection.hidden = !filterOlympiadId;
  $('#olympiad-selection-name').textContent = filterOlympiadName;
  $('#olympiad-search').placeholder = filterOlympiadId ? 'Найти другую олимпиаду' : 'Поиск по названию';
}

function renderOlympiadOptions(search = '') {
  const options = $('#olympiad-options');
  const needle = search.trim().toLocaleLowerCase('ru');
  const matching = olympiads.filter(olympiad => !needle || `${olympiad.short_name || ''} ${olympiad.name}`.toLocaleLowerCase('ru').includes(needle));
  options.replaceChildren();
  const addOption = (label, fullName, id) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'olympiad-option';
    button.setAttribute('role', 'option');
    button.setAttribute('aria-selected', String(Boolean(id && id === filterOlympiadId)));
    button.dataset.id = id;
    button.dataset.name = label;
    const shortLabel = document.createElement('strong');
    shortLabel.textContent = label;
    button.append(shortLabel);
    if (fullName && fullName !== label) {
      const fullLabel = document.createElement('small');
      fullLabel.textContent = fullName;
      button.append(fullLabel);
    }
    options.append(button);
  };
  addOption('Все олимпиады', '', '');
  for (const olympiad of matching) {
    addOption(olympiad.short_name || olympiad.name, olympiad.name, olympiad.id);
  }
  if (!matching.length) {
    const message = document.createElement('p');
    message.className = 'olympiad-empty';
    message.textContent = 'Олимпиады не найдены';
    options.append(message);
  }
  options.hidden = false;
  $('#olympiad-search').setAttribute('aria-expanded', 'true');
}

const olympiadSearch = $('#olympiad-search');
olympiadSearch.addEventListener('focus', () => renderOlympiadOptions(olympiadSearch.value));
olympiadSearch.addEventListener('input', () => renderOlympiadOptions(olympiadSearch.value));
$('#olympiad-options').addEventListener('click', event => {
  const option = event.target.closest('.olympiad-option');
  if (!option) return;
  filterOlympiadId = option.dataset.id;
  filterOlympiadName = option.dataset.name === 'Все олимпиады' ? '' : option.dataset.name;
  olympiadSearch.value = '';
  $('#olympiad-options').hidden = true;
  olympiadSearch.setAttribute('aria-expanded', 'false');
  updateOlympiadSelection();
});
$('#clear-olympiad').addEventListener('click', () => {
  filterOlympiadId = '';
  filterOlympiadName = '';
  updateOlympiadSelection();
});
document.addEventListener('click', event => {
  if (!event.target.closest('.olympiad-picker')) {
    $('#olympiad-options').hidden = true;
    olympiadSearch.setAttribute('aria-expanded', 'false');
  }
});

getJson('/olympiads').then(data => {
  olympiads = (data.items || []).map(item => ({...item, short_name:item.short_name || ''}));
}).catch(() => {});
