import { defineRailway, github, preserve, project, service } from "railway/iac";

// Manages only the two app services. The Postgres database and its volume stay
// unmanaged: the SDK's postgres() means postgres:18, and the live database is v17.
export const partial = "lionweather-app";

export default defineRailway(() => {
  const lionweatherFrontend = service("lionweather-frontend", {
    source: github("haomingkoo/lionweather", { checkSuites: false, rootDirectory: "/frontend" }),
    build: { builder: "RAILPACK" },
    deploy: { restartPolicyType: "ON_FAILURE", restartPolicyMaxRetries: 10 },
    replicas: { "asia-southeast1-eqsg3a": 1 },
    domains: ["lionweather.kooexperience.com"],
    env: {
      VITE_API_BASE_URL: preserve(),
      VITE_API_TARGET: preserve(),
    },
  });
  const lionweatherBackend = service("lionweather-backend", {
    source: github("haomingkoo/lionweather", { checkSuites: false, rootDirectory: "/backend" }),
    build: { builder: "DOCKERFILE", dockerfilePath: "Dockerfile" },
    deploy: { restartPolicyType: "ON_FAILURE", restartPolicyMaxRetries: 10 },
    replicas: { "asia-southeast1-eqsg3a": 1 },
    env: {
      ADMIN_SECRET: preserve(),
      DATABASE_URL: preserve(),
      DATA_ONE_MAP_API_KEY: preserve(),
      FIRMS_MAP_KEY: preserve(),
      WEATHERAPI_KEY: preserve(),
    },
  });

  return project("rare-possibility", {
    resources: [lionweatherFrontend, lionweatherBackend],
  });
});
