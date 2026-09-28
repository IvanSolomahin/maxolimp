const state = {period: 'week', olympiadId: '', tag: ''};
const $ = selector => document.querySelector(selector);
const authHref = `./olympiad-auth.html?next=${encodeURIComponent(location.pathname + location.search)}`;
let archivePage = 1;
let archiveTotal = 0;
const formatDay = (iso, options = {}) => new Date(iso).toLocaleDateString('ru-RU', {timeZone:'Europe/Moscow', ...options});

async function api(path) {
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

function row(title, subtitle, count, href) {
  const root = document.createElement('div');
  root.className = 'row';
  const rank = document.createElement('span');
  rank.className = 'rank';
  rank.textContent = '✓';
  const copy = document.createElement('div');
  copy.className = 'row-copy';
  const name = document.createElement(href ? 'a' : 'p');
  name.className = 'row-title';
  name.textContent = title;
  if (href) name.href = href;
  const sub = document.createElement('p');
  sub.className = 'row-sub';
  sub.textContent = subtitle || '';
  copy.append(name, sub);
  root.append(rank, copy);
  if (count !== undefined) {
    const number = document.createElement('b');
    number.className = 'count';
    number.textContent = count;
    root.append(number);
  }
  return root;
}

function fillOptions(select, items, defaultLabel, value, label, selected) {
  select.replaceChildren(new Option(defaultLabel, ''));
  items.forEach(item => select.add(new Option(label(item), value(item))));
  select.value = selected;
  if (select.value !== selected) select.value = '';
  return select.value;
}

async function loadOptions() {
  const data = await api(`/statistics?period=${state.period}`);
  if (!data) return;
  state.olympiadId = fillOptions($('#olympiad-filter'), data.by_olympiad.filter(item => item.id), 'Все олимпиады', item => item.id, item => item.name, state.olympiadId);
  state.tag = fillOptions($('#tag-filter'), data.by_tag.filter(item => item.tag), 'Все теги', item => item.tag, item => item.name, state.tag);
}

async function loadStats() {
  const params = query();
  const [stats, archive] = await Promise.all([api(`/statistics?${params}`), api(`/solved?${params}&size=20&page=1`)]);
  if (!stats || !archive) return;
  $('#period-count').textContent = stats.total_period;
  $('#chart-count').textContent = stats.total_period;
  $('#all-count').textContent = stats.total_all_time;
  $('#active-days').textContent = stats.active_days;
  $('#active-days').nextElementSibling.textContent = 'за выбранный период';
  $('#period-caption').textContent = {week:'за последние 7 дней', month:'за последние 30 дней', year:'за последние 12 месяцев'}[state.period];
  $('.chart-total strong').nextSibling.textContent = ` за ${state.period === 'week' ? 'неделю' : state.period === 'month' ? 'месяц' : 'год'}`;
  $('#chart-from').textContent = formatDay(stats.from);
  $('#chart-to').textContent = formatDay(new Date(new Date(stats.to).getTime() - 1));
  const max = Math.max(1, ...stats.buckets.map(item => item.count));
  $('#chart').replaceChildren(...stats.buckets.map(item => {
    const wrap = document.createElement('div');
    wrap.className = 'bar-wrap';
    const bar = document.createElement('div');
    bar.className = 'bar';
    bar.style.setProperty('--h', `${Math.round(item.count / max * 100)}%`);
    bar.title = `${item.count} задач`;
    const label = document.createElement('span');
    label.className = 'bar-label';
    label.textContent = formatDay(item.from, state.period === 'year' ? {month:'short'} : {day:'numeric', month:'numeric'});
    wrap.append(bar, label);
    return wrap;
  }));
  const groups = document.querySelectorAll('.breakdown .list-card');
  groups[0].replaceChildren(...stats.by_olympiad.map(item => row(item.name, '', item.count)));
  const tags = document.createElement('div');
  tags.className = 'tags';
  stats.by_tag.forEach(item => {
    const span = document.createElement('span');
    span.className = 'tag';
    span.textContent = `${item.name} `;
    const count = document.createElement('b');
    count.textContent = item.count;
    span.append(count);
    tags.append(span);
  });
  groups[1].replaceChildren(tags);
  $('#solved-list').replaceChildren(...archive.items.map(item => row(item.title, `${item.olympiad || item.tag || 'Задача'} · ${formatDay(item.solved_at)}`, undefined, `/tasks/${encodeURIComponent(item.id)}`)));
  $('#empty').hidden = archive.total > 0;
  $('#solved-list').hidden = archive.total === 0;
  archivePage = 1;
  archiveTotal = archive.total;
  $('#solved-more').hidden = archive.items.length >= archiveTotal;
  document.querySelectorAll('[data-period]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.period === state.period)));
}

async function refresh() {
  try { await loadOptions(); await loadStats(); }
  catch { $('#period-caption').textContent = 'Не удалось загрузить статистику. Обновите страницу.'; }
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
    $('#solved-list').append(...data.items.map(item => row(item.title, `${item.olympiad || item.tag || 'Задача'} · ${formatDay(item.solved_at)}`, undefined, `/tasks/${encodeURIComponent(item.id)}`)));
    button.hidden = $('#solved-list').children.length >= archiveTotal;
  } catch { button.textContent = 'Не удалось загрузить. Повторить'; }
  finally { button.disabled = false; }
});
$('#period-count').textContent = '—';
$('#chart-count').textContent = '—';
$('#all-count').textContent = '—';
$('#active-days').textContent = '—';
$('#chart').replaceChildren();
document.querySelectorAll('.breakdown .list-card').forEach(element => element.replaceChildren());
$('#solved-list').replaceChildren();
$('#empty').hidden = true;
refresh();
