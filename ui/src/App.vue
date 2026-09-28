<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, RouterView, useRoute } from "vue-router";
const route = useRoute();
const tabs = [
  { label: "Главная", path: "/", icon: "⌂" },
  { label: "Олимпиады", path: "/olympiads", icon: "◇" },
  { label: "Задачи", path: "/tasks", icon: "▤" },
  { label: "Статистика", path: "/statistics", icon: "▥" },
  { label: "Сообщества", path: "/communities", icon: "♧" },
];
const active = computed(() =>
  route.path === "/" ? "/" : "/" + route.path.split("/")[1],
);
</script>
<template>
  <div class="app-shell">
    <header class="site-header">
      <div class="header-inner">
        <RouterLink class="brand" to="/" aria-label="Maxolimp, главная"
          >maxolimp<span>.</span></RouterLink
        >
        <nav class="desktop-nav" aria-label="Основные разделы">
          <RouterLink
            v-for="tab in tabs"
            :key="tab.path"
            :to="tab.path"
            :aria-current="active === tab.path ? 'page' : undefined"
            >{{ tab.label }}</RouterLink
          >
        </nav>
        <RouterLink class="header-cta" to="/practice"
          >Тренироваться <span aria-hidden="true">↗</span></RouterLink
        >
      </div>
    </header>
    <main id="main" class="page-wrap"><RouterView /></main>
    <nav class="mobile-nav" aria-label="Разделы">
      <RouterLink
        v-for="tab in tabs"
        :key="tab.path"
        :to="tab.path"
        :aria-current="active === tab.path ? 'page' : undefined"
        ><span class="nav-icon" aria-hidden="true">{{ tab.icon }}</span
        >{{ tab.label }}</RouterLink
      >
    </nav>
  </div>
</template>
