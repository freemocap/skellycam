<template>
  <div>
    <video ref="video" autoplay></video>
    <button @click="startWebcam">Start Webcam</button>
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";

const video = ref(null);

const startWebcam = async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    if (video.value) {
      video.value.srcObject = stream;
    }
  } catch (error) {
    console.error("Error accessing the webcam", error);
  }
};

onMounted(() => {
  startWebcam();
});
</script>
