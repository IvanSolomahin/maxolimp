<script setup lang="ts">
import { ref, watch, onMounted } from "vue";
import { RouterLink } from "vue-router";
import StatusBox from "../components/StatusBox.vue";
import {
  olympiadApi,
  type Program,
  type Recommendation,
  type University,
} from "../lib/api";
import {
  favorites,
  getCriteria,
  saveCriteria,
  toggleFavorite,
} from "../lib/storage";

const stored = getCriteria();
const universityId = ref<number | null>(stored.university);
const programId = ref<number | null>(stored.program);
const universityQuery = ref("");
const programQuery = ref("");
const universities = ref<University[]>([]);
const programs = ref<Program[]>([]);
const recommendations = ref<Recommendation[]>([]);
const total = ref(0);
const page = ref(1);
const benefit = ref("all");
const favoriteIds = ref(favorites());
const stage = ref<"university" | "program" | "results">(
  stored.program ? "results" : stored.university ? "program" : "university",
);
const status = ref<"loading" | "error" | "ready">("loading");
let request = 0;
let timer: ReturnType<typeof setTimeout>;
function persist() {
  saveCriteria({ university: universityId.value, program: programId.value });
}
function benefitLabel(value: string) {
  if (value === "bvi" || value === "no entrance exams") return "БВИ";
  if (value === "100 points") return "100 баллов";
  if (value === "additional_points") return "Дополнительные баллы";
  return value;
}
async function loadUniversities() {
  const current = ++request;
  status.value = "loading";
  try {
    const data = await olympiadApi.universities(universityQuery.value);
    if (current === request) {
      universities.value = data.items;
      status.value = "ready";
    }
  } catch {
    if (current === request) status.value = "error";
  }
}
async function loadPrograms() {
  if (!universityId.value) return;
  const current = ++request;
  status.value = "loading";
  try {
    const data = await olympiadApi.programs(
      universityId.value,
      programQuery.value,
    );
    if (current === request) {
      programs.value = data.items;
      status.value = "ready";
    }
  } catch {
    if (current === request) status.value = "error";
  }
}
async function loadRecommendations(append = false) {
  if (!universityId.value || !programId.value) {
    stage.value = "university";
    return;
  }
  const current = ++request;
  status.value = "loading";
  if (!append) page.value = 1;
  const params = new URLSearchParams({
    university_id: String(universityId.value),
    program_id: String(programId.value),
    page: String(page.value),
    size: "20",
  });
  if (benefit.value !== "all") params.set("benefit_type", benefit.value);
  try {
    const data = await olympiadApi.recommendations(params);
    if (current === request) {
      recommendations.value = append
        ? [...recommendations.value, ...data.items]
        : data.items;
      total.value = data.total;
      status.value = "ready";
    }
  } catch {
    if (current === request) status.value = "error";
  }
}
function selectUniversity(id: number) {
  universityId.value = id;
  programId.value = null;
  persist();
  stage.value = "program";
  programQuery.value = "";
  void loadPrograms();
}
function selectProgram(id: number) {
  programId.value = id;
  persist();
  stage.value = "results";
  void loadRecommendations();
}
function changeStage(next: typeof stage.value) {
  stage.value = next;
  if (next === "university") void loadUniversities();
  if (next === "program") void loadPrograms();
  if (next === "results") void loadRecommendations();
}
function loadMore() {
  page.value++;
  void loadRecommendations(true);
}
function retry() {
  if (stage.value === "university") void loadUniversities();
  else if (stage.value === "program") void loadPrograms();
  else void loadRecommendations();
}
watch(universityQuery, () => {
  if (stage.value === "university") {
    clearTimeout(timer);
    timer = setTimeout(loadUniversities, 300);
  }
});
watch(programQuery, () => {
  if (stage.value === "program") {
    clearTimeout(timer);
    timer = setTimeout(loadPrograms, 300);
  }
});
watch(benefit, () => {
  if (stage.value === "results") void loadRecommendations();
});
onMounted(retry);
</script>
<template>
  <div class="content-page">
    <div class="page-intro">
      <p class="eyebrow">Ваш путь к поступлению</p>
      <h1>Подбор олимпиад<span class="accent-mark">.</span></h1>
      <p>
        Два шага — и вы увидите олимпиады, которые подходят вашему направлению.
      </p>
    </div>
    <div class="stepper">
      <button
        :class="{ selected: stage === 'university' }"
        @click="changeStage('university')"
      >
        <span>01</span> Вуз</button
      ><button
        :disabled="!universityId"
        :class="{ selected: stage === 'program' }"
        @click="changeStage('program')"
      >
        <span>02</span> Направление</button
      ><button
        :disabled="!programId"
        :class="{ selected: stage === 'results' }"
        @click="changeStage('results')"
      >
        <span>03</span> Результат
      </button>
    </div>
    <section v-if="stage === 'university'" class="panel">
      <div class="panel-top">
        <div>
          <p class="eyebrow">Шаг 01</p>
          <h2>Куда хотите поступать?</h2>
        </div>
      </div>
      <input
        v-model="universityQuery"
        class="input"
        type="search"
        placeholder="Найти вуз"
        aria-label="Найти вуз"
      /><StatusBox v-if="status === 'loading'" state="loading" /><StatusBox
        v-else-if="status === 'error'"
        state="error"
        @retry="retry"
      /><StatusBox
        v-else-if="!universities.length"
        state="empty"
        title="Вузы не найдены"
      />
      <div v-else class="choice-list">
        <button
          v-for="item in universities"
          :key="item.id"
          class="choice-row"
          @click="selectUniversity(item.id)"
        >
          <span
            ><strong>{{ item.name }}</strong
            ><small>{{ item.cities.join(" · ") }}</small></span
          ><span>↗</span>
        </button>
      </div>
    </section>
    <section v-else-if="stage === 'program'" class="panel">
      <div class="panel-top">
        <div>
          <p class="eyebrow">Шаг 02</p>
          <h2>Какое направление?</h2>
        </div>
        <button class="text-button" @click="changeStage('university')">
          Изменить вуз
        </button>
      </div>
      <input
        v-model="programQuery"
        class="input"
        type="search"
        placeholder="Найти направление"
        aria-label="Найти направление"
      /><StatusBox v-if="status === 'loading'" state="loading" /><StatusBox
        v-else-if="status === 'error'"
        state="error"
        @retry="retry"
      /><StatusBox
        v-else-if="!programs.length"
        state="empty"
        title="Направления не найдены"
      />
      <div v-else class="choice-list">
        <button
          v-for="item in programs"
          :key="item.id"
          class="choice-row"
          @click="selectProgram(item.id)"
        >
          <span
            ><strong>{{ item.name }}</strong
            ><small>{{ item.code }}</small></span
          ><span>↗</span>
        </button>
      </div>
    </section>
    <section v-else class="panel">
      <div class="panel-top">
        <div>
          <p class="eyebrow">Подходящие варианты</p>
          <h2>Результаты подбора</h2>
          <p>{{ total }} олимпиад по выбранным критериям</p>
        </div>
        <button class="text-button" @click="changeStage('university')">
          Изменить выбор
        </button>
      </div>
      <div class="filter-pills">
        <button :aria-pressed="benefit === 'all'" @click="benefit = 'all'">
          Все льготы</button
        ><button :aria-pressed="benefit === 'bvi'" @click="benefit = 'bvi'">
          БВИ</button
        ><button
          :aria-pressed="benefit === '100 points'"
          @click="benefit = '100 points'"
        >
          100 баллов
        </button>
      </div>
      <StatusBox
        v-if="status === 'loading' && !recommendations.length"
        state="loading"
      /><StatusBox
        v-else-if="status === 'error'"
        state="error"
        @retry="retry"
      /><StatusBox
        v-else-if="!recommendations.length"
        state="empty"
        title="Олимпиады не найдены"
        message="Попробуйте изменить критерии или льготу."
      />
      <div v-else class="result-grid">
        <article
          v-for="item in recommendations"
          :key="item.id"
          class="result-card"
        >
          <div class="card-top">
            <span class="pill">{{ item.subject.name }}</span
            ><button
              class="icon-button"
              :aria-label="
                favoriteIds.includes(item.id)
                  ? 'Убрать из избранного'
                  : 'В избранное'
              "
              :aria-pressed="favoriteIds.includes(item.id)"
              @click="favoriteIds = toggleFavorite(item.id)"
            >
              {{ favoriteIds.includes(item.id) ? "♥" : "♡" }}
            </button>
          </div>
          <h3>{{ item.name }}</h3>
          <p>
            Сложность {{ item.complexity }}/5 ·
            {{ benefitLabel(item.benefit.type) }}
          </p>
          <RouterLink :to="`/olympiads/${item.id}`" class="card-link"
            >Подробнее <span>↗</span></RouterLink
          >
        </article>
      </div>
      <button
        v-if="recommendations.length < total"
        class="button button-outline load-more"
        :disabled="status === 'loading'"
        @click="loadMore"
      >
        Показать ещё
      </button>
    </section>
  </div>
</template>
