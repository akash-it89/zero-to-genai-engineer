import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";
import { csCheck, csInput, csSelect } from "./cloudscape";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SAMPLE_FILE = path.join(__dirname, "fixtures", "sample.txt");

async function switchPrincipal(page: import("@playwright/test").Page, id: string, roles = "") {
  await page.goto("/#/governance");
  await csInput(page, "principal-id-input").fill(id);
  await csInput(page, "principal-roles-input").fill(roles);
  await page.getByTestId("switch-principal-button").click();
  await expect(page.getByTestId("current-principal")).toContainText(id);
}

test.describe("Governance", () => {
  test("switching principal changes which content is accessible", async ({ page }) => {
    const variantName = `e2e-gov-${Date.now()}`;

    // Ingest as "carol" with a RESTRICTED policy naming only "bob".
    await switchPrincipal(page, "carol");

    await page.goto("/#/build-strategies");
    await csInput(page, "variant-name-input").fill(variantName);
    await csSelect(page, "select-embedding", "all-MiniLM-L6-v2 (local, 384d)");
    await csSelect(page, "select-reranker", "None (first-stage order)");
    await csSelect(page, "select-guardrail", "Disabled");
    await csSelect(page, "select-cache", "Disabled");
    await page.getByTestId("save-variant-button").click();
    await expect(page.getByTestId("save-message")).toContainText(variantName);

    await page.goto("/#/ingest");
    await csSelect(page, "access-level-select", "RESTRICTED");
    await csInput(page, "acl-input").fill("bob");
    await page.getByTestId("file-input").setInputFiles(SAMPLE_FILE);
    await page.getByTestId("ingest-button").click();
    await expect(page.getByTestId("ingested-list")).toContainText("sample.txt");

    await csSelect(page, "index-variant-select", variantName);
    await page.getByTestId("build-index-button").click();
    await expect(page.getByTestId("index-status")).toContainText("Indexed");

    // "alice" is neither the owner nor in the ACL -> no accessible context.
    await switchPrincipal(page, "alice");
    await page.goto("/#/chat");
    await csCheck(page, `variant-checkbox-${variantName}`);
    await csInput(page, "question-input").fill("What is the capital of France?");
    await page.getByTestId("ask-button").click();

    const aliceCard = page.getByTestId(`result-card-${variantName}`);
    await expect(aliceCard.getByTestId(`answer-${variantName}`)).toContainText("No accessible context");
    await expect(aliceCard.getByTestId(`filtered-count-${variantName}`)).not.toContainText("filtered: 0");

    // "bob" is named in the ACL -> gets a real answer.
    await switchPrincipal(page, "bob");
    await page.goto("/#/chat");
    await csCheck(page, `variant-checkbox-${variantName}`);
    await csInput(page, "question-input").fill("What is the capital of France?");
    await page.getByTestId("ask-button").click();

    const bobCard = page.getByTestId(`result-card-${variantName}`);
    await expect(bobCard.getByTestId(`answer-${variantName}`)).toContainText("Answer to");
    await expect(bobCard.getByTestId(`filtered-count-${variantName}`)).toContainText("filtered: 0");
  });
});
