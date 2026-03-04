<template>
  <v-card
    outlined
    tile
    style="cursor: pointer"
    @click="selectNote"
  >
    <v-card-title>{{ note.title }}</v-card-title>
    <v-card-text>{{ note.content }}</v-card-text>
  </v-card>
</template>

<script>
export default {
  props: {
    note: {
      type: Object,
      required: true,
    },
  },
  emits: ["selected"],
  methods: {
    selectNote() {
      this.$emit("selected");
    },
  },
};
</script>
