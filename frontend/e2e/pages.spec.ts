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

const GEO_CASE_ID = "geo-status-fixture";

function geoAnalytics({ coverage = {}, geospatial = {} }: { coverage?: Record<string, unknown>; geospatial?: Record<string, unknown> } = {}) {
  return {
    schema_version: "scamurai-analytics-test",
    generated_at: "2026-10-27T00:00:00Z",
    reference_time: null,
    scope: "Fixture case only",
    coverage: { posts: 0, ...coverage },
    narratives: [],
    automation: [],
    network: { nodes: [], edges: [], clusters: [], limitations: [] },
    geospatial: { points: [], locations: [], anomalies: [], map_note: "Aggregates only.", ...geospatial },
    alerts: [],
    limitations: [],
  };
}

async function openGeoCase(page: Page, analytics: ReturnType<typeof geoAnalytics>) {
  await emulatePages(page);
  await page.route(`${ORIGIN}/api/v1/cases/**`, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    const casePath = `/api/v1/cases/${GEO_CASE_ID}`;
    let body: unknown;
    if (pathname === casePath) {
      body = {
        id: GEO_CASE_ID, title: "Geo status fixture", purpose: "", allowed_sources: [],
        date_from: null, date_to: null, languages: ["en"], retention_days: null,
        limits: {}, my_role: "owner", created_at: "2026-10-27T00:00:00Z",
      };
    } else if (pathname === `${casePath}/analytics`) {
      body = analytics;
    } else if (pathname === `${casePath}/graph`) {
      body = { nodes: [], edges: [], truncated: false, total_nodes: 0, total_edges: 0 };
    } else if (pathname === `${casePath}/jobs`) {
      body = [];
    } else {
      await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Unexpected fixture endpoint" }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.addInitScript(() => localStorage.setItem("scamurai.devToken", "dev-token-owner"));
  await page.goto(`${ORIGIN}/scamurai/?case=${GEO_CASE_ID}&tab=geo`);
  await expect(page.getByRole("heading", { name: "Location patterns" })).toBeVisible();
}

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

test("GeoView identifies an API-reported no-observation state", async ({ page }) => {
  await openGeoCase(page, geoAnalytics({
    coverage: { geolocated_posts: 0 },
    geospatial: { privacy: { minimum_group_size: 3, suppressed_groups: 0, suppressed_observations: 0 } },
  }));

  await expect(page.getByRole("heading", { name: "No geo observations reported" })).toBeVisible();
  await expect(page.getByText(/API reports 0 linked posts with geospatial observations/)).toBeVisible();
});

test("GeoView explains threshold suppression without exposing withheld locations", async ({ page }) => {
  await openGeoCase(page, geoAnalytics({
    coverage: { geolocated_posts: 2 },
    geospatial: {
      privacy: {
        minimum_group_size: 3, suppressed_groups: 1, suppressed_observations: 2,
        suppressed_location_labels: ["Hidden District Must Not Render"],
      },
    },
  }));

  await expect(page.getByRole("heading", { name: "Locations withheld by privacy threshold" })).toBeVisible();
  await expect(page.getByText("1 group withheld.", { exact: false })).toBeVisible();
  await expect(page.getByText("2 observations withheld.", { exact: false })).toBeVisible();
  await expect(page.getByText("Suppression is not evidence of absence.", { exact: false })).toBeVisible();
  await expect(page.getByText("Hidden District Must Not Render", { exact: false })).toHaveCount(0);
  await expect(page.locator(".geo-map svg")).toHaveCount(0);
});

test("GeoView shows populated aggregates only when the API returns them", async ({ page }) => {
  await openGeoCase(page, geoAnalytics({
    coverage: { geolocated_posts: 3 },
    geospatial: {
      points: [{ key: "patna", label: "Patna", latitude: 25.5941, longitude: 85.1376, count: 2, intensity: 0.2, anomaly: false }],
      locations: [{ key: "patna", label: "Patna", observation_count: 2, post_count: 2, protected_subject_count: 3, narrative_ids: [], sources: ["authorized_import"], precisions: ["city_reported"], last_observed: "2026-10-26T00:00:00Z", baseline_status: "insufficient_baseline", anomaly: null }],
      privacy: { minimum_group_size: 3, suppressed_groups: 0, suppressed_observations: 0 },
    },
  }));

  await expect(page.locator(".geo-map svg")).toBeVisible();
  await expect(page.locator(".data-table")).toContainText("Patna");
  await expect(page.locator(".metric-card").filter({ hasText: "Displayed geo observations" })).toContainText("2");
  await expect(page.locator(".metric-card").filter({ hasText: "Displayed geo observations" })).toContainText("3 linked posts reported");
});

test("GeoView does not invent zero counts when coverage and privacy totals are missing", async ({ page }) => {
  await openGeoCase(page, geoAnalytics({
    coverage: {},
    geospatial: { privacy: { minimum_group_size: 3 } },
  }));

  await expect(page.getByRole("heading", { name: "Geospatial status unavailable" })).toBeVisible();
  await expect(page.getByText(/does not include enough coverage and privacy counts/)).toBeVisible();
  await expect(page.getByText(/0 linked posts|0 groups|0 observations/i)).toHaveCount(0);
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
