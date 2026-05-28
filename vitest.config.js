import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/panel/**/*.test.js"],
    environment: "node",
    globals: false,
    reporters: ["default"],
  },
});
