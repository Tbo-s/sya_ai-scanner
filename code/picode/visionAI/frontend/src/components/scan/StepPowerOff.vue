<template>
  <div class="step-wrapper">
    <v-icon size="80" color="warning">mdi-power</v-icon>
    <p class="step-text">
      Schakel je toestel <strong>volledig uit</strong> voordat je het in de machine plaatst.
    </p>
    <transition name="fade">
      <v-btn v-if="showOk" color="primary" size="large" @click="$emit('next')">
        OK – Toestel is uitgeschakeld
      </v-btn>
    </transition>
  </div>
</template>

<script>
export default {
  name: "StepPowerOff",
  emits: ["next"],
  data() {
    return { showOk: false };
  },
  mounted() {
    setTimeout(() => { this.showOk = true; }, 1200);
  },
};
</script>

<style scoped>
.step-wrapper {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 32px; min-height: 60vh; text-align: center;
}
.step-text { font-size: 24px; max-width: 600px; line-height: 1.5; }
.fade-enter-active, .fade-leave-active { transition: opacity .6s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
