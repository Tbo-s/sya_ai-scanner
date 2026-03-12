<template>
  <div class="step-wrapper">

    <!-- Error overlay -->
    <div v-if="scanStore.scanStatus === 'failed'" class="error-overlay">
      <v-icon size="64" color="error">mdi-alert-circle</v-icon>
      <p class="error-title">Er is een fout opgetreden</p>
      <p class="error-msg">{{ scanStore.errorMessage }}</p>
      <p class="error-hint">Neem contact op met het personeel.</p>
      <v-btn color="error" variant="outlined" @click="abort">Afbreken</v-btn>
    </div>

    <!-- Normal progress -->
    <template v-else>
      <v-icon size="56" :color="awaitingUser ? 'warning' : 'primary'" class="spin-icon">
        {{ awaitingUser ? 'mdi-hand-wave' : 'mdi-cog' }}
      </v-icon>

      <!-- Awaiting user confirmation -->
      <template v-if="awaitingUser">
        <p class="step-text">Toestel toegevoegd in de lade?</p>
        <v-btn color="success" size="x-large" :loading="confirmBusy" @click="confirm">
          Ja, toestel is geplaatst
        </v-btn>
      </template>

      <!-- Hardware sequence running -->
      <template v-else>
        <p class="step-text">Toestel wordt gescand…</p>
        <div class="progress-area">
          <div class="hw-step">Stap {{ scanStore.currentHwStep }}: {{ stepLabel }}</div>
          <v-progress-linear
            :model-value="progressPct"
            color="primary"
            height="8"
            rounded
            class="mt-2"
          />
        </div>
      </template>

      <!-- Emergency abort always visible -->
      <v-btn
        color="error"
        variant="text"
        size="small"
        class="abort-btn"
        @click="abort"
      >
        Noodstop
      </v-btn>
    </template>
  </div>
</template>

<script>
import axios from "axios";
import { useScanStore } from "@/store/scan";
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
  29: "Lade naar camerapos.",
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
  45: "Lade naar camerapos.",
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

const TOTAL_STEPS = 59 - 19 + 1;

export default {
  name: "StepMachineRunning",
  setup() {
    return { scanStore: useScanStore() };
  },
  data() {
    return { confirmBusy: false };
  },
  computed: {
    awaitingUser() {
      return this.scanStore.scanStatus === "awaiting_user";
    },
    stepLabel() {
      return STEP_NAMES[this.scanStore.currentHwStep] || this.scanStore.currentHwStepName || "Bezig…";
    },
    progressPct() {
      const n = Math.max(0, this.scanStore.currentHwStep - 19);
      return Math.round((n / TOTAL_STEPS) * 100);
    },
  },
  mounted() {
    webSocketService.onMessage("scan_event", (event) => {
      this.scanStore.handleScanEvent(event);
    });
  },
  beforeUnmount() {
    webSocketService.offMessage("scan_event");
  },
  methods: {
    async confirm() {
      this.confirmBusy = true;
      try {
        await axios.post("/api/scan/confirm");
      } catch (e) {
        console.error("confirm failed", e);
      } finally {
        this.confirmBusy = false;
      }
    },
    async abort() {
      try {
        await axios.post("/api/scan/abort");
      } catch { /* ignore */ }
      this.scanStore.reset();
    },
  },
};
</script>

<style scoped>
.step-wrapper {
  position: relative;
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 32px; min-height: 60vh; text-align: center;
}
.step-text { font-size: 24px; max-width: 600px; }
.progress-area { width: 100%; max-width: 500px; }
.hw-step { font-size: 16px; opacity: .8; margin-bottom: 4px; }
.abort-btn { position: absolute; bottom: 16px; right: 16px; }
.error-overlay {
  display: flex; flex-direction: column; align-items: center; gap: 16px;
}
.error-title { font-size: 24px; font-weight: 700; color: rgb(var(--v-theme-error)); }
.error-msg { font-size: 16px; opacity: .85; }
.error-hint { font-size: 14px; opacity: .65; }
@keyframes spin { to { transform: rotate(360deg); } }
.spin-icon { animation: spin 3s linear infinite; }
</style>
