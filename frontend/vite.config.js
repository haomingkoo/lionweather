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
      host: true,
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
    preview: {
      port: 5173,
      host: "0.0.0.0",
      strictPort: true,
      // Allow Railway domains and custom domain
      allowedHosts: [
        "lionweather-frontend-production.up.railway.app",
        "lionweather.kooexperience.com",
        ".railway.app",
      ],
    },
  };
});
