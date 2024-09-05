<template>
  <div>
    <h3>Camera Status</h3>

    <h5>Available Cameras:</h5>
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









