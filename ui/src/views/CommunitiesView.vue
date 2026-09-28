<script setup lang="ts">
import { ref } from "vue";
import { RouterLink } from "vue-router";
const mode = ref<"online" | "offline">("online");
</script>
<template>
  <div class="content-page">
    <div class="page-intro">
      <p class="eyebrow">Вместе интереснее</p>
      <h1>Сообщества<span class="accent-mark">.</span></h1>
      <p>Раздел для олимпиадных чатов, кружков и встреч.</p>
    </div>
    <div class="filter-pills" role="group" aria-label="Тип сообщества">
      <button :aria-pressed="mode === 'online'" @click="mode = 'online'">
        Онлайн</button
      ><button :aria-pressed="mode === 'offline'" @click="mode = 'offline'">
        Кружки рядом
      </button>
    </div>
    <div class="coming-soon">
      <div class="coming-symbol" aria-hidden="true">♧</div>
      <p class="eyebrow">Каталог готовится</p>
      <h2>
        {{
          mode === "online"
            ? "Скоро здесь появятся сообщества"
            : "Скоро здесь появятся кружки"
        }}
      </h2>
      <p>
        Добавим {{ mode === "online" ? "сообщества" : "кружки" }}, когда сможем
        указать проверенные ссылки и актуальные данные. Пока можно выбрать
        олимпиаду и начать практику.
      </p>
      <div class="hero-actions">
        <RouterLink class="button button-dark" to="/olympiads"
          >Подобрать олимпиаду ↗</RouterLink
        ><RouterLink class="button button-outline" to="/tasks"
          >Найти задачи</RouterLink
        >
      </div>
    </div>
  </div>
</template>
