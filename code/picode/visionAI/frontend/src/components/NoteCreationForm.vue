<template>
  <!-- New note form -->
  <v-form @submit.prevent @keydown.enter.exact.prevent="addNote">
    <v-card style="padding: 10px">
      <v-card-title>Add a new Note</v-card-title>
      <v-card-subtitle>Press Enter to add the note.</v-card-subtitle>
      <v-card-text>
        <v-text-field
          v-model="newTaskTitle"
          label="Title"
          outlined
          dense
          ref="title"
        />
        <v-text-field
          v-model="newTaskContent"
          label="Content"
          outlined
          dense
          ref="content"
        />
      </v-card-text>
    </v-card>
  </v-form>

  <!-- Error message -->
  <v-fade-transition>
    <v-alert
      v-if="errorMessage"
      type="error"
      dense
      class="mt-4"
    >
      {{ errorMessage }}
    </v-alert>
  </v-fade-transition>

  <!-- Success message -->
  <v-fade-transition>
    <v-alert
      v-if="successMessage"
      type="success"
      dense
      class="mt-4"
    >
      {{ successMessage }}
    </v-alert>
  </v-fade-transition>
</template>

<script>
import axios from "axios";

export default {
  emits: ["noteAdded", "close"],
  data() {
    return {
      newTaskTitle: "New note",
      newTaskContent: "",

      errorMessage: "",
      successMessage: "",
    };
  },

  mounted() {
    // Focus the title input when the component is mounted and select the text
    this.$refs.title.focus();
    this.$refs.title.select();
  },
  methods: {
    addNote() {
      // Validate the note fields
      this.errorMessage = "";
      if (!this.newTaskTitle) {
        this.errorMessage = "The note title is required";
        return;
      }

      // Send the note to the server
      axios
        .post("/api/notes", {
          title: this.newTaskTitle,
          content: this.newTaskContent,
        })
        .then((response) => {
          const newNote = response.data;
          this.$emit("noteAdded", newNote);

          // Set the focus back and text selection
          this.$refs.title.focus();
          this.$refs.title.select();

          // Success message
          this.successMessage = "Note added successfully";

          // Clear the success message after 3 seconds
          if (this.successTimeout) clearTimeout(this.successTimeout);
          this.successTimeout = setTimeout(() => {
            this.successMessage = "";
          }, 3000);
        })
        .catch((error) => {
          console.error(error);
          if (
            error.response &&
            error.response.data &&
            error.response.data.detail
          ) {
            const details = error.response.data.detail;
            // Type error check:
            // [
            //   {
            //     type: "string_too_short",
            //     loc: ["body", "title"],
            //     msg: "String should have at least 1 character",
            //     input: "",
            //     ctx: { min_length: 1 },
            //     url: "https://errors.pydantic.dev/2.6/v/string_too_short",
            //   },
            // ];
            if (details[0].msg && details[0].loc) {
              this.errorMessage = details[0].msg + " at " + details[0].loc[1];
            } else this.errorMessage = details;
          } else this.errorMessage = "An error occurred while adding the note";
        });
    },
  },
};
</script>
