// Cloudscape components forward any `data-*` prop to their root DOM node
// (see @cloudscape-design/components/internal/base-component/getBaseProps)
// but don't declare `data-testid` in their typed prop interfaces. This helper
// spreads it in without fighting TypeScript's excess-property checks, so every
// existing Playwright `data-testid` selector keeps working unchanged.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function testId(id: string): any {
  return { "data-testid": id };
}
