import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backendPort = env.VITE_BACKEND_PORT || "8000";
  const apiTarget = env.VITE_API_TARGET || `http://localhost:${backendPort}`;

  return {
    plugins: [react()],
    server: {
      port: 5173,
      host: true, // Allow external access
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
    preview: {
      port: 5173,
      host: true, // Allow external access in preview mode (Railway uses this)
      allowedHosts: ["all"], // Allow all hosts for Railway deployment
    },
  };
});
