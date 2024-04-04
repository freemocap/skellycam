<template>
  <div>
    <p>🗣️</p>
    <slot />
    <p>🦶</p>
  </div>
</template>

<script setup>
import { ref } from 'vue';
const count = ref(0);
</script>


