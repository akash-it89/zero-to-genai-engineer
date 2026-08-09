import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import { csInput, csSelect } from "./cloudscape";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SAMPLE_FILE = path.join(__dirname, "fixtures", "sample.txt");

test.describe("Ingest", () => {
  test("ACL controls only appear for RESTRICTED/PRIVATE, and upload + index build succeed", async ({ page }) => {
    // First, save a variant to build an index for.
    const variantName = `e2e-ingest-${Date.now()}`;
    await page.goto("/#/build-strategies");
    await csInput(page, "variant-name-input").fill(variantName);
    await csSelect(page, "select-embedding", "all-MiniLM-L6-v2 (local, 384d)");
    await csSelect(page, "select-reranker", "None (first-stage order)");
    await csSelect(page, "select-guardrail", "Disabled");
    await csSelect(page, "select-cache", "Disabled");
    await page.getByTestId("save-variant-button").click();
    await expect(page.getByTestId("save-message")).toContainText(variantName);

    await page.goto("/#/ingest");
    await expect(page.getByTestId("ingest-page")).toBeVisible();

    // Regression: the "Files" label must be wired to the real file input via
    // matching id/for, or clicking the visible label text (the natural first
    // click for most users, not just the tiny native browser button) silently
    // does nothing — Cloudscape's FormField only generates this link when
    // given an explicit controlId matching the input's actual id.
    const fileInputId = await page.getByTestId("file-input").getAttribute("id");
    await expect(page.locator(`label[for="${fileInputId}"]`)).toHaveText("Files");

    // PUBLIC is the default — ACL controls are hidden.
    await expect(page.getByTestId("acl-controls")).toHaveCount(0);

    await csSelect(page, "access-level-select", "RESTRICTED");
    await expect(page.getByTestId("acl-controls")).toBeVisible();
    await csSelect(page, "access-level-select", "PUBLIC");
    await expect(page.getByTestId("acl-controls")).toHaveCount(0);

    await page.getByTestId("file-input").setInputFiles(SAMPLE_FILE);
    await page.getByTestId("ingest-button").click();
    await expect(page.getByTestId("ingested-list")).toContainText("sample.txt");

    await csSelect(page, "index-variant-select", variantName);
    await page.getByTestId("build-index-button").click();
    await expect(page.getByTestId("index-status")).toContainText("Indexed");
  });
});
