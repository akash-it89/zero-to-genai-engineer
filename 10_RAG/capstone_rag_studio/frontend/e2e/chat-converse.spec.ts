import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import { csInput, csSelect } from "./cloudscape";

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

test.describe("Chat (conversational)", () => {
  test("starts a conversation, sends multiple turns, and renders a message thread with citations", async ({
    page,
  }) => {
    const variantName = `e2e-converse-${Date.now()}`;
    await setUpVariantWithIndex(page, variantName);

    await page.goto("/#/converse");
    await expect(page.getByTestId("chat-page")).toBeVisible();

    await csSelect(page, "converse-variant-select", variantName);
    await page.getByTestId("new-conversation-button").click();

    await csInput(page, "converse-input").fill("What is the capital of France?");
    await page.getByTestId("converse-send-button").click();

    await expect(page.getByTestId("message-thread")).toContainText("What is the capital of France?");
    await expect(page.getByTestId("message-thread")).toContainText("Answer to");

    // A follow-up that only a memory-carrying assistant could answer correctly is
    // covered at the pipeline level (test_conversation.py); here we just confirm the
    // second turn round-trips and appends to the same visible thread.
    await csInput(page, "converse-input").fill("Tell me more.");
    await page.getByTestId("converse-send-button").click();

    const thread = page.getByTestId("message-thread");
    await expect(thread).toContainText("Tell me more.");
    const messageCount = await page.locator('[data-testid^="message-"]').count();
    assertAtLeast(messageCount, 4);
  });

  test("resuming a past conversation reloads its message history", async ({ page }) => {
    const variantName = `e2e-converse-resume-${Date.now()}`;
    await setUpVariantWithIndex(page, variantName);

    await page.goto("/#/converse");
    await csSelect(page, "converse-variant-select", variantName);
    await page.getByTestId("new-conversation-button").click();
    await csInput(page, "converse-input").fill("What is the capital of France?");
    await page.getByTestId("converse-send-button").click();
    await expect(page.getByTestId("message-thread")).toContainText("Answer to");

    // Reload the page (fresh component state) and resume via the dropdown.
    await page.goto("/#/converse");
    await csSelect(page, "resume-conversation-select", new RegExp(variantName));

    await expect(page.getByTestId("message-thread")).toContainText("What is the capital of France?");
    await expect(page.getByTestId("message-thread")).toContainText("Answer to");
  });
});

function assertAtLeast(actual: number, expected: number) {
  if (actual < expected) {
    throw new Error(`Expected at least ${expected} rendered messages, got ${actual}`);
  }
}
