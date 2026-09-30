const state = {period: 'week', olympiadId: '', tag: ''};
const $ = selector => document.querySelector(selector);
const demoMode = new URLSearchParams(location.search).get('demo') === '1';
const authHref = `./olympiad-auth.html?next=${encodeURIComponent(location.pathname + location.search)}`;
let archivePage = 1;
let archiveTotal = 0;
let refreshId = 0;
const formatDay = (iso, options = {}) => new Date(iso).toLocaleDateString('ru-RU', {timeZone: 'Europe/Moscow', ...options});
const dayKey = date => date.toISOString().slice(0, 10);
const taskWord = count => count % 10 === 1 && count % 100 !== 11 ? 'задача' : count % 10 >= 2 && count % 10 <= 4 && (count % 100 < 12 || count % 100 > 14) ? 'задачи' : 'задач';

const demoOlympiads = [
  {id: 'math', name: 'Высшая проба'},
  {id: 'physics', name: 'Физтех'},
  {id: 'informatics', name: 'ВсОШ'},
];
const demoTags = ['Алгебра', 'Геометрия', 'Комбинаторика', 'Механика', 'Теория чисел'];
const demoTitles = [
  'Неравенство для положительных чисел', 'Площади в треугольнике', 'Размещения с ограничениями',
  'Движение по наклонной плоскости', 'Делимость и остатки', 'Система уравнений',
  'Окружности и касательные', 'Подсчёт путей', 'Законы сохранения', 'Простые числа',
];
const demoOffsets = [0, 0, 1, 2, 2, 2, 3, 4, 4, 5, 6, 6, 8, 9, 11, 14, 18, 20, 23, 27, 32, 37, 43, 51, 63, 74, 90, 110, 130, 155, 185, 217, 250, 292, 320];
const demoTasks = demoOffsets.map((offset, index) => {
  const solved = new Date();
  solved.setHours(12, 0, 0, 0);
  solved.setDate(solved.getDate() - offset);
  const olympiad = demoOlympiads[index % demoOlympiads.length];
  const tag = demoTags[index % demoTags.length];
  return {id: `demo-${index}`, title: demoTitles[index % demoTitles.length], olympiad_id: olympiad.id, olympiad: olympiad.name, tags: [tag], solved_at: solved.toISOString()};
});

function demoResponse(path) {
  const [resource, search = ''] = path.split('?');
  const params = new URLSearchParams(search);
  const period = params.get('period') || 'week';
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const matches = demoTasks.filter(item => (!params.get('olympiad_id') || item.olympiad_id === params.get('olympiad_id')) && (!params.get('tag') || item.tags.includes(params.get('tag'))));
  const buckets = [];
  if (period === 'year') {
    for (let offset = 11; offset >= 0; offset--) {
      const from = new Date(today.getFullYear(), today.getMonth() - offset, 1);
      const to = new Date(today.getFullYear(), today.getMonth() - offset + 1, 1);
      buckets.push({from: from.toISOString(), to: to.toISOString(), count: matches.filter(item => new Date(item.solved_at) >= from && new Date(item.solved_at) < to).length});
    }
  } else {
    const days = period === 'month' ? 30 : 7;
    for (let offset = days - 1; offset >= 0; offset--) {
      const from = new Date(today);
      from.setDate(from.getDate() - offset);
      const to = new Date(from);
      to.setDate(to.getDate() + 1);
      buckets.push({from: from.toISOString(), to: to.toISOString(), count: matches.filter(item => new Date(item.solved_at) >= from && new Date(item.solved_at) < to).length});
    }
  }
  const from = buckets[0].from;
  const to = buckets.at(-1).to;
  const periodTasks = matches.filter(item => new Date(item.solved_at) >= new Date(from) && new Date(item.solved_at) < new Date(to));
  if (resource === '/solved') {
    const page = Number(params.get('page') || 1);
    const size = Number(params.get('size') || 20);
    return {total: periodTasks.length, items: periodTasks.slice((page - 1) * size, page * size)};
  }
  const by_olympiad = demoOlympiads.map(item => ({...item, count: periodTasks.filter(task => task.olympiad_id === item.id).length})).filter(item => item.count).sort((a, b) => b.count - a.count);
  const by_tag = demoTags.map(tag => ({tag, name: tag, count: periodTasks.filter(task => task.tags.includes(tag)).length})).filter(item => item.count).sort((a, b) => b.count - a.count);
  return {period, from, to, total_period: periodTasks.length, total_all_time: matches.length, active_days: new Set(periodTasks.map(item => dayKey(new Date(item.solved_at)))).size, buckets, by_olympiad, by_tag};
}

async function api(path) {
  if (demoMode) return demoResponse(path);
  let response = await fetch(`/api/progress${path}`);
  if (response.status === 401) {
    await window.maxUserReady;
    response = await fetch(`/api/progress${path}`);
    if (response.status === 401) { location.href = authHref; return null; }
  }
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function query() {
  const params = new URLSearchParams({period: state.period});
  if (state.olympiadId) params.set('olympiad_id', state.olympiadId);
  if (state.tag) params.set('tag', state.tag);
  return params;
}

function archiveRow(item) {
  const root = document.createElement('div');
  root.className = 'row';
  const icon = document.createElement('span');
  icon.className = 'rank';
  icon.textContent = '✓';
  icon.setAttribute('aria-hidden', 'true');
  const copy = document.createElement('div');
  copy.className = 'row-copy';
  const name = document.createElement(demoMode ? 'p' : 'a');
  name.className = 'row-title';
  name.textContent = item.title;
  if (!demoMode) name.href = `/tasks/${encodeURIComponent(item.id)}`;
  const sub = document.createElement('p');
  sub.className = 'row-sub';
  sub.textContent = [item.olympiad, item.tags?.join(', '), formatDay(item.solved_at)].filter(Boolean).join(' · ');
  copy.append(name, sub);
  root.append(icon, copy);
  return root;
}

function breakdownRow(item, total) {
  const root = document.createElement('div');
  root.className = 'breakdown-row';
  const name = document.createElement('span');
  name.className = 'row-title';
  name.textContent = item.name;
  const count = document.createElement('strong');
  count.className = 'count';
  count.textContent = item.count;
  const track = document.createElement('div');
  track.className = 'progress-track';
  const fill = document.createElement('span');
  fill.className = 'progress-fill';
  fill.style.setProperty('--share', `${Math.round(item.count / Math.max(total, 1) * 100)}%`);
  track.append(fill);
  root.append(name, count, track);
  return root;
}

function fillOptions(select, items, defaultLabel, value, label, selected) {
  select.replaceChildren(new Option(defaultLabel, ''));
  items.forEach(item => select.add(new Option(label(item), value(item))));
  select.value = selected;
  if (select.value !== selected) select.value = '';
  return select.value;
}

function render(stats, archive) {
  $('#period-count').textContent = stats.total_period;
  $('#period-unit').textContent = ` ${taskWord(stats.total_period)}`;
  $('#chart-count').textContent = stats.total_period;
  $('#chart-unit').textContent = taskWord(stats.total_period);
  $('#all-count').textContent = stats.total_all_time;
  $('#active-days').textContent = stats.active_days;
  $('#period-caption').textContent = {week: 'за последние 7 дней', month: 'за последние 30 дней', year: 'за последние 12 месяцев'}[state.period];
  $('#chart-period-label').textContent = state.period === 'year' ? 'По месяцам за год' : `По дням за ${state.period === 'week' ? 'неделю' : 'месяц'}`;
  $('#chart-from').textContent = formatDay(stats.from, {day: 'numeric', month: 'short'});
  $('#chart-to').textContent = formatDay(new Date(new Date(stats.to).getTime() - 1), {day: 'numeric', month: 'short'});
  const max = Math.max(1, ...stats.buckets.map(item => item.count));
  $('#chart').replaceChildren(...stats.buckets.map((item, index) => {
    const wrap = document.createElement('div');
    wrap.className = 'bar-wrap';
    const bar = document.createElement('div');
    bar.className = `bar${item.count === max && item.count ? ' peak' : ''}${index === stats.buckets.length - 1 ? ' today' : ''}`;
    bar.style.setProperty('--h', `${Math.round(item.count / max * 100)}%`);
    const date = formatDay(item.from, state.period === 'year' ? {month: 'long', year: 'numeric'} : {day: 'numeric', month: 'long'});
    bar.title = `${date}: ${item.count} ${taskWord(item.count)}`;
    const label = document.createElement('span');
    label.className = 'bar-label';
    label.textContent = state.period === 'year' ? formatDay(item.from, {month: 'short'}) : state.period === 'week' ? formatDay(item.from, {weekday: 'short'}) : (index % 5 === 0 || index === stats.buckets.length - 1 ? formatDay(item.from, {day: 'numeric'}) : '');
    wrap.append(bar, label);
    return wrap;
  }));
  $('#chart').setAttribute('aria-label', `Решено ${stats.total_period} ${taskWord(stats.total_period)}. ${stats.buckets.map(item => `${formatDay(item.from, state.period === 'year' ? {month: 'long'} : {day: 'numeric', month: 'long'})}: ${item.count}`).join('; ')}`);
  const olympiadList = $('#olympiad-breakdown');
  olympiadList.replaceChildren(...stats.by_olympiad.map(item => breakdownRow(item, stats.total_period)));
  if (!stats.by_olympiad.length) olympiadList.textContent = 'Пока нет решений за этот период';
  olympiadList.classList.toggle('inline-empty', !stats.by_olympiad.length);
  const tags = document.createElement('div');
  tags.className = 'tags';
  stats.by_tag.forEach(item => {
    const span = document.createElement('span');
    span.className = 'tag';
    span.textContent = item.name;
    const count = document.createElement('b');
    count.textContent = item.count;
    span.append(count);
    tags.append(span);
  });
  const tagList = $('#tag-breakdown');
  tagList.replaceChildren(...(stats.by_tag.length ? [tags] : [document.createTextNode('Пока нет тем за этот период')]));
  tagList.classList.toggle('inline-empty', !stats.by_tag.length);
  $('#solved-list').replaceChildren(...archive.items.map(archiveRow));
  $('#empty').hidden = archive.total > 0;
  $('#solved-list').hidden = archive.total === 0;
  archivePage = 1;
  archiveTotal = archive.total;
  $('#solved-more').hidden = archive.items.length >= archiveTotal;
  document.querySelectorAll('[data-period]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.period === state.period)));
}

async function refresh() {
  const requestId = ++refreshId;
  try {
    const options = await api(`/statistics?period=${state.period}`);
    if (!options || requestId !== refreshId) return;
    state.olympiadId = fillOptions($('#olympiad-filter'), options.by_olympiad.filter(item => item.id), 'Все олимпиады', item => item.id, item => item.name, state.olympiadId);
    state.tag = fillOptions($('#tag-filter'), options.by_tag.filter(item => item.tag), 'Все теги', item => item.tag, item => item.name, state.tag);
    const params = query();
    const [stats, archive] = await Promise.all([api(`/statistics?${params}`), api(`/solved?${params}&size=20&page=1`)]);
    if (!stats || !archive || requestId !== refreshId) return;
    render(stats, archive);
  } catch {
    if (requestId === refreshId) $('#period-caption').textContent = 'Не удалось загрузить статистику. Обновите страницу.';
  }
}

document.querySelectorAll('[data-period]').forEach(button => button.addEventListener('click', () => { state.period = button.dataset.period; refresh(); }));
$('#olympiad-filter').addEventListener('change', event => { state.olympiadId = event.target.value; refresh(); });
$('#tag-filter').addEventListener('change', event => { state.tag = event.target.value; refresh(); });
$('#solved-more').addEventListener('click', async () => {
  const button = $('#solved-more');
  button.disabled = true;
  try {
    const next = archivePage + 1;
    const data = await api(`/solved?${query()}&size=20&page=${next}`);
    if (!data) return;
    archivePage = next;
    $('#solved-list').append(...data.items.map(archiveRow));
    button.hidden = $('#solved-list').children.length >= archiveTotal;
  } catch { button.textContent = 'Не удалось загрузить. Повторить'; }
  finally { button.disabled = false; }
});
if (demoMode) $('#demo-badge').hidden = false;
refresh();
