const TOPICS = [
  {
    name: "Динамическое программирование",
    count: 40,
    subtopics: [
      "ДП по подотрезкам и профилю",
      "ДП по деревьям",
      "Оптимизация пересчёта: монотонный стек, СМО",
    ],
    tasks: [
      {
        name: "Наибольшая возрастающая подпоследовательность за O(n log n)",
        diff: "Средняя",
      },
      {
        name: "Разбиение строки на палиндромы минимальным числом разрезов",
        diff: "Средняя",
      },
      {
        name: "Рюкзак с ограничением по весу и количеству предметов",
        diff: "Лёгкая",
      },
      { name: "ДП по маске: коммивояжёр на 18 городах", diff: "Сложная" },
      {
        name: "Наибольшая общая подпоследовательность трёх строк",
        diff: "Сложная",
      },
    ],
  },
  {
    name: "Графы и алгоритмы на графах",
    count: 35,
    subtopics: [
      "Кратчайшие пути: Дейкстра, Флойд — Уоршелл",
      "Компоненты связности, мосты и точки сочленения",
      "LCA и разреженные таблицы",
    ],
    tasks: [
      {
        name: "Кратчайший путь с ограничением на число пересадок",
        diff: "Средняя",
      },
      { name: "Поиск мостов в графе дорог", diff: "Средняя" },
      { name: "LCA в дереве с оффлайн-запросами", diff: "Сложная" },
      { name: "Проверка графа на двудольность", diff: "Лёгкая" },
      {
        name: "Минимальное остовное дерево с запрещёнными рёбрами",
        diff: "Сложная",
      },
    ],
  },
  {
    name: "Структуры данных",
    count: 30,
    subtopics: [
      "Дерево отрезков и дерево Фенвика",
      "Система непересекающихся множеств",
      "Персистентные структуры",
    ],
    tasks: [
      { name: "Сумма на отрезке с точечными обновлениями", diff: "Лёгкая" },
      {
        name: "Количество различных чисел на отрезке (офлайн)",
        diff: "Средняя",
      },
      { name: "Динамическая связность через СНМ с откатами", diff: "Сложная" },
      {
        name: "K-я порядковая статистика в персистентном дереве",
        diff: "Сложная",
      },
      {
        name: "Массовое присваивание на отрезке с ленивыми обновлениями",
        diff: "Средняя",
      },
    ],
  },
  {
    name: "Строки",
    count: 25,
    subtopics: [
      "Z-функция и префикс-функция",
      "Алгоритм Ахо — Корасик",
      "Суффиксный массив",
    ],
    tasks: [
      {
        name: "Поиск всех вхождений образца в текст (Z-функция)",
        diff: "Лёгкая",
      },
      {
        name: "Поиск нескольких образцов сразу (Ахо — Корасик)",
        diff: "Средняя",
      },
      {
        name: "Наибольшая общая подстрока через суффиксный массив",
        diff: "Сложная",
      },
      { name: "Количество различных подстрок строки", diff: "Средняя" },
      { name: "Минимальный период строки", diff: "Лёгкая" },
    ],
  },
  {
    name: "Жадные алгоритмы и потоки",
    count: 20,
    subtopics: [
      "Максимальный поток",
      "Паросочетания",
      "Жадные доказательства через обмен",
    ],
    tasks: [
      {
        name: "Максимальное паросочетание в двудольном графе",
        diff: "Средняя",
      },
      { name: "Расписание задач с дедлайнами и штрафами", diff: "Лёгкая" },
      { name: "Максимальный поток минимальной стоимости", diff: "Сложная" },
      { name: "Покрытие отрезков минимальным числом точек", diff: "Лёгкая" },
    ],
  },
  {
    name: "Комбинаторика и теория вероятностей",
    count: 20,
    subtopics: [
      "Комбинаторика на путях и сетках",
      "Математическое ожидание",
      "Формула включений-исключений",
    ],
    tasks: [
      { name: "Число путей на сетке с препятствиями", diff: "Лёгкая" },
      { name: "Ожидаемое число ходов в случайном блуждании", diff: "Средняя" },
      {
        name: "Включения-исключения для чисел, не кратных набору простых",
        diff: "Средняя",
      },
      { name: "Число способов раскрасить граф в k цветов", diff: "Сложная" },
    ],
  },
  {
    name: "Теория чисел",
    count: 15,
    subtopics: [
      "Модулярная арифметика",
      "Решето Эратосфена и его модификации",
      "Китайская теорема об остатках",
    ],
    tasks: [
      { name: "Быстрое возведение в степень по модулю", diff: "Лёгкая" },
      { name: "Решение системы сравнений по модулю (КТО)", diff: "Средняя" },
      { name: "Подсчёт делителей на отрезке решетом", diff: "Средняя" },
      { name: "Дискретный логарифм baby-step giant-step", diff: "Сложная" },
    ],
  },
  {
    name: "Геометрия",
    count: 15,
    subtopics: [
      "Выпуклая оболочка",
      "Пересечение отрезков",
      "Работа с векторным произведением",
    ],
    tasks: [
      { name: "Построение выпуклой оболочки набора точек", diff: "Средняя" },
      { name: "Проверка пересечения двух отрезков", diff: "Лёгкая" },
      { name: "Площадь многоугольника по координатам вершин", diff: "Лёгкая" },
      { name: "Ближайшая пара точек за O(n log n)", diff: "Сложная" },
    ],
  },
];

const topicsList = document.getElementById("topics-list");
const dialog = document.getElementById("breakdown-dialog");

function render() {
  const totalCount = TOPICS.reduce((s, t) => s + t.count, 0);
  document.getElementById("totals-num").textContent = "≈ " + totalCount;
  document.getElementById("totals-topics").textContent = TOPICS.length;

  topicsList.innerHTML = "";
  TOPICS.forEach((topic, i) => {
    const card = document.createElement("article");
    card.className = "topic-card";
    card.innerHTML = `
          <div class="topic-head">
            <div><p class="topic-kicker">Тема ${i + 1}</p><h2>${topic.name}</h2></div>
            <span class="count-badge">≈ ${topic.count} заданий</span>
          </div>
          <div class="topic-foot">
            <button class="breakdown-btn" type="button" data-breakdown="${i}">Примеры заданий</button>
            <a class="start-btn" href="./olympiad-task-solve.html?topic=${i}">Начать решать</a>
          </div>`;

    card
      .querySelector("[data-breakdown]")
      .addEventListener("click", () => openTasks(topic));

    topicsList.appendChild(card);
  });
}

function openTasks(topic) {
  document.getElementById("sheet-title").textContent = topic.name;
  document.getElementById("sheet-sub").textContent =
    topic.subtopics.join(" · ");
  document.getElementById("sheet-total").textContent = topic.count;
  const list = document.getElementById("task-list");
  list.innerHTML = topic.tasks
    .map(
      (t, i) => `
        <li class="task-item">
          <input type="checkbox" id="task-${i}">
          <label class="task-row" for="task-${i}">
            <span class="task-check">✓</span>
            <span><span class="task-name">${t.name}</span><span class="task-diff">${t.diff}</span></span>
          </label>
        </li>`,
    )
    .join("");
  dialog.showModal();
}

document
  .getElementById("close-dialog")
  .addEventListener("click", () => dialog.close());
document
  .getElementById("back-button")
  .addEventListener("click", () => history.back());

render();
