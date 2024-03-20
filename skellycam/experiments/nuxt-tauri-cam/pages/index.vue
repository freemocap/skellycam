<template>
  <div class="webcam-viewer">
    <video ref="videoElement" autoplay></video>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';

const videoElement = ref(null);

const startWebcam = async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    if(videoElement.value) {
      videoElement.value.srcObject = stream;
    }
  } catch (err) {
    console.error('Error accessing the webcam:', err);
  }
};

onMounted(() => {
  startWebcam();
});
</script>

<style>
.webcam-viewer video {
  width: 100%;
  height: auto;
}
</style>
