import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  // Every test hits the same docker-compose app container (a single
  // uvicorn process), unlike the frontend/backend unit tests which get
  // isolated fixtures — running many browser contexts against it at once
  // causes real contention, not flakiness in the app itself. Serial with a
  // roomier assertion timeout matches what's actually being tested.
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  timeout: 15_000,
  expect: { timeout: 10_000 },
  use: {
    // The app + Postgres stack from ../docker-compose.yaml, exposed on
    // 8100 — not spawned by this config, since these tests exercise the
    // real container image, not a dev server.
    baseURL: process.env.BASE_URL ?? "http://localhost:8100",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
