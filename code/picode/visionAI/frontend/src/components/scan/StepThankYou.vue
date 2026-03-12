<template>
  <div class="step-wrapper">
    <v-icon size="80" :color="accepted ? 'success' : 'secondary'">
      {{ accepted ? 'mdi-check-circle' : 'mdi-hand-wave' }}
    </v-icon>

    <p class="title-text">{{ accepted ? "Bedankt!" : "Geen probleem!" }}</p>

    <p class="sub-text">
      {{ accepted
        ? "Je bod is geaccepteerd. We nemen contact met je op voor de verdere afhandeling."
        : "Je hebt het bod geweigerd. Je toestel staat klaar om te worden opgehaald." }}
    </p>

    <div v-if="countdown > 0" class="countdown">
      Nieuwe scan in {{ countdown }}s
    </div>

    <v-btn color="primary" variant="outlined" @click="restart">
      Start opnieuw
    </v-btn>
  </div>
</template>

<script>
import { useScanStore } from "@/store/scan";

export default {
  name: "StepThankYou",
  emits: ["restart"],
  setup() {
    return { scanStore: useScanStore() };
  },
  data() {
    return { countdown: 30, interval: null };
  },
  computed: {
    accepted() {
      return this.scanStore.customerAccepted === true;
    },
  },
  mounted() {
    this.interval = setInterval(() => {
      this.countdown -= 1;
      if (this.countdown <= 0) this.restart();
    }, 1000);
  },
  beforeUnmount() {
    clearInterval(this.interval);
  },
  methods: {
    restart() {
      clearInterval(this.interval);
      this.scanStore.reset();
      this.$emit("restart");
    },
  },
};
</script>

<style scoped>
.step-wrapper {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 32px; min-height: 60vh; text-align: center;
}
.title-text { font-size: 48px; font-weight: 800; }
.sub-text { font-size: 20px; max-width: 600px; opacity: .85; line-height: 1.5; }
.countdown { font-size: 16px; opacity: .6; }
</style>
