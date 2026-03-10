

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
        <div
          v-if="showScan && !showCamera"
          style="display: flex; gap: 12px; flex-wrap: wrap; justify-content: center;"
        >
          <v-btn
            prepend-icon="mdi-video"
            color="primary"
            @click="startScan"
          >
            scan
          </v-btn>
          <v-btn
            prepend-icon="mdi-form-textbox"
            color="secondary"
            variant="tonal"
            @click="toggleManualImeiInput"
          >
            typ imei
          </v-btn>
        </div>
      </transition>

      <div
        v-if="showManualImeiInput && !showCamera"
        style="width: 100%; max-width: 460px; display: flex; flex-direction: column; gap: 10px;"
      >
        <v-text-field
          :model-value="formattedManualImeiDisplay"
          label="IMEI"
          variant="outlined"
          density="comfortable"
          readonly
          hide-details="auto"
        />
        <div
          style="
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 8px;
          "
        >
          <v-btn :disabled="manualImeiInput.length >= 15" @click="appendManualDigit('1')">1</v-btn>
          <v-btn :disabled="manualImeiInput.length >= 15" @click="appendManualDigit('2')">2</v-btn>
          <v-btn :disabled="manualImeiInput.length >= 15" @click="appendManualDigit('3')">3</v-btn>
          <v-btn :disabled="manualImeiInput.length >= 15" @click="appendManualDigit('4')">4</v-btn>
          <v-btn :disabled="manualImeiInput.length >= 15" @click="appendManualDigit('5')">5</v-btn>
          <v-btn :disabled="manualImeiInput.length >= 15" @click="appendManualDigit('6')">6</v-btn>
          <v-btn :disabled="manualImeiInput.length >= 15" @click="appendManualDigit('7')">7</v-btn>
          <v-btn :disabled="manualImeiInput.length >= 15" @click="appendManualDigit('8')">8</v-btn>
          <v-btn :disabled="manualImeiInput.length >= 15" @click="appendManualDigit('9')">9</v-btn>
          <v-btn color="warning" variant="tonal" @click="clearManualImei">C</v-btn>
          <v-btn :disabled="manualImeiInput.length >= 15" @click="appendManualDigit('0')">0</v-btn>
          <v-btn color="secondary" variant="tonal" @click="removeManualDigit">
            ⌫
          </v-btn>
        </div>
        <div style="display: flex; gap: 10px; justify-content: center;">
          <v-btn
            color="primary"
            :loading="manualImeiBusy"
            :disabled="manualImeiInput.length !== 15"
            @click="submitManualImei"
          >
            Bevestig IMEI
          </v-btn>
          <v-btn
            color="secondary"
            variant="text"
            @click="toggleManualImeiInput"
          >
            Annuleer
          </v-btn>
        </div>
        <div v-if="manualImeiError" style="font-size: 14px; color: #ff6b6b;">
          {{ manualImeiError }}
        </div>
      </div>

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
        Toestel herkend
      </div>

      <div style="text-align: center; font-size: 20px; font-weight: 600;">
        Model: {{ deviceModel || "Onbekend toestel" }}
      </div>

      <div style="text-align: center; font-size: 20px; font-weight: 600;">
        Maximale waarde: EUR {{ formattedDeviceMaxValue }}
      </div>

      <div style="text-align: center; font-size: 16px; opacity: 0.85;">
        Stuur poortcommando naar Arduino Leonardo
      </div>

      <div style="display: flex; gap: 12px; flex-wrap: wrap; justify-content: center;">
        <v-btn
          color="success"
          :loading="gateCommandBusy"
          @click="sendGateCommand('GATE_OPEN')"
        >
          Test GATE_OPEN
        </v-btn>
        <v-btn
          color="error"
          variant="outlined"
          :loading="gateCommandBusy"
          @click="sendGateCommand('GATE_CLOSE')"
        >
          Test GATE_CLOSE
        </v-btn>
      </div>

      <div v-if="lastGateCommand" style="font-size: 14px; opacity: 0.85;">
        Laatste commando: {{ lastGateCommand }}
      </div>

      <div style="display: flex; gap: 12px; flex-wrap: wrap; justify-content: center;">
        <v-btn
          color="primary"
          variant="tonal"
          :loading="gatePositionBusy"
          @click="fetchGatePosition"
        >
          Lees gate positie
        </v-btn>
        <div style="font-size: 14px; opacity: 0.9; align-self: center;">
          Gate positie: <strong>{{ gatePosition || "Onbekend" }}</strong>
        </div>
      </div>

      <div v-if="gateCommandError" style="font-size: 14px; color: #ff6b6b;">
        {{ gateCommandError }}
      </div>

      <div v-if="deviceLookupError" style="font-size: 14px; color: #ff6b6b;">
        {{ deviceLookupError }}
      </div>
    </template>
  </v-container>
</template>

<script>
import axios from "axios";
import { nextTick } from "vue";

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
      deviceModel: "",
      deviceMaxValueEur: 0,
      deviceLookupBusy: false,
      deviceLookupError: "",
      scanInterval: null,
      gateCommandBusy: false,
      gateCommandError: "",
      lastGateCommand: "",
      gatePositionBusy: false,
      gatePosition: "",
      showManualImeiInput: false,
      manualImeiInput: "",
      manualImeiError: "",
      manualImeiBusy: false,
    };
  },
  computed: {
    cameraStreamUrl() {
      return `/api/camera/stream?t=${this.cameraKey}`;
    },
    formattedDeviceMaxValue() {
      const value = Number(this.deviceMaxValueEur || 0);
      return value.toFixed(2);
    },
    formattedManualImeiDisplay() {
      return this.manualImeiInput;
    },
  },
  methods: {
    startFlow() {
      this.step = 1;
      this.showOk = false;
      this.showScan = false;
      this.imeiNumber = "";
      this.deviceModel = "";
      this.deviceMaxValueEur = 0;
      this.deviceLookupError = "";
      this.gateCommandError = "";
      this.lastGateCommand = "";
      this.gatePosition = "";
      this.showManualImeiInput = false;
      this.manualImeiInput = "";
      this.manualImeiError = "";
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
  this.showManualImeiInput = false;
  this.manualImeiError = "";
  this.stopImeiDetection();

  // forceer volledige reset van oude stream
  this.showCamera = false;
  this.cameraKey = Date.now();

  await nextTick();

  this.toggleCamera(true);
  this.startImeiDetection();
},

async stopScan() {
  this.stopImeiDetection();

  if (this.showCamera) {
    this.toggleCamera(false);
  }

  // forceer img echt weg
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

    async goBack() {
      clearTimeout(this.timer);
      this.stopImeiDetection();

      await this.stopScan();

      if (this.step > 0) {
        this.step -= 1;
      }

      this.showOk = false;
      this.showScan = false;
      this.showManualImeiInput = false;
      this.manualImeiInput = "";
      this.manualImeiError = "";

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

    async sendGateCommand(command, options = {}) {
      const { silentError = false } = options;

      this.gateCommandBusy = true;
      this.gateCommandError = "";

      try {
        const response = await axios.post("/api/arduino/leonardo/gate", {
          command,
        });
        this.lastGateCommand = response.data?.command || command;
        this.fetchGatePosition({ silentError: true });
      } catch (error) {
        const message =
          error?.response?.data?.detail || "Kon gate-commando niet versturen.";
        this.gateCommandError = String(message);
        if (!silentError) {
          console.error("Failed to send gate command", error);
        }
      } finally {
        this.gateCommandBusy = false;
      }
    },

    async fetchGatePosition(options = {}) {
      const { silentError = false } = options;

      this.gatePositionBusy = true;

      try {
        const response = await axios.get("/api/arduino/leonardo/gate-position");
        this.gatePosition = response.data?.position || "";
      } catch (error) {
        if (!silentError) {
          const message =
            error?.response?.data?.detail || "Kon gate positie niet lezen.";
          this.gateCommandError = String(message);
          console.error("Failed to fetch gate position", error);
        }
      } finally {
        this.gatePositionBusy = false;
      }
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
      if (!this.manualImeiInput) {
        return;
      }
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
      this.stopImeiDetection();
      this.showManualImeiInput = false;
      this.manualImeiInput = "";
      this.manualImeiError = "";

      await this.stopScan();
      await this.lookupDeviceFromImei(this.imeiNumber, { silentError: true });

      this.step = 4;
      await this.sendGateCommand("GATE_OPEN", { silentError: true });
      await this.fetchGatePosition({ silentError: true });
    },

    async lookupDeviceFromImei(imei, options = {}) {
      const { silentError = false } = options;

      this.deviceLookupBusy = true;
      this.deviceLookupError = "";

      try {
        const response = await axios.post("/api/device/lookup", { imei });
        this.deviceModel = response.data?.model || "Unknown device";
        this.deviceMaxValueEur = Number(response.data?.max_value_eur || 0);
      } catch (error) {
        if (!silentError) {
          const message =
            error?.response?.data?.detail || "Kon toestelgegevens niet ophalen.";
          this.deviceLookupError = String(message);
          console.error("Failed to lookup device by IMEI", error);
        }
      } finally {
        this.deviceLookupBusy = false;
      }
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
