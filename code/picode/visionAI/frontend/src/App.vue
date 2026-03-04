<template>
  <v-app>
    <v-main>
      <!-- App bar, will be present on all pages -->
      <v-app-bar :elevation="2">
        <v-app-bar-title
          class="text-h5 font-weight-bold"
          style="width: 100%; text-align: center"
        >
          SYA
        </v-app-bar-title>
      </v-app-bar>

      <!-- The router view will be rendered here -->
      <router-view />
    </v-main>
  </v-app>
</template>

<script>
export default {
  beforeUnmount() {
    this.$websocket.close();
  },
};
</script>
