#!/usr/bin/env python3
"""Generate the public-safe ForgeCore ops dashboard and status JSON.

Static-first v1. Reads repo outputs and rendered site files, then writes:
  - site/dist/status/forgecore-status.json
  - site/dist/ops/index.html

Public-safe means no secrets, subscriber counts, private API responses, revenue
metrics, detailed workflow logs, or private Kit dashboard data.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from utils import WORKSPACE

SITE_DIST = WORKSPACE / "site" / "dist"
CONTENT_ISSUES = WORKSPACE / "content" / "issues"
CONTENT_EMAIL = WORKSPACE / "content" / "email"
STATE_DIR = WORKSPACE / "state"
KIT_SENT = STATE_DIR / "kit_sent.json"
CENTRAL = ZoneInfo("America/Chicago")
SITE_BASE_URL = "https://news.forgecore.co"
AUTONOMOUS_WORKFLOW = ".github/workflows/autonomous-newsletter-recovery.yml"
MANUAL_REPAIR_WORKFLOW = ".github/workflows/repair-dropped-newsletter-run.yml"
DEPLOY_WORKFLOW = ".github/workflows/deploy-site.yml"

# Schedule gates use America/Chicago local time. They are intentionally aligned
# with the production workflow targets and CEO review windows.
SLOT_WINDOWS = {
    "am": {
        "prepare_due": (7, 45),
        "send_due": (10, 7),
        "send_repair_due": (10, 35),
    },
    "pm": {
        "prepare_due": (13, 45),
        "send_due": (16, 7),
        "send_repair_due": (16, 50),
    },
}


def now_central() -> datetime:
    return datetime.now(CENTRAL)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def minutes(pair: tuple[int, int]) -> int:
    return pair[0] * 60 + pair[1]


def local_minutes() -> int:
    now = now_central()
    return now.hour * 60 + now.minute


def fmt_time(pair: tuple[int, int]) -> str:
    hour, minute = pair
    suffix = "AM" if hour < 12 else "PM"
    display_hour = hour % 12 or 12
    return f"{display_hour}:{minute:02d} {suffix} CT"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def issue_title(path: Path) -> str:
    text = read_text(path)
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("-", " ").title()


def today_slug(slot: str) -> str:
    return f"{now_central().date().isoformat()}-{slot}"


def sent_record_blocks_email(record: object) -> bool:
    if not isinstance(record, dict):
        return False
    return record.get("email_delivery") == "scheduled_or_sent" or record.get("mode") == "public"


def slot_status(slot: str, sent_log: dict) -> dict:
    slug = today_slug(slot)
    issue_path = CONTENT_ISSUES / f"{slug}.md"
    email_path = CONTENT_EMAIL / f"{slug}.md"
    record = sent_log.get(slug, {})
    issue_exists = issue_path.exists()
    email_snapshot_exists = email_path.exists()
    sent = sent_record_blocks_email(record)
    window = SLOT_WINDOWS[slot]
    now_min = local_minutes()
    prepare_due = now_min >= minutes(window["prepare_due"])
    send_due = now_min >= minutes(window["send_due"])
    send_repair_due = now_min >= minutes(window["send_repair_due"])

    if issue_exists and email_snapshot_exists and sent:
        status = "sent"
        repair_action = "no_action"
        next_expected_action = "No action needed."
    elif not issue_exists and not prepare_due:
        status = "pending_prepare"
        repair_action = "no_action"
        next_expected_action = f"Prepare window opens at {fmt_time(window['prepare_due'])}."
    elif issue_exists and email_snapshot_exists and not sent and not send_repair_due:
        status = "pending_send"
        repair_action = "no_action"
        next_expected_action = f"Send is expected around {fmt_time(window['send_due'])}; repair check begins at {fmt_time(window['send_repair_due'])}."
    elif not issue_exists and prepare_due and not send_repair_due:
        status = "needs_prepare_repair"
        repair_action = "prepare_only"
        next_expected_action = "Prepare window has passed, but send-repair window has not. Prepare the issue without forcing email."
    elif not issue_exists and send_repair_due:
        status = "needs_prepare_repair"
        repair_action = "prepare_and_send"
        next_expected_action = "Issue is missing after send-repair window. Autonomous recovery may prepare and send through guarded workflow."
    elif issue_exists and not email_snapshot_exists:
        status = "needs_prepare_repair"
        repair_action = "prepare_only"
        next_expected_action = "Issue exists but locked email snapshot is missing. Rerun prepare flow."
    elif issue_exists and email_snapshot_exists and not sent and send_repair_due:
        status = "needs_send_repair"
        repair_action = "send_only"
        next_expected_action = "Issue and email snapshot exist, but no public Kit send record exists after repair window."
    else:
        status = "unknown"
        repair_action = "investigate"
        next_expected_action = "Unexpected state. Human review required."

    rob_approval_required = repair_action == "investigate"
    return {
        "slot": slot,
        "slug": slug,
        "title": issue_title(issue_path) if issue_exists else "",
        "issue_path": f"content/issues/{slug}.md",
        "email_path": f"content/email/{slug}.md",
        "issue_exists": issue_exists,
        "email_snapshot_exists": email_snapshot_exists,
        "kit_sent_record_exists": sent,
        "broadcast_id_present": bool(isinstance(record, dict) and record.get("broadcast_id")),
        "web_url": f"{SITE_BASE_URL}/{slug}/",
        "status": status,
        "recommended_repair_action": repair_action,
        "next_expected_action": next_expected_action,
        "schedule": {
            "prepare_due": fmt_time(window["prepare_due"]),
            "send_due": fmt_time(window["send_due"]),
            "send_repair_due": fmt_time(window["send_repair_due"]),
        },
        "autonomous_recovery_workflow": AUTONOMOUS_WORKFLOW,
        "manual_repair_workflow": MANUAL_REPAIR_WORKFLOW,
        "rob_approval_required": rob_approval_required,
    }


def latest_issue() -> dict:
    if not CONTENT_ISSUES.exists():
        return {"slug": "", "title": "", "path": "", "exists": False}
    files = sorted(CONTENT_ISSUES.glob("*.md"), key=lambda p: p.name, reverse=True)
    if not files:
        return {"slug": "", "title": "", "path": "", "exists": False}
    path = files[0]
    return {
        "slug": path.stem,
        "title": issue_title(path),
        "path": f"content/issues/{path.name}",
        "exists": True,
        "web_url": f"{SITE_BASE_URL}/{path.stem}/",
    }


def site_status(latest: dict) -> dict:
    slug = latest.get("slug", "")
    index = read_text(SITE_DIST / "index.html")
    rss = read_text(SITE_DIST / "rss.xml")
    sitemap = read_text(SITE_DIST / "sitemap.xml")
    article_path = SITE_DIST / slug / "index.html" if slug else Path("__missing__")
    homepage_has_latest = bool(slug and slug in index)
    rss_has_latest = bool(slug and slug in rss)
    sitemap_has_latest = bool(slug and slug in sitemap)
    article_route_exists = bool(slug and article_path.exists())
    healthy = homepage_has_latest and rss_has_latest and sitemap_has_latest and article_route_exists
    return {
        "site_dist_exists": SITE_DIST.exists(),
        "latest_slug": slug,
        "homepage_has_latest": homepage_has_latest,
        "rss_has_latest": rss_has_latest,
        "sitemap_has_latest": sitemap_has_latest,
        "latest_article_route_exists": article_route_exists,
        "status": "fresh" if healthy else "stale_or_incomplete",
        "recommended_repair_action": "no_action" if healthy else "deploy-site",
        "deploy_workflow": DEPLOY_WORKFLOW,
    }


def overall_status(am: dict, pm: dict, site: dict) -> dict:
    risks: list[str] = []
    waiting: list[str] = []
    repair_needed = False
    for slot in (am, pm):
        if slot["recommended_repair_action"] != "no_action":
            repair_needed = True
            risks.append(f"{slot['slot'].upper()} status is {slot['status']}.")
        elif slot["status"].startswith("pending_"):
            waiting.append(f"{slot['slot'].upper()} status is {slot['status']}.")
    if site["recommended_repair_action"] != "no_action":
        repair_needed = True
        risks.append("Rendered site output does not fully reflect the latest issue.")

    if repair_needed:
        status = "repair_needed"
        current_required_action = "Autonomous recovery should act on the next scheduled check; use manual repair only if urgent."
    elif waiting:
        status = "waiting"
        current_required_action = "No repair needed yet. Waiting for scheduled newsletter window."
    else:
        status = "healthy"
        current_required_action = "No action needed."

    return {
        "status": status,
        "repair_needed": repair_needed,
        "risks": risks,
        "waiting": waiting,
        "current_required_action": current_required_action,
    }


def build_status() -> dict:
    sent_log = read_json(KIT_SENT)
    am = slot_status("am", sent_log)
    pm = slot_status("pm", sent_log)
    latest = latest_issue()
    site = site_status(latest)
    overall = overall_status(am, pm, site)
    return {
        "generated_at": utc_now_iso(),
        "generated_at_central": now_central().replace(microsecond=0).isoformat(),
        "public_safe": True,
        "overall": overall,
        "am": am,
        "pm": pm,
        "latest_issue": latest,
        "site": site,
        "autonomous_recovery_workflow": AUTONOMOUS_WORKFLOW,
        "manual_repair_workflow": MANUAL_REPAIR_WORKFLOW,
        "deploy_workflow": DEPLOY_WORKFLOW,
        "source_docs": [
            "docs/forgecore-ai-team-os-ceo-monitoring.md",
            "docs/kit-newsletter-ops.md",
            "docs/cloudflare-github-ops.md",
            "docs/dropped-newsletter-run-repair.md",
            "docs/autonomous-github-recovery.md",
            "docs/ops-dashboard.md",
        ],
        "privacy_note": "Public-safe v1 excludes subscriber counts, private Kit metrics, API responses, secrets, revenue data, and workflow logs.",
    }


def write_status_json(status: dict) -> None:
    out_dir = SITE_DIST / "status"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "forgecore-status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")


def dashboard_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <title>ForgeCore Ops Dashboard</title>
  <style>
    :root{--bg:#07111f;--panel:#0f172a;--muted:#94a3b8;--text:#e5e7eb;--line:#1e293b;--good:#22c55e;--watch:#f59e0b;--bad:#ef4444;--info:#38bdf8}*{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:radial-gradient(circle at top left,#1e3a8a 0,#07111f 32%,#020617 100%);color:var(--text)}a{color:#7dd3fc}.wrap{width:min(1180px,94vw);margin:0 auto;padding:28px 0 56px}.hero{display:flex;justify-content:space-between;gap:24px;align-items:flex-end;margin-bottom:22px}.eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.16em;color:#bae6fd;font-weight:900}.hero h1{font-size:clamp(32px,6vw,64px);line-height:.94;letter-spacing:-.06em;margin:10px 0}.hero p{max-width:760px;color:#cbd5e1;font-size:17px}.badge{display:inline-flex;align-items:center;border:1px solid var(--line);border-radius:999px;padding:6px 10px;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.08em}.healthy{color:#86efac;border-color:rgba(34,197,94,.4);background:rgba(34,197,94,.08)}.repair_needed,.risk{color:#fecaca;border-color:rgba(239,68,68,.45);background:rgba(239,68,68,.1)}.waiting,.pending_prepare,.pending_send{color:#bfdbfe;border-color:rgba(59,130,246,.45);background:rgba(59,130,246,.1)}.watch{color:#fde68a;border-color:rgba(245,158,11,.45);background:rgba(245,158,11,.1)}.unknown{color:#cbd5e1;background:rgba(148,163,184,.08)}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.cards3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin-bottom:16px}.card{background:linear-gradient(180deg,rgba(15,23,42,.94),rgba(15,23,42,.74));border:1px solid rgba(148,163,184,.18);border-radius:22px;padding:20px;box-shadow:0 18px 44px rgba(0,0,0,.25)}.card h2,.card h3{margin:0 0 10px;letter-spacing:-.035em}.muted{color:var(--muted)}.big{font-size:28px;font-weight:950;letter-spacing:-.04em}.kv{display:grid;grid-template-columns:1fr auto;gap:10px;padding:10px 0;border-bottom:1px solid rgba(148,163,184,.12)}.kv:last-child{border-bottom:0}.ok{color:#86efac}.no{color:#fca5a5}.action{border:1px solid rgba(56,189,248,.35);background:rgba(8,47,73,.28);border-radius:18px;padding:16px;margin:18px 0}.code{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;background:#020617;border:1px solid rgba(148,163,184,.18);border-radius:12px;padding:10px;overflow:auto;white-space:pre-wrap}.list{margin:0;padding-left:18px}.list li{margin:6px 0;color:#cbd5e1}.footer{margin-top:18px;color:#64748b;font-size:13px}@media(max-width:840px){.hero{display:block}.grid,.cards3{grid-template-columns:1fr}}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="hero">
      <div>
        <div class="eyebrow">ForgeCore AI Team OS</div>
        <h1>Ops Dashboard</h1>
        <p>Public-safe production oversight for Rob: AM/PM publishing, autonomous GitHub recovery, Kit send-record presence, static site freshness, and schedule-aware repair recommendations.</p>
      </div>
      <div id="overallBadge" class="badge unknown">Loading</div>
    </section>

    <div class="cards3">
      <div class="card"><div class="muted">Current required action</div><div id="requiredAction" class="big">Loading...</div></div>
      <div class="card"><div class="muted">Last updated</div><div id="lastUpdated" class="big">—</div></div>
      <div class="card"><div class="muted">Latest issue</div><div id="latestIssue" class="big">—</div></div>
    </div>

    <section class="action">
      <h2>Autonomous recovery recommendation</h2>
      <p id="repairCopy" class="muted">Loading status...</p>
      <div id="repairInputs" class="code">—</div>
    </section>

    <div class="grid">
      <section class="card"><h2>AM slot</h2><div id="amSlot"></div></section>
      <section class="card"><h2>PM slot</h2><div id="pmSlot"></div></section>
      <section class="card"><h2>Site freshness</h2><div id="siteStatus"></div></section>
      <section class="card"><h2>CEO oversight boundaries</h2><ul class="list"><li>GitHub may autonomously prepare missing issues and send only through the guarded Kit workflow.</li><li>Never resend if Kit or state/kit_sent.json already shows a public send.</li><li>Rob approval is required for duplicate-send risk, correction emails, sponsor mistakes, or affiliate trust incidents.</li><li>Public-safe v1 excludes private Kit metrics, subscriber counts, secrets, revenue data, and workflow logs.</li></ul></section>
    </div>

    <section class="card" style="margin-top:16px"><h2>Source docs</h2><div id="sourceDocs"></div></section>
    <div class="footer">Generated by ops_status.py from repo and static site outputs. API-backed private metrics should wait until /ops/ is protected by Cloudflare Access.</div>
  </div>
<script>
const yesNo = (v) => v ? '<span class="ok">yes</span>' : '<span class="no">no</span>';
function row(label, value){ return `<div class="kv"><span class="muted">${label}</span><strong>${value}</strong></div>`; }
function slotBadgeClass(slot){
  if (slot.status === 'sent') return 'healthy';
  if (slot.status === 'pending_prepare' || slot.status === 'pending_send') return slot.status;
  if (slot.recommended_repair_action !== 'no_action') return 'repair_needed';
  return 'watch';
}
function slotHtml(slot){
  return [
    row('Status', `<span class="badge ${slotBadgeClass(slot)}">${slot.status}</span>`),
    row('Slug', slot.slug),
    row('Issue exists', yesNo(slot.issue_exists)),
    row('Email snapshot exists', yesNo(slot.email_snapshot_exists)),
    row('Kit sent record exists', yesNo(slot.kit_sent_record_exists)),
    row('Recommended repair', slot.recommended_repair_action),
    row('Next expected action', slot.next_expected_action),
    row('Prepare due', slot.schedule.prepare_due),
    row('Send due', slot.schedule.send_due),
    row('Repair check', slot.schedule.send_repair_due),
    row('Rob approval required', yesNo(slot.rob_approval_required))
  ].join('');
}
function siteHtml(site){
  return [
    row('Status', `<span class="badge ${site.status === 'fresh' ? 'healthy' : 'repair_needed'}">${site.status}</span>`),
    row('Homepage has latest', yesNo(site.homepage_has_latest)),
    row('RSS has latest', yesNo(site.rss_has_latest)),
    row('Sitemap has latest', yesNo(site.sitemap_has_latest)),
    row('Article route exists', yesNo(site.latest_article_route_exists)),
    row('Recommended repair', site.recommended_repair_action)
  ].join('');
}
function repairText(data){
  const repairs = [];
  const pending = [];
  for (const slot of [data.am, data.pm]) {
    if (slot.recommended_repair_action !== 'no_action') repairs.push(`${slot.slot.toUpperCase()}: ${slot.recommended_repair_action}`);
    else if (slot.status.startsWith('pending_')) pending.push(`${slot.slot.toUpperCase()}: ${slot.status}`);
  }
  if (data.site.recommended_repair_action !== 'no_action') repairs.push(`SITE: ${data.site.recommended_repair_action}`);
  if (repairs.length) return `Autonomous recovery should act on the next scheduled check: ${repairs.join(' · ')}`;
  if (pending.length) return `No repair needed yet. Waiting on schedule: ${pending.join(' · ')}`;
  return 'No repair needed right now.';
}
function repairInputs(data){
  const target = [data.am, data.pm].find(s => s.recommended_repair_action !== 'no_action');
  if (!target) {
    if (data.site.recommended_repair_action !== 'no_action') return `workflow: ${data.deploy_workflow}`;
    return 'no action';
  }
  return `autonomous workflow: ${data.autonomous_recovery_workflow}\nmanual fallback: ${data.manual_repair_workflow}\nissue_slot: ${target.slot}\nallow_send: true\nexpected action: ${target.recommended_repair_action}\nreason: ${target.slot.toUpperCase()} status is ${target.status}`;
}
fetch('/status/forgecore-status.json', {cache:'no-store'})
  .then(r => r.json())
  .then(data => {
    const overall = data.overall.status;
    document.getElementById('overallBadge').className = `badge ${overall}`;
    document.getElementById('overallBadge').textContent = overall.replaceAll('_',' ');
    document.getElementById('requiredAction').textContent = data.overall.current_required_action;
    document.getElementById('lastUpdated').textContent = data.generated_at_central || data.generated_at;
    document.getElementById('latestIssue').innerHTML = data.latest_issue.exists ? `<a href="${data.latest_issue.web_url}">${data.latest_issue.slug}</a>` : 'missing';
    document.getElementById('repairCopy').textContent = repairText(data);
    document.getElementById('repairInputs').textContent = repairInputs(data);
    document.getElementById('amSlot').innerHTML = slotHtml(data.am);
    document.getElementById('pmSlot').innerHTML = slotHtml(data.pm);
    document.getElementById('siteStatus').innerHTML = siteHtml(data.site);
    document.getElementById('sourceDocs').innerHTML = data.source_docs.map(d => `<div class="code" style="margin:8px 0">${d}</div>`).join('');
  })
  .catch(err => {
    document.getElementById('overallBadge').className = 'badge repair_needed';
    document.getElementById('overallBadge').textContent = 'status load failed';
    document.getElementById('requiredAction').textContent = 'Check /status/forgecore-status.json generation.';
    document.getElementById('repairCopy').textContent = String(err);
  });
</script>
</body>
</html>
"""


def write_dashboard() -> None:
    out_dir = SITE_DIST / "ops"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(dashboard_html(), encoding="utf-8")


def main() -> None:
    SITE_DIST.mkdir(parents=True, exist_ok=True)
    status = build_status()
    write_status_json(status)
    write_dashboard()
    print(f"[ops] wrote {SITE_DIST / 'status' / 'forgecore-status.json'}")
    print(f"[ops] wrote {SITE_DIST / 'ops' / 'index.html'}")
    print(f"[ops] overall={status['overall']['status']}")


if __name__ == "__main__":
    main()
