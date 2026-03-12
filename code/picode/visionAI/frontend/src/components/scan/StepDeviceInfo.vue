<template>
  <div class="step-wrapper">
    <v-icon size="64" color="success">mdi-cellphone-check</v-icon>

    <p class="step-label">Toestel herkend</p>

    <div class="info-card">
      <div class="info-row">
        <span class="label">Model</span>
        <span class="value">{{ deviceModel || "Onbekend toestel" }}</span>
      </div>
      <div class="info-row">
        <span class="label">Max. waarde</span>
        <span class="value highlight">EUR {{ formattedValue }}</span>
      </div>
      <div class="info-row">
        <span class="label">IMEI</span>
        <span class="value mono">{{ imei }}</span>
      </div>
    </div>

    <p class="sub-text">
      {{ canAccept
        ? "Dit toestel kan worden overgenomen."
        : "Dit toestel heeft op dit moment geen overnamwaarde." }}
    </p>

    <v-btn color="primary" size="large" @click="$emit('next')">
      Bevestig
    </v-btn>
  </div>
</template>

<script>
export default {
  name: "StepDeviceInfo",
  emits: ["next"],
  props: {
    imei: { type: String, default: "" },
    deviceModel: { type: String, default: "" },
    maxValueEur: { type: Number, default: 0 },
  },
  computed: {
    formattedValue() {
      return Number(this.maxValueEur || 0).toFixed(2);
    },
    canAccept() {
      return this.maxValueEur > 0;
    },
  },
};
</script>

<style scoped>
.step-wrapper {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 24px; min-height: 60vh; text-align: center;
}
.step-label { font-size: 28px; font-weight: 700; }
.info-card {
  background: rgba(255,255,255,.06); border-radius: 12px;
  padding: 24px 40px; display: flex; flex-direction: column; gap: 16px; min-width: 360px;
}
.info-row { display: flex; justify-content: space-between; gap: 24px; }
.label { opacity: .7; font-size: 16px; }
.value { font-size: 18px; font-weight: 600; }
.highlight { color: rgb(var(--v-theme-success)); font-size: 22px; }
.mono { font-family: monospace; }
.sub-text { font-size: 16px; opacity: .8; max-width: 560px; }
</style>
