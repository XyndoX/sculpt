"""Run: python3 -I skills/sculpt/scripts/test_mine.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import mine  # noqa: E402


def tool(name, **inp):
    return {"type": "assistant", "timestamp": "2026-01-01T10:00:00Z",
            "message": {"model": "m1", "usage": {"output_tokens": 5},
                        "content": [{"type": "tool_use", "name": name, "input": inp}]}}


def user(content, **kw):
    return {"type": "user", "timestamp": "2026-01-01T10:30:00Z", "message": {"content": content}, **kw}


def test():
    home = Path(tempfile.mkdtemp())
    plug = home / "cache" / "p1"
    (plug / "skills" / "s1").mkdir(parents=True)
    (plug / "skills" / "s1" / "SKILL.md").write_text("x")
    c = home / ".claude"
    (c / "skills" / "mine-used").mkdir(parents=True)
    (c / "skills" / "mine-used" / "SKILL.md").write_text("x")
    (c / "skills" / "mine-idle").mkdir()
    (c / "skills" / "mine-idle" / "SKILL.md").write_text("x")
    hooked = home / "cache" / "p3"
    (hooked / "hooks").mkdir(parents=True)
    (hooked / "hooks" / "hooks.json").write_text("{}")
    (c / "plugins").mkdir()
    (c / "plugins" / "installed_plugins.json").write_text(json.dumps({"plugins": {
        "p1@m": [{"installPath": str(plug)}], "p2@m": [{"installPath": "/nope"}],
        "p3@m": [{"installPath": str(hooked)}]}}))
    (c / "settings.json").write_text(json.dumps({"enabledPlugins": {"p1@m": True, "p2@m": True, "p3@m": True}}))
    proj = c / "projects" / "-x"
    proj.mkdir(parents=True)
    rows = [
        {"type": "attachment", "attachment": {"type": "hook_success", "hookName": "SessionStart:startup"}},
        user("build the thing", cwd="/work/x"),
        tool("Skill", skill="p1:s1"),
        tool("Skill", skill="mine-used"),
        tool("Bash", command="make"), tool("Bash", command="make"), tool("Bash", command="make"),
        user([{"type": "tool_result", "is_error": True, "content": "Exit code 2"}]),
        user("no, that's wrong, use the other file"),
        user("<command-name>/p1:s1</command-name>", isMeta=True),
        user("[Request interrupted by user]"),
        {"type": "system", "subtype": "compact_boundary"},
        user("Another Claude session sent a message: hi"),
        user("das geht immer noch nicht"),
        "not json at all",
    ]
    (proj / "s.jsonl").write_text("\n".join(r if isinstance(r, str) else json.dumps(r) for r in rows))

    d = mine.digest(home, days=9999)
    assert d["sessions"] == 1 and d["longest_sessions"][0]["minutes"] == 30, d["longest_sessions"]
    assert d["used"]["tools"]["Bash"] == 3
    assert d["used"]["skills"] == {"p1:s1": 1, "mine-used": 1}
    assert d["used"]["hooks"] == {"SessionStart:startup [hook_success]": 1}
    assert d["unused"]["plugins"] == ["p2@m"], d["unused"]
    assert d["unused"]["passive_hook_plugins"] == ["p3@m"]
    assert d["unused"]["skills"] == ["mine-idle"], d["unused"]
    f = d["friction"]
    assert f["retry_loops"] == {"Bash": 1} and f["interrupts"] == 1 and f["compactions"] == 1
    assert f["tool_errors"] == {"Exit code N": 1}
    assert [x["text"][:3] for x in f["corrections"]] == ["no,", "das"], f["corrections"]
    assert d["prompts"]["total"] == 3 and f["corrections_total"] == 2
    assert d["sessions_per_project"] == {"/work/x": 1}
    print("ok")


if __name__ == "__main__":
    test()
