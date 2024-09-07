<template>
  <div>
    <p> Websocket status: {{ isConnected ? 'Connected' : 'Disconnected' }} </p>
    <div>
      <button @click="connectWebSocket">Connect Websocket</button>
      <!--      <button @click="sendMessage('Hello from the client')">Send WS Message</button>-->
      <!--      <button @click="fetchHello">Fetch HTTP Hello</button>-->
      <button @click="connectToCameras">Connect to Cameras</button>
      <button @click="closeCameras">Close Cameras</button>
      <button @click="fetchAppState">Fetch App State</button>

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

import {closeCameras, connectToCameras, fetchAppState} from "~/composables/server-client-methods";

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
  background-color: #33aa88;
  font-size: medium;
  font-weight: bold;
  color: black;
}

.image-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); /* Creates a responsive grid */
  gap: 10px; /* Adds space between grid items */

}

.image-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1 1 400px; /* Allows flexibility and ensures a minimum width */
}

img {
  width: 100%; /* Makes the image take full width of the wrapper */
  height: auto; /* Maintains the aspect ratio */
}
</style>
