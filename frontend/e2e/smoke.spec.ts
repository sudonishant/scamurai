import { test, expect } from "@playwright/test";

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

async function loginAndOpenCase(page: any) {
  await page.goto("/");
  await page.getByLabel("Bearer token").fill("dev-token-owner");
  await page.getByRole("button", { name: "Open live workspace" }).click();
  await expect(page.getByRole("heading", { name: "Choose an investigation" })).toBeVisible();
  const caseRow = page.locator(".case-row").filter({ hasText: caseTitle });
  await caseRow.getByRole("button", { name: /Open case/i }).click();
  await expect(page.getByRole("heading", { name: "Situation awareness" })).toBeVisible();
}

async function installFetchStub(page: any, mode: "exports" | "comments" | "sources") {
  await page.addInitScript((testMode) => {
    const state: any = { testMode, exportReads: 0, exportRecords: [], submittedExport: null, commentQueries: [], initialCommentFailures: 2, sourceRequests: [] };
    (window as any).__scamuraiE2E = state;
    const nativeFetch = window.fetch.bind(window);
    const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const requestUrl = input instanceof Request ? input.url : String(input);
      const url = new URL(requestUrl, window.location.href);
      const method = (init?.method || (input instanceof Request ? input.method : "GET")).toUpperCase();
      if (testMode === "exports" && url.pathname.endsWith("/exports")) {
        if (method === "GET") {
          state.exportReads += 1;
          if (state.exportReads <= 2) {
            await new Promise((resolve) => setTimeout(resolve, 350));
            return json({ detail: "temporary exports outage" }, 503);
          }
          return json(state.exportRecords);
        }
        state.submittedExport = JSON.parse(String(init?.body || "{}"));
        const created = { id: "pw-selected-export", fmt: "json", scope: "selected", redaction_mode: "redacted", status: "ready", sha256: "abcdef0123456789", expires_at: null, created_at: "2026-10-24T00:00:00Z", download_url: null };
        state.exportRecords = [created, ...state.exportRecords];
        return json(created, 202);
      }
      if (url.pathname.endsWith("/comments")) {
        const query = url.searchParams.get("q") || "";
        state.commentQueries.push(query);
        if (testMode === "comments" && state.initialCommentFailures > 0) {
          state.initialCommentFailures -= 1;
          return json({ detail: "comments temporarily unavailable" }, 503);
        }
        if (testMode === "comments" && !query) await new Promise((resolve) => setTimeout(resolve, 350));
        return json({ total: 2, coverage: [], items: [
          { id: "comment-selected-1", stable_id: null, raw_text: "First selectable comment", author_ref: "alpha", timestamp: null, timestamp_precision: "unknown", parent_comment_id: null, permalink: null, permalink_status: "not_available", review_status: "unreviewed", uncertain_duplicate: false, analysis: null },
          { id: "comment-selected-2", stable_id: null, raw_text: testMode === "comments" ? "alpha test comment" : "Second selectable comment", author_ref: "beta", timestamp: null, timestamp_precision: "unknown", parent_comment_id: null, permalink: null, permalink_status: "not_available", review_status: "unreviewed", uncertain_duplicate: false, analysis: null },
        ] });
      }
      if (testMode === "sources" && url.pathname.endsWith("/connectors/mastodon/import")) {
        state.sourceRequests.push(JSON.parse(String(init?.body || "{}")));
        return json({ posts: 2, accounts: 1, geo_observations: 0, coverage: "One permitted public page imported.", statuses_returned: 2, skipped_reblogs: 0 });
      }
      const response = await nativeFetch(input, init);
      return response;
    };
  }, mode);
}

async function installAlertFixture(page: any) {
  await page.addInitScript(() => {
    const nativeFetch = window.fetch.bind(window);
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const requestUrl = input instanceof Request ? input.url : String(input);
      const response = await nativeFetch(input, init);
      const url = new URL(requestUrl, window.location.href);
      if (!url.pathname.endsWith("/analytics") || !response.ok) return response;
      const data: any = await response.json();
      data.alerts = [
        { id: "alert-test-narrative", type: "narrative_acceleration", title: "Narrative destination test", severity: "high", attention_score: 80, narrative_id: "narrative-test", rule: "test rule", recommended_action: "Review narrative" },
        { id: "alert-test-coordination", type: "coordination_review", title: "Coordination destination test", severity: "review", attention_score: 50, narrative_id: null, rule: "test rule", recommended_action: "Review network" },
        { id: "alert-test-geo", type: "geospatial_spike", title: "Geospatial destination test", severity: "elevated", attention_score: 60, narrative_id: null, rule: "test rule", recommended_action: "Review geo" },
        { id: "alert-test-gap", type: "data_coverage_gap", title: "Coverage destination test", severity: "data_gap", attention_score: null, narrative_id: null, rule: "test rule", recommended_action: "Review access" },
      ];
      return new Response(JSON.stringify(data), { status: response.status, headers: { "content-type": "application/json" } });
    };
  });
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
  await page.locator(".workspace-nav").getByRole("button", { name: "Geospatial", exact: true }).click();
  await expect(page.locator(".geo-map svg")).toBeVisible();
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


test("collection controls accept manual evidence and expose authorized workflow actions", async ({ page }) => {
  await loginAndOpenCase(page);
  await page.getByRole("button", { name: /Collect & run/i }).click();
  await expect(page.getByRole("heading", { name: "Add evidence & run workflows" })).toBeVisible();
  await expect(page.getByText("Authorized file import")).toBeVisible();
  await expect(page.getByRole("button", { name: "Coordination features" })).toBeEnabled();
  await page.getByPlaceholder("Paste source text…").fill("Playwright manual evidence control validation.");
  await page.getByRole("button", { name: "Add text", exact: true }).click();
  await expect(page.locator(".inline-alert.success")).toContainText("Manual text evidence added.");
});

test("active workspace tab is addressable and restored from the URL", async ({ page }) => {
  await loginAndOpenCase(page);
  await page.locator(".workspace-nav").getByRole("button", { name: "Narratives", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`[?&]case=${caseId}.*[?&]tab=narratives|[?&]tab=narratives.*[?&]case=${caseId}`));
  await page.reload();
  await expect(page.locator('.workspace-nav button[aria-current="page"]')).toHaveText("Narratives");
  await page.goBack();
  await expect(page.locator('.workspace-nav button[aria-current="page"]')).toHaveText("Overview");
});

test("evidence graph relationships open their drill-down drawer", async ({ page }) => {
  await loginAndOpenCase(page);
  await page.locator(".workspace-nav").getByRole("button", { name: "Evidence graph", exact: true }).click();
  const inspect = page.getByRole("button", { name: "Inspect relationships" });
  await expect(inspect).toBeEnabled();
  await inspect.click();
  const relationship = page.locator(".graph-relationship-option").first();
  await expect(relationship).toBeVisible();
  await relationship.click();
  await expect(page.locator(".panel.right h3")).toHaveText("Relationship");
  await expect(page.locator(".panel.right")).toContainText("How was this derived?");
});

test("selected-record exports select comments, report failures, and send selected IDs", async ({ page }) => {
  await installFetchStub(page, "exports");
  await loginAndOpenCase(page);
  await page.locator(".workspace-nav").getByRole("button", { name: "Exports", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Loading exports");
  await expect(page.getByRole("alert")).toContainText("temporary exports outage");
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByText("No exports have been generated for this case.")).toBeVisible();
  await page.getByLabel("Scope").selectOption("selected");
  const firstComment = page.locator(".export-selection-item").filter({ hasText: "First selectable comment" });
  await expect(firstComment).toBeVisible();
  const generate = page.getByRole("button", { name: "Generate", exact: true });
  await expect(generate).toBeDisabled();
  await firstComment.locator("input").check();
  await expect(generate).toBeEnabled();
  await generate.click();
  await expect(page.locator("tbody tr").filter({ hasText: "selected" })).toBeVisible();
  const submitted = await page.evaluate(() => (window as any).__scamuraiE2E.submittedExport);
  expect(submitted).toMatchObject({ scope: "selected", selected_ids: ["comment-selected-1"] });
});

test("comments show retryable errors and debounce search until typing settles", async ({ page }) => {
  await installFetchStub(page, "comments");
  await loginAndOpenCase(page);
  await page.locator(".workspace-nav").getByRole("button", { name: "Comments", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("comments temporarily unavailable");
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByRole("status")).toContainText("Loading comments");
  await expect(page.getByText("alpha test comment")).toBeVisible();
  const filter = page.getByLabel("Filter comments");
  await filter.fill("a");
  await filter.fill("al");
  await filter.fill("alpha");
  await expect.poll(async () => (await page.evaluate(() => (window as any).__scamuraiE2E.commentQueries)).filter((query: string) => query === "alpha").length).toBe(1);
  const requestedQueries: string[] = await page.evaluate(() => (window as any).__scamuraiE2E.commentQueries);
  expect(requestedQueries.filter((query) => query === "a" || query === "al")).toEqual([]);
});

test("account comparison builds a pairwise result and source integration controls return visible status", async ({ page }) => {
  await installFetchStub(page, "sources");
  await loginAndOpenCase(page);
  await page.locator(".workspace-nav").getByRole("button", { name: "Compare accounts", exact: true }).click();
  const accounts = page.locator(".pill-row button");
  await expect(accounts).toHaveCount(3);
  await accounts.nth(0).click();
  await accounts.nth(1).click();
  await page.getByRole("button", { name: /Build pairwise matrix \(1 pairs\)/ }).click();
  await expect(page.locator(".compare-pair")).toHaveCount(1);

  await page.locator(".workspace-nav").getByRole("button", { name: "Connectors", exact: true }).click();
  await page.locator('input[placeholder="disinformation"]').fill("browser-check");
  await page.getByRole("button", { name: "Import public timeline" }).click();
  await expect(page.locator(".result-callout")).toContainText("2 new posts · 1 accounts");
  const sourceRequests = await page.evaluate(() => (window as any).__scamuraiE2E.sourceRequests);
  expect(sourceRequests).toMatchObject([{ instance: "mastodon.social", hashtag: "browser-check" }]);
});

test("every overview alert family opens its matching investigation section", async ({ page }) => {
  await installAlertFixture(page);
  await loginAndOpenCase(page);
  const destinations = [
    ["Narrative destination test", "Narratives"],
    ["Coordination destination test", "Network & behavior"],
    ["Geospatial destination test", "Geospatial"],
    ["Coverage destination test", "Connectors"],
  ];
  for (const [title, destination] of destinations) {
    await page.locator(".alert-row").filter({ hasText: title }).click();
    await expect(page.locator('.workspace-nav button[aria-current="page"]')).toContainText(destination);
    await page.locator(".workspace-nav").getByRole("button", { name: "Overview", exact: true }).click();
  }
});
