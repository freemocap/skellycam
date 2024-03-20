<template>
  <div>
    <video ref="video" autoplay></video>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from "vue";
import { defineProps } from "vue";

const props = defineProps({
  camera: Object,
});

const video = ref(null);

const startWebcam = async () => {
  try {
    const constraints = {
      video: {
        deviceId: props.camera ? { exact: props.camera.deviceId } : undefined,
      },
    };
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    if (video.value) {
      video.value.srcObject = stream;
    }
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
</script>
