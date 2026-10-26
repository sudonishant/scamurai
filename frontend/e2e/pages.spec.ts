import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { resolve, sep, extname } from "node:path";

const DIST = resolve(process.cwd(), "dist");
const ORIGIN = "https://pages.example.test";
const STATIC_ORIGIN = "https://scamurai.github.io";
const MIME: Record<string, string> = {
  ".html": "text/html; charset=utf-8", ".js": "application/javascript",
  ".css": "text/css", ".json": "application/json", ".png": "image/png",
  ".svg": "image/svg+xml", ".woff": "font/woff", ".woff2": "font/woff2",
};

// Emulate GitHub Pages: existing files are served; missing paths return the
// production 404.html. No dev-server SPA fallback or external network is used.
async function emulatePages(page: Page, origin = ORIGIN) {
  await page.route(`${origin}/**`, async (route) => {
    const url = new URL(route.request().url());
    let relative: string;
    try {
      relative = decodeURIComponent(url.pathname).replace(/^\/scamurai\/?/, "");
    } catch {
      await route.fulfill({ status: 400, body: "Invalid path" });
      return;
    }
    const candidate = resolve(DIST, relative || "index.html");
    if (candidate !== DIST && !candidate.startsWith(`${DIST}${sep}`)) {
      await route.fulfill({ status: 403, body: "Blocked path" });
      return;
    }
    try {
      const body = await readFile(candidate);
      await route.fulfill({ status: 200, body, contentType: MIME[extname(candidate)] || "application/octet-stream" });
    } catch {
      await route.fulfill({
        status: 404, body: await readFile(resolve(DIST, "404.html")),
        contentType: "text/html; charset=utf-8",
      });
    }
  });
}

test.beforeAll(async () => {
  await readFile(resolve(DIST, "index.html"));
  await readFile(resolve(DIST, "404.html"));
});

test("Pages fallback recovers path-style case and evidence deep links", async ({ page }) => {
  const runtimeErrors: string[] = [];
  page.on("pageerror", (error) => runtimeErrors.push(error.message));
  await emulatePages(page);

  await page.goto(`${ORIGIN}/scamurai/cases/case-123/alerts/alert-456`);
  await expect(page).toHaveURL(/case=case-123/);
  await expect(page).toHaveURL(/tab=alerts/);
  await expect(page).toHaveURL(/alert=alert-456/);
  await expect(page.getByRole("heading", { name: "SCAMURAI", exact: true })).toBeVisible();

  await page.goto(`${ORIGIN}/scamurai/accounts/account-123?purpose=review`);
  await expect(page).toHaveURL(/purpose=review/);
  await expect(page).toHaveURL(/tab=accounts/);
  await expect(page).toHaveURL(/account=account-123/);
  await expect(page.getByRole("heading", { name: "SCAMURAI", exact: true })).toBeVisible();

  await page.goto(`${ORIGIN}/scamurai/posts/post-123`);
  await expect(page).toHaveURL(/tab=narratives/);
  await expect(page).toHaveURL(/post=post-123/);
  await expect(page.getByRole("heading", { name: "SCAMURAI", exact: true })).toBeVisible();
  expect(runtimeErrors).toEqual([]);
});

test("static preview labels synthetic cases and disables mock live-source collection", async ({ page }) => {
  let externalSourceRequests = 0;
  await page.route("https://dns.google/**", async (route) => {
    externalSourceRequests += 1;
    await route.abort();
  });
  await emulatePages(page, STATIC_ORIGIN);
  await page.goto(`${STATIC_ORIGIN}/scamurai/`);

  const notice = page.getByRole("note", { name: "Data provenance notice" });
  await expect(notice).toContainText("SYNTHETIC PUBLIC DEMO");
  await expect(notice).toContainText("not verified or source-backed");
  await expect(page.getByText("BROWSER DEMO CASES · LOCAL ONLY")).toBeVisible();
  await expect(page.getByText("SYNTHETIC · LOCAL ONLY")).toBeVisible();

  await page.locator(".case-row").getByRole("button", { name: /Open preview/i }).click();
  await expect(notice).toContainText("fictional examples");
  await page.locator(".workspace-nav").getByRole("button", { name: "Live OSINT", exact: true }).click();
  await expect(page.getByRole("button", { name: /Investigate target/i })).toBeDisabled();
  await expect(page.getByText("Live OSINT collection is disabled in this browser preview", { exact: false })).toBeVisible();
  expect(externalSourceRequests).toBe(0);
});

test("connected API mode identifies live case-scoped data", async ({ page }) => {
  await emulatePages(page);
  await page.route(`${ORIGIN}/api/v1/cases`, async (route) => {
    expect(route.request().headers().authorization).toBe("Bearer dev-token-owner");
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.goto(`${ORIGIN}/scamurai/`);
  await page.getByLabel("Bearer token").fill("dev-token-owner");
  await page.getByRole("button", { name: "Open live workspace" }).click();

  await expect(page.getByRole("heading", { name: "Choose an investigation" })).toBeVisible();
  await expect(page.getByRole("note", { name: "Data provenance notice" })).toContainText("LIVE API · CASE-SCOPED DATA");
  await expect(page.getByText("SYNTHETIC PUBLIC DEMO", { exact: true })).toHaveCount(0);
});

test("Pages fallback keeps unknown routes honest and offers a safe workspace link", async ({ page }) => {
  await emulatePages(page);
  const response = await page.goto(`${ORIGIN}/scamurai/not-a-real-investigation-route`);
  expect(response?.status()).toBe(404);
  await expect(page.getByRole("heading", { name: "Investigation route not found" })).toBeVisible();
  await expect(page.getByText("No investigation data was substituted.", { exact: false })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open live workspace" })).toHaveAttribute("href", "/scamurai/");
  await expect(page.getByText("Page not found · GitHub Pages")).toHaveCount(0);
});
