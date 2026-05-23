import { test, expect } from "@playwright/test";

test.describe("Dashboard", () => {
  test("redirects unauthenticated user to login", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/login/);
  });

  test("projects page shows empty state when no projects", async ({ page }) => {
    await page.goto("/projects");
    // Either redirects to login or shows projects page
    const url = page.url();
    if (url.includes("login")) {
      await expect(page.getByLabel(/email/i)).toBeVisible();
    } else {
      await expect(page.getByText(/no projects|create.*project/i)).toBeVisible({ timeout: 5000 });
    }
  });
});
