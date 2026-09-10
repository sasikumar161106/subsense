import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  test: {
    globals: true,
    environment: "node",
    testTimeout: 20000,
    alias: {
      "@subsense/shared": path.resolve(__dirname, "../../packages/shared/src"),
    },
  },
});
