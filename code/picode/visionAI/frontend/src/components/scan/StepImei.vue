<template>
  <div class="step-wrapper">
    <p class="step-text">
      Toets <strong>*#06#</strong> op je toestel om het IMEI-nummer te tonen.
    </p>

    <!-- Scan / manual buttons -->
    <transition name="fade">
      <div v-if="showButtons && !showCamera && !showManual" class="btn-row">
        <v-btn prepend-icon="mdi-video" color="primary" size="large" @click="startScan">
          Scan
        </v-btn>
        <v-btn prepend-icon="mdi-form-textbox" color="secondary" variant="tonal" size="large"
               @click="showManual = true">
          Typ IMEI
        </v-btn>
      </div>
    </transition>

    <!-- Camera stream -->
    <template v-if="showCamera">
      <img :key="cameraKey" :src="cameraStreamUrl" alt="camera stream" class="camera-img" />
      <div class="hint">Zoeken naar IMEI-barcode...</div>
      <v-btn color="secondary" variant="outlined" @click="stopScan">Stop camera</v-btn>
    </template>

    <!-- Manual numpad -->
    <div v-if="showManual && !showCamera" class="numpad-wrapper">
      <v-text-field
        :model-value="manualImei"
        label="IMEI (15 cijfers)"
        variant="outlined"
        density="comfortable"
        readonly
        hide-details="auto"
      />
      <div class="numpad">
        <v-btn v-for="d in '123456789'" :key="d" :disabled="manualImei.length >= 15"
               @click="manualImei += d">{{ d }}</v-btn>
        <v-btn color="warning" variant="tonal" @click="manualImei = ''">C</v-btn>
        <v-btn :disabled="manualImei.length >= 15" @click="manualImei += '0'">0</v-btn>
        <v-btn color="secondary" variant="tonal" @click="manualImei = manualImei.slice(0,-1)">⌫</v-btn>
      </div>
      <div class="btn-row">
        <v-btn color="primary" :loading="busy" :disabled="manualImei.length !== 15"
               @click="submitManual">Bevestig IMEI</v-btn>
        <v-btn color="secondary" variant="text" @click="showManual = false; manualImei = ''">Annuleer</v-btn>
      </div>
      <div v-if="error" class="error-text">{{ error }}</div>
    </div>
  </div>
</template>

<script>
import axios from "axios";
import { nextTick } from "vue";

export default {
  name: "StepImei",
  emits: ["done"],
  data() {
    return {
      showButtons: false,
      showCamera: false,
      showManual: false,
      cameraKey: 0,
      manualImei: "",
      busy: false,
      error: "",
      scanInterval: null,
      timer: null,
    };
  },
  computed: {
    cameraStreamUrl() {
      return `/api/camera/stream?t=${this.cameraKey}`;
    },
  },
  mounted() {
    this.timer = setTimeout(() => { this.showButtons = true; }, 800);
  },
  beforeUnmount() {
    this.stopScan();
    clearTimeout(this.timer);
  },
  methods: {
    async startScan() {
      this.showManual = false;
      this.error = "";
      this.stopScan();
      this.showCamera = false;
      this.cameraKey = Date.now();
      await nextTick();
      this.showCamera = true;
      axios.post("/api/arduino/servo", { enabled: true }).catch(() => {});
      this.scanInterval = setInterval(async () => {
        try {
          const r = await axios.get("/api/imei/detect");
          if (r.data?.found && r.data?.imei) {
            await this.complete(r.data.imei);
          }
        } catch { /* ignore */ }
      }, 800);
    },
    stopScan() {
      clearInterval(this.scanInterval);
      this.scanInterval = null;
      if (this.showCamera) {
        axios.post("/api/arduino/servo", { enabled: false }).catch(() => {});
      }
      this.showCamera = false;
      this.cameraKey = Date.now();
    },
    async submitManual() {
      if (this.manualImei.length !== 15) {
        this.error = "IMEI moet exact 15 cijfers bevatten.";
        return;
      }
      this.busy = true;
      this.error = "";
      try {
        await this.complete(this.manualImei);
      } finally {
        this.busy = false;
      }
    },
    async complete(imei) {
      this.stopScan();
      this.showManual = false;
      this.manualImei = "";
      this.$emit("done", imei);
    },
  },
};
</script>

<style scoped>
.step-wrapper {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 24px; min-height: 60vh; text-align: center;
}
.step-text { font-size: 22px; max-width: 700px; }
.btn-row { display: flex; gap: 16px; flex-wrap: wrap; justify-content: center; }
.camera-img { width: 100%; max-width: 880px; border-radius: 12px; border: 1px solid rgba(255,255,255,.12); }
.hint { font-size: 16px; opacity: .8; }
.numpad-wrapper { width: 100%; max-width: 460px; display: flex; flex-direction: column; gap: 10px; }
.numpad { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.error-text { color: #ff6b6b; font-size: 14px; }
.fade-enter-active, .fade-leave-active { transition: opacity .6s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
