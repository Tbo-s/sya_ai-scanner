<template>
  <v-container class="page-container">
    <v-btn
      v-if="showBackButton"
      icon="mdi-arrow-left"
      variant="text"
      class="back-btn"
      @click="goBack"
    />

    <template v-if="step === 0">
      <v-btn color="primary" size="x-large" @click="startFlow">Start</v-btn>
    </template>

    <template v-else-if="step === 1">
      <div class="prompt">Screen protector en case zijn verwijderd?</div>
      <transition name="fade">
        <v-btn v-if="showPrimaryAction" color="primary" @click="nextStep">OK</v-btn>
      </transition>
    </template>

    <template v-else-if="step === 2">
      <div class="prompt">Is het toestel proper?</div>
      <transition name="fade">
        <v-btn v-if="showPrimaryAction" color="primary" @click="nextStep">OK</v-btn>
      </transition>
    </template>

    <template v-else-if="step === 3">
      <div class="prompt">Toets *#06# in op je toestel voor het IMEI-nummer.</div>

      <transition name="fade">
        <div v-if="showPrimaryAction && !showCamera" class="action-row">
          <v-btn prepend-icon="mdi-video" color="primary" @click="startScanCamera">Scan IMEI</v-btn>
          <v-btn prepend-icon="mdi-form-textbox" color="secondary" variant="tonal" @click="toggleManualImeiInput">
            Typ IMEI
          </v-btn>
        </div>
      </transition>

      <div v-if="showManualImeiInput && !showCamera" class="manual-imei">
        <v-text-field
          :model-value="manualImeiInput"
          label="IMEI"
          variant="outlined"
          density="comfortable"
          readonly
          hide-details="auto"
        />
        <div class="keypad">
          <v-btn v-for="digit in digits" :key="digit" :disabled="manualImeiInput.length >= 15" @click="appendManualDigit(digit)">
            {{ digit }}
          </v-btn>
          <v-btn color="warning" variant="tonal" @click="clearManualImei">C</v-btn>
          <v-btn :disabled="manualImeiInput.length >= 15" @click="appendManualDigit('0')">0</v-btn>
          <v-btn color="secondary" variant="tonal" @click="removeManualDigit">⌫</v-btn>
        </div>
        <div class="action-row">
          <v-btn color="primary" :loading="manualImeiBusy" :disabled="manualImeiInput.length !== 15" @click="submitManualImei">
            Bevestig IMEI
          </v-btn>
          <v-btn color="secondary" variant="text" @click="toggleManualImeiInput">Annuleer</v-btn>
        </div>
        <div v-if="manualImeiError" class="error-text">{{ manualImeiError }}</div>
      </div>

      <img v-if="showCamera" :key="cameraKey" :src="cameraStreamUrl" alt="USB camera stream" class="camera-stream" />
      <div v-if="showCamera" class="secondary-text">Zoeken naar IMEI barcode...</div>
      <v-btn v-if="showCamera" color="secondary" variant="outlined" @click="stopScanCamera">Stop camera</v-btn>
    </template>

    <template v-else-if="step === 4">
      <div class="title">Toestel herkend</div>
      <div class="subtitle">Model: {{ deviceModel || "Onbekend toestel" }}</div>
      <div class="subtitle">Maximale waarde: EUR {{ formattedDeviceMaxValue }}</div>

      <div class="action-row">
        <v-btn color="success" :loading="gateCommandBusy" @click="sendGateCommand('GATE_OPEN')">Test GATE_OPEN</v-btn>
        <v-btn color="error" variant="outlined" :loading="gateCommandBusy" @click="sendGateCommand('GATE_CLOSE')">Test GATE_CLOSE</v-btn>
        <v-btn color="info" variant="tonal" :loading="piCaptureBusy" @click="capturePiPhoto('post_imei')">Neem foto (Pi camera)</v-btn>
      </div>

      <div class="action-row">
        <v-btn color="primary" variant="tonal" :loading="gatePositionBusy" @click="fetchGatePosition">Lees gate positie</v-btn>
        <div class="secondary-text">Gate positie: <strong>{{ gatePosition || "Onbekend" }}</strong></div>
      </div>

      <div v-if="gateCommandError" class="error-text">{{ gateCommandError }}</div>
      <div v-if="deviceLookupError" class="error-text">{{ deviceLookupError }}</div>
      <div v-if="piCaptureError" class="error-text">{{ piCaptureError }}</div>
      <div v-if="piCaptureSuccess" class="secondary-text">{{ piCaptureSuccess }}</div>

      <v-btn color="primary" @click="step = 5">Volgende</v-btn>
    </template>

    <template v-else-if="step === 5">
      <div class="title">Max prijs van toestel = EUR {{ formattedDeviceMaxValue }}</div>
      <v-btn color="primary" @click="step = 6">OK</v-btn>
    </template>

    <template v-else-if="step === 6">
      <div class="title">Schakel het toestel volledig uit.</div>
      <v-btn color="primary" :loading="scanBusy" @click="startMachineScan">Toestel is uitgeschakeld</v-btn>
      <div v-if="scanError" class="error-text">{{ scanError }}</div>
    </template>

    <template v-else-if="step === 7">
      <div v-if="scanStatus === 'failed'" class="overlay">
        <v-icon size="64" color="error">mdi-alert-circle</v-icon>
        <div class="title">Er is een fout opgetreden</div>
        <div class="error-text">{{ scanError || "Onbekende fout" }}</div>
        <v-btn color="error" variant="outlined" @click="abortScan">Afbreken</v-btn>
      </div>

      <template v-else>
        <v-icon size="56" :color="awaitingUser ? 'warning' : 'primary'" class="spin-icon">
          {{ awaitingUser ? "mdi-hand-wave" : "mdi-cog" }}
        </v-icon>

        <template v-if="awaitingUser">
          <div class="prompt">Toestel toegevoegd in de lade?</div>
          <v-btn color="success" size="x-large" :loading="confirmBusy" @click="confirmScan">Ja, toestel is geplaatst</v-btn>
        </template>

        <template v-else>
          <div class="prompt">Toestel wordt gescand...</div>
          <div class="progress-area">
            <div class="secondary-text">Stap {{ currentHwStep }}: {{ currentHwStepLabel }}</div>
            <v-progress-linear :model-value="progressPct" color="primary" height="8" rounded class="mt-2" />
          </div>
        </template>

        <v-btn color="error" variant="text" class="abort-btn" @click="abortScan">Noodstop</v-btn>
      </template>
    </template>

    <template v-else-if="step === 8">
      <div class="title">Scan voltooid</div>
      <div class="subtitle">Model: {{ deviceModel || "Onbekend toestel" }}</div>
      <div class="subtitle">Grade: {{ aiResult?.grade || "-" }}</div>
      <div class="subtitle">Bod: EUR {{ finalOffer }}</div>
      <div v-if="damageDetailsText" class="secondary-text">Schade: {{ damageDetailsText }}</div>
      <v-btn color="primary" @click="resetFlow">Nieuwe scan</v-btn>
    </template>
  </v-container>
</template>

<script>
import axios from "axios";
import { nextTick } from "vue";
import { webSocketService } from "@/services/websocket";

const STEP_NAMES = {
  19: "Gate openen",
  20: "Lade uitschuiven",
  21: "Wachten op toestel",
  23: "Lade sluiten",
  24: "Gate sluiten",
  25: "Arm naar voorkant",
  27: "Vacuüm aanzetten",
  28: "Arm omhoog",
  29: "Lade naar camerapositie",
  30: "Pols positioneren",
  31: "Foto voorkant 1",
  32: "Pols draaien",
  33: "Foto voorkant 2",
  34: "Pols draaien",
  35: "Foto voorkant 3",
  36: "Pols draaien",
  37: "Lade terugzetten",
  38: "Pols thuis",
  39: "Arm omlaag",
  40: "Vacuüm uitzetten",
  41: "Arm naar achterkant",
  42: "Arm benaderen",
  43: "Vacuüm aanzetten",
  44: "Arm omhoog",
  45: "Lade naar camerapositie",
  46: "Pols positioneren",
  47: "Foto achterkant 1",
  48: "Pols draaien",
  49: "Foto achterkant 2",
  50: "Pols draaien",
  51: "Foto achterkant 3",
  52: "Pols draaien",
  53: "AI-analyse",
  54: "Lade terugzetten",
  55: "Pols thuis",
  56: "Arm omlaag",
  57: "Vacuüm uitzetten",
  58: "Gate openen",
  59: "Lade uitschuiven",
};

export default {
  name: "HomePage",
  data() {
    return {
      step: 0,
      timer: null,
      showPrimaryAction: false,
      showCamera: false,
      cameraKey: 0,
      scanInterval: null,
      imeiNumber: "",
      deviceModel: "",
      deviceMaxValueEur: 0,
      deviceLookupError: "",
      gateCommandBusy: false,
      gateCommandError: "",
      gatePositionBusy: false,
      gatePosition: "",
      piCaptureBusy: false,
      piCaptureError: "",
      piCaptureSuccess: "",
      showManualImeiInput: false,
      manualImeiInput: "",
      manualImeiError: "",
      manualImeiBusy: false,
      scanBusy: false,
      scanStatus: "idle",
      scanError: "",
      currentHwStep: 0,
      currentHwStepName: "",
      aiResult: null,
      sessionId: null,
      confirmBusy: false,
      digits: ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
    };
  },
  computed: {
    showBackButton() {
      return this.step > 0 && this.step < 7;
    },
    cameraStreamUrl() {
      return `/api/camera/stream?t=${this.cameraKey}`;
    },
    formattedDeviceMaxValue() {
      return Number(this.deviceMaxValueEur || 0).toFixed(2);
    },
    awaitingUser() {
      return this.scanStatus === "awaiting_user";
    },
    currentHwStepLabel() {
      return STEP_NAMES[this.currentHwStep] || this.currentHwStepName || "Bezig";
    },
    progressPct() {
      const totalSteps = 59 - 19 + 1;
      const current = Math.max(0, this.currentHwStep - 19);
      return Math.round((current / totalSteps) * 100);
    },
    finalOffer() {
      return Number(this.aiResult?.final_offer_eur || 0).toFixed(2);
    },
    damageDetailsText() {
      const details = this.aiResult?.damage_details || [];
      return details.join(", ");
    },
  },
  mounted() {
    webSocketService.onMessage("scan_event", this.handleScanEvent);
  },
  beforeUnmount() {
    clearTimeout(this.timer);
    this.stopImeiDetection();
    this.stopScanCamera();
    webSocketService.offMessage("scan_event");
  },
  methods: {
    startFlow() {
      this.resetFlow();
      this.step = 1;
      this.startActionTimer();
    },
    nextStep() {
      this.showPrimaryAction = false;
      this.step += 1;
      if (this.step === 2 || this.step === 3) {
        this.startActionTimer();
      }
    },
    startActionTimer() {
      clearTimeout(this.timer);
      this.timer = setTimeout(() => {
        this.showPrimaryAction = true;
      }, 1000);
    },
    async startScanCamera() {
      this.showManualImeiInput = false;
      this.manualImeiError = "";
      this.stopImeiDetection();
      this.showCamera = false;
      this.cameraKey = Date.now();
      await nextTick();
      this.toggleCamera(true);
      this.startImeiDetection();
    },
    async stopScanCamera() {
      this.stopImeiDetection();
      if (this.showCamera) {
        this.toggleCamera(false);
      }
      this.showCamera = false;
      this.cameraKey = Date.now();
      await nextTick();
    },
    startImeiDetection() {
      this.stopImeiDetection();
      this.scanInterval = setInterval(async () => {
        try {
          const response = await axios.get("/api/imei/detect");
          if (response.data?.found && response.data?.imei) {
            await this.completeImeiFlow(response.data.imei);
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
    toggleCamera(enabled) {
      this.showCamera = enabled;
      this.cameraKey += 1;
      axios.post("/api/arduino/servo", { enabled }).catch((error) => {
        console.error("Failed to toggle Arduino servo", error);
      });
    },
    normalizeImeiInput(rawImei) {
      return String(rawImei || "").replace(/\D/g, "");
    },
    appendManualDigit(digit) {
      if (this.manualImeiInput.length >= 15) {
        return;
      }
      this.manualImeiInput += digit;
      this.manualImeiError = "";
    },
    removeManualDigit() {
      this.manualImeiInput = this.manualImeiInput.slice(0, -1);
      this.manualImeiError = "";
    },
    clearManualImei() {
      this.manualImeiInput = "";
      this.manualImeiError = "";
    },
    toggleManualImeiInput() {
      this.showManualImeiInput = !this.showManualImeiInput;
      if (!this.showManualImeiInput) {
        this.manualImeiInput = "";
        this.manualImeiError = "";
      }
    },
    async submitManualImei() {
      const normalized = this.normalizeImeiInput(this.manualImeiInput);
      if (normalized.length !== 15) {
        this.manualImeiError = "IMEI moet exact 15 cijfers bevatten.";
        return;
      }
      this.manualImeiBusy = true;
      this.manualImeiError = "";
      try {
        await this.completeImeiFlow(normalized);
      } finally {
        this.manualImeiBusy = false;
      }
    },
    async completeImeiFlow(imei) {
      this.imeiNumber = this.normalizeImeiInput(imei);
      await this.stopScanCamera();
      this.showManualImeiInput = false;
      this.manualImeiInput = "";
      await this.lookupDeviceFromImei(this.imeiNumber);
      this.step = 4;
      await this.sendGateCommand("GATE_OPEN");
      await this.fetchGatePosition();
    },
    async lookupDeviceFromImei(imei) {
      this.deviceLookupError = "";
      try {
        const response = await axios.post("/api/device/lookup", { imei });
        this.deviceModel = response.data?.model || "Unknown device";
        this.deviceMaxValueEur = Number(response.data?.max_value_eur || 0);
      } catch (error) {
        this.deviceLookupError = error?.response?.data?.detail || "Kon toestelgegevens niet ophalen.";
        this.deviceModel = "Unknown device";
        this.deviceMaxValueEur = 0;
      }
    },
    async sendGateCommand(command) {
      this.gateCommandBusy = true;
      this.gateCommandError = "";
      try {
        await axios.post("/api/arduino/leonardo/gate", { command });
      } catch (error) {
        this.gateCommandError = error?.response?.data?.detail || "Kon gate-commando niet versturen.";
      } finally {
        this.gateCommandBusy = false;
      }
    },
    async fetchGatePosition() {
      this.gatePositionBusy = true;
      try {
        const response = await axios.get("/api/arduino/leonardo/gate-position");
        this.gatePosition = response.data?.position || "";
      } catch (error) {
        this.gateCommandError = error?.response?.data?.detail || "Kon gate positie niet lezen.";
      } finally {
        this.gatePositionBusy = false;
      }
    },
    async capturePiPhoto(tag = "capture") {
      this.piCaptureBusy = true;
      this.piCaptureError = "";
      this.piCaptureSuccess = "";
      try {
        const response = await axios.post("/api/camera/pi/capture", {
          imei: this.imeiNumber,
          tag,
        });
        this.piCaptureSuccess = `Foto opgeslagen: ${response.data?.filename || "ok"}`;
      } catch (error) {
        this.piCaptureError = error?.response?.data?.detail || "Kon geen foto nemen met Pi camera.";
      } finally {
        this.piCaptureBusy = false;
      }
    },
    async startMachineScan() {
      this.scanBusy = true;
      this.scanError = "";
      try {
        const response = await axios.post("/api/scan/start", {
          imei: this.imeiNumber,
          device_model: this.deviceModel,
          max_value_eur: this.deviceMaxValueEur,
        });
        this.sessionId = response.data?.session_id || null;
        this.scanStatus = "running";
        this.step = 7;
      } catch (error) {
        this.scanError = error?.response?.data?.detail || "Kon scan niet starten.";
      } finally {
        this.scanBusy = false;
      }
    },
    handleScanEvent(event) {
      const { type, step, step_name, data } = event;
      this.currentHwStep = step;
      this.currentHwStepName = step_name;
      if (type === "awaiting_user") {
        this.scanStatus = "awaiting_user";
      } else if (type === "step_complete") {
        this.scanStatus = "running";
        if (step_name === "ai_done" && data) {
          this.aiResult = data;
        }
      } else if (type === "scan_complete") {
        this.scanStatus = "complete";
        this.aiResult = data?.ai_result || this.aiResult;
        this.step = 8;
      } else if (type === "scan_failed") {
        this.scanStatus = "failed";
        this.scanError = data?.error || data?.reason || "Onbekende fout";
      }
    },
    async confirmScan() {
      this.confirmBusy = true;
      try {
        await axios.post("/api/scan/confirm");
      } catch (error) {
        this.scanError = error?.response?.data?.detail || "Bevestiging mislukt.";
      } finally {
        this.confirmBusy = false;
      }
    },
    async abortScan() {
      try {
        await axios.post("/api/scan/abort");
      } catch (error) {
        this.scanError = error?.response?.data?.detail || "Afbreken mislukt.";
        return;
      }
      this.resetFlow();
    },
    async goBack() {
      clearTimeout(this.timer);
      this.stopImeiDetection();
      await this.stopScanCamera();
      if (this.step > 0) {
        this.step -= 1;
      }
      this.showPrimaryAction = false;
      this.showManualImeiInput = false;
      this.manualImeiInput = "";
      this.manualImeiError = "";
      if (this.step === 1 || this.step === 2 || this.step === 3) {
        this.startActionTimer();
      }
    },
    resetFlow() {
      clearTimeout(this.timer);
      this.stopImeiDetection();
      this.toggleCamera(false);
      this.step = 0;
      this.showPrimaryAction = false;
      this.showCamera = false;
      this.cameraKey = 0;
      this.imeiNumber = "";
      this.deviceModel = "";
      this.deviceMaxValueEur = 0;
      this.deviceLookupError = "";
      this.gateCommandBusy = false;
      this.gateCommandError = "";
      this.gatePositionBusy = false;
      this.gatePosition = "";
      this.piCaptureBusy = false;
      this.piCaptureError = "";
      this.piCaptureSuccess = "";
      this.showManualImeiInput = false;
      this.manualImeiInput = "";
      this.manualImeiError = "";
      this.manualImeiBusy = false;
      this.scanBusy = false;
      this.scanStatus = "idle";
      this.scanError = "";
      this.currentHwStep = 0;
      this.currentHwStepName = "";
      this.aiResult = null;
      this.sessionId = null;
      this.confirmBusy = false;
    },
  },
};
</script>

<style scoped>
.page-container {
  position: relative;
  max-width: 1000px;
  min-height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  text-align: center;
}

.back-btn {
  position: absolute;
  top: 70px;
  left: 20px;
}

.prompt,
.title {
  font-size: 24px;
  max-width: 800px;
}

.subtitle {
  font-size: 20px;
  font-weight: 600;
}

.secondary-text {
  font-size: 16px;
  opacity: 0.85;
}

.error-text {
  font-size: 14px;
  color: rgb(var(--v-theme-error));
}

.action-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
}

.manual-imei {
  width: 100%;
  max-width: 460px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.keypad {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.camera-stream {
  width: 100%;
  max-width: 900px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.progress-area {
  width: 100%;
  max-width: 500px;
}

.abort-btn {
  position: absolute;
  bottom: 16px;
  right: 16px;
}

.overlay {
  display: flex;
  flex-direction: column;
  gap: 16px;
  align-items: center;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.6s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.spin-icon {
  animation: spin 3s linear infinite;
}
</style>
