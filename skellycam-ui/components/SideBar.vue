<template>
  <v-navigation-drawer v-model="drawer" :rail="rail" app class="bg-cyan-darken-4">
    <v-list class="pa-0">
      <v-list-item :class="drawer ? 'justify-end' : 'justify-center'" class="px-3 d-flex" @click="toggleRail">
        <v-icon class="clickable" large>
          {{ railIcon }}
        </v-icon>
      </v-list-item>
      <v-list-item>
        <CameraStatus/>
      </v-list-item>
      <v-list-item>
        <ApiButtons/>
      </v-list-item>
    </v-list>
  </v-navigation-drawer>
</template>


<script setup>

import CameraStatus from "~/components/CameraStatus.vue";

const drawer = ref(true);
const rail = ref(true);

const railIcon = computed(() => (rail.value ? 'mdi-cog' : 'mdi-chevron-left'));

const toggleRail = () => {
  console.log('toggleRail');
  rail.value = !rail.value;

  if (rail.value) {
    drawer.value = true;
  }
}
</script>

<style>
.clickable {
  cursor: pointer;
}
</style>
