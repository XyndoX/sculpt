# Levers

Pick the smallest lever that removes the friction. Order is roughly cost, cheapest first.

| Lever | Use when | Lives in | Strength |
|---|---|---|---|
| **Remove** a plugin, skill, MCP server | Unused across the window and not seasonal; or it causes errors | `settings.json` `enabledPlugins`, `~/.claude.json` | Frees context on every turn. Best value per minute. |
| **Memory / CLAUDE.md line** | Claude repeats a choice the user keeps reversing | `~/.claude/CLAUDE.md`, project `CLAUDE.md`, memory dir | Asks, doesn't enforce. One line, stated as the rule plus why. |
| **Permission allowlist** | The same safe command gets denied or prompted again and again | `settings.json` `permissions.allow` | Removes waiting time. Never allow destructive commands. |
| **Hook** | A rule keeps getting broken despite being written down, or a check must run every time (format on edit, block edits to a path, run tests before stop) | `settings.json` `hooks` or a plugin's `hooks/hooks.json` | Enforces. The only lever that guarantees behaviour. |
| **Skill** | The user re-explains the same multi-step procedure across sessions | `~/.claude/skills/<name>/SKILL.md` | Loads only when relevant. Description decides when it fires; make it specific. |
| **Subagent** | Work floods the main context (searches, log digging, reviews) or needs a different model | `~/.claude/agents/<name>.md` | Keeps the main thread clean. Give it a narrow job and a report format. |
| **Slash command / workflow** | A fixed sequence the user starts by hand every time | plugin `commands/`, or a skill with arguments | Turns a paragraph of prompt into one word. |
| **Plugin** | Several of the above belong together and are worth sharing | a repo with `.claude-plugin/plugin.json` | Packaging, not a fix by itself. |

## Sizing rules

- A mistake that happened once is an anecdote. Twice in different sessions is a pattern. Propose fixes for patterns.
- If a CLAUDE.md rule already exists for the friction and it still happens, upgrade to a hook rather than rewording the rule.
- A new skill must name at least two transcript moments it would have shortened.
- Skill descriptions that fire on everything are a cost: they compete with other skills. Narrow them.
- Agents that always run on the most expensive model for mechanical work are a cost too; check `used.agents` for the model split.

## Signals in the digest and what they usually mean

- `friction.tool_errors` dominated by permission denials → allowlist or a hook that explains the rule up front.
- `friction.retry_loops` → Claude is stuck on one call; usually a missing instruction about the environment (wrong path, wrong tool) or a broken script.
- High `compactions` per session → sessions too long; propose handoffs or splitting work, or subagents for the heavy reading.
- `prompts.under_40_chars` high with many corrections → under-specified prompts; coaching, not config.
- Many `unused.plugins` → context tax on every turn; prune.
- An agent type used heavily on one model → check whether a cheaper or stronger model fits the job better.
