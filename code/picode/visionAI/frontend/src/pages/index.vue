<!-- SYA AI-Scanner – main workflow coordinator -->
<template>
  <v-container class="page-container">

    <!-- Back button (only during UI-only steps, not while machine runs) -->
    <v-btn
      v-if="uiStep > 0 && uiStep < 19"
      icon="mdi-arrow-left"
      variant="text"
      class="back-btn"
      @click="goBack"
    />

    <!-- ── Step 0-3: Welcome + start ─────────────────────────────────────── -->
    <StepWelcome
      v-if="uiStep < 4"
      @next="advance"
    />

    <!-- ── Steps 4-8: Prepare device ─────────────────────────────────────── -->
    <StepPrepare
      v-else-if="uiStep < 9"
      @next="advance"
    />

    <!-- ── Steps 9-13: IMEI scan ──────────────────────────────────────────── -->
    <StepImei
      v-else-if="uiStep < 14"
      @done="onImeiDone"
    />

    <!-- ── Steps 14-16: Device info + confirm ─────────────────────────────── -->
    <StepDeviceInfo
      v-else-if="uiStep < 17"
      :imei="scanStore.imei"
      :device-model="scanStore.deviceModel"
      :max-value-eur="scanStore.maxValueEur"
      @next="advance"
    />

    <!-- ── Steps 17-18: Power off instruction ─────────────────────────────── -->
    <StepPowerOff
      v-else-if="uiStep < 19"
      @next="startMachineScan"
    />

    <!-- ── Steps 19-59: Machine running ───────────────────────────────────── -->
    <StepMachineRunning
      v-else-if="uiStep < 60"
    />

    <!-- ── Steps 60-62: Phone ready + offer ───────────────────────────────── -->
    <StepPhoneReady
      v-else-if="uiStep < 63"
      @accept="onAccept"
      @reject="onReject"
    />

    <!-- ── Steps 63-65: Thank you + countdown ─────────────────────────────── -->
    <StepThankYou
      v-else
      @restart="onRestart"
    />

  </v-container>
</template>

<script>
import axios from "axios";
import { useScanStore } from "@/store/scan";

import StepWelcome       from "@/components/scan/StepWelcome.vue";
import StepPrepare       from "@/components/scan/StepPrepare.vue";
import StepImei          from "@/components/scan/StepImei.vue";
import StepDeviceInfo    from "@/components/scan/StepDeviceInfo.vue";
import StepPowerOff      from "@/components/scan/StepPowerOff.vue";
import StepMachineRunning from "@/components/scan/StepMachineRunning.vue";
import StepPhoneReady    from "@/components/scan/StepPhoneReady.vue";
import StepThankYou      from "@/components/scan/StepThankYou.vue";

export default {
  name: "HomePage",

  components: {
    StepWelcome,
    StepPrepare,
    StepImei,
    StepDeviceInfo,
    StepPowerOff,
    StepMachineRunning,
    StepPhoneReady,
    StepThankYou,
  },

  setup() {
    return { scanStore: useScanStore() };
  },

  computed: {
    uiStep() {
      return this.scanStore.uiStep;
    },
  },

  methods: {
    advance() {
      this.scanStore.advance();
    },

    goBack() {
      if (this.scanStore.uiStep > 0) {
        this.scanStore.setUiStep(this.scanStore.uiStep - 1);
      }
    },

    // Called by StepImei when IMEI is confirmed
    async onImeiDone(imei) {
      this.scanStore.setImei(imei);

      // Lookup device model + value
      try {
        const r = await axios.post("/api/device/lookup", { imei });
        this.scanStore.setDeviceInfo(
          r.data?.model || "Onbekend toestel",
          Number(r.data?.max_value_eur || 0),
        );
      } catch {
        this.scanStore.setDeviceInfo("Onbekend toestel", 0);
      }

      this.scanStore.setUiStep(14);
    },

    // Called by StepPowerOff when user confirms device is off
    async startMachineScan() {
      this.scanStore.setUiStep(19);

      try {
        const r = await axios.post("/api/scan/start", {
          imei: this.scanStore.imei,
          device_model: this.scanStore.deviceModel,
          max_value_eur: this.scanStore.maxValueEur,
        });
        this.scanStore.sessionId = r.data.session_id;
        this.scanStore.scanStatus = "running";
      } catch (e) {
        this.scanStore.errorMessage =
          e?.response?.data?.detail || "Kon scan niet starten.";
        this.scanStore.scanStatus = "failed";
      }
    },

    onAccept() {
      this.scanStore.setUiStep(63);
    },

    onReject() {
      this.scanStore.setUiStep(63);
    },

    onRestart() {
      this.scanStore.reset();
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
}
.back-btn {
  position: absolute;
  top: 70px;
  left: 20px;
}
</style>
