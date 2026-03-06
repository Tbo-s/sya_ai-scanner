<!-- HomePage -->
<template>
  <v-container
    style="
      position: relative;
      max-width: 1000px;
      min-height: calc(100vh - 120px);
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 16px;
    "
  >
    <!-- Back button -->
    <v-btn
      v-if="step > 0"
      icon="mdi-arrow-left"
      variant="text"
      style="
        position: absolute;
        top: 70px;
        left: 20px;
      "
      @click="goBack"
    />

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
          v-if="showScan && !showCamera"
          prepend-icon="mdi-video"
          color="primary"
          @click="startScan"
        >
          scan
        </v-btn>
      </transition>

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

      <div v-if="showCamera" style="font-size: 16px; opacity: 0.8;">
        Zoeken naar imei barcode...
      </div>

      <v-btn
        v-if="showCamera"
        color="secondary"
        variant="outlined"
        @click="stopScan"
      >
        Stop camera
      </v-btn>
    </template>

    <!-- STEP 4: IMEI gevonden -->
    <template v-else-if="step === 4">
      <div style="text-align: center; font-size: 24px; max-width: 800px;">
        dit is jouw imei nummer:
      </div>

      <div style="text-align: center; font-size: 32px; font-weight: bold;">
        {{ imeiNumber }}
      </div>
    </template>
  </v-container>
</template>

<script>
import axios from "axios";

export default {
  name: "HomePage",
  data() {
    return {
      step: 0,
      showOk: false,
      showScan: false,
      timer: null,

      showCamera: false,
      cameraKey: 0,

      imeiNumber: "",
      scanInterval: null,
    };
  },
  computed: {
    cameraStreamUrl() {
      return `/api/camera/stream?t=${this.cameraKey}`;
    },
  },
  methods: {
    startFlow() {
      this.step = 1;
      this.showOk = false;
      this.showScan = false;
      this.startOkTimer();
    },

    nextStep() {
      this.showOk = false;
      this.showScan = false;
      this.step += 1;

      if (this.step === 2) {
        this.startOkTimer();
        return;
      }

      if (this.step === 3) {
        this.startScanTimer();
        return;
      }
    },

    startOkTimer() {
      clearTimeout(this.timer);
      this.timer = setTimeout(() => {
        this.showOk = true;
      }, 1000);
    },

    startScanTimer() {
      clearTimeout(this.timer);
      this.timer = setTimeout(() => {
        this.showScan = true;
      }, 1000);
    },

    async startScan() {
      if (!this.showCamera) {
        this.toggleCamera(true);
      }

      this.startImeiDetection();
    },

    stopScan() {
      this.stopImeiDetection();

      if (this.showCamera) {
        this.toggleCamera(false);
      }
    },

    startImeiDetection() {
      this.stopImeiDetection();

      this.scanInterval = setInterval(async () => {
        try {
          const response = await axios.get("/api/imei/detect");
          if (response.data?.found && response.data?.imei) {
            this.imeiNumber = response.data.imei;
            this.stopImeiDetection();

            if (this.showCamera) {
              this.toggleCamera(false);
            }

            this.step = 4;
          }
        } catch (error) {
          console.error("Failed to detect IMEI", error);
        }
      }, 800);
    },

    stopImeiDetection() {
      if (this.scanInterval) {
        clearInterval(this.scanInterval);
        this.scanInterval = null;
      }
    },

    goBack() {
      clearTimeout(this.timer);
      this.stopImeiDetection();

      this.stopScan();
      this.showCamera = false;
      this.cameraKey++;

      if (this.step > 0) {
        this.step -= 1;
      }

      this.showOk = false;
      this.showScan = false;

      if (this.step === 1 || this.step === 2) {
        this.startOkTimer();
      }

      if (this.step === 3) {
        this.startScanTimer();
        return;
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
    this.stopImeiDetection();
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