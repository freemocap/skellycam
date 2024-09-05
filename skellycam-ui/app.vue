<template>
  <NuxtLayout>
    <v-app id="inspire" class="bg-grey-darken-4">
      <NuxtPage/>
    </v-app>
  </NuxtLayout>

</template>


<script>
const websocket = useWebSocket()
await websocket.connectWebSocket()

onUnmounted(() => {
  if (websocket) {
    websocket.closeWebsocket();
  }
});
</script>
