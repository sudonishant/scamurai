import { test, expect } from "@playwright/test";
import type { Page } from "@playwright/test";
import { readFile } from "node:fs/promises";
import { resolve, sep, extname } from "node:path";

const DIST = resolve(process.cwd(), "dist");
const ORIGIN = "https://pages.example.test";
const MIME: Record<string, string> = {
  ".html": "text/html; charset=utf-8", ".js": "application/javascript",
  ".css": "text/css", ".json": "application/json", ".png": "image/png",
  ".svg": "image/svg+xml", ".woff": "font/woff", ".woff2": "font/woff2",
};

// Emulate GitHub Pages: existing files are served; missing paths return the
// production 404.html. No dev-server SPA fallback or external network is used.
async function emulatePages(page: Page) {
  await page.route(`${ORIGIN}/**`, async (route) => {
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

test("Pages fallback keeps unknown routes honest and offers a safe workspace link", async ({ page }) => {
  await emulatePages(page);
  const response = await page.goto(`${ORIGIN}/scamurai/not-a-real-investigation-route`);
  expect(response?.status()).toBe(404);
  await expect(page.getByRole("heading", { name: "Investigation route not found" })).toBeVisible();
  await expect(page.getByText("No investigation data was substituted.", { exact: false })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open live workspace" })).toHaveAttribute("href", "/scamurai/");
  await expect(page.getByText("Page not found · GitHub Pages")).toHaveCount(0);
});
