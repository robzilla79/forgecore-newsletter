#!/usr/bin/env python3
"""Validate that issue sources support the issue topic.

This is intentionally validation-only. It does not rewrite issue Markdown,
repair source lists, or add links. It fails loudly when an issue has enough URLs
numerically but the editorial sources do not overlap with the headline,
workflow, tool, or operator job-to-be-done.
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from utils import WORKSPACE, artifact_suffix_for_issue, dump_json, issue_path_for_today, load_text

MIN_EDITORIAL_SOURCES = int(os.getenv("MIN_EDITORIAL_SOURCES", "3"))
MIN_RELEVANT_SOURCES = int(os.getenv("MIN_RELEVANT_SOURCES", "2"))
RUN_TOKEN = os.getenv("RUN_TOKEN", "").strip()
PRIMARY_CTA_URL = os.getenv("PRIMARY_CTA_URL", "").strip().rstrip("/").lower()
KIT_SIGNUP_URL = os.getenv("KIT_SIGNUP_URL", "").strip().rstrip("/").lower()

NON_EDITORIAL_DOMAINS = {
    "forge-daily.kit.com",
    "kit.com",
    "beehiiv.com",
    "forgecore-newsletter.beehiiv.com",
    "news.forgecore.co",
    "forgecore.co",
    "example.com",
}

STOPWORDS = {
    "about", "after", "again", "against", "also", "with", "from", "that", "this", "into", "your", "you", "for",
    "and", "the", "can", "how", "why", "what", "when", "where", "week", "issue", "solo", "founders", "founder",
    "operators", "operator", "client", "clients", "using", "use", "uses", "tool", "tools", "workflow", "workflows",
    "automation", "automate", "automating", "maximum", "efficiency", "effective", "guide", "playbook", "brief",
    "newsletter", "ai", "a", "an", "to", "of", "in", "on", "is", "are", "be", "as", "by", "or", "at",
}

DOMAIN_KEYWORDS = {
    "openai.com": {"openai", "chatgpt", "gpt", "model", "api", "agent", "agents"},
    "zapier.com": {"zapier", "automation", "automate", "workflow", "crm", "lead", "linkedin", "capi"},
    "hubspot.com": {"hubspot", "crm", "marketing", "sales", "lead", "pricing", "brand", "customer"},
    "descript.com": {"descript", "transcript", "meeting", "audio", "video", "summarize"},
    "notion.so": {"notion", "database", "workspace", "notes", "docs"},
    "canva.com": {"canva", "design", "creative", "visual", "content"},
}


def normalize_url(url: str) -> str:
    return url.strip().rstrip(".,)]}")


def domain_for(url: str) -> str:
    host = urlparse(url).netloc.lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def raw_urls(text: str) -> list[str]:
    source_text = text.split("## Sources", 1)[-1] if "## Sources" in text else text
    return list(dict.fromkeys(normalize_url(match.group(0)) for match in re.finditer(r"https?://[^\s)>\]]+", source_text)))


def is_non_editorial_url(url: str) -> bool:
    normalized = normalize_url(url).rstrip("/").lower()
    domain = domain_for(normalized)
    if PRIMARY_CTA_URL and normalized == PRIMARY_CTA_URL:
        return True
    if KIT_SIGNUP_URL and normalized == KIT_SIGNUP_URL:
        return True
    return domain in NON_EDITORIAL_DOMAINS or any(domain.endswith("." + d) for d in NON_EDITORIAL_DOMAINS)


def issue_terms(text: str) -> set[str]:
    heading_bits: list[str] = []
    for pattern in [r"^#\s+(.+)$", r"^## Tool of the Week\s*\n(.+?)(?=^## |\Z)", r"^## Workflow\s*\n(.+?)(?=^## |\Z)"]:
        match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
        if match:
            heading_bits.append(match.group(1)[:1200])
    terms: set[str] = set()
    for token in re.findall(r"[A-Za-z][A-Za-z0-9+-]{2,}", "\n".join(heading_bits).lower()):
        token = token.strip("-+")
        if len(token) >= 4 and token not in STOPWORDS:
            terms.add(token)
    return terms


def source_tokens(url: str) -> set[str]:
    parsed = urlparse(url)
    domain = domain_for(url)
    blob = " ".join([domain, parsed.path.replace("-", " ").replace("_", " ")]).lower()
    tokens = {token for token in re.findall(r"[a-z][a-z0-9]{2,}", blob) if token not in STOPWORDS and len(token) >= 4}
    tokens |= DOMAIN_KEYWORDS.get(domain, set())
    return tokens


def relevance_hits(url: str, terms: set[str]) -> set[str]:
    tokens = source_tokens(url)
    hits = tokens & terms
    # Treat closely related singular/plural tokens as a hit without full stemming.
    for term in terms:
        if term.endswith("s") and term[:-1] in tokens:
            hits.add(term)
        elif f"{term}s" in tokens:
            hits.add(term)
    return hits


def validate(issue_path: Path) -> dict:
    text = load_text(issue_path)
    urls = raw_urls(text)
    editorial_urls = [url for url in urls if not is_non_editorial_url(url)]
    terms = issue_terms(text)
    relevant = []
    weak = []
    for url in editorial_urls:
        hits = sorted(relevance_hits(url, terms))
        if hits:
            relevant.append({"url": url, "hits": hits[:8]})
        else:
            weak.append(url)

    domains = [domain_for(url) for url in editorial_urls]
    domain_counts = Counter(domains)
    errors: list[str] = []
    warnings: list[str] = []
    if len(editorial_urls) < MIN_EDITORIAL_SOURCES:
        errors.append(f"Not enough editorial source URLs: found {len(editorial_urls)}, need {MIN_EDITORIAL_SOURCES}")
    if len(relevant) < MIN_RELEVANT_SOURCES:
        errors.append(
            f"Too few topic-relevant editorial sources: found {len(relevant)}, need {MIN_RELEVANT_SOURCES}; "
            f"issue terms sampled: {', '.join(sorted(terms)[:12]) or 'none'}"
        )
    if weak:
        warnings.append("Editorial sources with weak topic overlap: " + ", ".join(weak[:4]))
    if domain_counts:
        top_domain, top_count = domain_counts.most_common(1)[0]
        if top_count == len(editorial_urls) and len(editorial_urls) >= MIN_EDITORIAL_SOURCES:
            warnings.append(f"All editorial sources come from one domain: {top_domain}")

    return {
        "passed": not errors,
        "issue": issue_path.as_posix(),
        "raw_url_count": len(urls),
        "editorial_url_count": len(editorial_urls),
        "relevant_source_count": len(relevant),
        "issue_terms": sorted(terms)[:40],
        "relevant_sources": relevant,
        "ignored_non_editorial_urls": [url for url in urls if is_non_editorial_url(url)],
        "errors": errors,
        "warnings": warnings,
        "run_token": RUN_TOKEN,
        "validation_only": True,
    }


def main() -> int:
    issue_path = issue_path_for_today()
    result = validate(issue_path)
    out_path = WORKSPACE / "state" / f"source-relevance-{artifact_suffix_for_issue(issue_path)}.json"
    result["artifact_path"] = out_path.as_posix()
    dump_json(out_path, result)
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
