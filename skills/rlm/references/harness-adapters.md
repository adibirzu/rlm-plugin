# Harness adapters

Read this reference before delegating partitions to sub-agents, or when unsure how the current harness runs commands, workers, or scratch files. Find your harness below and apply its four lines. Paths in this file are relative to the skill directory unless they start with `~`.

How to read the entries:

- **Invocation** is how a user or a parent agent starts this skill.
- **Delegation** is how to run a partition in a separate context.
- **Scratchpad** is where the Print Contract state lives and how to run the bundled scripts.
- **Fallback** is what to do when delegation is unavailable or refused.

Facts were checked on 2026-11-20 against each CLI's `--help` output and against working sessions. Anything marked "unverified" was not observed directly. Check the session's own tool list before relying on it. Tool and flag names change between releases, so when the session disagrees with this file, trust the session.

## Rules for every harness

- Use a sub-agent tool only when the session lists one. Never assume a tool exists because another harness has it.
- A worker gets a brief that stands alone: scope paths or a chunk id from the manifest, the question, exclusions, tier and depth budget, and the worker result format from `SKILL.md`. Workers do not inherit the parent context.
- Workers are read-only unless the user asked for fixes. Ask for the strictest sandbox the harness offers.
- Have each worker write its result to `.rlm/<topic>/worker-NN.md` or return it as its final message. Validate it with `scripts/rlm_ledger.py` before reading it into the synthesis.
- A child process that runs another harness's CLI is also the way to get a reviewer from a different model family. Pass it the claim and the source locations only.
- Shell state usually does not persist between tool calls. Keep state in `.rlm/<topic>/` files. Use a persistent REPL only where the harness provides one.
- Choose the tier from the model that does the work, not from the harness. A local model served through any of these harnesses is the small tier.

## Claude Code

Skill directory: `~/.claude/skills/rlm`, or the `rlm` plugin from the marketplace.

- Invocation: `/rlm <task> [path]` for the personal skill and `/rlm:rlm <task> [path]` for the plugin. The description also triggers it automatically. Headless: `claude -p "<prompt>"`.
- Delegation: the `Agent` tool (named `Task` in older releases) with a `subagent_type`. Use a read-only search type such as `Explore` for discovery partitions and a general-purpose type for analysis. Send several `Agent` calls in one message to run independent partitions in parallel.
- Scratchpad: the `Bash` tool keeps the working directory but not shell variables, so state goes in `.rlm/<topic>/`. Run the scripts with `python3 <skill-dir>/scripts/rlm_inventory.py`.
- Fallback: review the partitions one after another in the main thread and report that coverage was sequential.

## Codex

Skill directory: `~/.codex/skills/rlm`, or the plugin described by `.codex-plugin/plugin.json`.

- Invocation: `$rlm <task>` in the interactive session. A leading slash is not accepted for skills. Headless: `codex exec "<prompt>"`.
- Delegation: worker processes through `codex exec --sandbox read-only -C <dir> -o .rlm/<topic>/worker-NN.md "<brief>"`. Add `-m <model>` to pick the worker model and `--json` for an event stream. An in-session sub-agent tool is unverified. Use one only if the session lists it.
- Scratchpad: the shell tool plus `.rlm/<topic>/` files. The read-only sandbox blocks writes, so let the parent write worker output through `-o`.
- Fallback: sequential partitions in the current session.

## Agent Skills directory

Skill directory: `~/.agents/skills/rlm`. This is the shared location defined by the Agent Skills convention, and more than one harness reads it.

- Invocation: whatever the host harness uses for skills. Follow that harness's entry in this file.
- Delegation: the host harness's mechanism.
- Scratchpad: the host harness's shell and `.rlm/<topic>/`.
- Fallback: the host harness's fallback.

On many machines `~/.agents/skills` is a symlink to another harness's skill directory, for example `~/.codex/skills`. `install.sh` detects that and reports the entry as an alias instead of linking the skill twice.

## Gemini CLI

Skill directory: `~/.gemini/skills/rlm`. Gemini CLI also discovers `~/.agents/skills`.

- Invocation: `/rlm <task>`. The turn opens with a skill activation tool call. Headless: `gemini -p "<prompt>"` with `--output-format json` for machine-readable output.
- Delegation: use the sub-agent tool the session lists, if any. Tool names differ by release and are unverified here. Independent read-only tool calls may be issued together in one turn. Otherwise run workers as `gemini -p "<brief>"` child processes.
- Scratchpad: the shell tool plus `.rlm/<topic>/` files. An untrusted workspace does not load project skills, so run inside a trusted workspace.
- Fallback: sequential partitions in the current session.

## Antigravity

Skill directory: `~/.gemini/config/skills/rlm`.

- Invocation: ask in plain language, for example "use the rlm skill to audit services/". A slash form is unverified. Headless: `agy -p "<prompt>"`, with `--output-format json` when a parent parses the result. `--disable-slash-commands` turns off skill expansion in print mode, so do not pass it.
- Delegation: `invoke_subagent` for one worker and `run_workflow` for a scripted fan-out, when the session lists them (names unverified in this review). Parallel tool calls in one turn work for independent read-only partitions.
- Scratchpad: the terminal tool plus `.rlm/<topic>/` files inside a trusted workspace.
- Fallback: `agy -p` child processes, or sequential partitions.

## Cursor

Skill directory: `~/.cursor/skills/rlm`.

- Invocation: `/rlm <task>` in the agent. Headless: `cursor-agent -p "<prompt>" --output-format json --workspace <dir>`.
- Delegation: the `Task` tool with a `subagent_type` and an explicit model, run in the background for parallel partitions. Read-only sub-agents lose access to connected tools, so give them file paths and nothing else to fetch.
- Scratchpad: the terminal tool plus `.rlm/<topic>/` files.
- Fallback: `cursor-agent -p` child processes, or sequential partitions.

## OpenCode

Skill directories: `~/.config/opencode/skills/rlm` and `~/.opencode/skills/rlm`. An installation uses one or both. `install.sh` links whichever exists.

- Invocation: ask in plain language. The agent loads the skill through its skill tool, subject to the `permission.skill` setting. Headless: `opencode run "<prompt>" --format json`, with `--agent <name>` and `-m <provider/model>` as needed.
- Delegation: a built-in sub-agent tool is unverified here. Use it if the session lists it. Otherwise run workers as `opencode run "<brief>" --format json` child processes.
- Scratchpad: the shell tool plus `.rlm/<topic>/` files.
- Fallback: sequential partitions. OpenCode often fronts local models with small context windows. Treat those as the small tier and take partitions from `scripts/rlm_inventory.py`.

## Pi

Skill directory: `~/.pi/skills/rlm`. A session can also load the skill explicitly with `pi --skill <path-to-rlm>`.

- Invocation: ask in plain language, or start with `pi --skill <path-to-rlm>`. Headless: `pi -p "<prompt>"`, with `--mode json` for structured output.
- Delegation: Pi has no built-in sub-agent tool. An extension loaded with `-e <path>` can add one, and fleet tooling such as `fm` dispatches workers from outside the session. Without either, run `pi -p "<brief>"` child processes.
- Scratchpad: the shell tool plus `.rlm/<topic>/` files.
- Fallback: sequential partitions in the current session.

## Grok

Skill directory: `~/.grok/skills/rlm`.

- Invocation: `/rlm <task>`. The skill popup can swallow the first Enter. Headless mode takes `--output-format json`.
- Delegation: built-in sub-agents, on by default and disabled by `--no-subagents`. Custom workers can be defined with `--agents <JSON>` or selected with `--agent <name>`.
- Scratchpad: the shell tool plus `.rlm/<topic>/` files.
- Fallback: sequential partitions when sub-agents are disabled.

## Cline

Skill directory: `~/.cline/skills/rlm`.

- Invocation: ask in plain language. A prompt given on the command line starts the first turn. `-p` runs in plan mode, which suits review-only analysis. `--json` prints messages as JSON.
- Delegation: no sub-agent tool is verified. Treat delegation as unavailable unless the session lists one.
- Scratchpad: the terminal tool plus `.rlm/<topic>/` files.
- Fallback: sequential partitions in the current task. Keep each partition's result in a ledger file so the context stays small.

## Installing into every harness

From a checkout of this repository:

```bash
./install.sh --check            # read-only report, exit 3 on drift
./install.sh --sync-harnesses   # symlink the skill into each harness that is present
```

The sync links only harnesses whose home directory exists. It replaces an identical copy with a symlink, refuses a copy that differs unless `--backup` is given, and moves anything it replaces to `~/.rlm-skill-backups/`. It never deletes.
