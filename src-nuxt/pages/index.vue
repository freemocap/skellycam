<template>
  <div class="viewport-container">
    <ThreeDViewport />
    <CameraGrid class="overlay"/>
  </div>
</template>

<script setup lang="ts">

</script>


<style scoped>
.viewport-container{
  position: relative;
  width: 100%;
  height: 100vh;
}
.overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 33vw;
  height: 33vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}

</style>
