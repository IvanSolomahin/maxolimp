<script setup lang="ts">
import { ref, watch, nextTick } from "vue";
import "../lib/math-render.js";
declare global {
  var taskMath: {
    renderMathText: (element: HTMLElement, value: string) => void;
  };
}
const props = defineProps<{ text: string }>();
const el = ref<HTMLElement | null>(null);
watch(
  () => props.text,
  async (value) => {
    await nextTick();
    if (el.value) globalThis.taskMath.renderMathText(el.value, value);
  },
  { immediate: true },
);
</script>
<template><span ref="el" class="math-text"></span></template>
