import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  publicDir: false,
  server: {
    proxy: {
      "/api/max": { target: "http://localhost:8000" },
      "/api/tasks": {
        target: "http://localhost:8000",
        rewrite: (path) => path.replace(/^\/api\/tasks/, ""),
      },
      "/api/olympiads": {
        target: "http://localhost:8001",
        rewrite: (path) => path.replace(/^\/api\/olympiads/, ""),
      },
    },
  },
});
