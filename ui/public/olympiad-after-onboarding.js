const list = document.getElementById('topics-list');
const totals = document.getElementById('totals-num');

async function loadTasks() {
  const params = new URLSearchParams({subject: 'math', page: '1', size: '20'});
  list.textContent = 'Загружаем задачи…';
  try {
    const response = await fetch(`/api/tasks/tasks?${params}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    totals.textContent = data.total;
    if (!data.items.length) {
      list.textContent = 'В банке пока нет опубликованных задач.';
      return;
    }
    list.replaceChildren(...data.items.map(task => {
      const card = document.createElement('article');
      card.className = 'topic-card';
      const heading = document.createElement('div');
      heading.className = 'topic-head';
      const title = document.createElement('h2');
      title.textContent = task.title;
      const snippet = document.createElement('p');
      snippet.textContent = task.snippet || '';
      const meta = document.createElement('p');
      meta.className = 'topic-kicker';
      meta.textContent = [task.olympiad, task.difficulty == null ? '' : `Сложность ${task.difficulty} / 10`].filter(Boolean).join(' · ');
      heading.append(meta, title, snippet);
      const footer = document.createElement('div');
      footer.className = 'topic-foot';
      const link = document.createElement('a');
      link.className = 'start-btn';
      link.href = `/tasks/${encodeURIComponent(task.id)}`;
      link.textContent = 'Открыть задачу →';
      footer.append(link);
      card.append(heading, footer);
      return card;
    }));
  } catch {
    list.textContent = 'Не удалось загрузить задачи. Откройте банк задач и попробуйте ещё раз.';
  }
}

document.getElementById('back-button').addEventListener('click', () => history.back());
loadTasks();
