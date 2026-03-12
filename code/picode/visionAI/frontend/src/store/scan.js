import { defineStore } from "pinia";

export const useScanStore = defineStore("scan", {
  state: () => ({
    uiStep: 0,
    sessionId: null,
    imei: null,
    deviceModel: null,
    maxValueEur: 0,
    scanStatus: "idle",       // idle | running | awaiting_user | complete | failed
    currentHwStep: 0,
    currentHwStepName: "",
    aiResult: null,
    errorMessage: null,
    customerAccepted: null,
  }),

  getters: {
    finalOfferEur: (state) => state.aiResult?.final_offer_eur ?? 0,
    damageGrade: (state) => state.aiResult?.grade ?? "",
    damageDetails: (state) => state.aiResult?.damage_details ?? [],
    isScanning: (state) => state.scanStatus === "running" || state.scanStatus === "awaiting_user",
  },

  actions: {
    setUiStep(step) {
      this.uiStep = step;
    },

    advance() {
      this.uiStep += 1;
    },

    setImei(imei) {
      this.imei = imei;
    },

    setDeviceInfo(model, maxValue) {
      this.deviceModel = model;
      this.maxValueEur = maxValue;
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
        if (data?.ai_result) {
          this.aiResult = data.ai_result;
        }
        this.uiStep = 60;
      } else if (type === "scan_failed") {
        this.scanStatus = "failed";
        this.errorMessage = data?.error || data?.reason || "Onbekende fout";
      }
    },

    setCustomerDecision(accepted) {
      this.customerAccepted = accepted;
    },

    reset() {
      this.uiStep = 0;
      this.sessionId = null;
      this.imei = null;
      this.deviceModel = null;
      this.maxValueEur = 0;
      this.scanStatus = "idle";
      this.currentHwStep = 0;
      this.currentHwStepName = "";
      this.aiResult = null;
      this.errorMessage = null;
      this.customerAccepted = null;
    },
  },
});
