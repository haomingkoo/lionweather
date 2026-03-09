import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backendPort = env.VITE_BACKEND_PORT || "8000";
  const rawTarget = env.VITE_API_TARGET || `http://localhost:${backendPort}`;
  // Force https so the proxy target is never http in production (mixed-content)
  const apiTarget = rawTarget.replace(/^http:\/\//, "https://");
  const previewPort = parseInt(process.env.PORT || env.PORT || "5173", 10);

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
      port: previewPort,
      host: "0.0.0.0",
      strictPort: false,
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
        },
      },
      // Allow Railway domains and custom domain
      allowedHosts: [
        "lionweather-frontend-production.up.railway.app",
        "lionweather.kooexperience.com",
        "weather.kooexperience.com",
        ".railway.app",
      ],
    },
  };
});
