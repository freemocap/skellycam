<template>
  <div>
    <h1>Wowee its skellycam :O</h1>
    <div>
      <button @click="connectWebSocket">Connect Websocket</button>
      <button @click="sendMessage('Hello from the client')">Send WS Message</button>
      <p> Websocket status: {{ isConnected ? 'Connected' : 'Disconnected' }}</p>
      <button @click="fetchHello">Fetch HTTP Hello</button>
      <button @click="connectToCameras">Test Connect to Cameras</button>

      <h2>Messages</h2>
      <ul>
        <li v-for="(msg, index) in messages" :key="index">{{ msg }}</li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">

const wsUrl = 'ws://localhost:8003/ws/connect'; // Update this with your actual WebSocket URL
const {
  connectWebSocket,
  sendMessage,
  messages,
  isConnected
} = useWebSocket(wsUrl);


const fetchHello = async () => {
  const response = await fetch('http://localhost:8003/hello');
  const data = await response.json();
  messages.value.push(`Fetched: ${JSON.stringify(data)}`);
  console.log(data);
}

const connectToCameras = async () => {
  const response = await fetch('http://localhost:8003/connect/test');
  const data = await response.json();
  messages.value.push(`Fetched: ${JSON.stringify(data)}`);
  console.log(data);
}
</script>

<style scoped>
h1 {
  font-size: 24px;
}

button {
  margin-right: 10px;
  padding: 10px;
}

ul {
  list-style-type: none;
  padding: 0;
}

li {
  background: #654a7b;
  margin-bottom: 5px;
  padding: 10px;
  border: 1px solid #ddd;
}
</style>
