---
name: sculpt
description: Review past Claude Code sessions and resculpt the setup into a better version of itself — find the bottlenecks, which plugins, skills, agents, hooks, MCP servers and workflows earn their keep and which are dead weight, what new skill, hook, agent or workflow would remove recurring friction, and how the user can steer Claude better. Use when the user says "sculpt", "/sculpt", "review my sessions", "where is my bottleneck", "what am I not using", "improve my Claude setup", "make Claude better from my history", "coach me", or roughly monthly as maintenance. Writes a ranked report with concrete proposals; changes nothing until the user approves.
argument-hint: "[days, default 30] [focus, e.g. 'hooks' or 'project brickforge']"
---

# Sculpt

Turn session history into a sharper setup. The output is a report the user can act on in five minutes, plus the edits they approve. Every claim in the report cites a number from the digest or a quoted moment from a transcript. No evidence, no proposal.

## 1. Mine

Run the miner (stdlib Python, read-only, a few seconds for a month of history):

```sh
python3 -I "<this skill's directory>/scripts/mine.py" --days <N> --out "$TMPDIR/sculpt-digest.json"
```

Read the digest. It holds: the installed surface (`inventory_counts`), what was actually used (`used`: tools, skills, slash commands, agents with their models, MCP servers, hooks), what never was (`unused`, with hook-only plugins split into `passive_hook_plugins`), friction (`tool_errors`, `retry_loops`, `interrupts`, `compactions`, `api_errors`, `corrections`), and a spread `prompts.sample` of the user's own words.

If a previous report exists in `~/.claude/sculpt/reports/`, read the newest one. Check which of its proposals were applied and whether the numbers they targeted moved. Lead the new report with that scorecard: it is how the setup learns.

## 2. Look closer

The digest says where; the transcripts say why. For the top three friction signals, open the sessions behind them (`~/.claude/projects/<project>/*.jsonl`, grep for the error text or correction) and read the turns around each one. You are looking for the root cause, which is usually one of:

- **A missing instruction**: Claude keeps making a choice the user keeps reversing. Fix: a `CLAUDE.md` line or a memory.
- **A missing guard**: a mistake that rules alone don't stop (wrong command, edits to a protected file, skipped tests). Fix: a hook. Hooks enforce; instructions only ask.
- **A missing procedure**: the user re-explains the same multi-step job across sessions. Fix: a skill.
- **A missing specialist**: work that floods the main context (log digging, wide searches, reviews). Fix: a subagent, or routing to an existing one.
- **Tool friction**: the same error class recurring (permission denials, a flaky MCP server, a broken script). Fix: an allowlist entry, a config change, or removing the tool.
- **Steering**: the prompt itself set Claude up to fail (no goal, no done-condition, five tasks in one line). Fix: coaching, not config.

Read `references/levers.md` for the catalogue of fixes and when each one is the right size.

## 3. Find what's missing

For each recurring job with no tool behind it, check whether one already exists before proposing to build it: the user's installed-but-unused list first (often the answer is already installed), then the marketplaces they have added (`~/.claude/plugins/known_marketplaces.json`), then a web search for a maintained plugin or skill. Building new is the last option and must name the transcript moments it would have saved.

## 4. Coach the captain

Using `prompts.sample` and the sessions you read, give the user three habits at most, each with one quoted prompt of theirs and a rewritten version. Judge against what makes agentic sessions go well: a stated goal and a done-condition, one bounded task at a time, verification asked for (tests, a run, a screenshot), context pointed at (files, issues, the roadmap) instead of re-explained, decisions made instead of deferred to Claude. Be direct and specific; skip praise and generalities.

## 5. Report

Write `~/.claude/sculpt/reports/<YYYY-MM-DD>.md` (create the folder) with these sections, each kept short:

1. **Scorecard**: last report's proposals → applied? effect? (omit on the first run)
2. **Bottlenecks**: the top three, each with its evidence (number + quoted moment) and root cause.
3. **Proposals**, ranked by friction removed per minute of effort. Each one: what, why (evidence), the exact change (file path and the diff, command or new file content), and the risk. Group as *Prune*, *Fix*, *Add*.
4. **Captain's notes**: the three habits.
5. **Kept on purpose**: unused things that are still worth keeping (seasonal, just installed, passive hooks doing their job), so the next run doesn't re-flag them.

Then give the user a short summary in chat: the top bottleneck, the three highest-value proposals, and the report path. Ask which proposals to apply.

## 6. Apply

Apply only what the user approves, one proposal at a time, each verified (a hook gets a test trigger, a pruned plugin gets a `claude plugin list` check, a new skill gets listed). Disable rather than uninstall. Back up any settings file before editing it. If the user's config is under git, commit each applied proposal separately with the proposal title as the message, so any one can be reverted.

## Rules

- Read-only until approval. The miner never writes; you write only the report before the user says yes.
- The digest contains the user's private prompts. The report stays in `~/.claude/sculpt/`; never paste digest contents into issues, PRs, or anything outside the machine.
- Counts lie in small windows. A skill used once in 30 days may be seasonal; say so instead of pruning it.
- Prefer deleting to adding. A proposal that removes a plugin, rule, or step beats one that adds a new one for the same gain.
