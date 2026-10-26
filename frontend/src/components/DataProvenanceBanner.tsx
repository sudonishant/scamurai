import { isSandboxActive } from "../lib/api";

export default function DataProvenanceBanner() {
  const sandbox = isSandboxActive();

  return (
    <section
      className={`data-provenance-banner ${sandbox ? "sandbox" : "live"}`}
      role="note"
      aria-label="Data provenance notice"
    >
      <span className="data-provenance-label">
        {sandbox ? "SYNTHETIC PUBLIC DEMO" : "LIVE API · CASE-SCOPED DATA"}
      </span>
      <p>
        {sandbox
          ? "Seeded cases, findings, scores and source records are fictional examples, not verified or source-backed findings. Preview changes stay in this browser, separate from live backend cases. Source collection is disabled here; do not enter private or sensitive case data."
          : "Check each record’s source, collection method, access status and review state. A connected API or source link does not by itself verify a claim or establish authorization."}
      </p>
    </section>
  );
}
