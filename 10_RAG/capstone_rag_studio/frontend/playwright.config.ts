import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.resolve(__dirname, "..");
const PYTHON = process.env.RAG_STUDIO_PYTHON ?? "python3";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 35_000 },   // cold-start embedding/model loads plus a live-ish OpenAI-shaped round trip can take a while
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `${PYTHON} -m backend.mock_server_for_e2e`,
      cwd: PROJECT_ROOT,
      port: 8000,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      env: { RAG_STUDIO_E2E_PORT: "8000" },
    },
    {
      command: "npm run dev -- --port 5173",
      cwd: __dirname,
      port: 5173,
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
      env: { VITE_API_BASE_URL: "http://localhost:8000" },
    },
  ],
});
