import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Relative asset paths so the static build works when served under any
  // mount path (e.g. the Freebuff deploy host) — not just at the root.
  base: "./",
  server: {
    host: "0.0.0.0",
    hmr: false,
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
