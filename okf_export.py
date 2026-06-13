#!/usr/bin/env python3
"""
OKF Exporter — AgentPay Shared Brain → Open Knowledge Format bundle
====================================================================
Reads the AgentPay/AgentWorld shared brain (SQLite) and emits a
conformant Open Knowledge Format (OKF v0.1) bundle: a directory of
markdown files with YAML frontmatter, cross-links, index.md and log.md.

OKF spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md

Usage:
    python3 okf_export.py --db /var/lib/agentworld/shared_brain.db --out ./agentpay-brain-okf

The output bundle is:
  - Just markdown (readable anywhere, renderable on GitHub)
  - Just files (git-shippable, no SDK)
  - Self-describing (every concept has a `type`)

This is the PUBLIC, opt-in, PII-free slice of the brain. It deliberately
exports only SYSTEM/agent-learned facts, world events, patterns and skills —
never private prompts, wallet keys, customer data, or raw user content.
"""
import argparse, os, re, sqlite3, json, hashlib
from datetime import datetime, timezone

# ── PII / sensitive guard ────────────────────────────────────────────────
# Concepts containing any of these patterns are SKIPPED from the public bundle.
_BLOCK_PATTERNS = [
    re.compile(r"0x[a-fA-F0-9]{40}"),               # raw EVM wallet/private addresses
    re.compile(r"\b[A-Za-z0-9]{43,44}\b"),          # solana-style keys
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY"),    # any private key block
    re.compile(r"\b(?:sk|pk)_[A-Za-z0-9]{20,}"),    # stripe-style secrets
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),  # emails
    re.compile(r"(?i)\b(private[_ ]?key|secret|api[_ ]?key|password|seed phrase)\b"),
]

def _is_safe(*texts):
    blob = " ".join(t for t in texts if t)
    return not any(p.search(blob) for p in _BLOCK_PATTERNS)

def _slug(s, maxlen=60):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (s or "").strip().lower()).strip("-")
    return (s[:maxlen] or "concept").rstrip("-")

def _yaml_escape(s):
    s = (s or "").replace("\n", " ").strip()
    if any(c in s for c in ':#[]{}"\'') :
        return '"' + s.replace('"', '\\"') + '"'
    return s

def _now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def _frontmatter(d):
    lines = ["---"]
    for k, v in d.items():
        if v is None or v == "":
            continue
        if isinstance(v, list):
            lines.append(f"{k}: [{', '.join(_yaml_escape(str(x)) for x in v)}]")
        else:
            lines.append(f"{k}: {_yaml_escape(str(v))}")
    lines.append("---")
    return "\n".join(lines)

def _write(out, relpath, content):
    p = os.path.join(out, relpath)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content.rstrip() + "\n")
    return relpath

def _rows(con, table):
    try:
        cur = con.execute(f"SELECT * FROM {table}")
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    except sqlite3.Error:
        return []

# ── Concept emitters (one per brain table) ───────────────────────────────
def export_knowledge(con, out, manifest):
    rows = _rows(con, "brain_knowledge")
    written = []
    for r in rows:
        fact = r.get("fact", "")
        if not _is_safe(fact, r.get("agent_name"), r.get("domain")):
            continue
        cat = _slug(r.get("category") or "general", 30)
        sid = _slug(fact, 50) + "-" + (r.get("fact_hash", "")[:8] or str(r.get("id")))
        rel = f"knowledge/{cat}/{sid}.md"
        fm = _frontmatter({
            "type": "Agent Fact",
            "title": fact[:80],
            "description": fact[:160],
            "tags": [r.get("domain"), r.get("category")],
            "timestamp": r.get("ts"),
            "confidence": r.get("confidence"),
            "times_confirmed": r.get("times_confirmed"),
            "learned_by": r.get("agent_name") or r.get("agent_id"),
            "origin": "agentpay-shared-brain",
        })
        body = f"# Fact\n\n{fact}\n\n# Provenance\n\n" \
               f"- **Domain:** {r.get('domain')}\n" \
               f"- **Category:** {r.get('category')}\n" \
               f"- **Learned by:** {r.get('agent_name') or r.get('agent_id')}\n" \
               f"- **Confidence:** {r.get('confidence')}\n" \
               f"- **Confirmations:** {r.get('times_confirmed')}\n"
        _write(out, rel, fm + "\n\n" + body)
        written.append((rel, fact[:80], r.get("description") or fact[:120]))
        manifest.append({"concept": rel[:-3], "type": "Agent Fact", "ts": r.get("ts")})
    return written

def export_events(con, out, manifest):
    rows = _rows(con, "brain_world_events")
    written = []
    for r in rows:
        hl = r.get("headline", "")
        detail = r.get("detail", "")
        if not _is_safe(hl, detail):
            continue
        sid = _slug(hl, 50) + "-" + str(r.get("id"))
        rel = f"events/{sid}.md"
        fm = _frontmatter({
            "type": "World Event",
            "title": hl[:80],
            "description": (detail or hl)[:160],
            "tags": [r.get("domain"), r.get("event_type"), r.get("city")],
            "timestamp": r.get("ts"),
            "impact": r.get("impact"),
            "origin": "agentpay-shared-brain",
        })
        body = f"# {hl}\n\n{detail}\n\n# Context\n\n" \
               f"- **Type:** {r.get('event_type')}\n" \
               f"- **City:** {r.get('city')}\n" \
               f"- **Impact:** {r.get('impact')}\n"
        _write(out, rel, fm + "\n\n" + body)
        written.append((rel, hl[:80], (detail or hl)[:120]))
        manifest.append({"concept": rel[:-3], "type": "World Event", "ts": r.get("ts")})
    return written

def export_patterns(con, out, manifest):
    rows = _rows(con, "brain_patterns")
    written = []
    for r in rows:
        ctx = r.get("context", ""); act = r.get("action", "")
        if not _is_safe(ctx, act, r.get("outcome")):
            continue
        sid = _slug(act, 40) + "-" + str(r.get("id"))
        rel = f"patterns/{_slug(r.get('pattern_type') or 'general',20)}/{sid}.md"
        fm = _frontmatter({
            "type": "Strategy Pattern",
            "title": (act or ctx)[:80],
            "description": f"{r.get('pattern_type')} pattern → {r.get('outcome')}",
            "tags": [r.get("domain"), r.get("pattern_type"), r.get("outcome")],
            "timestamp": r.get("ts"),
            "outcome_score": r.get("outcome_score"),
            "origin": "agentpay-shared-brain",
        })
        body = f"# Situation\n\n{ctx}\n\n# Action\n\n{act}\n\n# Outcome\n\n" \
               f"**{r.get('outcome')}** (score: {r.get('outcome_score')}, seen {r.get('times_seen')}x)\n"
        _write(out, rel, fm + "\n\n" + body)
        written.append((rel, (act or ctx)[:80], f"{r.get('pattern_type')} → {r.get('outcome')}"))
        manifest.append({"concept": rel[:-3], "type": "Strategy Pattern", "ts": r.get("ts")})
    return written

def export_skills(con, out, manifest):
    rows = _rows(con, "brain_skills")
    written = []
    for r in rows:
        nm = r.get("skill_name", ""); desc = r.get("description", "")
        if not _is_safe(nm, desc):
            continue
        sid = _slug(nm, 40) + "-" + str(r.get("id"))
        rel = f"skills/{sid}.md"
        fm = _frontmatter({
            "type": "Agent Skill",
            "title": nm[:80],
            "description": (desc or nm)[:160],
            "tags": [r.get("domain"), "skill"],
            "timestamp": r.get("ts"),
            "skill_level": r.get("skill_level"),
            "success_rate": r.get("success_rate"),
            "origin": "agentpay-shared-brain",
        })
        body = f"# {nm}\n\n{desc}\n\n# Mastery\n\n" \
               f"- **Level:** {r.get('skill_level')}/10\n" \
               f"- **Success rate:** {r.get('success_rate')}\n" \
               f"- **Times used:** {r.get('times_used')}\n"
        _write(out, rel, fm + "\n\n" + body)
        written.append((rel, nm[:80], (desc or nm)[:120]))
        manifest.append({"concept": rel[:-3], "type": "Agent Skill", "ts": r.get("ts")})
    return written

def write_index(out, section_dir, title, items):
    """Emit an OKF index.md (progressive disclosure) for a folder."""
    if not items:
        return
    lines = [f"# {title}\n"]
    for rel, t, desc in items:
        # link relative to the index location
        name = os.path.relpath(os.path.join(out, rel), os.path.join(out, section_dir))
        lines.append(f"* [{t}]({name}) - {desc}")
    _write(out, os.path.join(section_dir, "index.md"), "\n".join(lines))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    os.makedirs(args.out, exist_ok=True)
    manifest = []

    know = export_knowledge(con, args.out, manifest)
    evts = export_events(con, args.out, manifest)
    pats = export_patterns(con, args.out, manifest)
    skil = export_skills(con, args.out, manifest)

    # Per-section index files (OKF §6 progressive disclosure)
    write_index(args.out, "knowledge", "Agent Knowledge", know)
    write_index(args.out, "events", "World Events", evts)
    write_index(args.out, "patterns", "Strategy Patterns", pats)
    write_index(args.out, "skills", "Agent Skills", skil)

    total = len(know) + len(evts) + len(pats) + len(skil)

    # Root index.md
    root_index = f"""# AgentPay Shared Brain — OKF Bundle

The public, opt-in, PII-free knowledge graph that AgentPay/AgentWorld agents
learn collectively. Conformant with the [Open Knowledge Format (OKF) v0.1](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md).

Generated: {_now_iso()} · {total} concepts

# Sections

* [knowledge/](knowledge/) - Facts agents have learned ({len(know)})
* [events/](events/) - Significant world events agents witnessed ({len(evts)})
* [patterns/](patterns/) - Strategies that succeeded or failed ({len(pats)})
* [skills/](skills/) - Capabilities agents have mastered ({len(skil)})
"""
    _write(args.out, "index.md", root_index)

    # log.md (OKF §7 chronological history)
    log = f"# Update Log\n\n* {_now_iso()} — Exported {total} concepts from the AgentPay shared brain.\n"
    _write(args.out, "log.md", log)

    # machine-readable manifest (extension, non-reserved)
    _write(args.out, "MANIFEST.json", json.dumps({
        "format": "OKF",
        "version": "0.1",
        "producer": "AgentPay Shared Brain Exporter",
        "generated": _now_iso(),
        "concept_count": total,
        "concepts": manifest,
    }, indent=2))

    con.close()
    print(f"OKF bundle written to {args.out} — {total} concepts "
          f"(knowledge={len(know)} events={len(evts)} patterns={len(pats)} skills={len(skil)})")

if __name__ == "__main__":
    main()
