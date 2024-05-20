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
import { ref, onUnmounted } from 'vue';

const wsUrl = 'ws://localhost:8003/ws/connect'; // Update this with your actual WebSocket URL
const ws = ref<WebSocket | null>(null);
const messages = ref<string[]>([]);
const isConnected = ref(false);

const connectWebSocket = () => {
  if (ws.value) {
    ws.value.close();
  }

  ws.value = new WebSocket(wsUrl);

  ws.value.onopen = () => {
    console.log('WebSocket connection established');
    isConnected.value = true;
  };

  ws.value.onmessage = (event) => {
    if (typeof event.data === 'string') {
      messages.value.push(event.data);
    } else if (event.data instanceof Blob) {
      const reader = new FileReader();
      reader.onload = () => {
        if (reader.result) {
          messages.value.push(reader.result as string);
        }
      };
      reader.readAsText(event.data);
    }
  };

  ws.value.onclose = () => {
    console.log('WebSocket connection closed');
    isConnected.value = false;
  };

  ws.value.onerror = (error) => {
    console.error('WebSocket error:', error);
  };
};

const sendMessage = () => {
  if (ws.value && isConnected.value) {
    ws.value.send('Hello, server!');
  }
};

onUnmounted(() => {
  if (ws.value) {
    ws.value.close();
  }
});
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
  background: #f4f4f4;
  margin-bottom: 5px;
  padding: 10px;
  border: 1px solid #ddd;
}
</style>
