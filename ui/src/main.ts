import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";
import HomeView from "./views/HomeView.vue";
import OlympiadsView from "./views/OlympiadsView.vue";
import OlympiadView from "./views/OlympiadView.vue";
import TasksView from "./views/TasksView.vue";
import TaskView from "./views/TaskView.vue";
import PracticeView from "./views/PracticeView.vue";
import StatisticsView from "./views/StatisticsView.vue";
import CommunitiesView from "./views/CommunitiesView.vue";
import { validateMax } from "./lib/max";
import "./style.css";

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    { path: "/", component: HomeView, meta: { title: "Главная" } },
    {
      path: "/olympiads",
      component: OlympiadsView,
      meta: { title: "Подбор олимпиад" },
    },
    {
      path: "/olympiads/:id(\\d+)",
      component: OlympiadView,
      meta: { title: "Олимпиада" },
    },
    { path: "/tasks", component: TasksView, meta: { title: "Задачи" } },
    { path: "/tasks/:id", component: TaskView, meta: { title: "Задача" } },
    { path: "/practice", component: PracticeView, meta: { title: "Тренажёр" } },
    {
      path: "/statistics",
      component: StatisticsView,
      meta: { title: "Статистика" },
    },
    {
      path: "/communities",
      component: CommunitiesView,
      meta: { title: "Сообщества" },
    },
    { path: "/olympiad-home.html", redirect: "/" },
    { path: "/olympiad-onboarding.html", redirect: "/olympiads" },
    { path: "/olympiad-after-onboarding.html", redirect: "/olympiads" },
    { path: "/olympiad-task-search.html", redirect: "/tasks" },
    {
      path: "/olympiad-task-solve.html",
      redirect: () => ({ path: "/practice", query: {} }),
    },
    { path: "/olympiad-statistics.html", redirect: "/statistics" },
    { path: "/olympiad-community.html", redirect: "/communities" },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});
router.afterEach((to) => {
  document.title = `${String(to.meta.title || "Maxolimp")} — Maxolimp`;
});
void validateMax().then((user) => {
  if (user) sessionStorage.setItem("max-user-v1", JSON.stringify(user));
});
createApp(App).use(router).mount("#app");
