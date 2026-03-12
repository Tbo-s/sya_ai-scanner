<template>
  <div class="step-wrapper">
    <!-- Logo / brand -->
    <div class="brand-title">SYA</div>
    <div class="brand-subtitle">Smartphone Grading Machine</div>

    <transition name="fade">
      <div v-if="showContent" class="step-content">
        <p class="step-text">
          Wil je een prijsberekening voor je toestel?
        </p>
        <v-btn color="primary" size="x-large" @click="$emit('next')">
          Start
        </v-btn>
      </div>
    </transition>
  </div>
</template>

<script>
export default {
  name: "StepWelcome",
  emits: ["next"],
  data() {
    return { showContent: false };
  },
  mounted() {
    setTimeout(() => { this.showContent = true; }, 600);
  },
};
</script>

<style scoped>
.step-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 24px;
  min-height: 60vh;
  text-align: center;
}
.brand-title {
  font-size: 72px;
  font-weight: 800;
  letter-spacing: 8px;
  color: rgb(var(--v-theme-primary));
}
.brand-subtitle {
  font-size: 20px;
  opacity: 0.7;
  letter-spacing: 2px;
}
.step-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
}
.step-text {
  font-size: 24px;
  max-width: 600px;
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.6s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
