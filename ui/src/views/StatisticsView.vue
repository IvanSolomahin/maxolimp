<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { legacySolved, solvedTasks, type SolvedTask } from "../lib/storage";
const tasks = ref<SolvedTask[]>([]);
const legacy = ref<string[]>([]);
const legacyOnly = computed(() =>
  legacy.value.filter(
    (name) => !tasks.value.some((task) => task.title === name),
  ),
);
const period = ref<"week" | "month" | "year">("week");
const olympiad = ref("");
const tag = ref("");
function refresh() {
  tasks.value = solvedTasks();
  legacy.value = legacySolved();
}
onMounted(() => {
  refresh();
  window.addEventListener("maxolimp:solved", refresh);
});
onUnmounted(() => window.removeEventListener("maxolimp:solved", refresh));
const periodDays = computed(() =>
  period.value === "week" ? 7 : period.value === "month" ? 30 : 365,
);
const olympiads = computed(() =>
  [...new Set(tasks.value.flatMap((x) => x.olympiads))].sort(),
);
const tags = computed(() =>
  [...new Set(tasks.value.flatMap((x) => x.tags))].sort(),
);
const filtered = computed(() =>
  tasks.value.filter(
    (x) =>
      (!olympiad.value || x.olympiads.includes(olympiad.value)) &&
      (!tag.value || x.tags.includes(tag.value)),
  ),
);
const recent = computed(() => {
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  start.setDate(start.getDate() - periodDays.value + 1);
  return filtered.value.filter((x) => new Date(x.solvedAt) >= start);
});
const buckets = computed(() => {
  const count = period.value === "week" ? 7 : period.value === "month" ? 6 : 12;
  const span = period.value === "week" ? 1 : period.value === "month" ? 5 : 31;
  return Array.from({ length: count }, (_, i) => {
    const end = new Date();
    end.setHours(23, 59, 59, 999);
    end.setDate(end.getDate() - (count - 1 - i) * span);
    const start = new Date(end);
    start.setHours(0, 0, 0, 0);
    start.setDate(start.getDate() - span + 1);
    return {
      label: start.toLocaleDateString("ru-RU", {
        day: "numeric",
        month: period.value === "year" ? "short" : undefined,
      }),
      value: recent.value.filter((x) => {
        const date = new Date(x.solvedAt);
        return date >= start && date <= end;
      }).length,
    };
  });
});
const maxBucket = computed(() =>
  Math.max(1, ...buckets.value.map((x) => x.value)),
);
const activeDays = computed(
  () =>
    new Set(recent.value.map((x) => new Date(x.solvedAt).toDateString())).size,
);
const byOlympiad = computed(() =>
  countGroups(recent.value.flatMap((x) => x.olympiads)),
);
const byTag = computed(() => countGroups(recent.value.flatMap((x) => x.tags)));
function countGroups(values: string[]) {
  const counts = new Map<string, number>();
  values.forEach((x) => counts.set(x, (counts.get(x) || 0) + 1));
  return [...counts].sort((a, b) => b[1] - a[1]);
}
</script>
<template>
  <div class="content-page">
    <div class="page-intro">
      <p class="eyebrow">Ваш прогресс</p>
      <h1>Статистика<span class="accent-mark">.</span></h1>
      <p>
        Учитываются только задачи, которые вы отметили решёнными. Прогресс
        хранится на этом устройстве.
      </p>
    </div>
    <div class="filter-row stats-filters">
      <div class="filter-pills">
        <button :aria-pressed="period === 'week'" @click="period = 'week'">
          Неделя</button
        ><button :aria-pressed="period === 'month'" @click="period = 'month'">
          Месяц</button
        ><button :aria-pressed="period === 'year'" @click="period = 'year'">
          Год
        </button>
      </div>
      <select
        v-model="olympiad"
        class="select"
        aria-label="Фильтр по олимпиаде"
      >
        <option value="">Все олимпиады</option>
        <option v-for="name in olympiads" :key="name">
          {{ name }}
        </option></select
      ><select v-model="tag" class="select" aria-label="Фильтр по теме">
        <option value="">Все темы</option>
        <option v-for="name in tags" :key="name">{{ name }}</option>
      </select>
    </div>
    <div class="stats-grid">
      <article class="stat-card primary">
        <p>За период</p>
        <strong>{{ recent.length }}</strong
        ><span>решённых задач</span>
      </article>
      <article class="stat-card">
        <p>Всего на устройстве</p>
        <strong>{{ tasks.length + legacyOnly.length }}</strong
        ><span>включая старый архив</span>
      </article>
      <article class="stat-card">
        <p>Активных дней</p>
        <strong>{{ activeDays }}</strong
        ><span>за выбранный период</span>
      </article>
    </div>
    <section class="panel stats-section">
      <div class="panel-top">
        <div>
          <p class="eyebrow">Динамика</p>
          <h2>Решения по времени</h2>
        </div>
      </div>
      <div
        v-if="recent.length"
        class="chart"
        role="img"
        :aria-label="`Решено за период: ${recent.length}`"
      >
        <div v-for="(bucket, i) in buckets" :key="i" class="chart-column">
          <div
            class="chart-bar"
            :style="{
              height: `${Math.max(5, (bucket.value / maxBucket) * 100)}%`,
            }"
            :title="`${bucket.value} задач`"
          ></div>
          <small>{{ bucket.label }}</small>
        </div>
      </div>
      <p v-else class="muted">За выбранный период нет отметок о решении.</p>
    </section>
    <div class="detail-columns">
      <section class="panel">
        <p class="eyebrow">Разрезы</p>
        <h2>По олимпиадам</h2>
        <p v-if="!byOlympiad.length" class="muted">Нет данных по олимпиадам.</p>
        <div v-for="[name, count] in byOlympiad" :key="name" class="count-row">
          <span>{{ name }}</span
          ><strong>{{ count }}</strong>
        </div>
      </section>
      <section class="panel">
        <p class="eyebrow">Разрезы</p>
        <h2>По темам</h2>
        <p v-if="!byTag.length" class="muted">Нет данных по темам.</p>
        <div v-for="[name, count] in byTag" :key="name" class="count-row">
          <span>{{ name }}</span
          ><strong>{{ count }}</strong>
        </div>
      </section>
    </div>
    <section class="panel stats-section">
      <div class="panel-top">
        <div>
          <p class="eyebrow">Архив</p>
          <h2>Решённые задачи</h2>
        </div>
        <RouterLink to="/tasks" class="text-button">Найти ещё ↗</RouterLink>
      </div>
      <p v-if="!tasks.length && !legacyOnly.length" class="muted">
        Пока нет решённых задач. Откройте задачу и отметьте её после сравнения
        ответа.
      </p>
      <RouterLink
        v-for="item in [...tasks].reverse()"
        :key="item.id"
        :to="`/tasks/${item.id}`"
        class="archive-row"
        ><span>{{ item.title }}</span
        ><small>{{
          new Date(item.solvedAt).toLocaleDateString("ru-RU")
        }}</small></RouterLink
      ><template v-if="legacyOnly.length"
        ><p class="eyebrow legacy-heading">Старые отметки · дата неизвестна</p>
        <div v-for="name in legacyOnly" :key="name" class="archive-row legacy">
          <span>{{ name }}</span
          ><small>из старого архива</small>
        </div></template
      >
    </section>
  </div>
</template>
