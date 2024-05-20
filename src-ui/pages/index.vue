<template>
  <div>
    <p> Websocket status: {{ isConnected ? 'Connected' : 'Disconnected' }}</p>
    <div>
      <button @click="connectWebSocket">Connect Websocket</button>
      <button @click="sendMessage('Hello from the client')">Send WS Message</button>
      <button @click="fetchHello">Fetch HTTP Hello</button>
      <button @click="testConnectToCameras">Test Connect to Cameras</button>
      <button @click="connectToCameras">Connect to Cameras</button>

      <div v-for="(imgSrc, cameraId) in latestImages" :key="cameraId">
        <h3>{{ cameraId }}</h3>
        <img v-if="imgSrc" :src="imgSrc"  class="smol-image" />
        <p v-else>No image available</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">

const wsUrl = 'ws://localhost:8003/ws/connect'; // Update this with your actual WebSocket URL
const {
  connectWebSocket,
  sendMessage,
  isConnected,
  latestImages
} = useWebSocket(wsUrl);


const fetchHello = async () => {
  const response = await fetch('http://localhost:8003/hello');
  const data = await response.json();
  console.log(data);
}

const testConnectToCameras = async () => {
  const response = await fetch('http://localhost:8003/connect/test');
  const data = await response.json();
  console.log(data);
}
const connectToCameras = async () => {
  const response = await fetch('http://localhost:8003/connect');
  const data = await response.json();
  console.log(data);
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

</style>
