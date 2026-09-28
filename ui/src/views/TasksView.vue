<script setup lang="ts">
import { ref, watch, onMounted } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { taskApi, type TaskListItem } from "../lib/api";
import StatusBox from "../components/StatusBox.vue";
import MathText from "../components/MathText.vue";
const route = useRoute();
const router = useRouter();
const query = ref(String(route.query.q || ""));
const subject = ref(String(route.query.subject || "math"));
const sort = ref(String(route.query.sort || "relevance"));
const grade = ref(String(route.query.grade || ""));
const olympiadId = ref(String(route.query.olympiad_id || ""));
const difficultyMin = ref(String(route.query.difficulty_min || ""));
const difficultyMax = ref(String(route.query.difficulty_max || ""));
const olympiads = ref<{ id: string; name: string }[]>([]);
const items = ref<TaskListItem[]>([]);
const total = ref(0);
const page = ref(1);
const status = ref<"loading" | "error" | "ready">("loading");
let request = 0;
let timer: ReturnType<typeof setTimeout>;
async function load(append = false) {
  const current = ++request;
  status.value = "loading";
  if (!append) {
    page.value = 1;
    items.value = [];
  }
  const params = new URLSearchParams({
    subject: subject.value,
    sort: sort.value,
    page: String(page.value),
    size: "20",
  });
  if (query.value.trim()) params.set("q", query.value.trim());
  if (grade.value) params.set("grade", grade.value);
  if (olympiadId.value) params.set("olympiad_id", olympiadId.value);
  if (difficultyMin.value) params.set("difficulty_min", difficultyMin.value);
  if (difficultyMax.value) params.set("difficulty_max", difficultyMax.value);
  void router.replace({
    query: Object.fromEntries(
      [...params].filter(([key]) => key !== "page" && key !== "size"),
    ),
  });
  try {
    const data = await taskApi.list(params);
    if (current === request) {
      items.value = append ? [...items.value, ...data.items] : data.items;
      total.value = data.total;
      status.value = "ready";
    }
  } catch {
    if (current === request) status.value = "error";
  }
}
function loadMore() {
  page.value++;
  void load(true);
}
watch(query, () => {
  clearTimeout(timer);
  timer = setTimeout(() => load(), 300);
});
watch(
  [subject, sort, grade, olympiadId, difficultyMin, difficultyMax],
  () => void load(),
);
onMounted(() => {
  void load();
  void taskApi
    .olympiads()
    .then((data) => {
      olympiads.value = data.items;
    })
    .catch(() => {});
});
</script>
<template>
  <div class="content-page">
    <div class="page-intro">
      <p class="eyebrow">Каталог задач</p>
      <h1>Найдите задачу<span class="accent-mark">.</span></h1>
      <p>
        Фильтруйте по предмету, олимпиаде и сложности. Каждая задача открывается
        по отдельной ссылке.
      </p>
    </div>
    <div class="search-panel">
      <div class="search-row">
        <input
          v-model="query"
          type="search"
          class="input search-input"
          placeholder="Название или тема задачи"
          aria-label="Поиск задач"
        /><select v-model="subject" class="select" aria-label="Предмет">
          <option value="math">Математика</option>
          <option value="physics">Физика</option></select
        ><select v-model="sort" class="select" aria-label="Сортировка">
          <option value="relevance">По релевантности</option>
          <option value="newest">Сначала новые</option>
          <option value="difficulty">По сложности</option>
        </select>
      </div>
      <div class="filter-row">
        <label
          >Класс
          <select v-model="grade" class="select">
            <option value="">Любой</option>
            <option
              v-for="n in [5, 6, 7, 8, 9, 10, 11]"
              :key="n"
              :value="String(n)"
            >
              {{ n }}
            </option>
          </select></label
        ><label
          >Олимпиада
          <select v-model="olympiadId" class="select">
            <option value="">Любая</option>
            <option v-for="item in olympiads" :key="item.id" :value="item.id">
              {{ item.name }}
            </option>
          </select></label
        ><label
          >Сложность от
          <input
            v-model="difficultyMin"
            class="number-input"
            type="number"
            min="1"
            max="10" /></label
        ><label
          >до
          <input
            v-model="difficultyMax"
            class="number-input"
            type="number"
            min="1"
            max="10"
        /></label>
      </div>
    </div>
    <div class="list-heading">
      <h2>
        Результаты <span>{{ total }}</span>
      </h2>
      <RouterLink class="text-button" to="/practice"
        >Режим тренировки ↗</RouterLink
      >
    </div>
    <StatusBox
      v-if="status === 'loading' && !items.length"
      state="loading"
    /><StatusBox
      v-else-if="status === 'error'"
      state="error"
      @retry="load()"
    /><StatusBox
      v-else-if="!items.length"
      state="empty"
      title="Задачи не найдены"
      message="Попробуйте изменить запрос или фильтры."
    />
    <div v-else class="task-list">
      <RouterLink
        v-for="item in items"
        :key="item.id"
        :to="`/tasks/${item.id}`"
        class="task-list-item"
        ><div>
          <span class="eyebrow"
            >{{
              item.olympiad_short_name || item.olympiad || "Олимпиадная задача"
            }}
            <template v-if="item.number">· № {{ item.number }}</template></span
          >
          <h3><MathText :text="item.title" /></h3>
          <p><MathText :text="item.snippet || ''" /></p>
        </div>
        <div class="task-list-side">
          <span v-if="item.difficulty != null" class="pill"
            >{{ item.difficulty }}/10</span
          ><span class="arrow">↗</span>
        </div></RouterLink
      >
    </div>
    <button
      v-if="items.length < total && status === 'ready'"
      class="button button-outline load-more"
      @click="loadMore"
    >
      Показать ещё
    </button>
  </div>
</template>
