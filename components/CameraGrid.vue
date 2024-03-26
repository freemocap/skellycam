<template>
  <div class="webcam-grid">
    <SingleCameraView
      v-for="camera in cameras"
      :key="camera.deviceId"
      :camera="camera"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from "vue";

const cameras = ref([]);

const getCameras = async () => {
  try {
    console.log("Getting available cameras");
    const devices = await navigator.mediaDevices.enumerateDevices();
    console.log("All available devices", devices);

    const videoDevices = devices
      .filter((device) => device.kind === "videoinput")
      .filter((device) => !device.label.toLowerCase().includes("virtual"));

    console.log("Filtered video devices", videoDevices);

    cameras.value = videoDevices; //.slice(0, 4); // Get at most 4 cameras

    console.log("Using cameras", cameras.value);
  } catch (error) {
    console.error("Error listing cameras", error);
  }
};

onMounted(() => {
  console.log("Mounted CameraGrid");
  getCameras();
});
</script>

<style>
.webcam-grid {
  display: grid;
  grid-template-columns: repeat(
    auto-fill,
    minmax(200px, 600px)
  ); /* Creates as many columns as it can */
  gap: 10px; /* Spacing between webcam feeds */
}

video {
  width: 100%;
  height: auto;
  object-fit: cover; /* Ensures the video fills the space without distorting */
}
</style>
