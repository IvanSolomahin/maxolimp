<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, RouterLink } from "vue-router";
import { taskApi, type TaskDetail, type Solution } from "../lib/api";
import { markSolved, solvedTasks } from "../lib/storage";
import StatusBox from "../components/StatusBox.vue";
import MathText from "../components/MathText.vue";
const route = useRoute();
const task = ref<TaskDetail | null>(null);
const solution = ref<Solution | null>(null);
const status = ref<"loading" | "error" | "ready">("loading");
const submitted = ref(false);
const answer = ref("");
const solutionError = ref(false);
const solutionLoaded = ref(false);
const marked = ref(false);
const hasReference = computed(() =>
  Boolean(task.value?.answer?.trim() || task.value?.has_solution),
);
let request = 0;
async function load() {
  const current = ++request;
  const id = String(route.params.id);
  task.value = null;
  solution.value = null;
  submitted.value = false;
  answer.value = "";
  solutionError.value = false;
  solutionLoaded.value = false;
  status.value = "loading";
  try {
    const result = await taskApi.detail(id);
    if (current !== request) return;
    task.value = result;
    marked.value = solvedTasks().some((item) => item.id === id);
    status.value = "ready";
  } catch {
    if (current === request) status.value = "error";
  }
}
async function submit() {
  if (!answer.value.trim() || !task.value) return;
  submitted.value = true;
  if (task.value.has_solution) {
    const current = request;
    solutionError.value = false;
    try {
      const data = await taskApi.solutions(task.value.id);
      if (current === request)
        solution.value =
          data.items.find((item) => item.is_verified || !item.is_generated) ||
          null;
    } catch {
      if (current === request) solutionError.value = true;
    } finally {
      if (current === request) solutionLoaded.value = true;
    }
  }
}
function solve() {
  if (!task.value || !submitted.value) return;
  markSolved(task.value);
  marked.value = true;
}
watch(() => route.params.id, load, { immediate: true });
</script>
<template>
  <div class="content-page task-detail">
    <RouterLink to="/tasks" class="back-link">← К поиску задач</RouterLink
    ><StatusBox v-if="status === 'loading'" state="loading" /><StatusBox
      v-else-if="status === 'error'"
      state="error"
      @retry="load"
    /><template v-else-if="task"
      ><div class="detail-hero">
        <p class="eyebrow">
          Задача
          <template v-if="task.source.number"
            >№ {{ task.source.number }}</template
          >
        </p>
        <h1><MathText :text="task.title" /></h1>
        <div class="detail-pills">
          <span v-if="task.subject" class="pill">{{
            task.subject === "math"
              ? "Математика"
              : task.subject === "physics"
                ? "Физика"
                : task.subject
          }}</span
          ><span v-if="task.grade" class="pill">{{ task.grade }} класс</span
          ><span v-if="task.difficulty != null" class="pill"
            >Сложность {{ task.difficulty }}/10</span
          ><span
            v-for="olympiad in task.olympiads"
            :key="olympiad.id"
            class="pill"
            >{{ olympiad.short_name || olympiad.name }}</span
          >
        </div>
      </div>
      <div class="detail-columns">
        <section class="panel statement">
          <p class="eyebrow">Условие</p>
          <div class="statement-text">
            <MathText :text="task.statement || 'Условие не указано'" />
          </div>
          <a
            v-if="
              task.source.url?.startsWith('https://') ||
              task.source.url?.startsWith('http://')
            "
            class="text-button"
            :href="task.source.url"
            target="_blank"
            rel="noopener noreferrer"
            >Первоисточник ↗</a
          >
        </section>
        <section class="panel answer-panel">
          <p class="eyebrow">Ваш ответ</p>
          <h2>Попробуйте решить сами</h2>
          <p>
            После отправки покажем доступные эталонные материалы. Ответ не
            оценивается автоматически.
          </p>
          <form v-if="!submitted" @submit.prevent="submit">
            <label class="field-label" for="answer">Ответ</label
            ><textarea
              id="answer"
              v-model="answer"
              class="textarea"
              rows="4"
              placeholder="Введите ваш ответ"
            ></textarea
            ><button class="button button-dark" :disabled="!answer.trim()">
              Отправить ответ
            </button>
          </form>
          <template v-else
            ><div class="notice">
              Ответ отправлен. Сравните его с эталоном и сами решите, отметить
              ли задачу решённой.
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
            <p v-if="!hasReference">Эталонные материалы пока не добавлены.</p>
            <button
              class="button button-lime"
              :disabled="marked"
              @click="solve"
            >
              {{ marked ? "Отмечено решённой" : "Отметить решённой" }}
            </button></template
          >
        </section>
      </div></template
    >
  </div>
</template>
