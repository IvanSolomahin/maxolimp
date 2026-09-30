const els = {
  progressLabel: document.getElementById('progress-label'),
  progressTopic: document.getElementById('progress-topic'),
  progressValue: document.getElementById('progress-value'),
  taskTopic: document.getElementById('task-topic'),
  taskDiff: document.getElementById('task-diff'),
  taskTitle: document.getElementById('task-title'),
  taskStatement: document.getElementById('task-statement'),
  answerInput: document.getElementById('answer-input'),
  feedback: document.getElementById('feedback'),
  solutionCard: document.getElementById('solution-card'),
  nextButton: document.getElementById('next-button'),
};

// === Проверка решения нейросетью ===
const solutionFile = document.getElementById('solution-file');
const checkSolutionBtn = document.getElementById('check-solution-button');
const checkStatus = document.getElementById('solution-check-status');
const checkResult = document.getElementById('solution-check-result');

let queue = [];
let index = 0;
let task = null;
let renderVersion = 0;

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
    return response.ok;
  } catch {
    return false;
  }
}

async function render() {
  const version = ++renderVersion;
  if (!queue.length) { showError('Задачи пока не найдены.'); return; }
  const current = queue[index];
  els.progressLabel.textContent = `Задание ${index + 1} из ${queue.length}`;
  els.progressTopic.textContent = 'Задачи из базы';
  els.progressValue.style.width = `${Math.round((index + 1) / queue.length * 100)}%`;
  els.taskTitle.textContent = 'Загрузка задачи…';
  els.answerInput.value = '';
  els.answerInput.disabled = true;
  solutionFile.disabled = true;
  checkSolutionBtn.disabled = true;
  els.solutionCard.hidden = true;
  els.feedback.hidden = true;
  resetCheckUi();
  task = null;
  try {
    const detail = await getJson(`/tasks/${encodeURIComponent(current.id)}`);
    if (version !== renderVersion) return;
    task = detail;
    els.taskTopic.textContent = detail.tags?.join(' · ') || detail.olympiads?.[0]?.name || 'Задача';
    els.taskDiff.textContent = detail.difficulty == null ? '' : `Сложность ${detail.difficulty} / 10`;
    els.taskTitle.textContent = detail.title;
    els.taskStatement.textContent = detail.statement;
    taskMath.renderMathText(els.taskTitle, detail.title);
    taskMath.renderMathText(els.taskStatement, detail.statement);
    els.answerInput.disabled = false;
    solutionFile.disabled = false;
    checkSolutionBtn.disabled = false;
  } catch {
    if (version === renderVersion) showError('Не удалось загрузить задачу. Попробуйте следующую.');
  }
}

async function showReferenceSolution() {
  if (!task) return;
  const submitted = task;
  const version = renderVersion;
  const answer = document.getElementById('reference-answer');
  const solution = document.getElementById('reference-solution');
  answer.textContent = submitted.answer || '';
  if (submitted.answer) taskMath.renderMathText(answer, submitted.answer);
  answer.previousElementSibling.hidden = !submitted.answer;
  answer.hidden = !submitted.answer;
  solution.textContent = '';
  solution.previousElementSibling.hidden = !submitted.has_solution;
  solution.hidden = !submitted.has_solution;
  els.solutionCard.hidden = !submitted.answer && !submitted.has_solution;
  if (submitted.has_solution) {
    solution.textContent = 'Загрузка решения…';
    try {
      const data = await getJson(`/tasks/${encodeURIComponent(submitted.id)}/solutions`);
      if (version !== renderVersion) return;
      const item = data.items?.find(value => value.is_verified) || data.items?.[0];
      solution.textContent = item?.content || 'Решение пока не добавлено.';
      if (item?.content) taskMath.renderMathText(solution, item.content);
    } catch {
      if (version === renderVersion) solution.textContent = 'Не удалось загрузить решение.';
    }
  }
}

// === Отправка решения на проверку нейросетью ===
async function submitSolutionForCheck() {
  if (!task || checkSolutionBtn.disabled) return;

  const file = solutionFile?.files?.[0];
  const answerText = els.answerInput.value.trim();
  if (!file && !answerText) {
    checkStatus.textContent = 'Напишите решение или приложите файл.';
    checkStatus.hidden = false;
    return;
  }

  const form = new FormData();
  if (file) form.append('file', file);
  if (answerText) form.append('answer_text', answerText);

  checkSolutionBtn.disabled = true;
  els.answerInput.disabled = true;
  solutionFile.disabled = true;
  els.answerInput.blur();
  els.feedback.hidden = true;
  els.solutionCard.hidden = true;
  checkStatus.textContent = 'Проверяем решение…';
  checkStatus.hidden = false;
  checkResult.hidden = true;
  checkResult.textContent = '';

  const taskId = task.id;
  const version = renderVersion;

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
    if (version !== renderVersion) return;

    checkStatus.textContent = 'Проверка завершена.';
    checkResult.textContent = data.result || 'Разбор не получен.';
    checkResult.hidden = false;

    const verdict = data.verdict === 0 ? 0 : 1;
    await showReferenceSolution();
    if (version !== renderVersion) return;

    if (verdict === 0) {
      const saved = await saveSolvedProgress(taskId);
      if (version !== renderVersion) return;
      showError(saved
        ? 'Задача зачтена. Прогресс сохранён.'
        : 'Задача зачтена, но не удалось сохранить прогресс.');
    } else {
      showError('Решение не зачтено. Сверьтесь с эталоном и попробуйте ещё раз.');
    }
  } catch (error) {
    if (version === renderVersion) checkStatus.textContent = `Ошибка проверки: ${error.message}`;
  } finally {
    if (version === renderVersion) {
      checkSolutionBtn.disabled = false;
      els.answerInput.disabled = false;
      solutionFile.disabled = false;
    }
  }
}

checkSolutionBtn.addEventListener('click', submitSolutionForCheck);

els.nextButton.addEventListener('click', () => { if (queue.length) { index = (index + 1) % queue.length; render(); } });
document.getElementById('back-button').addEventListener('click', () => history.back());

getJson('/tasks?subject=math&size=100').then(data => { queue = data.items || []; render(); }).catch(() => showError('Не удалось загрузить список задач.'));
