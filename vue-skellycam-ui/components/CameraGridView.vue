<template>
  <div class="image-container">
    <div v-for="(image, cameraId) in latestImages" :key="cameraId" class="image-wrapper">
      <img :alt="`Camera ${cameraId}`" :src="`data:image/jpeg;base64,${image}`"/>
      <p>{{ cameraId }}</p>
    </div>
  </div>
</template>


<script setup>
const {
  connectWebSocket,
  sendMessage,
  isConnected,
  latestImages
} = useWebSocket();

</script>

<style scoped>
.image-container {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center; /* Centers the images */
  width: 80%; /* Takes full width of the parent */
  height: 80vh; /* Takes the full viewport height */
  overflow: auto; /* Adds scroll if content overflows */
}

.image-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1 1 200px; /* Allows flexibility and ensures a minimum width */
}

img {
  width: 100%; /* Makes the image take full width of the wrapper */
  height: auto; /* Maintains the aspect ratio */
}
</style>
