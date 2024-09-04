<template>
  <div>
    <p> Websocket status: {{ isConnected ? 'Connected' : 'Disconnected' }} </p>
    <div>
      <button @click="connectWebSocket">Connect Websocket</button>
      <button @click="sendMessage('Hello from the client')">Send WS Message</button>
      <button @click="fetchHello">Fetch HTTP Hello</button>
      <button @click="fetchAppState">Fetch App State</button>
      <button @click="connectToCameras">Connect to Cameras</button>
      <button @click="closeCameras">Close Cameras</button>

      <div class="image-container">
        <div v-for="(image, cameraId) in latestImages" :key="cameraId" class="image-wrapper">
          <img :alt="`Camera ${cameraId}`" :src="`data:image/jpeg;base64,${image}`"/>
          <p>{{ cameraId }}</p>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">

const wsUrl = 'ws://localhost:8005/websocket/connect';
const {
  connectWebSocket,
  sendMessage,
  isConnected,
  latestImages
} = useWebSocket(wsUrl);

const logs = ref<string[]>([]);

const addLog = (message: string) => {
  console.log(`Adding log: ${message}`)
  logs.value.unshift(message);
}

const fetchHello = async () => {
  const response = await fetch('http://localhost:8005/app/healthcheck');
  const data = await response.json();
  console.log(data);
  addLog(`Fetch Hello: ${JSON.stringify(data)}`);
}
const fetchAppState = async () => {
  const response = await fetch('http://localhost:8005/app/state');
  const data = await response.json();
  console.log(data);
  addLog(`Fetch App State: ${JSON.stringify(data)}`);
}

const connectToCameras = async () => {
  const response = await fetch('http://localhost:8005/cameras/connect');
  const data = await response.json();
  console.log(data);
  addLog(`Connect to Cameras: ${JSON.stringify(data)}`);
}
const closeCameras = async () => {
  const response = await fetch('http://localhost:8005/cameras/close');
  const data = await response.json();
  console.log(data);
  addLog(`Close Cameras: ${JSON.stringify(data)}`);
}

</script>

<style scoped>
.smol-image {
  width: 640px;
  height: auto;
}

div {
  background-color: #654a7b;
}

h1 {
  font-size: 24px;
}

button {
  margin-right: 10px;
  padding: 10px;
  font-size: small;
}

.image-container {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center; /* Centers the images */
  width: 100%; /* Takes full width of the parent */
  height: 100vh; /* Takes the full viewport height */
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
