const TASKS = [
  {
    topic: "Динамическое программирование",
    diff: "Средняя",
    title: "Размен монет",
    statement:
      "Сколькими способами можно набрать сумму 6, используя монеты номиналом 1, 2 и 5 (порядок монет не важен)?",
    answer: "5",
    solution:
      "Перебираем число монет номинала 5. Без пятёрки остаются четыре разложения: 1+1+1+1+1+1, 2+1+1+1+1, 2+2+1+1 и 2+2+2. С одной пятёркой остаётся 1. Всего 5 способов.",
    hint: "Постройте ДП по достижимым суммам, добавляя монеты по одному номиналу за раз — так каждая комбинация посчитается ровно один раз.",
  },
  {
    topic: "Динамическое программирование",
    diff: "Средняя",
    title: "Наибольшая возрастающая подпоследовательность",
    statement:
      "Найдите длину наибольшей возрастающей подпоследовательности в массиве: 5, 2, 8, 6, 3, 6, 9, 7.",
    answer: "4",
    hint: "Заведите dp[i] — длину НВП, заканчивающейся в элементе i, и пересчитывайте её по всем j < i с меньшим значением.",
  },

  {
    topic: "Графы и алгоритмы на графах",
    diff: "Лёгкая",
    title: "Остовное дерево",
    statement:
      "В связном графе 7 вершин и 9 рёбер. Сколько рёбер нужно удалить, чтобы получить остовное дерево?",
    answer: "3",
    hint: "Остовное дерево на n вершинах содержит ровно n − 1 ребро.",
  },
  {
    topic: "Графы и алгоритмы на графах",
    diff: "Средняя",
    title: "Раскраска цикла",
    statement:
      "Каково минимальное число цветов, необходимое для раскраски вершин цикла из 5 вершин так, чтобы соседние вершины были разного цвета?",
    answer: "3",
    hint: "Циклы нечётной длины нельзя раскрасить в два цвета — понадобится третий.",
  },

  {
    topic: "Структуры данных",
    diff: "Лёгкая",
    title: "Стек",
    statement:
      "В пустой стек добавили элементы 1, 2, 3, затем дважды выполнили pop. Какой элемент теперь на вершине?",
    answer: "1",
    hint: "Стек работает по принципу LIFO — последний добавленный выходит первым.",
  },
  {
    topic: "Структуры данных",
    diff: "Средняя",
    title: "Дерево отрезков",
    statement:
      "Массив состоит из 8 элементов. Сколько узлов обычно выделяют под дерево отрезков при стандартной реализации массивом размера 4n?",
    answer: "32",
    hint: "Стандартная оценка размера массива под дерево отрезков — 4 · n.",
  },

  {
    topic: "Строки",
    diff: "Лёгкая",
    title: "Различные биграммы",
    statement:
      'Сколько различных подстрок длины 2 встречается в строке "abab"?',
    answer: "2",
    hint: "Переберите все позиции i от 0 до len−2 и соберите уникальные пары соседних символов.",
  },
  {
    topic: "Строки",
    diff: "Лёгкая",
    title: "Общий префикс",
    statement:
      'Какова длина наибольшего общего префикса строк "flower" и "flow"?',
    answer: "4",
    hint: "Сравнивайте символы посимвольно, пока они совпадают, и считайте количество совпадений.",
  },

  {
    topic: "Жадные алгоритмы и потоки",
    diff: "Лёгкая",
    title: "Размен монет жадно",
    statement:
      "Монеты номиналом 1, 5 и 10. Какое минимальное число монет жадным алгоритмом нужно, чтобы набрать сумму 18?",
    answer: "5",
    hint: "На каждом шаге берите монету наибольшего номинала, не превышающую остаток суммы.",
  },
  {
    topic: "Жадные алгоритмы и потоки",
    diff: "Средняя",
    title: "Покрытие отрезков точками",
    statement:
      "Даны отрезки [1,3], [2,5], [4,6], [6,8]. Какое минимальное число точек нужно расставить, чтобы каждый отрезок содержал хотя бы одну точку?",
    answer: "2",
    hint: "Отсортируйте отрезки по правому концу и жадно ставьте точку в конец текущего непокрытого отрезка.",
  },

  {
    topic: "Комбинаторика и теория вероятностей",
    diff: "Лёгкая",
    title: "Рассадка за круглым столом",
    statement:
      "Сколькими способами можно рассадить 4 различных человек за круглым столом, если рассадки, отличающиеся поворотом, считаются одинаковыми?",
    answer: "6",
    hint: "Число рассадок по кругу равно (n − 1)!.",
  },
  {
    topic: "Комбинаторика и теория вероятностей",
    diff: "Средняя",
    title: "Сумма на двух кубиках",
    statement:
      "Бросают два игральных кубика. Сколько существует пар значений, дающих в сумме 7?",
    answer: "6",
    hint: "Переберите все пары (a, b) от 1 до 6 и посчитайте те, где a + b = 7.",
  },

  {
    topic: "Теория чисел",
    diff: "Лёгкая",
    title: "НОД",
    statement: "Чему равен НОД чисел 48 и 18?",
    answer: "6",
    hint: "Используйте алгоритм Евклида: НОД(a, b) = НОД(b, a mod b).",
  },
  {
    topic: "Теория чисел",
    diff: "Лёгкая",
    title: "Простые числа",
    statement: "Сколько простых чисел меньше 20?",
    answer: "8",
    hint: "Переберите числа от 2 до 19 и проверьте каждое на делимость на числа меньше него.",
  },

  {
    topic: "Геометрия",
    diff: "Лёгкая",
    title: "Площадь треугольника",
    statement:
      "Чему равна площадь треугольника с вершинами (0,0), (4,0) и (0,3)?",
    answer: "6",
    hint: "Для прямоугольного треугольника площадь равна половине произведения катетов.",
  },
  {
    topic: "Геометрия",
    diff: "Лёгкая",
    title: "Расстояние между точками",
    statement: "Чему равно расстояние между точками (1,1) и (4,5)?",
    answer: "5",
    hint: "Используйте формулу расстояния: √((x₂−x₁)² + (y₂−y₁)²).",
  },
];

const params = new URLSearchParams(location.search);
const topicParam = params.get("topic");
const topicNames = [...new Set(TASKS.map((t) => t.topic))];
const selectedTopic =
  topicParam !== null && topicNames[Number(topicParam)]
    ? topicNames[Number(topicParam)]
    : null;
const queue = selectedTopic
  ? TASKS.filter((t) => t.topic === selectedTopic)
  : TASKS;

let index = 0;
let hintShown = false;
let checked = false;

const els = {
  progressLabel: document.getElementById("progress-label"),
  progressTopic: document.getElementById("progress-topic"),
  progressValue: document.getElementById("progress-value"),
  taskTopic: document.getElementById("task-topic"),
  taskDiff: document.getElementById("task-diff"),
  taskTitle: document.getElementById("task-title"),
  taskStatement: document.getElementById("task-statement"),
  answerInput: document.getElementById("answer-input"),
  checkButton: document.getElementById("check-button"),
  feedback: document.getElementById("feedback"),
  solutionCard: document.getElementById("solution-card"),
  hintToggle: document.getElementById("hint-toggle"),
  hintText: document.getElementById("hint-text"),
  nextButton: document.getElementById("next-button"),
};

function render() {
  const task = queue[index];
  els.progressLabel.textContent = `Задание ${index + 1} из ${queue.length}`;
  els.progressTopic.textContent = selectedTopic || "Все темы";
  els.progressValue.style.width =
    Math.round(((index + 1) / queue.length) * 100) + "%";

  els.taskTopic.textContent = task.topic;
  els.taskDiff.textContent = task.diff;
  els.taskTitle.textContent = task.title;
  els.taskStatement.textContent = task.statement;

  els.answerInput.value = "";
  els.answerInput.disabled = false;
  els.feedback.hidden = true;
  els.feedback.className = "feedback";
  els.solutionCard.hidden = true;
  document.getElementById("mark-solved").textContent = "Отметить решённой";
  document.getElementById("mark-solved").disabled = false;

  hintShown = false;
  checked = false;
  els.hintText.hidden = true;
  els.hintText.textContent = task.hint;
  els.hintToggle.textContent = "Показать подсказку";

  els.answerInput.focus();
}

function checkAnswer() {
  const given = els.answerInput.value.trim();
  if (!given || checked) return;
  checked = true;
  els.answerInput.disabled = true;
  els.checkButton.disabled = true;
  els.feedback.hidden = false;
  els.feedback.className = "feedback";
  els.feedback.textContent =
    "Ответ отправлен. Сверьте его с эталоном и отметьте задачу решённой.";
  document.getElementById("reference-answer").textContent = queue[index].answer;
  document.getElementById("reference-solution").textContent =
    queue[index].solution ||
    queue[index].hint ||
    "Решение для этой задачи пока не добавлено.";
  els.solutionCard.hidden = false;
}

els.checkButton.addEventListener("click", checkAnswer);
els.answerInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") checkAnswer();
});

els.hintToggle.addEventListener("click", () => {
  hintShown = !hintShown;
  els.hintText.hidden = !hintShown;
  els.hintToggle.textContent = hintShown
    ? "Скрыть подсказку"
    : "Показать подсказку";
});

document.getElementById("mark-solved").addEventListener("click", (e) => {
  const key = "maxolimp-solved";
  const solved = JSON.parse(localStorage.getItem(key) || "[]");
  const taskKey = queue[index].title;
  if (!solved.includes(taskKey)) solved.push(taskKey);
  localStorage.setItem(key, JSON.stringify(solved));
  e.currentTarget.textContent = "Задача решена";
  e.currentTarget.disabled = true;
});

els.nextButton.addEventListener("click", () => {
  index = (index + 1) % queue.length;
  els.checkButton.disabled = false;
  render();
});

document
  .getElementById("back-button")
  .addEventListener("click", () => history.back());

render();
