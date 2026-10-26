import { defineConfig } from "@playwright/test";

// Browser regression tests. Runs against a production build with the API mocked.
export default defineConfig({
  testDir: "e2e",
  timeout: 60000,
  use: { baseURL: "http://localhost:4199", viewport: { width: 1440, height: 900 } },
  webServer: { command: "npx vite preview --port 4199 --strictPort", url: "http://localhost:4199", reuseExistingServer: false },
});
