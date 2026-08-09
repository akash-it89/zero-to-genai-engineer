import { expect, test } from "@playwright/test";
import { csCheck, csInput } from "./cloudscape";

test.describe("Error resilience", () => {
  test("a forced backend error is displayed and the route stays usable", async ({ page }) => {
    const variantName = `e2e-unindexed-${Date.now()}`;

    // Save a variant but never ingest/index anything for it — chatting against it
    // is guaranteed to surface a backend error (Index_Not_Built or No_Documents_Ingested).
    await page.goto("/#/build-strategies");
    await csInput(page, "variant-name-input").fill(variantName);
    await page.getByTestId("save-variant-button").click();
    await expect(page.getByTestId("save-message")).toContainText(variantName);

    await page.goto("/#/chat");
    await csCheck(page, `variant-checkbox-${variantName}`);
    await csInput(page, "question-input").fill("Does this work?");
    await page.getByTestId("ask-button").click();

    const errorBanner = page.getByTestId("chat-error");
    await expect(errorBanner).toBeVisible();
    await expect(errorBanner).toContainText(/index|ingested/i);

    // The route stays usable: the input is still editable and a retry is possible.
    await csInput(page, "question-input").fill("A different question?");
    await expect(csInput(page, "question-input")).toHaveValue("A different question?");
    await page.getByTestId("ask-button").click();
    await expect(page.getByTestId("chat-error")).toBeVisible();

    // Navigation still works — the app hasn't crashed.
    await page.getByRole("link", { name: "Ingest" }).click();
    await expect(page.getByTestId("ingest-page")).toBeVisible();
  });
});
