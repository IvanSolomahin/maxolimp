<script setup lang="ts">
import { ref, watch } from "vue";
import { useRoute, RouterLink } from "vue-router";
import { olympiadApi, type Olympiad, type Stage } from "../lib/api";
import StatusBox from "../components/StatusBox.vue";
const route = useRoute();
const item = ref<Olympiad | null>(null);
const stages = ref<Stage[]>([]);
const status = ref<"loading" | "error" | "ready">("loading");
async function load() {
  const id = Number(route.params.id);
  status.value = "loading";
  item.value = null;
  stages.value = [];
  try {
    item.value = await olympiadApi.detail(id);
    status.value = "ready";
    try {
      stages.value = (await olympiadApi.stages(id)).items;
    } catch {
      stages.value = [];
    }
  } catch {
    status.value = "error";
  }
}
watch(() => route.params.id, load, { immediate: true });
</script>
<template>
  <div class="content-page">
    <RouterLink class="back-link" to="/olympiads"
      >← К результатам подбора</RouterLink
    ><StatusBox v-if="status === 'loading'" state="loading" /><StatusBox
      v-else-if="status === 'error'"
      state="error"
      @retry="load"
    /><template v-else-if="item"
      ><div class="detail-hero">
        <p class="eyebrow">Олимпиада</p>
        <h1>{{ item.name }}</h1>
        <p>{{ item.description || "Описание пока не добавлено." }}</p>
        <div class="detail-pills">
          <span class="pill">Сложность {{ item.complexity }}/5</span
          ><span
            v-for="subject in item.subjects"
            :key="subject.id"
            class="pill"
            >{{ subject.name }}</span
          >
        </div>
      </div>
      <div class="detail-columns">
        <section class="panel">
          <p class="eyebrow">Организатор</p>
          <h2>{{ item.host_university.name }}</h2>
          <p>
            Для актуальных условий участия проверьте официальный сайт олимпиады.
          </p>
        </section>
        <section class="panel">
          <p class="eyebrow">Этапы</p>
          <h2>Расписание</h2>
          <p v-if="!stages.length">Этапы пока не указаны.</p>
          <div v-for="stage in stages" :key="stage.id" class="stage-row">
            <strong>{{ stage.name }}</strong
            ><span
              >{{ new Date(stage.start_date).toLocaleDateString("ru-RU") }} ·
              {{
                stage.is_online
                  ? "онлайн"
                  : stage.location || "место уточняется"
              }}</span
            >
          </div>
        </section>
      </div>
      <div class="callout">
        <div>
          <h2>Готовы потренироваться?</h2>
          <p>
            Задачи из общего каталога помогут закрепить знания. Привязка к этой
            олимпиаде пока недоступна.
          </p>
        </div>
        <RouterLink class="button button-dark" to="/tasks"
          >Открыть задачи ↗</RouterLink
        >
      </div></template
    >
  </div>
</template>
