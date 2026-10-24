"""Bounded, source-attributed public-infrastructure OSINT.

The module deliberately performs no port scanning, brute force, credential
checks, login bypass or private-data discovery. It combines official/public
APIs with conservative parsers and preserves per-source failure states.

Sources:
* Google Public DNS JSON API (DNS-over-HTTPS)
* IANA RDAP bootstrap + authoritative registry RDAP
* Sectigo crt.sh Certificate Transparency search (historical observations)
* Internet Archive Wayback Availability API (one closest snapshot)
* The explicitly supplied public HTTP(S) page (metadata and headers only)
"""
from __future__ import annotations

import ipaddress
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote, urlunparse, urlparse

import httpx
import tldextract

from ..config import get_settings
from .connectors import fetch_permitted_source

settings = get_settings()
DOMAIN_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
DNS_TYPE_NAMES = {1: "A", 2: "NS", 5: "CNAME", 6: "SOA", 12: "PTR", 15: "MX", 16: "TXT", 28: "AAAA", 257: "CAA"}
MODULES = {"dns", "rdap", "web", "certificates", "archive"}
# Use the bundled Public Suffix List snapshot; never make a surprise network
# request just to normalize a target.
_EXTRACT = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SourceError(RuntimeError):
    def __init__(self, outcome: str, detail: str, status_code: int | None = None):
        super().__init__(detail)
        self.outcome = outcome
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class Target:
    original: str
    kind: str
    host: str
    registrable_domain: str | None
    url: str | None
    ip: str | None


def _ascii_host(host: str) -> str:
    host = host.rstrip(".").strip().lower()
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError("Invalid internationalized hostname") from exc
    if len(host) > 253 or "." not in host:
        raise ValueError("Enter a public domain with a valid suffix")
    labels = host.split(".")
    if any(not DOMAIN_LABEL.fullmatch(label) for label in labels):
        raise ValueError("Hostname contains invalid labels")
    return host


def normalize_target(raw: str) -> Target:
    value = raw.strip()
    if not value or len(value) > 2048 or any(ord(c) < 32 for c in value):
        raise ValueError("Target is empty, too long or contains control characters")

    # Bare IPs are accepted for allocation RDAP and reverse DNS only.
    try:
        ip = ipaddress.ip_address(value.split("%", 1)[0])
        if not ip.is_global:
            raise ValueError("Only globally routable IP addresses are allowed")
        return Target(value, "ip", str(ip), None, None, str(ip))
    except ValueError as exc:
        if "Only globally" in str(exc):
            raise
        ip = None

    candidate = value if "://" in value else f"https://{value}"
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only a public domain, IP or HTTP(S) URL is supported")
    if parsed.username or parsed.password:
        raise ValueError("Credentialed URLs are not allowed")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid URL port") from exc
    if port not in {None, 80, 443}:
        raise ValueError("Only standard HTTP/HTTPS ports are supported; port scanning is out of scope")

    host_text = parsed.hostname.rstrip(".")
    try:
        ip = ipaddress.ip_address(host_text.split("%", 1)[0])
    except ValueError:
        ip = None
    if ip:
        if not ip.is_global:
            raise ValueError("Only globally routable IP addresses are allowed")
        host = str(ip)
        registrable = None
        kind = "ip"
    else:
        host = _ascii_host(host_text)
        extracted = _EXTRACT(host)
        if not extracted.suffix or not extracted.domain:
            raise ValueError("A recognized public domain suffix is required")
        registrable = extracted.top_domain_under_public_suffix
        kind = "url" if "://" in value else "domain"

    # Remove fragments, tracking parameters and accidental credentials from
    # stored evidence. A path is retained because it identifies the document.
    path = parsed.path or "/"
    netloc = f"[{host}]" if ip and ip.version == 6 else host
    if port and not ((parsed.scheme == "https" and port == 443) or (parsed.scheme == "http" and port == 80)):
        netloc += f":{port}"
    clean_url = urlunparse((parsed.scheme, netloc, path, "", "", ""))
    return Target(value, kind, host, registrable, clean_url, str(ip) if ip else None)


def _url_with_params(url: str, params: dict[str, Any]) -> str:
    return str(httpx.URL(url, params=params))


def _json_source(url: str, *, timeout: float | None = None, max_bytes: int = 4_000_000) -> Any:
    result = fetch_permitted_source(
        url,
        timeout=timeout or settings.osint_timeout_seconds,
        max_bytes=max_bytes,
        max_text_chars=max_bytes,
        detect_login_wall=False,
    )
    if result.outcome == "successful_empty":
        return {}
    if result.outcome != "successful":
        raise SourceError(result.outcome, result.detail, result.status_code)
    try:
        return json.loads(result.text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise SourceError("unavailable", "Source returned malformed or truncated JSON", result.status_code) from exc


def _source(name: str, url: str, documentation: str) -> dict:
    return {"name": name, "query_url": url, "documentation": documentation}


def _dns_one(name: str, record_type: str) -> dict:
    url = _url_with_params("https://dns.google/resolve", {"name": name, "type": record_type, "do": "1", "cd": "0"})
    payload = _json_source(url, timeout=min(settings.osint_timeout_seconds, 8.0), max_bytes=1_000_000)
    status = int(payload.get("Status", 2))
    answers = payload.get("Answer") or []
    records = [{
        "name": str(row.get("name", "")).rstrip("."),
        "type": DNS_TYPE_NAMES.get(int(row.get("type", 0)), str(row.get("type", "unknown"))),
        "ttl": row.get("TTL"),
        "data": row.get("data"),
    } for row in answers if isinstance(row, dict)]
    return {
        "query": name,
        "type": record_type,
        "rcode": status,
        "rcode_label": {0: "NOERROR", 1: "FORMERR", 2: "SERVFAIL", 3: "NXDOMAIN", 4: "NOTIMP", 5: "REFUSED"}.get(status, str(status)),
        "authenticated_data": bool(payload.get("AD", False)),
        "records": records,
        "source": _source("Google Public DNS", url, "https://developers.google.com/speed/public-dns/docs/doh/json"),
    }


def collect_dns(target: Target) -> tuple[str, dict]:
    if target.ip:
        queries = [(ipaddress.ip_address(target.ip).reverse_pointer, "PTR")]
    else:
        queries = [(target.host, t) for t in ("A", "AAAA", "MX", "NS", "TXT", "CAA")]
        if target.registrable_domain and target.registrable_domain != target.host:
            queries.append((target.registrable_domain, "TXT"))
        if target.registrable_domain:
            queries.append((f"_dmarc.{target.registrable_domain}", "TXT"))

    answers: list[dict] = []
    errors: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(6, len(queries)), thread_name_prefix="scamurai-dns") as pool:
        futures = {pool.submit(_dns_one, name, typ): (name, typ) for name, typ in queries}
        for future in as_completed(futures):
            name, typ = futures[future]
            try:
                answers.append(future.result())
            except SourceError as exc:
                errors.append({"query": name, "type": typ, "outcome": exc.outcome, "detail": exc.detail})
            except Exception as exc:  # a single record family must not erase the rest
                errors.append({"query": name, "type": typ, "outcome": "unavailable", "detail": type(exc).__name__})
    answers.sort(key=lambda row: (row["query"], row["type"]))
    all_records = [dict(record, query=row["query"]) for row in answers for record in row["records"]]
    txt = [str(r["data"]) for r in all_records if r["type"] == "TXT"]
    email_security = None
    if not target.ip:
        spf = [v for v in txt if "v=spf1" in v.lower()]
        dmarc = [v for v in txt if "v=dmarc1" in v.lower()]
        email_security = {
            "mx_observed": any(r["type"] == "MX" for r in all_records),
            "spf_records_observed": spf,
            "dmarc_records_observed": dmarc,
            "note": "Observed DNS declarations only; this is not a deliverability or spoofing test.",
        }
    has_nxdomain = bool(answers) and all(row["rcode"] == 3 for row in answers) and not errors
    status = "partial" if errors else ("successful_empty" if has_nxdomain or not all_records else "successful")
    return status, {
        "records": all_records,
        "queries": [{k: v for k, v in row.items() if k != "records"} for row in answers],
        "errors": errors,
        "email_security": email_security,
        "limitations": [
            "DNS is a point-in-time resolver view; CDN answers can vary by resolver and time.",
            "AD=false means no DNSSEC authentication assertion in this response, not that a domain is malicious.",
        ],
    }


_BOOTSTRAP_CACHE: dict[str, tuple[float, dict]] = {}


def _bootstrap(kind: str) -> dict:
    now = time.monotonic()
    cached = _BOOTSTRAP_CACHE.get(kind)
    if cached and now - cached[0] < 86400:
        return cached[1]
    url = f"https://data.iana.org/rdap/{kind}.json"
    payload = _json_source(url, max_bytes=2_000_000)
    if not isinstance(payload, dict) or not isinstance(payload.get("services"), list):
        raise SourceError("unavailable", "IANA bootstrap response has an unexpected shape")
    _BOOTSTRAP_CACHE[kind] = (now, payload)
    return payload


def _rdap_url(target: Target) -> str:
    if target.ip:
        ip = ipaddress.ip_address(target.ip)
        kind = "ipv4" if ip.version == 4 else "ipv6"
        bootstrap = _bootstrap(kind)
        for prefixes, bases in bootstrap["services"]:
            try:
                if any(ip in ipaddress.ip_network(prefix) for prefix in prefixes):
                    return urljoin_rdap(bases[0], f"ip/{target.ip}")
            except ValueError:
                continue
        raise SourceError("successful_empty", "No authoritative RDAP service is registered for this IP range")
    domain = target.registrable_domain or target.host
    bootstrap = _bootstrap("dns")
    tld = domain.rsplit(".", 1)[-1]
    for labels, bases in bootstrap["services"]:
        if tld in labels:
            return urljoin_rdap(bases[0], f"domain/{quote(domain)}")
    raise SourceError("successful_empty", "No RDAP service is registered for this public suffix; legacy WHOIS is not fabricated")


def urljoin_rdap(base: str, path: str) -> str:
    return base.rstrip("/") + "/" + path.lstrip("/")


def _vcard_name(entity: dict) -> str | None:
    vcard = entity.get("vcardArray")
    if isinstance(vcard, list) and len(vcard) > 1 and isinstance(vcard[1], list):
        for field in vcard[1]:
            if isinstance(field, list) and len(field) >= 4 and field[0] in {"fn", "org"}:
                value = field[3]
                if isinstance(value, list):
                    value = " ".join(str(v) for v in value)
                if value:
                    return str(value)[:300]
    return None


def parse_rdap(payload: dict, target: Target, query_url: str) -> dict:
    entities = []
    for entity in payload.get("entities") or []:
        if not isinstance(entity, dict):
            continue
        roles = entity.get("roles") or []
        # Keep operational registry/registrar identities, not registrant phone,
        # email or street-address fields.
        if any(role in {"registrar", "registrar_dns", "rir", "regional_internet_registry", "abuse"} for role in roles):
            entities.append({"handle": entity.get("handle"), "roles": roles, "name": _vcard_name(entity)})
    return {
        "handle": payload.get("handle"),
        "name": payload.get("ldhName") or payload.get("unicodeName") or payload.get("name"),
        "type": payload.get("type"),
        "status": payload.get("status") or [],
        "events": [{"action": e.get("eventAction"), "date": e.get("eventDate")}
                   for e in (payload.get("events") or []) if isinstance(e, dict)],
        "nameservers": [n.get("ldhName") or n.get("unicodeName") for n in (payload.get("nameservers") or [])
                        if isinstance(n, dict)],
        "entities": entities,
        "network": ({k: payload.get(k) for k in ("startAddress", "endAddress", "ipVersion", "country", "parentHandle")}
                    if target.ip else None),
        "secure_dns": payload.get("secureDNS"),
        "links": [{"rel": link.get("rel"), "href": link.get("href")}
                  for link in (payload.get("links") or []) if isinstance(link, dict) and link.get("rel") in {"self", "related"}],
        "source": _source("Authoritative RDAP via IANA bootstrap", query_url, "https://datatracker.ietf.org/doc/html/rfc9224"),
        "limitations": [
            "RDAP describes registry data, not current website ownership intent or physical location.",
            "Registrant contact fields are intentionally not collected or displayed.",
        ] + (["The registry country is allocation metadata, not an IP geolocation or a person's location."] if target.ip else []),
    }


def collect_rdap(target: Target) -> tuple[str, dict]:
    url = _rdap_url(target)
    try:
        payload = _json_source(url)
    except SourceError as exc:
        if exc.status_code == 404:
            return "successful_empty", {"record": None, "source": _source("Authoritative RDAP", url, "https://datatracker.ietf.org/doc/html/rfc9224"), "note": "Registry returned not found; this is not proof that related infrastructure is unused."}
        raise
    if not isinstance(payload, dict):
        raise SourceError("unavailable", "RDAP response is not an object")
    return "successful", parse_rdap(payload, target, url)


class MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_title = False
        self.in_h1 = False
        self.title_parts: list[str] = []
        self.h1_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self.link_count = 0
        self.script_count = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        values = {k.lower(): (v or "") for k, v in attrs}
        if tag == "title":
            self.in_title = True
        elif tag == "h1":
            self.in_h1 = True
        elif tag == "a":
            self.link_count += 1
        elif tag == "script":
            self.script_count += 1
        elif tag == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            if key in {"description", "og:title", "og:description", "og:image", "og:site_name", "article:published_time", "generator"}:
                self.meta[key] = values.get("content", "")[:1000]

    def handle_endtag(self, tag: str):
        if tag == "title":
            self.in_title = False
        elif tag == "h1":
            self.in_h1 = False

    def handle_data(self, data: str):
        if self.in_title:
            self.title_parts.append(data)
        if self.in_h1:
            self.h1_parts.append(data)


def collect_web(target: Target) -> tuple[str, dict]:
    if not target.url:
        raise SourceError("not_supported", "Web metadata requires a URL or domain")
    result = fetch_permitted_source(target.url, timeout=settings.osint_timeout_seconds, max_bytes=2_000_000)
    if result.outcome != "successful":
        raise SourceError(result.outcome, result.detail, result.status_code)
    content_type = (result.content_type or "").lower()
    if content_type and not any(t in content_type for t in ("html", "text/plain", "xhtml")):
        raise SourceError("not_supported", f"Web metadata parser does not interpret {content_type.split(';')[0]}")
    parser = MetadataParser()
    try:
        parser.feed(result.text)
    except Exception:
        # HTML on the public web is often malformed; partial metadata is still
        # useful and must be labeled as such rather than crashing all sources.
        pass
    header_allowlist = {
        "server", "content-type", "content-language", "strict-transport-security",
        "content-security-policy", "x-content-type-options", "x-frame-options",
        "referrer-policy", "permissions-policy", "cache-control", "last-modified",
    }
    headers = {k: v[:1000] for k, v in result.headers.items() if k in header_allowlist}
    security_names = ["strict-transport-security", "content-security-policy", "x-content-type-options", "x-frame-options", "referrer-policy", "permissions-policy"]
    technologies = []
    if parser.meta.get("generator"):
        technologies.append({"name": parser.meta["generator"], "reported_by": "HTML generator meta"})
    if headers.get("server"):
        technologies.append({"name": headers["server"], "reported_by": "HTTP Server header"})
    return "successful", {
        "final_url": result.final_url,
        "http_status": result.status_code,
        "redirects": result.redirect_history,
        "title": " ".join("".join(parser.title_parts).split())[:500] or None,
        "h1": " ".join(" ".join(parser.h1_parts).split())[:500] or None,
        "meta": parser.meta,
        "link_count": parser.link_count,
        "script_count": parser.script_count,
        "headers": headers,
        "security_headers": {name: {"present": name in headers, "value": headers.get(name)} for name in security_names},
        "technologies_reported": technologies,
        "source": _source("Direct public-page observation", target.url, "https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html"),
        "limitations": [
            "Headers and generator metadata are self-reported and can be customized or spoofed.",
            "Missing security headers are hardening observations, not evidence of compromise or maliciousness.",
            "Only one bounded document was fetched; JavaScript was not executed and no login was attempted.",
        ],
    }


def collect_certificates(target: Target) -> tuple[str, dict]:
    if not target.registrable_domain:
        raise SourceError("not_supported", "Certificate search requires a domain")
    domain = target.registrable_domain
    url = _url_with_params("https://crt.sh/", {"q": f"%.{domain}", "output": "json"})
    payload = _json_source(url, timeout=max(settings.osint_timeout_seconds, 20.0), max_bytes=8_000_000)
    if not isinstance(payload, list):
        raise SourceError("unavailable", "Certificate search returned an unexpected response")
    hostnames: set[str] = set()
    cert_ids: set[str] = set()
    timestamps: list[str] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        if row.get("id") is not None:
            cert_ids.add(str(row["id"]))
        if row.get("entry_timestamp"):
            timestamps.append(str(row["entry_timestamp"]))
        for name in str(row.get("name_value", "")).splitlines():
            clean = name.strip().lower().rstrip(".")
            if clean.startswith("*."):
                clean = clean[2:]
            try:
                clean = _ascii_host(clean)
            except ValueError:
                continue
            if clean == domain or clean.endswith("." + domain):
                hostnames.add(clean)
    ordered = sorted(hostnames)
    cap = settings.osint_max_hostnames
    return "successful_empty" if not ordered else "successful", {
        "registrable_domain": domain,
        "hostnames": ordered[:cap],
        "unique_hostname_count": len(ordered),
        "truncated": len(ordered) > cap,
        "certificate_record_count": len(cert_ids),
        "first_log_timestamp_observed": min(timestamps) if timestamps else None,
        "last_log_timestamp_observed": max(timestamps) if timestamps else None,
        "source": _source("crt.sh Certificate Transparency search", url, "https://crt.sh/"),
        "limitations": [
            "CT names are historical certificate observations, not proof that a host is live, safe or controlled by the same operator.",
            "Wildcard labels were normalized to their base hostname; no host was probed.",
            "This public aggregator can be slow or rate-limited; failure is not an empty CT history.",
        ],
    }


def collect_archive(target: Target) -> tuple[str, dict]:
    if not target.url:
        raise SourceError("not_supported", "Archive lookup requires a URL or domain")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    url = _url_with_params("https://archive.org/wayback/available", {"url": target.url, "timestamp": timestamp})
    payload = _json_source(url, max_bytes=500_000)
    closest = (payload.get("archived_snapshots") or {}).get("closest") if isinstance(payload, dict) else None
    if not closest:
        return "successful_empty", {
            "snapshot": None,
            "source": _source("Internet Archive Wayback Availability API", url, "https://archive.org/help/wayback_api.php"),
            "note": "No closest accessible snapshot was returned; this does not prove the page was never archived.",
        }
    return "successful", {
        "snapshot": {"url": closest.get("url"), "timestamp": closest.get("timestamp"), "status": closest.get("status"), "available": closest.get("available")},
        "source": _source("Internet Archive Wayback Availability API", url, "https://archive.org/help/wayback_api.php"),
        "limitations": ["The Availability API returns one closest snapshot, not a complete capture history or proof of first publication."],
    }


COLLECTORS = {"dns": collect_dns, "rdap": collect_rdap, "web": collect_web, "certificates": collect_certificates, "archive": collect_archive}


def investigate(raw_target: str, selected_modules: list[str] | None = None) -> dict:
    target = normalize_target(raw_target)
    default = ["rdap", "dns"] if target.kind == "ip" else ["dns", "rdap", "web", "certificates", "archive"]
    selected = selected_modules or default
    selected = list(dict.fromkeys(selected))
    unknown = set(selected) - MODULES
    if unknown:
        raise ValueError(f"Unknown OSINT modules: {', '.join(sorted(unknown))}")
    if target.kind == "ip" and set(selected) - {"dns", "rdap"}:
        raise ValueError("IP investigations support only RDAP allocation and reverse DNS modules")
    if not selected:
        raise ValueError("Select at least one source module")

    results: list[dict] = []
    # Separate providers run concurrently; each collector has its own bounds.
    with ThreadPoolExecutor(max_workers=min(5, len(selected)), thread_name_prefix="scamurai-osint") as pool:
        futures = {pool.submit(COLLECTORS[name], target): name for name in selected}
        for future in as_completed(futures):
            name = futures[future]
            started = time.monotonic()
            try:
                status, data = future.result()
                results.append({"module": name, "status": status, "data": data, "error": None, "collected_at": utcnow_iso()})
            except SourceError as exc:
                results.append({"module": name, "status": exc.outcome, "data": None,
                                "error": {"detail": exc.detail, "status_code": exc.status_code}, "collected_at": utcnow_iso()})
            except Exception as exc:  # provider boundary: no fabricated fallback
                results.append({"module": name, "status": "unavailable", "data": None,
                                "error": {"detail": f"Collector failed: {type(exc).__name__}", "status_code": None}, "collected_at": utcnow_iso()})
    order = {name: i for i, name in enumerate(default)}
    results.sort(key=lambda row: order.get(row["module"], 99))
    good = sum(r["status"] in {"successful", "successful_empty"} for r in results)
    status = "complete" if good == len(results) else ("partial" if good else "unavailable")
    return {
        "schema_version": "scamurai-osint-v1",
        "target": target.original,
        "normalized_target": target.url or target.host,
        "target_type": target.kind,
        "host": target.host,
        "registrable_domain": target.registrable_domain,
        "status": status,
        "generated_at": utcnow_iso(),
        "modules": results,
        "summary": {"sources_succeeded": good, "sources_total": len(results), "sources_limited": len(results) - good},
        "limitations": [
            "Public-source observations are time-sensitive and must be corroborated before attribution or enforcement action.",
            "No port scanning, vulnerability exploitation, private access, breach lookup or identity resolution was performed.",
        ],
    }
