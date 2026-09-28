<script setup lang="ts">
defineProps<{
  state: "loading" | "error" | "empty";
  title?: string;
  message?: string;
}>();
defineEmits<{ retry: [] }>();
</script>
<template>
  <div class="status-box" role="status">
    <span class="status-icon" aria-hidden="true">{{
      state === "loading" ? "◌" : state === "error" ? "!" : "∅"
    }}</span>
    <h2>
      {{
        title ||
        (state === "loading"
          ? "Загрузка…"
          : state === "error"
            ? "Не удалось загрузить данные"
            : "Здесь пока пусто")
      }}
    </h2>
    <p v-if="message">{{ message }}</p>
    <button
      v-if="state === 'error'"
      class="button button-secondary"
      @click="$emit('retry')"
    >
      Повторить
    </button>
  </div>
</template>
