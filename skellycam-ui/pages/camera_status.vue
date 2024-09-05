<template>
  <div>
    <h1>Camera Status</h1>

    <h2>Available Cameras:</h2>
    <ul>
      <li v-for="(camera, index) in camerasStore.cameraDevices" :key="index">
        {{ camera }}
      </li>
    </ul>
  </div>
</template>

<script lang="ts" setup>
const camerasStore = useCamerasStore();
</script>









