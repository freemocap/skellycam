<template>
  <TresCanvas v-bind="gl">
    <OrbitControls/>
    <TresPerspectiveCamera :near=.01 :position="[0, 1, 5]"/>
    <!--    <TresMesh :rotation="[0, 0, 0]" :scale="[1.0, 1.0, 1.0]">-->
    <TresMesh v-for="(texture, index) in videoTextures" :key="index" :position="cameraPositions[index]"
              :rotation="[0,0,0]">
      <TresPlaneGeometry :args="[1.6, .9]"/>
      <TresMeshBasicMaterial :map="texture"/>
    </TresMesh>
    <TresAxesHelper :size="1"/>
    <TresGridHelper :divisions="100" :position="[0,-.001,0]" :size="100"/>
  </TresCanvas>
</template>

<script lang="ts" setup>
import * as THREE from 'three';

const {
  connectWebSocket,
  latestImages
} = useWebSocket();

const camerasStore = useCamerasStore();
const latestFramesStore = useLatestFrames();
const camerasReady = computed(() => camerasStore.camerasReady);
const videoTextures = ref<THREE.Texture[]>([]);


const planeWidth: number = 1.6;
const planeHeight: number = .9;
const planeSpacing: number = 0.1;

// Define the type for the array of positions
type Vector3 = [number, number, number];
type CameraPositions = ComputedRef<Vector3[]>;
type CameraPlane = ComputedRef<Vector3[]>;

const cameraPositions: CameraPositions = computed(() => {
  return videoTextures.value.map((_: any, index: number, array: THREE.Texture[]): Vector3 => {
    const offset: number = (planeWidth + planeSpacing) * (array.length - 1) / 2;
    return [(index * (planeWidth + planeSpacing)) - offset, planeHeight, 0];
  });
});

const gl = reactive({
  clearColor: '#0c352c',
  antialias: true,
});


onMounted(() => {
  const solidColorTexture = new THREE.Texture();

  // Create a canvas element
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  if (context) {
    canvas.width = 1;
    canvas.height = 1;
    context.fillStyle = '#ff0000'; // Set the desired solid color
    context.fillRect(0, 0, 1, 1);

    solidColorTexture.image = canvas;
    solidColorTexture.needsUpdate = true;

    videoTextures.value.push(solidColorTexture);
  }
  // Create initial textures for each camera
  for (let i = 0; i < Object.keys(latestImages.value).length; i++) {
    const texture = new THREE.Texture();
    videoTextures.value.push(texture);
  }

  // Connect to WebSocket and update textures when new images arrive
  connectWebSocket();

  watch(latestImages, (newImages) => {
    Object.keys(newImages).forEach((cameraId, index) => {
      const image = newImages[cameraId];
      const img = new Image();
      img.src = `data:image/jpeg;base64,${image}`;
      img.onload = () => {
        if (context) {
          canvas.width = img.width;
          canvas.height = img.height;
          context.drawImage(img, 0, 0);
          videoTextures.value[index].image = canvas;
          videoTextures.value[index].needsUpdate = true;
        }
      };
    });
  }, {deep: true});
});
</script>

