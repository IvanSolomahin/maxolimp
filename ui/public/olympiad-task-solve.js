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

// === Проверка решения нейросетью ===
const solutionFile = document.getElementById('solution-file');
const checkSolutionBtn = document.getElementById('check-solution-button');
const checkStatus = document.getElementById('solution-check-status');
const checkResult = document.getElementById('solution-check-result');

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

function resetCheckUi() {
  if (checkResult) {
    checkResult.hidden = true;
    checkResult.textContent = '';
  }
  if (checkStatus) {
    checkStatus.hidden = true;
    checkStatus.textContent = '';
  }
  if (solutionFile) solutionFile.value = '';
}

async function saveSolvedProgress(taskId) {
  try {
    let response = await fetch(
      `/api/progress/tasks/${encodeURIComponent(taskId)}/solved`,
      { method: 'POST' }
    );
    if (response.status === 401) {
      await window.maxUserReady;
      response = await fetch(
        `/api/progress/tasks/${encodeURIComponent(taskId)}/solved`,
        { method: 'POST' }
      );
    }
    if (response.ok) {
      solved = true;
      return true;
    }
    return false;
  } catch {
    return false;
  }
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
  if (els.markSolved) {
    els.markSolved.hidden = false;
    els.markSolved.disabled = false;
    els.markSolved.textContent = 'Отметить решённой';
  }
  resetCheckUi();
  solved = false;
  task = null;
  try {
    const detail = await getJson(`/tasks/${encodeURIComponent(current.id)}`);
    if (queue[index].id !== current.id) return;
    task = detail;
    els.taskTopic.textContent = detail.tags?.join(' · ') || detail.olympiads?.[0]?.name || 'Задача';
    els.taskDiff.textContent = detail.difficulty == null ? '' : `Сложность ${detail.difficulty} / 10`;
    els.taskTitle.textContent = detail.title;
    els.taskStatement.textContent = detail.statement;
    taskMath.renderMathText(els.taskTitle, detail.title);
    taskMath.renderMathText(els.taskStatement, detail.statement);
    els.answerInput.disabled = false;
    els.checkButton.disabled = false;
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
  els.answerInput.blur();
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
  if (els.markSolved) {
    els.markSolved.hidden = false;
    els.markSolved.disabled = solved;
    els.markSolved.textContent = solved ? 'Задача решена' : 'Отметить решённой';
  }
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

// === Отправка решения на проверку нейросетью ===
async function submitSolutionForCheck() {
  if (!task) return;

  const file = solutionFile?.files?.[0];
  if (!file) {
    checkStatus.textContent = 'Сначала загрузите файл с решением.';
    checkStatus.hidden = false;
    return;
  }

  const form = new FormData();
  form.append('file', file);

  checkSolutionBtn.disabled = true;
  checkStatus.textContent = 'Проверяем решение…';
  checkStatus.hidden = false;
  checkResult.hidden = true;
  checkResult.textContent = '';

  const taskId = task.id;

  try {
    let response = await fetch(
      `/api/tasks/${encodeURIComponent(taskId)}/check`,
      { method: 'POST', body: form }
    );

    if (response.status === 401) {
      await window.maxUserReady;
      response = await fetch(
        `/api/tasks/${encodeURIComponent(taskId)}/check`,
        { method: 'POST', body: form }
      );
      if (response.status === 401) {
        location.href = `./olympiad-auth.html?next=${encodeURIComponent(location.pathname + location.search)}`;
        return;
      }
    }

    const responseText = await response.text();
    let data = {};
    try {
      data = responseText ? JSON.parse(responseText) : {};
    } catch {
      throw new Error(
        `Backend вернул не JSON (${response.status}): ${responseText.slice(0, 300)}`
      );
    }
    if (!response.ok) throw new Error(data.detail || `HTTP ${response.status}`);

    checkStatus.textContent = 'Проверка завершена.';
    checkResult.textContent = data.result || 'Разбор не получен.';
    checkResult.hidden = false;

    // Ручную кнопку отметки убираем — решение проверено нейросетью
    if (els.markSolved) els.markSolved.hidden = true;

    const verdict = data.verdict === 0 ? 0 : 1;

    if (verdict === 0) {
      const saved = await saveSolvedProgress(taskId);
      showError(saved
        ? 'Задача зачтена. Прогресс сохранён.'
        : 'Задача зачтена, но не удалось сохранить прогресс.');
    } else {
      showError('Решение не зачтено. Сверьтесь с эталоном и попробуйте ещё раз.');
    }
  } catch (error) {
    checkStatus.textContent = `Ошибка проверки: ${error.message}`;
  } finally {
    checkSolutionBtn.disabled = false;
  }
}

els.checkButton.addEventListener('click', submitAnswer);
els.answerInput.addEventListener('keydown', event => { if (event.key === 'Enter') submitAnswer(); });

if (els.markSolved) {
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
}

if (checkSolutionBtn) {
  checkSolutionBtn.addEventListener('click', submitSolutionForCheck);
}

els.nextButton.addEventListener('click', () => { if (queue.length) { index = (index + 1) % queue.length; render(); } });
document.getElementById('back-button').addEventListener('click', () => history.back());

getJson('/tasks?subject=math&size=100').then(data => { queue = data.items || []; render(); }).catch(() => showError('Не удалось загрузить список задач.'));