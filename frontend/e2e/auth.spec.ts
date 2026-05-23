import { test, expect } from "@playwright/test";

test.describe("Authentication", () => {
  test("login page renders and shows form", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: /login|sign in/i })).toBeVisible();
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();
  });

  test("login with wrong credentials shows error", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/email/i).fill("bad@example.com");
    await page.getByLabel(/password/i).fill("wrongpassword");
    await page.getByRole("button", { name: /login|sign in/i }).click();
    await expect(page.getByText(/invalid|error|incorrect/i)).toBeVisible({ timeout: 5000 });
  });

  test("nav shows login link when unauthenticated", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("link", { name: /login/i })).toBeVisible();
  });
});
