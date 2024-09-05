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

import {closeCameras, connectToCameras, fetchAppState, fetchHello} from "~/composables/server-client-methods";

const {
  connectWebSocket,
  sendMessage,
  isConnected,
  latestImages
} = useWebSocket();


</script>

<style scoped>

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
