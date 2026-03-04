<!-- HomePage -->
<template>
  <v-container
    style="
      max-width: 1000px;
      min-height: calc(100vh - 120px);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 16px;
    "
  >
    <v-btn prepend-icon="mdi-video" color="primary" @click="toggleCamera">
      {{ showCamera ? "Stop camera" : "Start camera" }}
    </v-btn>

    <img
      v-if="showCamera"
      :key="cameraKey"
      :src="cameraStreamUrl"
      alt="USB camera stream"
      style="
        width: 100%;
        max-width: 900px;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.12);
      "
    />
  </v-container>
</template>

<script>
import axios from "axios";

export default {
  name: "HomePage",
  data() {
    return {
      showCamera: false,
      cameraKey: 0,
    };
  },
  methods: {
    toggleCamera() {
      const nextState = !this.showCamera;
      this.showCamera = nextState;
      this.cameraKey++;

      axios
        .post("/api/arduino/servo", { enabled: nextState })
        .catch((error) => {
          console.error("Failed to toggle Arduino servo", error);
        });
    },
  },
  computed: {
    cameraStreamUrl() {
      // `/api` is proxied to the backend by Vite in development.
      return `/api/camera/stream?t=${this.cameraKey}`;
    },
  },
};
</script>
