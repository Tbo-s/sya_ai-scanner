<template>
  <div class="step-wrapper">
    <!-- Step 5-6: remove case -->
    <template v-if="substep === 0">
      <v-icon size="64" color="warning">mdi-cellphone-remove</v-icon>
      <p class="step-text">
        Verwijder de screenprotector en het hoesje van je toestel.
      </p>
      <transition name="fade">
        <v-btn v-if="showOk" color="primary" size="large" @click="next">
          OK
        </v-btn>
      </transition>
    </template>

    <!-- Step 7-8: clean device -->
    <template v-else>
      <v-icon size="64" color="info">mdi-spray-bottle</v-icon>
      <p class="step-text">
        Is het toestel proper?<br />
        <span style="font-size: 16px; opacity: 0.75;">
          Reinig het toestel grondig — geen vettige vingers of vlekken zichtbaar.
        </span>
      </p>
      <transition name="fade">
        <v-btn v-if="showOk" color="primary" size="large" @click="$emit('next')">
          OK
        </v-btn>
      </transition>
    </template>
  </div>
</template>

<script>
export default {
  name: "StepPrepare",
  emits: ["next"],
  data() {
    return { substep: 0, showOk: false, timer: null };
  },
  mounted() {
    this.startTimer();
  },
  beforeUnmount() {
    clearTimeout(this.timer);
  },
  methods: {
    startTimer() {
      clearTimeout(this.timer);
      this.showOk = false;
      this.timer = setTimeout(() => { this.showOk = true; }, 1000);
    },
    next() {
      this.substep = 1;
      this.startTimer();
    },
  },
};
</script>

<style scoped>
.step-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 32px;
  min-height: 60vh;
  text-align: center;
}
.step-text { font-size: 24px; max-width: 640px; line-height: 1.5; }
.fade-enter-active, .fade-leave-active { transition: opacity 0.6s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
