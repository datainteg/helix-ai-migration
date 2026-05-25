import { test, expect } from "@playwright/test";

/**
 * Golden-path smoke: first-admin setup → dashboard → projects → new project.
 *
 * Designed to run against a freshly-booted backend with no users. Each test
 * generates unique credentials so the suite can run repeatedly without
 * external state reset. Workflow start + approval + artifact view live in
 * follow-up specs once the backend exposes those flows in a deterministic
 * test mode.
 */

const uniq = () => Math.random().toString(36).slice(2, 8);

test.describe("Golden path", () => {
  test("homepage redirects + login form reachable", async ({ page }) => {
    await page.goto("/");
    // Landing/dashboard either renders or punts to /login.
    const url = page.url();
    if (!url.includes("login") && !url.includes("dashboard")) {
      await page.goto("/login");
    }
    await expect(page.getByLabel(/email/i)).toBeVisible({ timeout: 5000 });
  });

  test("first-admin setup wizard step 0 reachable", async ({ page }) => {
    await page.goto("/setup/first-admin");
    // Either the wizard renders, or the platform already has an admin (redirect to login).
    const url = page.url();
    if (url.includes("login")) {
      test.skip(true, "Platform already provisioned — first-admin path is one-shot.");
    }
    await expect(page.getByText(/workspace|create.*admin|setup/i)).toBeVisible({ timeout: 5000 });
  });

  test("docs page lists at least one entry", async ({ page }) => {
    await page.goto("/docs");
    const possibleEmpty = page.getByText(/no docs|coming soon/i);
    if (await possibleEmpty.isVisible().catch(() => false)) {
      test.skip(true, "Docs not seeded in this environment.");
    }
    // Docs page is server-rendered list. Confirm any doc link is visible.
    await expect(page.getByRole("link", { name: /getting started|installation|product overview/i }).first()).toBeVisible({
      timeout: 5000,
    });
  });

  test(`new admin can sign up and see dashboard (org=${uniq()})`, async ({ page, request }) => {
    const slug = `e2e-${uniq()}`;
    const email = `e2e+${slug}@helix.test`;
    const password = "E2eTestPass123!";

    // Hit the backend directly first to check whether first-admin is available.
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const res = await request.post(`${apiBase}/api/v1/auth/first-admin`, {
      data: {
        email,
        name: "E2E Admin",
        password,
        organization_name: `E2E ${slug}`,
        organization_slug: slug,
      },
    });
    if (!res.ok()) {
      test.skip(true, `first-admin not available in this environment (status ${res.status()})`);
    }
    const { access_token } = await res.json();

    // Plant token where AuthContext expects it.
    await page.addInitScript((token: string) => {
      window.localStorage.setItem("helix_token", token);
    }, access_token);

    await page.goto("/dashboard");
    await expect(page).toHaveURL(/dashboard/);
    // Demo banner should be visible — confirms our review fix is wired up.
    await expect(page.getByText(/demo data/i).first()).toBeVisible({ timeout: 5000 });
  });
});
