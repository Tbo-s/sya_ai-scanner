<template>
  <div class="step-wrapper">
    <v-icon size="64" color="success">mdi-cellphone-arrow-down</v-icon>

    <p class="step-title">Je toestel kan worden opgehaald</p>

    <!-- AI result card -->
    <div class="result-card">
      <div class="grade-badge" :class="gradeClass">
        Grade {{ scanStore.damageGrade || "?" }}
      </div>
      <div class="offer-row">
        <span class="offer-label">Ons bod</span>
        <span class="offer-value">EUR {{ formattedOffer }}</span>
      </div>
      <div v-if="scanStore.damageDetails.length" class="details">
        <span v-for="d in scanStore.damageDetails" :key="d" class="detail-chip">{{ d }}</span>
      </div>
    </div>

    <p class="sub-text">Wil je dit bod accepteren?</p>

    <div class="btn-row">
      <v-btn color="success" size="large" @click="accept">
        Accepteer EUR {{ formattedOffer }}
      </v-btn>
      <v-btn color="error" variant="outlined" size="large" @click="reject">
        Weiger bod
      </v-btn>
    </div>
  </div>
</template>

<script>
import { useScanStore } from "@/store/scan";

export default {
  name: "StepPhoneReady",
  emits: ["accept", "reject"],
  setup() {
    return { scanStore: useScanStore() };
  },
  computed: {
    formattedOffer() {
      return Number(this.scanStore.finalOfferEur || 0).toFixed(2);
    },
    gradeClass() {
      const g = this.scanStore.damageGrade;
      if (g === "A") return "grade-a";
      if (g === "B") return "grade-b";
      if (g === "C") return "grade-c";
      return "grade-d";
    },
  },
  methods: {
    accept() {
      this.scanStore.setCustomerDecision(true);
      this.$emit("accept");
    },
    reject() {
      this.scanStore.setCustomerDecision(false);
      this.$emit("reject");
    },
  },
};
</script>

<style scoped>
.step-wrapper {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 24px; min-height: 60vh; text-align: center;
}
.step-title { font-size: 28px; font-weight: 700; }
.result-card {
  background: rgba(255,255,255,.06); border-radius: 16px;
  padding: 32px 48px; display: flex; flex-direction: column; align-items: center; gap: 20px;
}
.grade-badge {
  font-size: 32px; font-weight: 800; padding: 8px 28px;
  border-radius: 8px; letter-spacing: 2px;
}
.grade-a { background: #1b5e20; color: #a5d6a7; }
.grade-b { background: #33691e; color: #dce775; }
.grade-c { background: #e65100; color: #ffcc80; }
.grade-d { background: #b71c1c; color: #ef9a9a; }
.offer-row { display: flex; gap: 20px; align-items: baseline; }
.offer-label { font-size: 16px; opacity: .7; }
.offer-value { font-size: 36px; font-weight: 800; color: rgb(var(--v-theme-success)); }
.details { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.detail-chip {
  background: rgba(255,255,255,.1); border-radius: 20px;
  padding: 4px 12px; font-size: 13px; opacity: .85;
}
.sub-text { font-size: 18px; opacity: .8; }
.btn-row { display: flex; gap: 16px; flex-wrap: wrap; justify-content: center; }
</style>
