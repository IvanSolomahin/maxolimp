<script setup lang="ts">
import { ref, watch, onMounted } from "vue";
import { RouterLink } from "vue-router";
import {
  taskApi,
  type TaskDetail,
  type TaskListItem,
  type Solution,
} from "../lib/api";
import { markSolved, solvedTasks } from "../lib/storage";
import StatusBox from "../components/StatusBox.vue";
import MathText from "../components/MathText.vue";
const subject = ref("math");
const queue = ref<TaskListItem[]>([]);
const total = ref(0);
const page = ref(1);
const index = ref(0);
const task = ref<TaskDetail | null>(null);
const status = ref<"loading" | "error" | "ready">("loading");
const answer = ref("");
const submitted = ref(false);
const marked = ref(false);
const solution = ref<Solution | null>(null);
const solutionError = ref(false);
const solutionLoaded = ref(false);
let request = 0;
async function loadQueue() {
  const current = ++request;
  status.value = "loading";
  queue.value = [];
  task.value = null;
  index.value = 0;
  page.value = 1;
  try {
    const data = await taskApi.list(
      new URLSearchParams({ subject: subject.value, page: "1", size: "20" }),
    );
    if (current !== request) return;
    queue.value = data.items;
    total.value = data.total;
    if (queue.value.length) await loadTask(0, current);
    else status.value = "ready";
  } catch {
    if (current === request) status.value = "error";
  }
}
async function loadTask(next: number, current = request) {
  status.value = "loading";
  task.value = null;
  answer.value = "";
  submitted.value = false;
  solution.value = null;
  solutionError.value = false;
  solutionLoaded.value = false;
  try {
    const item = await taskApi.detail(queue.value[next].id);
    if (current !== request) return;
    task.value = item;
    index.value = next;
    marked.value = solvedTasks().some((x) => x.id === item.id);
    status.value = "ready";
  } catch {
    if (current === request) status.value = "error";
  }
}
async function nextTask() {
  if (index.value + 1 < queue.value.length) return loadTask(index.value + 1);
  if (queue.value.length >= total.value) return loadTask(0);
  const current = request;
  status.value = "loading";
  page.value++;
  try {
    const data = await taskApi.list(
      new URLSearchParams({
        subject: subject.value,
        page: String(page.value),
        size: "20",
      }),
    );
    if (current !== request) return;
    queue.value.push(...data.items);
    if (data.items.length) await loadTask(index.value + 1, current);
    else status.value = "ready";
  } catch {
    if (current === request) status.value = "error";
  }
}
async function submit() {
  if (!answer.value.trim() || !task.value) return;
  submitted.value = true;
  if (task.value.has_solution) {
    solutionError.value = false;
    try {
      const data = await taskApi.solutions(task.value.id);
      solution.value =
        data.items.find((x) => x.is_verified || !x.is_generated) || null;
    } catch {
      solutionError.value = true;
    } finally {
      solutionLoaded.value = true;
    }
  }
}
function solve() {
  if (task.value && submitted.value) {
    markSolved(task.value);
    marked.value = true;
  }
}
watch(subject, loadQueue);
onMounted(loadQueue);
</script>
<template>
  <div class="content-page">
    <div class="page-intro">
      <p class="eyebrow">Практика</p>
      <h1>Решайте в своём темпе<span class="accent-mark">.</span></h1>
      <p>
        Задачи из каталога. Вы вводите ответ, сравниваете с эталоном и сами
        отмечаете результат.
      </p>
    </div>
    <div class="practice-toolbar">
      <label
        >Предмет
        <select v-model="subject" class="select">
          <option value="math">Математика</option>
          <option value="physics">Физика</option>
        </select></label
      ><span v-if="total">Задача {{ index + 1 }} из {{ total }}</span>
    </div>
    <StatusBox v-if="status === 'loading'" state="loading" /><StatusBox
      v-else-if="status === 'error'"
      state="error"
      @retry="loadQueue"
    /><StatusBox
      v-else-if="!queue.length"
      state="empty"
      title="Задач пока нет"
      message="Попробуйте другой предмет или вернитесь позже."
    />
    <div v-else-if="task" class="practice-card">
      <div class="practice-top">
        <span class="eyebrow">Задача {{ index + 1 }} / {{ total }}</span
        ><RouterLink :to="`/tasks/${task.id}`" class="text-button"
          >Открыть отдельно ↗</RouterLink
        >
      </div>
      <h2><MathText :text="task.title" /></h2>
      <p class="practice-statement"><MathText :text="task.statement" /></p>
      <form v-if="!submitted" @submit.prevent="submit">
        <label for="practice-answer" class="field-label">Ваш ответ</label
        ><textarea
          id="practice-answer"
          v-model="answer"
          class="textarea"
          rows="3"
          placeholder="Введите ответ"
        ></textarea
        ><button class="button button-dark" :disabled="!answer.trim()">
          Показать эталон
        </button>
      </form>
      <div v-else class="reference-stack">
        <div class="notice">
          Сравните свой ответ с эталоном. Автоматической проверки нет.
        </div>
        <div v-if="task.answer?.trim()" class="reference">
          <p class="eyebrow">Эталонный ответ</p>
          <MathText :text="task.answer" />
        </div>
        <div v-if="task.has_solution" class="reference">
          <p class="eyebrow">Решение</p>
          <MathText v-if="solution" :text="solution.content" />
          <p v-else-if="solutionError">
            Не удалось загрузить решение.
            <button class="text-button" @click="submit">Повторить</button>
          </p>
          <p v-else-if="solutionLoaded">Решение пока не добавлено.</p>
          <p v-else>Загрузка решения…</p>
        </div>
        <p v-if="!task.answer?.trim() && !task.has_solution">
          Эталонные материалы пока не добавлены.
        </p>
        <div class="practice-actions">
          <button class="button button-lime" :disabled="marked" @click="solve">
            {{ marked ? "Отмечено решённой" : "Отметить решённой" }}</button
          ><button class="button button-outline" @click="nextTask">
            Следующая задача →
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
