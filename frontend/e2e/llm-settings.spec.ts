import { test, expect } from "@playwright/test";

test.describe("LLM Settings page", () => {
  test("page is accessible structure check (no auth needed for smoke)", async ({ page }) => {
    await page.goto("/admin/llm-settings");
    // Either shows login redirect or the LLM settings page
    const url = page.url();
    if (url.includes("login")) {
      await expect(page.getByLabel(/email/i)).toBeVisible();
    } else {
      await expect(page.getByText(/LLM Provider/i)).toBeVisible({ timeout: 5000 });
    }
  });
});
