

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
        <v-btn
          color="info"
          variant="tonal"
          :loading="wristSequenceBusy"
          @click="runWristSequenceTest"
        >
          Test Wrist Sequence (Sim)
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

      <div v-if="wristSequenceError" style="font-size: 14px; color: #ff6b6b;">
        {{ wristSequenceError }}
      </div>

      <div v-if="deviceLookupError" style="font-size: 14px; color: #ff6b6b;">
        {{ deviceLookupError }}
      </div>

      <v-btn color="primary" @click="goToPriceStep">
        Volgende
      </v-btn>
    </template>

    <!-- STEP 5: Max prijs -->
    <template v-else-if="step === 5">
      <div style="text-align: center; font-size: 24px; max-width: 800px;">
        max prijs van toestel = EUR {{ formattedDeviceMaxValue }}
      </div>

      <v-btn color="primary" @click="goToPowerOffStep">
        ok
      </v-btn>
    </template>

    <!-- STEP 6: Uitschakelen -->
    <template v-else-if="step === 6">
      <div style="text-align: center; font-size: 24px; max-width: 800px;">
        toestel volledige uitschakelen
      </div>

      <v-btn color="primary" @click="goToMachinePlanStep">
        ok
      </v-btn>
    </template>

    <!-- STEP 7: Machineflow -->
    <template v-else-if="step === 7">
      <div style="text-align: center; font-size: 24px; max-width: 900px;">
        Machineflow voor {{ deviceModel || "het toestel" }}
      </div>

      <div style="text-align: center; font-size: 16px; opacity: 0.85; max-width: 900px;">
        IMEI {{ imeiNumber || "onbekend" }} · max waarde EUR {{ formattedDeviceMaxValue }}
      </div>

      <div style="display: flex; gap: 12px; flex-wrap: wrap; justify-content: center;">
        <v-btn
          color="primary"
          variant="tonal"
          :loading="inspectionPlanBusy"
          @click="fetchInspectionPlan"
        >
          Vernieuw machineplan
        </v-btn>
        <v-btn
          color="secondary"
          :loading="inspectionRunBusy"
          @click="runInspection(true)"
        >
          Simuleer dry-run
        </v-btn>
        <v-btn
          color="warning"
          variant="outlined"
          :loading="inspectionRunBusy"
          @click="runInspection(false)"
        >
          Start ondersteunde hardware-acties
        </v-btn>
        <v-btn
          color="info"
          variant="tonal"
          :loading="stateMachineBusy"
          @click="fetchStateMachineDefinition"
        >
          State machine definitie
        </v-btn>
        <v-btn
          color="secondary"
          variant="outlined"
          :loading="stateMachineRunBusy"
          @click="runStateMachine(true)"
        >
          Run state machine (dry-run)
        </v-btn>
      </div>

      <div v-if="inspectionFlowError" style="font-size: 14px; color: #ff6b6b; text-align: center;">
        {{ inspectionFlowError }}
      </div>

      <v-card
        v-if="inspectionPlan"
        style="width: 100%; max-width: 980px; background: rgba(255, 255, 255, 0.03);"
      >
        <v-card-title>Gepland proces</v-card-title>
        <v-card-subtitle>
          {{ inspectionPlan.summary?.phase_count || 0 }} fases ·
          {{ inspectionPlan.summary?.step_count || 0 }} stappen ·
          {{ inspectionPlan.summary?.live_supported_step_count || 0 }} live ondersteund
        </v-card-subtitle>
        <v-card-text style="display: flex; flex-direction: column; gap: 14px;">
          <div
            v-for="phase in inspectionPlan.phases"
            :key="phase.id"
            style="padding: 12px; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.08);"
          >
            <div style="font-size: 18px; font-weight: 600;">
              {{ phase.title }}
            </div>
            <div style="font-size: 14px; opacity: 0.8; margin-top: 4px;">
              {{ phase.description }}
            </div>
            <div style="margin-top: 10px; display: flex; flex-direction: column; gap: 8px;">
              <div
                v-for="phaseStep in phase.steps"
                :key="phaseStep.id"
                style="display: flex; justify-content: space-between; gap: 12px; font-size: 14px;"
              >
                <div>
                  <strong>{{ phaseStep.title }}</strong>
                  <div style="opacity: 0.75;">{{ phaseStep.description }}</div>
                </div>
                <div style="opacity: 0.7; white-space: nowrap;">
                  {{ phaseStep.live_supported ? "live" : "nog te koppelen" }}
                </div>
              </div>
            </div>
          </div>
        </v-card-text>
      </v-card>

      <v-card
        v-if="inspectionRunResult"
        style="width: 100%; max-width: 980px; background: rgba(255, 255, 255, 0.03);"
      >
        <v-card-title>Laatste uitvoering</v-card-title>
        <v-card-subtitle>
          {{ inspectionRunResult.dry_run ? "Dry-run" : "Live poging" }}
        </v-card-subtitle>
        <v-card-text style="display: flex; flex-direction: column; gap: 14px;">
          <div
            v-for="phase in inspectionRunResult.phases"
            :key="phase.id"
            style="padding: 12px; border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.08);"
          >
            <div style="font-size: 18px; font-weight: 600;">
              {{ phase.title }}
            </div>
            <div style="margin-top: 10px; display: flex; flex-direction: column; gap: 8px;">
              <div
                v-for="phaseStep in phase.steps"
                :key="phaseStep.id"
                style="display: flex; justify-content: space-between; gap: 12px; font-size: 14px;"
              >
                <div>
                  <strong>{{ phaseStep.title }}</strong>
                  <div style="opacity: 0.75;">{{ formatInspectionStepDetail(phaseStep.detail) }}</div>
                </div>
                <div style="white-space: nowrap; font-weight: 600;">
                  {{ phaseStep.status }}
                </div>
              </div>
            </div>
          </div>
        </v-card-text>
      </v-card>

      <v-card
        v-if="stateMachineDefinition"
        style="width: 100%; max-width: 980px; background: rgba(255, 255, 255, 0.03);"
      >
        <v-card-title>State machine definitie</v-card-title>
        <v-card-text style="display: flex; flex-direction: column; gap: 8px;">
          <div>Initial state: {{ stateMachineDefinition.initial_state }}</div>
          <div>Aantal states: {{ stateMachineDefinition.states?.length || 0 }}</div>
          <div>Aantal flow-steps: {{ stateMachineDefinition.flow_steps?.length || 0 }}</div>
        </v-card-text>
      </v-card>

      <v-card
        v-if="stateMachineRunResult"
        style="width: 100%; max-width: 980px; background: rgba(255, 255, 255, 0.03);"
      >
        <v-card-title>State machine run</v-card-title>
        <v-card-subtitle>
          Final state: {{ stateMachineRunResult.final_state }}
        </v-card-subtitle>
        <v-card-text style="display: flex; flex-direction: column; gap: 8px;">
          <div>Aantal uitgevoerde states: {{ stateMachineRunResult.states?.length || 0 }}</div>
        </v-card-text>
      </v-card>

      <v-btn color="primary" @click="goToThankYouStep">
        Volgende
      </v-btn>
    </template>

    <!-- STEP 8: Afronding -->
    <template v-else-if="step === 8">
      <div style="text-align: center; font-size: 24px; max-width: 800px;">
        bedankt
      </div>

      <v-btn color="primary" @click="finishFlow">
        Home
      </v-btn>
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
      wristSequenceBusy: false,
      wristSequenceError: "",
      showManualImeiInput: false,
      manualImeiInput: "",
      manualImeiError: "",
      manualImeiBusy: false,
      inspectionPlanBusy: false,
      inspectionRunBusy: false,
      inspectionFlowError: "",
      inspectionPlan: null,
      inspectionRunResult: null,
      stateMachineBusy: false,
      stateMachineRunBusy: false,
      stateMachineDefinition: null,
      stateMachineRunResult: null,
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
      this.resetFlowState();
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

    async runWristSequenceTest() {
      this.wristSequenceBusy = true;
      this.wristSequenceError = "";

      try {
        await axios.post("/api/arduino/leonardo/wrist-sequence", {
          simulate: true,
        });
      } catch (error) {
        const message =
          error?.response?.data?.detail || "Kon wrist sequence test niet starten.";
        this.wristSequenceError = String(message);
        console.error("Failed to run wrist sequence test", error);
      } finally {
        this.wristSequenceBusy = false;
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

    goToPriceStep() {
      this.step = 5;
    },

    goToPowerOffStep() {
      this.step = 6;
    },

    async goToMachinePlanStep() {
      this.step = 7;
      await this.fetchInspectionPlan();
    },

    goToThankYouStep() {
      this.step = 8;
    },

    async finishFlow() {
      clearTimeout(this.timer);
      this.stopImeiDetection();
      await this.stopScan();
      await this.triggerGrblPostFlow();

      this.step = 0;
      this.showOk = false;
      this.showScan = false;
      this.resetFlowState();
    },

    async triggerGrblPostFlow() {
      try {
        await axios.post("/api/arduino/grbl/post-flow");
      } catch (error) {
        // No UI needed yet; keep flow moving even when GRBL is disconnected.
        console.error("Failed to run GRBL post-flow", error);
      }
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

    buildInspectionPayload(dryRun = true) {
      return {
        imei: this.imeiNumber,
        model: this.deviceModel,
        max_value_eur: this.deviceMaxValueEur,
        dry_run: dryRun,
      };
    },

    async fetchInspectionPlan() {
      this.inspectionPlanBusy = true;
      this.inspectionFlowError = "";

      try {
        const response = await axios.post(
          "/api/inspection/plan",
          this.buildInspectionPayload(true),
        );
        this.inspectionPlan = response.data;
      } catch (error) {
        const message =
          error?.response?.data?.detail || "Kon machineplan niet ophalen.";
        this.inspectionFlowError = String(message);
        console.error("Failed to fetch inspection plan", error);
      } finally {
        this.inspectionPlanBusy = false;
      }
    },

    async runInspection(dryRun = true) {
      this.inspectionRunBusy = true;
      this.inspectionFlowError = "";

      try {
        const response = await axios.post(
          "/api/inspection/run",
          this.buildInspectionPayload(dryRun),
        );
        this.inspectionRunResult = response.data;
      } catch (error) {
        const message =
          error?.response?.data?.detail || "Kon machineflow niet uitvoeren.";
        this.inspectionFlowError = String(message);
        console.error("Failed to run inspection flow", error);
      } finally {
        this.inspectionRunBusy = false;
      }
    },

    async fetchStateMachineDefinition() {
      this.stateMachineBusy = true;
      this.inspectionFlowError = "";

      try {
        const response = await axios.get("/api/inspection/state-machine/definition");
        this.stateMachineDefinition = response.data;
      } catch (error) {
        const message =
          error?.response?.data?.detail || "Kon state machine definitie niet ophalen.";
        this.inspectionFlowError = String(message);
        console.error("Failed to fetch inspection state machine definition", error);
      } finally {
        this.stateMachineBusy = false;
      }
    },

    async runStateMachine(dryRun = true) {
      this.stateMachineRunBusy = true;
      this.inspectionFlowError = "";

      try {
        const response = await axios.post("/api/inspection/state-machine/run", {
          ...this.buildInspectionPayload(dryRun),
          trigger_emergency_stop: false,
        });
        this.stateMachineRunResult = response.data;
      } catch (error) {
        const message =
          error?.response?.data?.detail || "Kon state machine niet uitvoeren.";
        this.inspectionFlowError = String(message);
        console.error("Failed to run inspection state machine", error);
      } finally {
        this.stateMachineRunBusy = false;
      }
    },

    formatInspectionStepDetail(detail) {
      if (detail === null || detail === undefined || detail === "") {
        return "";
      }
      if (typeof detail === "string") {
        return detail;
      }
      try {
        return JSON.stringify(detail);
      } catch (error) {
        return String(detail);
      }
    },

    resetFlowState() {
      this.imeiNumber = "";
      this.deviceModel = "";
      this.deviceMaxValueEur = 0;
      this.deviceLookupError = "";
      this.gateCommandError = "";
      this.wristSequenceError = "";
      this.lastGateCommand = "";
      this.gatePosition = "";
      this.showManualImeiInput = false;
      this.manualImeiInput = "";
      this.manualImeiError = "";
      this.inspectionFlowError = "";
      this.inspectionPlan = null;
      this.inspectionRunResult = null;
      this.stateMachineDefinition = null;
      this.stateMachineRunResult = null;
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
