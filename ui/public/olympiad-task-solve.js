const els = {
  progressLabel: document.getElementById('progress-label'),
  progressTopic: document.getElementById('progress-topic'),
  progressValue: document.getElementById('progress-value'),
  taskTopic: document.getElementById('task-topic'),
  taskDiff: document.getElementById('task-diff'),
  taskTitle: document.getElementById('task-title'),
  taskStatement: document.getElementById('task-statement'),
  answerInput: document.getElementById('answer-input'),
  checkButton: document.getElementById('check-button'),
  feedback: document.getElementById('feedback'),
  solutionCard: document.getElementById('solution-card'),
  hintToggle: document.getElementById('hint-toggle'),
  nextButton: document.getElementById('next-button'),
  markSolved: document.getElementById('mark-solved'),
};

let queue = [];
let index = 0;
let task = null;
let solved = false;

async function getJson(path) {
  const response = await fetch(`/api/tasks${path}`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

function showError(message) {
  els.feedback.textContent = message;
  els.feedback.hidden = false;
}

async function render() {
  if (!queue.length) { showError('Задачи пока не найдены.'); return; }
  const current = queue[index];
  els.progressLabel.textContent = `Задание ${index + 1} из ${queue.length}`;
  els.progressTopic.textContent = 'Задачи из базы';
  els.progressValue.style.width = `${Math.round((index + 1) / queue.length * 100)}%`;
  els.taskTitle.textContent = 'Загрузка задачи…';
  els.answerInput.value = '';
  els.answerInput.disabled = true;
  els.checkButton.disabled = true;
  els.solutionCard.hidden = true;
  els.feedback.hidden = true;
  els.hintToggle.hidden = true;
  document.getElementById('hint-text').hidden = true;
  solved = false;
  task = null;
  try {
    const detail = await getJson(`/tasks/${encodeURIComponent(current.id)}`);
    if (queue[index].id !== current.id) return;
    task = detail;
    els.taskTopic.textContent = detail.classifier || detail.olympiads?.[0]?.name || 'Задача';
    els.taskDiff.textContent = detail.difficulty == null ? '' : `Сложность ${detail.difficulty} / 10`;
    els.taskTitle.textContent = detail.title;
    els.taskStatement.textContent = detail.statement;
    taskMath.renderMathText(els.taskTitle, detail.title);
    taskMath.renderMathText(els.taskStatement, detail.statement);
    els.answerInput.disabled = false;
    els.checkButton.disabled = false;
    els.answerInput.focus();
    let response = await fetch(`/api/progress/tasks/${encodeURIComponent(detail.id)}`);
    if (response.status === 401) {
      await window.maxUserReady;
      response = await fetch(`/api/progress/tasks/${encodeURIComponent(detail.id)}`);
    }
    if (response.ok) solved = (await response.json()).solved;
  } catch {
    showError('Не удалось загрузить задачу. Попробуйте следующую.');
  }
}

async function submitAnswer() {
  if (!task || !els.answerInput.value.trim() || els.checkButton.disabled) return;
  const submitted = task;
  els.answerInput.disabled = true;
  els.checkButton.disabled = true;
  showError('Ответ отправлен. Сверьте его с эталоном и решите, отмечать ли задачу.');
  const answer = document.getElementById('reference-answer');
  const solution = document.getElementById('reference-solution');
  answer.textContent = submitted.answer || '';
  if (submitted.answer) taskMath.renderMathText(answer, submitted.answer);
  answer.previousElementSibling.hidden = !submitted.answer;
  answer.hidden = !submitted.answer;
  solution.textContent = '';
  solution.previousElementSibling.hidden = !submitted.has_solution;
  solution.hidden = !submitted.has_solution;
  els.markSolved.disabled = solved;
  els.markSolved.textContent = solved ? 'Задача решена' : 'Отметить решённой';
  els.solutionCard.hidden = false;
  if (submitted.has_solution) {
    solution.textContent = 'Загрузка решения…';
    try {
      const data = await getJson(`/tasks/${encodeURIComponent(submitted.id)}/solutions`);
      if (task?.id !== submitted.id) return;
      const item = data.items?.find(value => value.is_verified || !value.is_generated);
      solution.textContent = item?.content || 'Решение пока не добавлено.';
      if (item?.content) taskMath.renderMathText(solution, item.content);
    } catch {
      solution.textContent = 'Не удалось загрузить решение.';
    }
  }
}

els.checkButton.addEventListener('click', submitAnswer);
els.answerInput.addEventListener('keydown', event => { if (event.key === 'Enter') submitAnswer(); });
els.markSolved.addEventListener('click', async () => {
  if (!task || els.solutionCard.hidden) return;
  els.markSolved.disabled = true;
  try {
    const response = await fetch(`/api/progress/tasks/${encodeURIComponent(task.id)}/solved`, {method:'POST'});
    if (response.status === 401) {
      location.href = `./olympiad-auth.html?next=${encodeURIComponent(location.pathname + location.search)}`;
      return;
    }
    if (!response.ok) throw new Error();
    solved = true;
    els.markSolved.textContent = 'Задача решена';
  } catch {
    els.markSolved.disabled = false;
    showError('Не удалось сохранить решение. Попробуйте ещё раз.');
  }
});
els.nextButton.addEventListener('click', () => { if (queue.length) { index = (index + 1) % queue.length; render(); } });
document.getElementById('back-button').addEventListener('click', () => history.back());

getJson('/tasks?subject=math&size=100').then(data => { queue = data.items || []; render(); }).catch(() => showError('Не удалось загрузить список задач.'));
