import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The dev server runs on 3000 to match the port the docker-compose frontend
// service publishes, so local and containerized URLs line up.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 3000,
  },
  preview: {
    host: true,
    port: 3000,
  },
});
