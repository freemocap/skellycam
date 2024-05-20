<template>
  <div>
    <h1>WebSocket Demo</h1>
    <div>
      <button @click="connectWebSocket">Connect</button>
      <button @click="sendMessage" :disabled="!isConnected">Send Message</button>
    </div>
    <div>
      <h2>Messages</h2>
      <ul>
        <li v-for="(msg, index) in messages" :key="index">{{ msg }}</li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">

const wsUrl = 'ws://localhost:8003/ws/connect'; // Update this with your actual WebSocket URL
const { connectWebSocket, sendMessage, messages, isConnected } = useWebSocket(wsUrl);
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
