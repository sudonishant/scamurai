import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { writeFile } from "node:fs/promises";

const AUTH = { Authorization: "Bearer dev-token-owner" };
let caseId = "";
let caseTitle = "";

const campaign = {
  platform: "playwright-synthetic-validation",
  accounts: ["alpha", "beta", "gamma"].map((handle) => ({ handle, platform_id: handle, profile_url: `https://example.social/${handle}` })),
  posts: ["00:05", "01:05", "02:05", "03:01", "03:02", "03:03"].map((time, index) => ({
    source_id: `playwright-${index}`,
    account_handle: ["alpha", "beta", "alpha", "alpha", "beta", "gamma"][index],
    url: `https://example.social/post/${index}`,
    text: "Bridge closed tonight share this urgent public safety update",
    language: "en",
    timestamp: `2026-10-20T${time}:00+00:00`,
    timestamp_precision: "minute",
    collection_status: "SYNTHETIC_VALIDATION_IMPORT",
    location: { name: "Darbhanga", latitude: 26.1542, longitude: 85.8918, precision: "city_reported" },
  })),
};

async function waitForJob(request: any, jobId: string) {
  await expect.poll(async () => (await (await request.get(`/api/v1/cases/${caseId}/jobs/${jobId}`, { headers: AUTH })).json()).lifecycle).toBe("completed");
}

// QA-only corpus created through the real API. The product itself has no demo mode.
test.beforeAll(async ({ request }) => {
  caseTitle = `Playwright validation ${Date.now()}`;
  const created = await request.post("/api/v1/cases", { headers: AUTH, data: { title: caseTitle, purpose: "Self-contained browser validation corpus", languages: ["en"] } });
  expect(created.ok()).toBeTruthy();
  caseId = (await created.json()).id;

  const imported = await request.post(`/api/v1/cases/${caseId}/uploads`, { headers: AUTH, multipart: {
    file: { name: "campaign.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(campaign)) }, kind: "json", meta: "{}",
  } });
  expect(imported.ok()).toBeTruthy();

  const png = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64");
  const media = await request.post(`/api/v1/cases/${caseId}/uploads`, { headers: AUTH, multipart: {
    file: { name: "one-pixel.png", mimeType: "image/png", buffer: png }, kind: "image", meta: "{}",
  } });
  expect(media.ok()).toBeTruthy();
  for (const workflow of ["media_forensics", "coordination_detection"]) {
    const run = await request.post(`/api/v1/cases/${caseId}/runs`, { headers: AUTH, data: { workflow, client_idempotency_key: `playwright-${workflow}-${Date.now()}` } });
    expect(run.ok()).toBeTruthy();
    await waitForJob(request, (await run.json()).job_id);
  }
  const findings = await request.get(`/api/v1/cases/${caseId}/findings`, { headers: AUTH });
  expect(findings.ok()).toBeTruthy();
  expect((await findings.json()).length).toBeGreaterThan(0);
});

test("live workspace renders real API data and access requirements", async ({ page }) => {
  const runtimeErrors: string[] = [];
  page.on("pageerror", (error) => runtimeErrors.push(error.message));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "SCAMURAI", exact: true })).toBeVisible();
  await page.getByLabel("Bearer token").fill("dev-token-owner");
  await page.getByRole("button", { name: "Open live workspace" }).click();
  await expect(page.getByRole("heading", { name: "Choose an investigation" })).toBeVisible();

  const caseRow = page.locator(".case-row").filter({ hasText: caseTitle });
  await caseRow.getByRole("button", { name: /Open case/i }).click();
  await expect(page.getByRole("heading", { name: "Situation awareness" })).toBeVisible();
  await expect(page.locator(".metric-card").filter({ hasText: "Collected posts" }).locator("strong")).toHaveText("6");

  await page.locator(".workspace-nav").getByRole("button", { name: "Narratives", exact: true }).click();
  await expect(page.locator(".narrative-list-item").first()).toContainText("bridge · closed · tonight");
  await expect(page.locator(".narrative-detail")).toContainText("Earliest & amplification order");

  await page.locator(".workspace-nav").getByRole("button", { name: "Geospatial", exact: true }).click();
  await expect(page.locator(".geo-map svg")).toBeVisible();
  await expect(page.locator(".geo-map")).toContainText("Darbhanga");

  await page.locator(".workspace-nav").getByRole("button", { name: "Media lab", exact: true }).click();
  await expect(page.locator(".media-detail")).toContainText("one-pixel.png");
  await expect(page.locator(".model-panel")).toBeVisible();

  await page.locator(".workspace-nav").getByRole("button", { name: "Network & behavior", exact: true }).click();
  await expect(page.locator(".account-graph svg")).toBeVisible();
  await expect(page.locator(".behavior-table")).toContainText("not bot probability");

  await page.locator(".workspace-nav").getByRole("button", { name: "Connectors", exact: true }).click();
  await expect(page.getByRole("heading", { name: "API & access requirements" })).toBeVisible();
  await expect(page.locator(".access-row")).toHaveCount(11);
  await expect(page.locator(".access-table")).toContainText("SCAMURAI_YOUTUBE_API_KEY");
  await expect(page.locator(".access-table")).toContainText("NOT AVAILABLE");
  expect(runtimeErrors).toEqual([]);
});

test("runtime has no demo path and real finding reviews refresh", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: /Explore synthetic demo/i })).toHaveCount(0);
  await page.getByLabel("Bearer token").fill("Bearer dev-token-owner");
  await page.getByRole("button", { name: "Open live workspace" }).click();
  await expect(page.getByRole("heading", { name: "Choose an investigation" })).toBeVisible();
  await expect(page.getByText("Synthetic demo is active")).toHaveCount(0);

  const caseRow = page.locator(".case-row").filter({ hasText: caseTitle });
  await caseRow.getByRole("button", { name: /Open case/i }).click();
  await page.locator(".workspace-nav").getByRole("button", { name: "Findings & review", exact: true }).click();
  const finding = page.locator(".finding-card").first();
  await expect(finding).toBeVisible();
  await finding.getByRole("button", { name: "Accept", exact: true }).click();
  await expect(finding).toContainText("review: accepted");
});

test("mobile live workspace has no page-level horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.getByRole("button", { name: /Case owner/i }).click();
  const caseRow = page.locator(".case-row").filter({ hasText: caseTitle });
  await caseRow.getByRole("button", { name: /Open case/i }).click();
  await expect(page.getByRole("heading", { name: "Situation awareness" })).toBeVisible();
  const dimensions = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, viewport: window.innerWidth }));
  expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.viewport + 1);
  await page.locator(".workspace-nav").getByRole("button", { name: "Accounts", exact: true }).click();
  await expect(page.locator(".account-evidence")).toBeVisible();
  const accountDimensions = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, viewport: window.innerWidth }));
  expect(accountDimensions.scroll).toBeLessThanOrEqual(accountDimensions.viewport + 1);
  await page.locator(".workspace-nav").getByRole("button", { name: "Geospatial", exact: true }).click();
  await expect(page.locator(".geo-map svg")).toBeVisible();
});

test("global search opens account and post evidence with reload-safe deep links", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Case owner/i }).click();
  const caseRow = page.locator(".case-row").filter({ hasText: caseTitle });
  await caseRow.getByRole("button", { name: /Open case/i }).click();

  await page.getByLabel("Search this investigation").fill("alpha");
  const accountResult = page.locator(".global-search-results button").filter({ hasText: "@alpha" }).first();
  await expect(accountResult).toBeVisible();
  await accountResult.click();
  await expect(page.getByRole("heading", { name: "@alpha", exact: true })).toBeVisible();
  await expect(page).toHaveURL(/tab=accounts/);
  await expect(page).toHaveURL(/account=/);
  await expect(page.locator(".account-evidence")).toContainText("First seen by Scamurai");

  await page.reload();
  await expect(page.getByRole("heading", { name: "@alpha", exact: true })).toBeVisible();
  await page.getByLabel("Search this investigation").fill("Bridge");
  const postResult = page.locator(".global-search-results button").filter({ hasText: "playwright-0" }).first();
  await expect(postResult).toBeVisible();
  await postResult.click();
  await expect(page).toHaveURL(/tab=narratives/);
  await expect(page).toHaveURL(/post=/);
  await expect(page.locator(".source-post-list article.focused-evidence")).toBeVisible();
});

test("alert review persists through direct deep-link reload", async ({ page, request }) => {
  const analytics = await request.get(`/api/v1/cases/${caseId}/analytics`, { headers: AUTH });
  expect(analytics.ok()).toBeTruthy();
  await page.goto("/");
  await page.getByRole("button", { name: /Case owner/i }).click();
  const caseRow = page.locator(".case-row").filter({ hasText: caseTitle });
  await caseRow.getByRole("button", { name: /Open case/i }).click();
  await page.locator(".workspace-nav").getByRole("button", { name: "Alerts", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Alerts & analyst decisions" })).toBeVisible();
  await page.locator(".review-queue-item").filter({ hasText: "Narrative acceleration" }).first().click();
  const alertId = await page.locator(".review-detail").getAttribute("data-alert-id");
  expect(alertId).toBeTruthy();
  await page.getByLabel("Review state").selectOption("acknowledged");
  await page.getByLabel(/Analyst note/).fill("Browser source coverage review");
  await page.getByRole("button", { name: "Save audited review" }).click();
  await expect.poll(async () => {
    const rows = await (await request.get(`/api/v1/cases/${caseId}/alerts`, { headers: AUTH })).json();
    return rows.find((row: any) => row.id === alertId)?.status;
  }).toBe("acknowledged");

  await page.goto(`/?case=${caseId}&tab=alerts&alert=${alertId}`);
  await expect(page.locator(".review-detail")).toHaveAttribute("data-alert-id", alertId!);
  await expect(page.getByLabel("Review state")).toHaveValue("acknowledged");
  await expect(page.getByLabel(/Analyst note/)).toHaveValue("Browser source coverage review");
});

test("hosted live API can be configured before login and survives an unauthorized response", async ({ page }) => {
  let authorized = false;
  const corsHeaders = {
    "access-control-allow-origin": "*",
    "access-control-allow-headers": "authorization,content-type",
    "access-control-allow-methods": "GET,OPTIONS",
  };
  await page.route("https://api.example.test/api/v1/cases", async (route) => {
    if (route.request().method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers: corsHeaders });
      return;
    }
    expect(route.request().headers().authorization).toBe("Bearer dev-token-owner");
    await route.fulfill({
      status: authorized ? 200 : 401,
      headers: { ...corsHeaders, "content-type": "application/json" },
      body: JSON.stringify(authorized ? [] : { detail: "Invalid development token" }),
    });
  });
  await page.goto("/");
  await page.locator(".login-api-config summary").click();
  await page.getByLabel("FastAPI base URL").fill("ftp://invalid.example");
  await page.getByRole("button", { name: "Save connection" }).click();
  await expect(page.getByRole("alert")).toContainText("must use HTTP or HTTPS");

  await page.getByLabel("FastAPI base URL").fill("https://api.example.test/");
  await page.getByRole("button", { name: "Save connection" }).click();
  await expect(page.locator(".inline-alert.success")).toContainText("https://api.example.test");
  await page.getByLabel("Bearer token").fill("dev-token-owner");
  await page.getByRole("button", { name: "Open live workspace" }).click();
  await expect(page.getByRole("alert")).toContainText("Invalid development token");
  expect(await page.evaluate(() => localStorage.getItem("scamurai.apiUrl"))).toBe("https://api.example.test");

  authorized = true;
  await page.getByRole("button", { name: "Open live workspace" }).click();
  await expect(page.getByRole("heading", { name: "Choose an investigation" })).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("scamurai.apiUrl"))).toBe("https://api.example.test");
});

test("a live transport failure shows an error and never offers demo evidence", async ({ page }) => {
  await page.route("**/api/v1/cases", (route) => route.abort("failed"));
  await page.goto("/");
  await page.getByLabel("Bearer token").fill("dev-token-owner");
  await page.getByRole("button", { name: "Open live workspace" }).click();
  await expect(page.locator(".inline-alert.danger")).toContainText("Live backend is unreachable");
  expect(await page.evaluate(() => localStorage.getItem("scamurai.devToken"))).toBeNull();
  await expect(page.getByRole("heading", { name: "Choose an investigation" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Explore synthetic demo/i })).toHaveCount(0);
});

test("core investigation screens have no detectable axe accessibility violations", async ({ page }) => {
  const violations: string[] = [];
  const audit: Record<string, unknown[]> = {};
  async function scan(screen: string) {
    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
      .analyze();
    audit[screen] = results.violations.map((violation) => ({
      id: violation.id, impact: violation.impact, help: violation.help,
      nodes: violation.nodes.map((node) => ({ target: node.target, summary: node.failureSummary })),
    }));
    for (const violation of results.violations) {
      for (const node of violation.nodes) {
        violations.push(`${screen} / ${violation.id}: ${node.target.join(" ")} — ${node.failureSummary || violation.help}`);
      }
    }
  }

  await page.goto("/");
  await scan("login");
  await page.getByRole("button", { name: /Case owner/i }).click();
  await expect(page.getByRole("heading", { name: "Choose an investigation" })).toBeVisible();
  await scan("case selection");
  const caseRow = page.locator(".case-row").filter({ hasText: caseTitle });
  await caseRow.getByRole("button", { name: /Open case/i }).click();
  await expect(page.getByRole("heading", { name: "Situation awareness" })).toBeVisible();
  await scan("overview");

  const views = [
    ["Alerts", ".review-detail"],
    ["Accounts", ".account-evidence"],
    ["Narratives", ".narrative-detail"],
    ["Network & behavior", ".behavior-table"],
    ["Geospatial", ".geo-map svg"],
    ["Media lab", ".media-detail"],
    ["Findings & review", ".finding-card"],
    ["Connectors", ".access-table"],
  ] as const;
  for (const [label, selector] of views) {
    await page.locator(".workspace-nav").getByRole("button", { name: label, exact: true }).click();
    await expect(page.locator(selector).first()).toBeVisible();
    await scan(label);
  }
  const reportPath = test.info().outputPath("axe-wcag-report.json");
  await writeFile(reportPath, JSON.stringify(audit, null, 2), "utf8");
  await test.info().attach("axe-wcag-report.json", { path: reportPath, contentType: "application/json" });
  expect(violations).toEqual([]);
});
