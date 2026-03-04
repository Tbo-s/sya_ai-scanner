<template>
  <div>
    <!-- List all messages -->
    <v-snackbar
      :style="{
        'margin-bottom': calcMargin(i),
      }"
      v-for="(message, i) in messages.slice(0, 10)"
      :key="i"
      v-model="show"
      timeout="-1"
      :color="message.type"
      :offset="100"
    >
      <!-- Message content -->
      <div style="display: flex; align-items: center; gap: 10px">
        <!-- Message Icons -->
        <v-icon v-if="message.type === 'info'">mdi-information</v-icon>
        <v-icon v-if="message.type === 'success'">mdi-check</v-icon>
        <v-icon v-if="message.type === 'warning'">mdi-alert</v-icon>
        <v-icon v-if="message.type === 'error'">mdi-alert-circle</v-icon>

        <!-- Message Text -->
        <div
          style="
            white-space: nowrap;
            max-width: 500px;
            overflow: hidden;
            text-overflow: ellipsis;
          "
        >
          {{ message.message }}
        </div>
      </div>
    </v-snackbar>
  </div>
</template>

<script>
import messagesStore from "@/store/messages";
import { mapStores } from "pinia";

export default {
  name: "AppMessenger",
  data: () => {
    return {
      show: true,
    };
  },
  methods: {
    calcMargin(i) {
      return 10 + i * 55 + "px";
    },
  },
  computed: {
    messages() {
      return this.messagesStore.messages;
    },

    // Import the messages store
    ...mapStores(messagesStore),
  },
};
</script>
