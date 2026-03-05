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
    <!-- STEP 0: Start -->
    <template v-if="step === 0">
      <v-btn color="primary" @click="startFlow">
        Start
      </v-btn>
    </template>

    <!-- STEP 1 -->
    <template v-else-if="step === 1">
      <div style="text-align: center; font-size: 20px; max-width: 700px;">
        screen protector en case is verwijderd van je toestel?
      </div>

      <transition name="fade">
        <v-btn v-if="showOk" color="primary" @click="nextStep">
          ok
        </v-btn>
      </transition>
    </template>

    <!-- STEP 2 -->
    <template v-else-if="step === 2">
      <div style="text-align: center; font-size: 20px; max-width: 700px;">
        is het toestel proper
      </div>

      <transition name="fade">
        <v-btn v-if="showOk" color="primary" @click="nextStep">
          ok
        </v-btn>
      </transition>
    </template>

    <!-- STEP 3: IMEI + scan -->
    <template v-else-if="step === 3">
      <div style="text-align: center; font-size: 20px; max-width: 800px;">
        toets *#06# in op je toestel voor het imei nummer
      </div>

      <transition name="fade">
        <v-btn
          v-if="showScan"
          prepend-icon="mdi-video"
          color="primary"
          @click="startScan"
        >
          scan
        </v-btn>
      </transition>

      <!-- Camera stream (jouw originele code, enkel getoond als showCamera=true) -->
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

      <!-- optioneel: stop-knop tonen zodra camera aan staat -->
      <v-btn
        v-if="showCamera"
        color="secondary"
        variant="outlined"
        @click="stopScan"
      >
        Stop camera
      </v-btn>
    </template>
  </v-container>
</template>

<script>
import axios from "axios";

export default {
  name: "HomePage",
  data() {
    return {
      // flow state
      step: 0,
      showOk: false,
      showScan: false,
      timer: null,

      // camera state (jouw originele)
      showCamera: false,
      cameraKey: 0,
    };
  },
  computed: {
    cameraStreamUrl() {
      // `/api` is proxied to the backend by Vite in development.
      return `/api/camera/stream?t=${this.cameraKey}`;
    },
  },
  methods: {
    // ---- Flow ----
    startFlow() {
      this.step = 1;
      this.showOk = false;
      this.showScan = false;
      this.startOkTimer();
    },

    nextStep() {
      this.showOk = false;
      this.showScan = false;

      // ga naar volgende stap
      this.step += 1;

      // stap 2: opnieuw ok na 3s
      if (this.step === 2) {
        this.startOkTimer();
        return;
      }

      // stap 3: scan knop na 3s
      if (this.step === 3) {
        this.startScanTimer();
        return;
      }
    },

    startOkTimer() {
      clearTimeout(this.timer);
      this.timer = setTimeout(() => {
        this.showOk = true;
      }, 3000);
    },

    startScanTimer() {
      clearTimeout(this.timer);
      this.timer = setTimeout(() => {
        this.showScan = true;
      }, 3000);
    },

    // ---- Camera (merged from your current code) ----
    startScan() {
      // enkel starten als hij nog niet aan staat
      if (!this.showCamera) {
        this.toggleCamera(true);
      }
    },

    stopScan() {
      if (this.showCamera) {
        this.toggleCamera(false);
      }
    },

    toggleCamera(forceState) {
      const nextState =
        typeof forceState === "boolean" ? forceState : !this.showCamera;

      this.showCamera = nextState;
      this.cameraKey++;

      axios
        .post("/api/arduino/servo", { enabled: nextState })
        .catch((error) => {
          console.error("Failed to toggle Arduino servo", error);
        });
    },
  },
  beforeUnmount() {
    clearTimeout(this.timer);
  },
};
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.6s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>