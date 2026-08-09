import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import { csCheck, csInput, csSelect } from "./cloudscape";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SAMPLE_FILE = path.join(__dirname, "fixtures", "sample.txt");

async function setUpVariantWithIndex(page: import("@playwright/test").Page, variantName: string) {
  await page.goto("/#/build-strategies");
  await csInput(page, "variant-name-input").fill(variantName);
  await csSelect(page, "select-embedding", "all-MiniLM-L6-v2 (local, 384d)");
  await csSelect(page, "select-reranker", "None (first-stage order)");
  await csSelect(page, "select-guardrail", "Disabled");
  await csSelect(page, "select-cache", "Disabled");
  await page.getByTestId("save-variant-button").click();
  await expect(page.getByTestId("save-message")).toContainText(variantName);

  await page.goto("/#/ingest");
  await page.getByTestId("file-input").setInputFiles(SAMPLE_FILE);
  await page.getByTestId("ingest-button").click();
  await expect(page.getByTestId("ingested-list")).toContainText("sample.txt");

  await csSelect(page, "index-variant-select", variantName);
  await page.getByTestId("build-index-button").click();
  await expect(page.getByTestId("index-status")).toContainText("Indexed");
}

test.describe("Chat & Compare", () => {
  test("ask returns a cited answer with per-stage timing + filtered count, evaluate, and view trace", async ({
    page,
  }) => {
    const variantName = `e2e-chat-${Date.now()}`;
    await setUpVariantWithIndex(page, variantName);

    await page.goto("/#/chat");
    await expect(page.getByTestId("chat-compare-page")).toBeVisible();
    await csCheck(page, `variant-checkbox-${variantName}`);

    await csInput(page, "question-input").fill("What is the capital of France?");
    await page.getByTestId("ask-button").click();

    const card = page.getByTestId(`result-card-${variantName}`);
    await expect(card).toBeVisible();
    await expect(card.getByTestId(`answer-${variantName}`)).toContainText("Answer to");
    await expect(card.getByTestId(`filtered-count-${variantName}`)).toContainText("Governance filtered");
    await expect(card.getByTestId(`timing-${variantName}`)).toContainText("generate");

    await card.getByTestId(`evaluate-button-${variantName}`).click();
    await expect(card.getByTestId(`evaluation-${variantName}`)).toBeVisible();

    await card.getByTestId(`trace-button-${variantName}`).click();
    await expect(card.getByTestId(`trace-${variantName}`)).toContainText("generate");
  });

  test("chat controls only appear on the Chat & Compare route", async ({ page }) => {
    await page.goto("/#/ingest");
    await expect(page.getByTestId("question-input")).toHaveCount(0);

    await page.goto("/#/build-strategies");
    await expect(page.getByTestId("question-input")).toHaveCount(0);

    await page.goto("/#/chat");
    await expect(page.getByTestId("question-input")).toHaveCount(1);
  });
});
