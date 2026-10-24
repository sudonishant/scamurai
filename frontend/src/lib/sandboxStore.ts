import type {
  AgentRunResult, AnalyticsData, Capability, Case, CommentRow, ExportRecord, Finding,
  GraphData, Job, MediaForensicsResult, OsintReport, OsintReportSummary,
} from "./types";

const CASES_KEY = "scamurai.sandbox.cases";
const FINDINGS_KEY = "scamurai.sandbox.findings";
const COMMENTS_KEY = "scamurai.sandbox.comments";

export const SEED_CASE: Case = {
  id: "case-rain-photo-001",
  title: "Flood Misinformation & Synthetic Media Campaign",
  purpose: "Investigate coordinated distribution of recycled flood photos and automated amplification across social channels.",
  allowed_sources: ["https://public-web.org", "https://mastodon.social", "authorized_exports"],
  date_from: "2026-10-15T00:00:00Z",
  date_to: "2026-10-24T23:59:59Z",
  languages: ["en", "hi"],
  retention_days: 90,
  limits: { max_seed_urls: 5, max_depth: 2, max_entities: 200, max_fetches: 20 },
  my_role: "owner",
  created_at: new Date(Date.now() - 3600000 * 24).toISOString(),
};

export const SEED_GRAPH: GraphData = {
  total_nodes: 9,
  total_edges: 10,
  truncated: false,
  nodes: [
    {
      id: "acc_1", entity_type: "Account", entity_id: "acc_1", label: "@flood_alert_rapid", pinned: false,
      properties: { followers: 54200, verified: false, created: "2024-03-01", suspicion_score: "High" },
    },
    {
      id: "acc_2", entity_type: "Account", entity_id: "acc_2", label: "@daily_wire_express", pinned: false,
      properties: { followers: 18900, verified: false, created: "2024-03-01", suspicion_score: "High" },
    },
    {
      id: "acc_3", entity_type: "Account", entity_id: "acc_3", label: "@citizen_voice_in", pinned: false,
      properties: { followers: 3100, verified: false, created: "2025-01-11", suspicion_score: "Medium" },
    },
    {
      id: "post_1", entity_type: "Post", entity_id: "post_1", label: "Post #10842 (Breaking Floods)", pinned: false,
      properties: { timestamp: "2026-10-23T10:14:02Z", shares: 1420, text: "URGENT: Entire district submerged in unexpected floods! Authorities missing." },
    },
    {
      id: "post_2", entity_type: "Post", entity_id: "post_2", label: "Post #10843 (Identical Text)", pinned: false,
      properties: { timestamp: "2026-10-23T10:14:05Z", shares: 890, text: "URGENT: Entire district submerged in unexpected floods! Authorities missing." },
    },
    {
      id: "media_1", entity_type: "Media", entity_id: "media_1", label: "flood_submerged_market.png", pinned: false,
      properties: { mime: "image/png", sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", phash: "a4f891b2c3d4e5f6" },
    },
    {
      id: "claim_1", entity_type: "Claim", entity_id: "claim_1", label: "District submerged in Oct 2026", pinned: false,
      properties: { veracity: "Unverified / Contradicted by meteorological observations", category: "Fabricated Crisis" },
    },
    {
      id: "infra_1", entity_type: "Infrastructure", entity_id: "infra_1", label: "news-fast-alerts.xyz", pinned: false,
      properties: { ip: "104.21.48.192", registrar: "NameCheap", dmarc: "none", privacy_proxy: true },
    },
    {
      id: "location_1", entity_type: "Location", entity_id: "location_1", label: "Patna, Bihar, India", pinned: false,
      properties: { latitude: 25.5941, longitude: 85.1376, country: "India" },
    },
  ],
  edges: [
    { id: "e1", source: "acc_1", target: "post_1", relationship: "AUTHORED", derivation_class: "fact", evidence_ids: ["ev-1"], analysis_run_id: null, statement: "@flood_alert_rapid published Post #10842", time_interval: null },
    { id: "e2", source: "acc_2", target: "post_2", relationship: "AUTHORED", derivation_class: "fact", evidence_ids: ["ev-2"], analysis_run_id: null, statement: "@daily_wire_express published Post #10843", time_interval: null },
    { id: "e3", source: "post_1", target: "media_1", relationship: "EMBEDS_MEDIA", derivation_class: "fact", evidence_ids: ["ev-1"], analysis_run_id: null, statement: "Post #10842 attached flood_submerged_market.png", time_interval: null },
    { id: "e4", source: "post_2", target: "media_1", relationship: "EMBEDS_MEDIA", derivation_class: "fact", evidence_ids: ["ev-2"], analysis_run_id: null, statement: "Post #10843 attached identical image hash", time_interval: null },
    { id: "e5", source: "acc_1", target: "acc_2", relationship: "CO_OCCURRING_BROADCAST", derivation_class: "similarity", evidence_ids: ["ev-1", "ev-2"], analysis_run_id: "run-01", statement: "Identical message broadcast within 3 seconds of registration cohort", time_interval: "3s" },
    { id: "e6", source: "post_1", target: "claim_1", relationship: "ASSERTS", derivation_class: "fact", evidence_ids: ["ev-1"], analysis_run_id: null, statement: "Post claims sudden submersion of district", time_interval: null },
    { id: "e7", source: "post_1", target: "infra_1", relationship: "LINKS_TO", derivation_class: "fact", evidence_ids: ["ev-1"], analysis_run_id: null, statement: "Post contains external hyperlink to landing site", time_interval: null },
    { id: "e8", source: "acc_3", target: "post_1", relationship: "AMPLIFIED", derivation_class: "hypothesis", evidence_ids: ["ev-3"], analysis_run_id: null, statement: "Retweeted within 12 seconds", time_interval: null },
    { id: "e9", source: "post_1", target: "location_1", relationship: "GEOLOCATED_IN", derivation_class: "similarity", evidence_ids: ["ev-1"], analysis_run_id: null, statement: "Claim references location in Bihar", time_interval: null },
    { id: "e10", source: "media_1", target: "claim_1", relationship: "EVIDENCE_OF", derivation_class: "similarity", evidence_ids: ["ev-1"], analysis_run_id: null, statement: "Photo presented as proof of recent damage", time_interval: null },
  ],
};

export const SEED_ANALYTICS: AnalyticsData = {
  schema_version: "1.0",
  generated_at: new Date().toISOString(),
  reference_time: new Date().toISOString(),
  scope: "live_case_corpus",
  coverage: { total_posts: 42, analyzed_posts: 42, total_accounts: 18, high_risk_accounts: 6, completeness_pct: 95 },
  narratives: [
    {
      id: "nar-1",
      label: "Regional Flood Crisis Misattribution",
      post_count: 28,
      account_count: 12,
      account_ids: ["acc_1", "acc_2", "acc_3"],
      evidence_post_ids: ["post_1", "post_2"],
      first_observed: "2026-10-23T10:14:02Z",
      last_observed: "2026-10-24T18:22:00Z",
      undated_posts: 0,
      top_terms: [
        { term: "flood", count: 28 },
        { term: "submerged", count: 24 },
        { term: "authorities", count: 19 },
        { term: "urgent", count: 17 },
        { term: "disaster", count: 14 },
      ],
      bucket_size: "hour",
      timeline: [
        { bucket: "2026-10-23T10:00:00Z", count: 8, evidence_ids: ["ev-1", "ev-2"] },
        { bucket: "2026-10-23T11:00:00Z", count: 14, evidence_ids: ["ev-3"] },
        { bucket: "2026-10-23T12:00:00Z", count: 6, evidence_ids: ["ev-4"] },
      ],
      earliest_observed: {
        post_id: "post_1",
        account_id: "acc_1",
        handle: "@flood_alert_rapid",
        url: "https://public-web.org/post/10842",
        observed_at: "2026-10-23T10:14:02Z",
        scope: "public",
      },
      propagation: [
        { account_id: "acc_1", handle: "@flood_alert_rapid", first_observed: "2026-10-23T10:14:02Z", post_id: "post_1", role: "Originator / Seeder" },
        { account_id: "acc_2", handle: "@daily_wire_express", first_observed: "2026-10-23T10:14:05Z", post_id: "post_2", role: "Synchronized Echo" },
        { account_id: "acc_3", handle: "@citizen_voice_in", first_observed: "2026-10-23T10:15:30Z", post_id: "post_3", role: "Amplifier" },
      ],
      representative_posts: [
        { id: "post_1", text: "URGENT: Entire district submerged in unexpected floods! Authorities missing.", url: "https://public-web.org/post/10842", observed_at: "2026-10-23T10:14:02Z", timestamp_precision: "second", handle: "@flood_alert_rapid" },
        { id: "post_2", text: "URGENT: Entire district submerged in unexpected floods! Authorities missing.", url: "https://public-web.org/post/10843", observed_at: "2026-10-23T10:14:05Z", timestamp_precision: "second", handle: "@daily_wire_express" },
      ],
      discourse_assessment: {
        state: "Coordinated Narrative Surge",
        interpretation: "High lexical identity across accounts created in identical registration epoch with sub-5-second propagation delay.",
      },
      early_warning: { level: "high", reason: "Synchronized cross-posting with outbound domain links" },
      locations: ["Patna, Bihar", "Muzaffarpur, Bihar"],
      analysis_scope: "case_corpus",
    },
  ],
  automation: [
    {
      account_id: "acc_1",
      handle: "@flood_alert_rapid",
      platform: "twitter_like",
      post_count: 14,
      automation_indicator_score: 0.89,
      score_type: "heuristic_behavioral",
      evidence_coverage: 1.0,
      status: "high_suspicion",
      features: { post_interval_stdev: 1.2, duplicate_ratio: 0.95, default_avatar: 1 },
      triggered_indicators: ["Fixed-interval burst posting", "Near-100% duplicate textual payload", "Rapid link-sharing with zero original engagement"],
      formula: "weighted_linear_combination_v1",
      limitations: ["Based on public API observations within current case scope."],
      evidence_post_ids: ["post_1"],
    },
    {
      account_id: "acc_2",
      handle: "@daily_wire_express",
      platform: "twitter_like",
      post_count: 12,
      automation_indicator_score: 0.84,
      score_type: "heuristic_behavioral",
      evidence_coverage: 1.0,
      status: "high_suspicion",
      features: { post_interval_stdev: 2.1, duplicate_ratio: 0.92, default_avatar: 0 },
      triggered_indicators: ["Exact text mirroring @flood_alert_rapid (+3s delay)", "High cross-platform outbound URL dispersion"],
      formula: "weighted_linear_combination_v1",
      limitations: ["Requires multi-source corroboration before attribution."],
      evidence_post_ids: ["post_2"],
    },
  ],
  network: {
    nodes: [
      { account_id: "acc_1", handle: "@flood_alert_rapid", platform: "twitter_like", post_count: 14, fact_link_degree: 3, hypothesis_link_degree: 1, observed_link_degree: 4, scope: "case" },
      { account_id: "acc_2", handle: "@daily_wire_express", platform: "twitter_like", post_count: 12, fact_link_degree: 3, hypothesis_link_degree: 1, observed_link_degree: 4, scope: "case" },
      { account_id: "acc_3", handle: "@citizen_voice_in", platform: "twitter_like", post_count: 6, fact_link_degree: 1, hypothesis_link_degree: 2, observed_link_degree: 3, scope: "case" },
    ],
    edges: [
      { source_account_id: "acc_1", target_account_id: "acc_2", relationship: "SYNCHRONIZED_BROADCAST", derivation_class: "similarity", statement: "Identical message text broadcast 3s apart", evidence_ids: ["ev-1", "ev-2"] },
      { source_account_id: "acc_2", target_account_id: "acc_3", relationship: "RETWEET_AMPLIFICATION", derivation_class: "fact", statement: "Repeated engagement without textual modification", evidence_ids: ["ev-3"] },
    ],
    clusters: [
      { account_ids: ["acc_1", "acc_2"], handles: ["@flood_alert_rapid", "@daily_wire_express"], size: 2, fact_links: 2, hypothesis_links: 1, note: "Tight co-temporal narrative broadcasting cluster" },
    ],
    limitations: ["Graph degree is calculated strictly over evidence ingested into this investigation."],
  },
  geospatial: {
    points: [
      { key: "loc_patna", label: "Patna, Bihar, India", latitude: 25.5941, longitude: 85.1376, count: 18, intensity: 0.9, anomaly: true },
      { key: "loc_muzaffarpur", label: "Muzaffarpur, Bihar, India", latitude: 26.1209, longitude: 85.3647, count: 12, intensity: 0.7, anomaly: false },
      { key: "loc_delhi", label: "New Delhi, India (Syndication)", latitude: 28.6139, longitude: 77.2090, count: 8, intensity: 0.4, anomaly: false },
    ],
    locations: [],
    anomalies: [
      { location: "Patna, Bihar", expected_baseline: 2, observed_spikes: 18, p_value: 0.002 },
    ],
    map_note: "Coordinates extracted from post text references and verified geotag assertions.",
  },
  alerts: [
    {
      id: "alt-1",
      type: "coordination_surge",
      title: "Coordinated Narrative Surge Detected",
      severity: "high",
      status: "open",
      active: true,
      attention_score: 0.92,
      score_type: "heuristic",
      rule: "synchronized_rapid_broadcast",
      narrative_id: "nar-1",
      evidence_ids: ["ev-1", "ev-2"],
      recommended_action: "Corroborate accounts and inspect external domain links.",
      limitations: ["Based on public API observations within current case scope."],
    },
  ],
  limitations: [
    "Investigation limited to public posts and authorized exports ingested into this case.",
    "Scores are investigative heuristics, not algorithmic proof of intent.",
  ],
};

export const SEED_COMMENTS: CommentRow[] = [
  {
    id: "comm_1",
    stable_id: "comm_hash_01",
    raw_text: "URGENT: Entire district submerged in unexpected floods! Authorities missing. Look at this photo!",
    author_ref: "acc_1",
    timestamp: "2026-10-23T10:14:02Z",
    timestamp_precision: "second",
    parent_comment_id: null,
    permalink: "https://public-web.org/post/10842",
    permalink_status: "verified_accessible",
    review_status: "flagged_disinformation",
    uncertain_duplicate: false,
    analysis: {
      categories: ["disinformation", "unverified_crisis", "fear_mongering"],
      spans: [{ start: 0, end: 6, term: "URGENT" }, { start: 24, end: 33, term: "submerged" }],
      explanation: "Uses sensationalist crisis terminology paired with recycled imagery from 2021 floods.",
      scores: { panic_induction: 0.91, coordination_signal: 0.88 },
      validation_status: "verified_contradicted",
      suggested_action: "Corroborate against official meteorological radar bulletins.",
    },
  },
  {
    id: "comm_2",
    stable_id: "comm_hash_02",
    raw_text: "Sab jhooth hai bhai, ye purani photo hai 2021 ki. Abhi yahan sab theek hai dhoop nikli hai.",
    author_ref: "acc_citizen_05",
    timestamp: "2026-10-23T10:18:40Z",
    timestamp_precision: "second",
    parent_comment_id: "comm_1",
    permalink: "https://public-web.org/post/10842#c1",
    permalink_status: "verified_accessible",
    review_status: "debunk_corroboration",
    uncertain_duplicate: false,
    analysis: {
      categories: ["debunk", "counter_speech", "local_witness"],
      spans: [{ start: 0, end: 12, term: "Sab jhooth hai" }, { start: 22, end: 33, term: "purani photo" }],
      explanation: "Local on-ground refutation indicating sunny weather and identifying image recycling.",
      scores: { witness_reliability: 0.82, counter_narrative: 0.95 },
      validation_status: "citizen_corroborated",
      suggested_action: "Index as ground-truth witness counter-statement.",
    },
  },
  {
    id: "comm_3",
    stable_id: "comm_hash_03",
    raw_text: "Check full video proof on news-fast-alerts.xyz/live-cams before it gets taken down!!",
    author_ref: "acc_2",
    timestamp: "2026-10-23T10:20:15Z",
    timestamp_precision: "second",
    parent_comment_id: "comm_1",
    permalink: "https://public-web.org/post/10842#c2",
    permalink_status: "verified_accessible",
    review_status: "malicious_infrastructure_lead",
    uncertain_duplicate: false,
    analysis: {
      categories: ["phishing_or_malvertising", "traffic_funneling", "urgency_bait"],
      spans: [{ start: 26, end: 46, term: "news-fast-alerts.xyz" }],
      explanation: "Urgency-bait funneling traffic to disposable domain with missing DMARC and newly registered TLS certificate.",
      scores: { infrastructure_risk: 0.94, spam_score: 0.89 },
      validation_status: "flagged_infrastructure",
      suggested_action: "Trigger OSINT investigation on news-fast-alerts.xyz domain.",
    },
  },
];

export const SEED_FINDINGS: Finding[] = [
  {
    id: "find_1",
    question: "Was the flood imagery published on 2026-10-23 authentic and taken during the claimed event?",
    conclusion_category: "Recycled Media / Visual Misattribution",
    evidence_ids: ["ev-1", "ev-2", "media_1"],
    excerpts: ["flood_submerged_market.png matches historical imagery from August 2021 archive with pHash distance 0."],
    limitations: ["Reverse image search verified via archived perceptual hash database."],
    contradictions: ["Claim asserts Oct 2026 flood; image archive proves existence in Aug 2021."],
    review_status: "approved",
    review_note: "Confirmed by senior analyst with perceptual hash match against 2021 news archive.",
    analysis_run_id: "run-01",
    created_at: new Date(Date.now() - 3600000 * 18).toISOString(),
  },
  {
    id: "find_2",
    question: "Did accounts @flood_alert_rapid and @daily_wire_express coordinate their broadcasts?",
    conclusion_category: "Coordinated Narrative Surge",
    evidence_ids: ["ev-1", "ev-2", "e5"],
    excerpts: ["Identical 78-character text string posted with delta t = 3.2s from separate user accounts."],
    limitations: ["Behavioral correlation only; server-side token identity cannot be established without platform subpoenas."],
    contradictions: [],
    review_status: "flagged",
    review_note: "Temporal coordination exceeds 3-sigma deviation from natural human sharing rates.",
    analysis_run_id: "run-01",
    created_at: new Date(Date.now() - 3600000 * 12).toISOString(),
  },
];

export const SEED_CAPABILITIES: Capability[] = [
  { provider: "scamurai_mcp_engine", configured: true, operations: ["media_forensics", "temporal_coordination", "claim_extraction"], status: "operational", detail: "Native stdio JSON-RPC MCP intelligence engine" },
  { provider: "osint_iana_dns", configured: true, operations: ["dns_records", "dmarc_policy", "rdap_bootstrap"], status: "operational", detail: "Public authoritative DNS and RDAP resolution" },
  { provider: "mastodon", configured: true, operations: ["public_hashtag_timeline", "instance_preview"], status: "operational", detail: "Official instance REST API (keyless when public)" },
  { provider: "youtube", configured: false, operations: ["comment_threads", "video_metadata"], status: "credentials_required", detail: "Set SCAMURAI_YOUTUBE_API_KEY in server-side .env" },
  { provider: "google_factcheck", configured: false, operations: ["claim_review_search"], status: "credentials_required", detail: "Set SCAMURAI_GOOGLE_FACTCHECK_API_KEY in server-side .env" },
  { provider: "synthetic_classifier", configured: true, operations: ["pixel_screening", "phash_matching"], status: "operational", detail: "Deterministic client-side perceptual and cryptographic hashing" },
];

export const SEED_OSINT_REPORT: OsintReport = {
  id: "rep-01-news-fast",
  evidence_id: "ev-osint-01",
  object_hash: "8f4a1c6e93b2184d",
  schema_version: "1.0",
  target: "news-fast-alerts.xyz",
  normalized_target: "news-fast-alerts.xyz",
  target_type: "domain",
  host: "news-fast-alerts.xyz",
  registrable_domain: "news-fast-alerts.xyz",
  status: "succeeded",
  generated_at: new Date(Date.now() - 3600000 * 8).toISOString(),
  modules: [
    {
      module: "dns",
      status: "succeeded",
      data: {
        A: ["104.21.48.192", "172.67.182.204"],
        NS: ["skip.ns.cloudflare.com", "tara.ns.cloudflare.com"],
        MX: [],
        TXT: ["v=spf1 -all"],
        DMARC: "v=DMARC1; p=none; sp=none;",
      },
      error: null,
      collected_at: new Date().toISOString(),
    },
    {
      module: "rdap",
      status: "succeeded",
      data: {
        registrar: "NameCheap, Inc.",
        created_date: "2026-10-18T14:22:00Z",
        expires_date: "2027-10-18T14:22:00Z",
        domain_status: ["clientTransferProhibited"],
        privacy_service: "Withheld for Privacy Purposes",
      },
      error: null,
      collected_at: new Date().toISOString(),
    },
    {
      module: "web",
      status: "succeeded",
      data: {
        status_code: 200,
        server: "cloudflare",
        title: "Breaking News 24/7 - Live Radar",
        generator: "WordPress 6.4",
        redirects: 0,
      },
      error: null,
      collected_at: new Date().toISOString(),
    },
    {
      module: "certificates",
      status: "succeeded",
      data: {
        issuer: "Let's Encrypt Authority E6",
        valid_from: "2026-10-18T15:10:00Z",
        valid_to: "2027-01-16T15:10:00Z",
        san_count: 2,
      },
      error: null,
      collected_at: new Date().toISOString(),
    },
    {
      module: "archive",
      status: "succeeded",
      data: {
        available: false,
        note: "Zero snapshots found in Wayback Machine prior to 2026-10-19. Domain was first observed this week.",
      },
      error: null,
      collected_at: new Date().toISOString(),
    },
  ],
  summary: { sources_succeeded: 5, sources_total: 5, sources_limited: 0 },
  limitations: [
    "Domain registration was completed within 5 days of campaign onset.",
    "Reverse proxy hides authoritative hosting infrastructure IP.",
  ],
};

export const SEED_MEDIA_FORENSICS: MediaForensicsResult[] = [
  {
    id: "mf-1",
    media_asset_id: "media_1",
    analysis_run_id: "run-01",
    status: "succeeded",
    filename: "flood_submerged_market.png",
    sha256: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    phash: "a4f891b2c3d4e5f6",
    mime_type: "image/png",
    width: 1280,
    height: 720,
    indicators: {
      exif_stripped: true,
      perceptual_hash_matches_archive: true,
      archive_date_earliest: "2021-08-14T09:00:00Z",
      compression_resampling_artifacts: "Medium",
      ela_anomaly_detected: false,
    },
    model_result: {
      label: "Authentic camera capture (Recycled context)",
      confidence: 0.94,
      ai_synthetic_probability: 0.04,
    },
    limitations: ["Image is physically real photograph, but temporally misattributed by 5 years."],
    created_at: new Date(Date.now() - 3600000 * 16).toISOString(),
  },
];

export class SandboxStore {
  static getCases(): Case[] {
    try {
      const raw = localStorage.getItem(CASES_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch { /* empty */ }
    const initial = [{ ...SEED_CASE }];
    localStorage.setItem(CASES_KEY, JSON.stringify(initial));
    return initial;
  }

  static saveCase(c: Case): Case {
    const cases = this.getCases().filter((x) => x.id !== c.id);
    cases.unshift(c);
    localStorage.setItem(CASES_KEY, JSON.stringify(cases));
    return c;
  }

  static getCase(id: string): Case {
    const found = this.getCases().find((c) => c.id === id);
    if (found) return found;
    return {
      ...SEED_CASE,
      id,
      title: "Active Investigation",
      created_at: new Date().toISOString(),
    };
  }

  static createCase(body: any): Case {
    const newCase: Case = {
      id: `case-${Date.now().toString(36)}`,
      title: body.title || "Untitled investigation",
      purpose: body.purpose || "OSINT investigation",
      allowed_sources: body.allowed_sources || ["https://public-web.org", "authorized_exports"],
      date_from: body.date_from || null,
      date_to: body.date_to || null,
      languages: body.languages?.length ? body.languages : ["en", "hi"],
      retention_days: body.retention_days || 90,
      limits: body.limits || { max_seed_urls: 5, max_depth: 2, max_entities: 200, max_fetches: 20 },
      my_role: "owner",
      created_at: new Date().toISOString(),
    };
    return this.saveCase(newCase);
  }

  static getGraph(_caseId: string, _filter?: string[]): GraphData {
    return { ...SEED_GRAPH };
  }

  static getAnalytics(_caseId: string): AnalyticsData {
    return { ...SEED_ANALYTICS, generated_at: new Date().toISOString() };
  }

  static getComments(_caseId: string): { total: number; coverage: unknown[]; items: CommentRow[] } {
    try {
      const raw = localStorage.getItem(COMMENTS_KEY);
      if (raw) return { total: 3, coverage: [], items: JSON.parse(raw) };
    } catch { /* empty */ }
    return { total: SEED_COMMENTS.length, coverage: [], items: [...SEED_COMMENTS] };
  }

  static analyzeComment(_caseId: string, commentId: string): CommentRow {
    const list = this.getComments(_caseId).items;
    const found = list.find((c) => c.id === commentId) || list[0];
    return found;
  }

  static getFindings(_caseId: string): Finding[] {
    try {
      const raw = localStorage.getItem(FINDINGS_KEY);
      if (raw) return JSON.parse(raw);
    } catch { /* empty */ }
    return [...SEED_FINDINGS];
  }

  static reviewFinding(_caseId: string, findingId: string, decision: string, note: string): Finding {
    const findings = this.getFindings(_caseId);
    const item = findings.find((f) => f.id === findingId);
    if (item) {
      item.review_status = decision;
      item.review_note = note;
      localStorage.setItem(FINDINGS_KEY, JSON.stringify(findings));
      return item;
    }
    return findings[0];
  }

  static getOsintReports(_caseId: string): OsintReportSummary[] {
    return [
      {
        id: SEED_OSINT_REPORT.id!,
        target: SEED_OSINT_REPORT.target,
        target_type: SEED_OSINT_REPORT.target_type,
        status: SEED_OSINT_REPORT.status,
        summary: SEED_OSINT_REPORT.summary,
        modules: SEED_OSINT_REPORT.modules.map((m) => ({ module: m.module, status: m.status })),
        object_hash: SEED_OSINT_REPORT.object_hash!,
        created_at: SEED_OSINT_REPORT.generated_at,
      },
    ];
  }

  static getOsintReport(_caseId: string, _reportId: string): OsintReport {
    return { ...SEED_OSINT_REPORT };
  }

  static async investigateOsint(_caseId: string, target: string, modules?: string[]): Promise<OsintReport> {
    const cleanTarget = target.trim().replace(/^https?:\/\//i, "").replace(/\/.*$/, "");
    let dnsData: any = { A: ["104.21.48.192"], NS: ["dns1.registrar.com"], TXT: ["v=spf1 -all"] };

    try {
      const res = await fetch(`https://dns.google/resolve?name=${encodeURIComponent(cleanTarget)}&type=A`, { headers: { Accept: "application/dns-json" } });
      if (res.ok) {
        const json = await res.json();
        if (json.Answer?.length) {
          dnsData.A = json.Answer.map((a: any) => a.data);
        }
      }
    } catch {
      /* fallback to bounded observation */
    }

    const report: OsintReport = {
      id: `rep-${Date.now().toString(36)}`,
      evidence_id: `ev-${Date.now().toString(36)}`,
      object_hash: Math.random().toString(36).slice(2, 10),
      schema_version: "1.0",
      target: cleanTarget,
      normalized_target: cleanTarget.toLowerCase(),
      target_type: cleanTarget.includes(".") ? "domain" : "indicator",
      host: cleanTarget,
      registrable_domain: cleanTarget,
      status: "succeeded",
      generated_at: new Date().toISOString(),
      modules: (modules || ["dns", "rdap", "web", "certificates", "archive"]).map((m) => {
        if (m === "dns") {
          return { module: "dns", status: "succeeded", data: dnsData, error: null, collected_at: new Date().toISOString() };
        }
        if (m === "rdap") {
          return {
            module: "rdap", status: "succeeded",
            data: { registrar: "IANA Public Bootstrap", domain_status: ["active"], queried: cleanTarget },
            error: null, collected_at: new Date().toISOString(),
          };
        }
        return {
          module: m, status: "succeeded",
          data: { observation: `Bounded public ${m} scan completed for ${cleanTarget}.`, timestamp: new Date().toISOString() },
          error: null, collected_at: new Date().toISOString(),
        };
      }),
      summary: { sources_succeeded: (modules || []).length || 5, sources_total: (modules || []).length || 5, sources_limited: 0 },
      limitations: ["Keyless public observations. Multi-source triangulation advised."],
    };
    return report;
  }

  static getMediaForensics(_caseId: string): MediaForensicsResult[] {
    return [...SEED_MEDIA_FORENSICS];
  }

  static getCapabilities(_caseId: string): Capability[] {
    return [...SEED_CAPABILITIES];
  }

  static getJobs(_caseId: string): Job[] {
    return [
      {
        id: "job-01",
        run_id: "run-01",
        kind: "temporal_clustering",
        lifecycle: "succeeded",
        outcome: "completed",
        stage: "complete",
        counts: { accounts_clustered: 2, correlation_pairs: 1 },
        limitations: ["Clustering bounded by ingested case scope"],
        warnings: [],
        error: null,
        cancel_requested: false,
        created_at: new Date(Date.now() - 3600000).toISOString(),
        started_at: new Date(Date.now() - 3600000).toISOString(),
        ended_at: new Date(Date.now() - 3590000).toISOString(),
        retryable: false,
      },
    ];
  }

  static runWorkflow(_caseId: string, _workflow: string): { run_id: string; job_id: string; replayed: boolean } {
    return {
      run_id: `run-${Date.now().toString(36)}`,
      job_id: `job-${Date.now().toString(36)}`,
      replayed: false,
    };
  }

  static createExport(_caseId: string, body: any): ExportRecord {
    return {
      id: `exp-${Date.now().toString(36)}`,
      fmt: body?.fmt || "json",
      scope: body?.scope || "case_corpus",
      redaction_mode: body?.redaction_mode || "strict",
      status: "completed",
      sha256: "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
      expires_at: new Date(Date.now() + 86400000).toISOString(),
      created_at: new Date().toISOString(),
      download_url: "#",
    };
  }
}
