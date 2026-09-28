<script setup lang="ts">
import { RouterLink } from "vue-router";
</script>
<template>
  <div class="home-view">
    <section class="hero">
      <div class="hero-main">
        <p class="eyebrow">
          <span class="dot"></span> Олимпиады и практика в одном месте
        </p>
        <h1>Большие цели<br /><em>начинаются здесь.</em></h1>
        <p class="hero-copy">
          Найдите олимпиады для поступления, выбирайте настоящие задачи и
          следите за своим прогрессом.
        </p>
        <div class="hero-actions">
          <RouterLink class="button button-dark" to="/olympiads"
            >Подобрать олимпиаду <span>↗</span></RouterLink
          ><RouterLink class="button button-outline" to="/tasks"
            >Искать задачи</RouterLink
          >
        </div>
      </div>
      <div class="hero-art" aria-hidden="true">
        <div class="art-orbit art-orbit-one"></div>
        <div class="art-orbit art-orbit-two"></div>
        <div class="art-core">М</div>
        <span class="art-label label-one">знания</span
        ><span class="art-label label-two">практика</span
        ><span class="art-label label-three">результат</span>
      </div>
    </section>
    <section class="section">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Ваш маршрут</p>
          <h2>С чего начнём?</h2>
        </div>
        <p>Выберите следующий шаг. Вернуться к нему можно в любой момент.</p>
      </div>
      <div class="feature-grid">
        <RouterLink to="/olympiads" class="feature-card"
          ><span class="feature-index">01 / ПОДБОР</span
          ><span class="feature-symbol">◇</span>
          <h3>Найдите свою олимпиаду</h3>
          <p>Выберите вуз и направление — покажем подходящие варианты.</p>
          <span class="feature-link">Подобрать <b>↗</b></span></RouterLink
        ><RouterLink to="/tasks" class="feature-card"
          ><span class="feature-index">02 / ЗАДАЧИ</span
          ><span class="feature-symbol">▤</span>
          <h3>Перейдите к задачам</h3>
          <p>Ищите по предмету, сложности и олимпиаде. Изучайте решения.</p>
          <span class="feature-link">Найти задачу <b>↗</b></span></RouterLink
        ><RouterLink to="/practice" class="feature-card"
          ><span class="feature-index">03 / ПРАКТИКА</span
          ><span class="feature-symbol">↗</span>
          <h3>Решайте в своём темпе</h3>
          <p>Пробуйте ответить сами и отмечайте выполненные задания.</p>
          <span class="feature-link">Начать <b>↗</b></span></RouterLink
        >
      </div>
    </section>
    <section class="bottom-banner">
      <div>
        <p class="eyebrow">Учиться вместе</p>
        <h2>Рядом есть те, кто тоже готовится.</h2>
      </div>
      <RouterLink class="button button-lime" to="/communities"
        >Смотреть сообщества ↗</RouterLink
      >
    </section>
  </div>
</template>
