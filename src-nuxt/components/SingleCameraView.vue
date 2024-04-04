<template>
  <div class="camera-container" >
    <video  ref="video" autoplay muted></video>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, provide } from 'vue';
import { defineProps } from 'vue';

const props = defineProps({
  camera: Object,
});

const video = ref(null);
const stream = ref(null);

const startWebcam = async () => {
  try {
    const constraints = {
      video: {
        deviceId: props.camera ? { exact: props.camera.deviceId } : undefined,
        width: { ideal: 1920 },
        height: { ideal: 1080 },
        facingMode: 'user',
      },
    };
    stream.value = await navigator.mediaDevices.getUserMedia(constraints);
    if (video.value) {
      video.value.srcObject = stream.value;
    }

    provide('getStream', () => stream.value); // Provide the stream to the parent component

  } catch (error) {
    console.error("Error accessing the webcam", error);
  }
};

watch(
    () => props.camera,
    (newVal, oldVal) => {
      if (newVal !== oldVal) {
        startWebcam();
      }
    },
    { immediate: true }
);

onMounted(() => {
  if (props.camera) {
    startWebcam();
  }
});

onUnmounted( () => {
  if (stream.value) {
    console.log("Stopping stream");
    let tracks = stream.value.getTracks();
    tracks.forEach(track => track.stop());
  }
});
</script>

<style>
.camera-container {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.border-active {
  border: 2px solid red;
  box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}
</style>
