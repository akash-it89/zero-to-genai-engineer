// Shared helpers for interacting with Cloudscape Design System components in
// Playwright. Cloudscape forwards `data-testid` to each component's root DOM
// node (not necessarily the native form element), and `Select` is a custom
// listbox rather than a native <select>, so the interaction patterns differ
// from plain HTML.
import type { Locator, Page } from "@playwright/test";

/** The native <input> nested inside a Cloudscape Input's root testid wrapper. */
export function csInput(page: Page, testid: string): Locator {
  return page.locator(`[data-testid="${testid}"] input`);
}

/** The native <textarea> nested inside a Cloudscape Textarea's root testid wrapper. */
export function csTextarea(page: Page, testid: string): Locator {
  return page.locator(`[data-testid="${testid}"] textarea`);
}

/** Opens a Cloudscape Select by its wrapper testid and clicks the option with the given
 * label — a string matches exactly, a RegExp matches by pattern (e.g. an option whose
 * label includes a generated timestamp suffix you can't spell out exactly). */
export async function csSelect(page: Page, testid: string, optionLabel: string | RegExp): Promise<void> {
  await page.locator(`[data-testid="${testid}"]`).click();
  const isExact = typeof optionLabel === "string";
  await page.getByRole("option", { name: optionLabel, exact: isExact }).click();
}

/** Opens a Cloudscape Select by its wrapper testid, without picking an option (for inspecting the open listbox). */
export async function csOpenSelect(page: Page, testid: string): Promise<void> {
  await page.locator(`[data-testid="${testid}"]`).click();
}

/** Clicks a Cloudscape Checkbox/Toggle by its wrapper testid.
 *
 * Cloudscape's `getBaseProps` attaches `data-testid` to the Checkbox/Toggle's root
 * <span>, which stretches to the full width of its flex/block container — the
 * visually-clickable control (native input + label) sits only at its left edge.
 * Clicking the wrapper's bounding-box *center* (Playwright's default) can land in
 * empty space to the right of the control and silently do nothing. Always click the
 * nested native input directly instead. */
export function csCheckboxInput(page: Page, testid: string): Locator {
  return page.locator(`[data-testid="${testid}"] input[type="checkbox"]`);
}

export async function csCheck(page: Page, testid: string): Promise<void> {
  const input = csCheckboxInput(page, testid);
  await input.click();
  if (!(await input.isChecked())) {
    await input.click();
  }
}
