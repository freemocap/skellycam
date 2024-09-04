<template>
  <div class="image-container">
    <div v-for="(image, cameraId) in latestImages" :key="cameraId" class="image-wrapper">
      <img :alt="`Camera ${cameraId}`" :src="`data:image/jpeg;base64,${image}`"/>
      <p>{{ cameraId }}</p>
    </div>
  </div>
</template>


</script>

<style scoped>
.image-container {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.image-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
}

img {
  max-width: 100px;
  max-height: 100px;
}
</style>
