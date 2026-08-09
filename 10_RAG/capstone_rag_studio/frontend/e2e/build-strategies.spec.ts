import { expect, test } from "@playwright/test";
import { csInput, csOpenSelect, csSelect } from "./cloudscape";

test.describe("Build Strategies", () => {
  test("every selector renders from the Options_Catalog, flags unavailable/reserved, and saves a variant", async ({
    page,
  }) => {
    await page.goto("/#/build-strategies");
    await expect(page.getByTestId("build-strategies-page")).toBeVisible();

    // A reserved option is present, listed, and disabled with a "reserved" label.
    await csOpenSelect(page, "select-query_transform");
    const reservedOption = page.getByRole("option", { name: /reserved — unavailable in v1/ }).first();
    await expect(reservedOption).toBeVisible();
    await expect(reservedOption).toHaveAttribute("aria-disabled", "true");
    await page.keyboard.press("Escape");

    // An unavailable (missing-key) option is present and disabled.
    await csOpenSelect(page, "select-reranker");
    const cohereOption = page.getByRole("option", { name: /Cohere Rerank/ });
    await expect(cohereOption).toHaveAttribute("aria-disabled", "true");
    await page.keyboard.press("Escape");

    const variantName = `e2e-variant-${Date.now()}`;
    await csInput(page, "variant-name-input").fill(variantName);
    await csSelect(page, "select-embedding", "all-MiniLM-L6-v2 (local, 384d)");
    await csSelect(page, "select-reranker", "None (first-stage order)");
    await csSelect(page, "select-guardrail", "Disabled");
    await csSelect(page, "select-cache", "Disabled");
    await page.getByTestId("save-variant-button").click();

    await expect(page.getByTestId("save-message")).toContainText(variantName);
    await expect(page.getByTestId("variant-list")).toContainText(variantName);
  });

  test("duplicate variant name save shows an error", async ({ page }) => {
    await page.goto("/#/build-strategies");
    const variantName = `e2e-dup-${Date.now()}`;

    await csInput(page, "variant-name-input").fill(variantName);
    await page.getByTestId("save-variant-button").click();
    await expect(page.getByTestId("save-message")).toContainText(variantName);

    // Save again with the same name -> rejected.
    await csInput(page, "variant-name-input").fill(variantName);
    await page.getByTestId("save-variant-button").click();
    await expect(page.getByTestId("save-error")).toContainText("already exists");
  });
});
