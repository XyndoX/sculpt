#!/usr/bin/env python3
"""Mine Claude Code session transcripts into a compact usage + friction digest.

Usage: python3 -I mine.py [--days 30] [--home ~] [--out digest.json]

Read-only. Walks ~/.claude/projects/*/*.jsonl and the installed tool surface
(plugins, skills, agents, hooks, MCP servers), then prints one JSON digest:
what exists, what got used, what failed, where the user had to correct Claude.
Stdlib only, so it runs anywhere Claude Code does.
"""
import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# English + German; matched in the first 150 chars of a human prompt.
CORRECTION_RE = re.compile(
    r"^(no\b|nope|nein\b|stop|stopp)|\b(that'?s not|not what i|why did you|i (said|told you)|"
    r"you forgot|you didn'?t|still (broken|wrong|not)|doesn'?t work|not working|wrong|undo|revert|"
    r"falsch|immer noch|geht (immer noch )?nicht|funktioniert (immer noch )?nicht|kaputt|nochmal|"
    r"warum hast du|hab ich (doch )?gesagt|keine ahnung wo du)\b", re.I)
# Human-looking turns that are really machine traffic.
NOISE = ("Another Claude session", "This session is being continued", "Reply with exactly",
         "Caveat:", "[Image")
SAMPLES = 40  # cap on quoted user messages, keeps the digest readable


def load_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def inventory(home):
    """Everything installed that could be used: plugin -> parts, plus personal parts."""
    claude = home / ".claude"
    settings = load_json(claude / "settings.json")
    enabled = {k for k, v in settings.get("enabledPlugins", {}).items() if v}
    installed = load_json(claude / "plugins" / "installed_plugins.json").get("plugins", {})
    plugins = {}
    for key, entries in installed.items():
        root = Path(entries[0]["installPath"]) if entries else None
        parts = {"skills": [], "agents": [], "commands": [], "hooks": False}
        if root and root.exists():
            parts["skills"] = sorted(p.parent.name for p in root.glob("skills/*/SKILL.md"))
            parts["agents"] = sorted(p.stem for p in root.glob("agents/*.md"))
            parts["commands"] = sorted(p.stem for p in root.glob("commands/*.md"))
            parts["hooks"] = (root / "hooks" / "hooks.json").exists()
        plugins[key] = {"enabled": key in enabled, **parts}
    cj = load_json(home / ".claude.json")
    mcp = set(cj.get("mcpServers", {}))
    for proj in cj.get("projects", {}).values():
        if isinstance(proj, dict):
            mcp |= set(proj.get("mcpServers") or {})
    return {
        "plugins": plugins,
        "skills": sorted(p.parent.name for p in (claude / "skills").glob("*/SKILL.md")),
        "agents": sorted(p.stem for p in (claude / "agents").glob("*.md")),
        "hooks": sorted(settings.get("hooks", {})),
        "mcp_servers": sorted(mcp),
    }


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def ts(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


def scan(home, days):
    cutoff = time.time() - days * 86400
    c = defaultdict(Counter)
    corrections, prompts, sessions = [], [], []
    for f in (home / ".claude" / "projects").glob("*/*.jsonl"):
        if f.stat().st_mtime < cutoff:
            continue
        times, turns, last_call, repeat = [], 0, None, 0
        project = f.parent.name
        for line in f.open(errors="replace"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            t, msg = d.get("type"), d.get("message") or {}
            if d.get("timestamp") and (x := ts(d["timestamp"])):
                times.append(x)
            if d.get("cwd"):
                project = d["cwd"]
            if t == "system":
                c["system"][d.get("subtype")] += 1
            elif t == "attachment":
                a = d.get("attachment") or {}
                if a.get("type", "").startswith("hook"):
                    c["hooks"][f'{a.get("hookName")} [{a["type"]}]'] += 1
            elif t == "assistant":
                c["models"][msg.get("model")] += 1
                u = msg.get("usage") or {}
                c["tokens"][msg.get("model")] += u.get("output_tokens", 0)
                for b in msg.get("content") or []:
                    if b.get("type") != "tool_use":
                        continue
                    name, inp = b.get("name"), b.get("input") or {}
                    c["tools"][name] += 1
                    if name == "Skill":
                        c["skills"][inp.get("skill")] += 1
                    elif name in ("Agent", "Task"):
                        c["agents"][f'{inp.get("subagent_type") or "general"} ({inp.get("model") or "inherit"})'] += 1
                    elif name.startswith("mcp__"):
                        c["mcp"][name.split("__")[1]] += 1
                    call = (name, json.dumps(inp, sort_keys=True))
                    repeat = repeat + 1 if call == last_call else 0
                    last_call = call
                    if repeat == 2:  # third identical call in a row
                        c["retry_loops"][name] += 1
            elif t == "user" and not d.get("isMeta"):
                content = msg.get("content")
                if isinstance(content, list):
                    for b in content:
                        if b.get("type") == "tool_result" and b.get("is_error"):
                            err = str(b.get("content"))[:80].replace("\n", " ")
                            c["tool_errors"][re.sub(r"\d+", "N", err)] += 1
                txt = text_of(content).strip()
                if not txt or txt.startswith("<"):
                    if m := re.search(r"<command-name>/?([^<]+)</command-name>", txt):
                        c["slash_commands"][m.group(1)] += 1
                    continue
                if txt.startswith("[Request interrupted"):
                    c["interrupts"][txt[:45]] += 1
                    continue
                if txt.startswith(NOISE):
                    continue
                turns += 1
                prompts.append({"project": project, "text": txt[:240], "chars": len(txt)})
                if CORRECTION_RE.search(txt[:150]):
                    c["system"]["corrections"] += 1
                    if len(corrections) < SAMPLES:
                        corrections.append({"project": project, "text": txt[:240]})
        if times:
            sessions.append({"project": project, "turns": turns,
                             "minutes": round((max(times) - min(times)) / 60)})
    return c, corrections, prompts, sessions


def unused(inv, c):
    used_skills = {s for s in c["skills"] if s} | set(c["slash_commands"])
    used_plugins = {s.split(":")[0] for s in used_skills if ":" in s}
    used_plugins |= {m.split("_")[1] for m in c["mcp"] if m.startswith("plugin_")}
    agent_types = {a.split(" (")[0] for a in c["agents"]}
    used_plugins |= {a.split(":")[0] for a in agent_types if ":" in a}
    idle = [k for k, v in inv["plugins"].items() if v["enabled"] and k.split("@")[0] not in used_plugins]
    return {
        # Hook-only plugins act every session without being "called"; judge them by their effect.
        "plugins": sorted(k for k in idle if not inv["plugins"][k]["hooks"]),
        "passive_hook_plugins": sorted(k for k in idle if inv["plugins"][k]["hooks"]),
        "skills": sorted(s for s in inv["skills"] if s not in used_skills),
        "agents": sorted(a for a in inv["agents"] if a not in agent_types),
        "mcp_servers": sorted(m for m in inv["mcp_servers"]
                              if m not in c["mcp"] and f"claude_ai_{m}" not in c["mcp"]),
    }


def digest(home, days):
    inv = inventory(home)
    c, corrections, prompts, sessions = scan(home, days)
    lengths = sorted(p["chars"] for p in prompts) or [0]
    per_project = Counter(s["project"] for s in sessions)
    top = lambda k, n=25: dict(c[k].most_common(n))
    return {
        "window_days": days,
        "sessions": len(sessions),
        "sessions_per_project": dict(per_project.most_common(15)),
        "longest_sessions": sorted(sessions, key=lambda s: -s["minutes"])[:8],
        "inventory_counts": {"plugins_enabled": sum(v["enabled"] for v in inv["plugins"].values()),
                             "skills": len(inv["skills"]), "agents": len(inv["agents"]),
                             "mcp_servers": len(inv["mcp_servers"]), "settings_hooks": inv["hooks"]},
        "used": {k: top(k) for k in ("tools", "skills", "slash_commands", "agents", "mcp", "hooks", "models")},
        "output_tokens_by_model": dict(c["tokens"]),
        "unused": unused(inv, c),
        "friction": {"tool_errors": top("tool_errors", 20), "retry_loops": top("retry_loops"),
                     "interrupts": sum(c["interrupts"].values()),
                     "compactions": c["system"]["compact_boundary"],
                     "api_errors": c["system"]["api_error"],
                     "corrections_total": c["system"]["corrections"],
                     "corrections": corrections},
        "prompts": {"total": len(prompts), "median_chars": lengths[len(lengths) // 2],
                    "under_40_chars": sum(n < 40 for n in lengths),
                    # Even spread across the window, for judging how the user steers.
                    "sample": prompts[::max(1, len(prompts) // SAMPLES)][:SAMPLES]},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--home", type=Path, default=Path.home())
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    out = json.dumps(digest(a.home, a.days), indent=1, default=str)
    if a.out:
        a.out.write_text(out)
        print(f"wrote {a.out}", file=sys.stderr)
    else:
        print(out)


if __name__ == "__main__":
    main()
