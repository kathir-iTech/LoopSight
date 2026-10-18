import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 40_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? "github" : "list",
  use: { baseURL: "http://127.0.0.1:3100", trace: "retain-on-failure",
    launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE, args: ["--no-sandbox"] } },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: `${process.env.LOOPSIGHT_TEST_PYTHON || "../../.venv/bin/python"} -m uvicorn services.inference.main:app --app-dir ../.. --host 127.0.0.1 --port 8100`,
      url: "http://127.0.0.1:8100/health", timeout: 60_000,
      env: { GEMINI_API_KEY: "", DYNAMO_TABLE_NAME: "", LOOPSIGHT_EVIDENCE_BUCKET: "", LOOPSIGHT_API_TOKEN: "", DEMO_MODE: "",
        LOOPSIGHT_SQLITE_PATH: `/tmp/loopsight-browser-${process.pid}.sqlite3`, OPENBLAS_NUM_THREADS: "1", OMP_NUM_THREADS: "1" },
    },
    {
      command: "npm run start -- --hostname 127.0.0.1 --port 3100",
      url: "http://127.0.0.1:3100", timeout: 60_000,
      env: { INFERENCE_API_URL: "http://127.0.0.1:8100", INFERENCE_API_TOKEN: "", DEMO_MODE: "", NEXT_TELEMETRY_DISABLED: "1" },
    },
  ],
});
