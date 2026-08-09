import { expect, test } from "@playwright/test";
import { csCheck, csSelect, csTextarea } from "./cloudscape";

test.describe("Evaluation Dashboard", () => {
  test("running the golden set against DeepEval shows a scores table with pass/fail + reasons", async ({ page }) => {
    await page.goto("/#/evaluation");
    await expect(page.getByTestId("evaluation-dashboard-page")).toBeVisible();

    await csSelect(page, "framework-select", "DeepEval");
    await csCheck(page, "metric-checkbox-context_precision");
    await page.getByTestId("run-evaluation-button").click();

    await expect(page.getByTestId("evaluation-results")).toBeVisible();
    await expect(page.getByTestId("metric-row-faithfulness")).toBeVisible();
    await expect(page.getByTestId("metric-pass-faithfulness")).toContainText("PASS");
    await expect(page.getByTestId("metric-reason-faithfulness")).toContainText("mocked judge");
    await expect(page.getByTestId("metric-bar-faithfulness")).toBeVisible();
  });

  test("golden records without a reference are reported as excluded", async ({ page }) => {
    await page.goto("/#/evaluation");
    const goldenSet = JSON.stringify([
      { id: "with-ref", question: "Q1", answer: "A1", contexts: ["c1"], reference: "A1" },
      { id: "without-ref", question: "Q2", answer: "A2", contexts: ["c2"] },
    ]);
    await csTextarea(page, "golden-set-textarea").fill(goldenSet);
    await csCheck(page, "metric-checkbox-context_precision");
    await page.getByTestId("run-evaluation-button").click();

    await expect(page.getByTestId("excluded-records")).toContainText("without-ref");
  });
});
