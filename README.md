# RLM Plugin v4.0: budgeted recursive analysis for agent harnesses

[![Version](https://img.shields.io/badge/version-4.0.0-blue.svg)](https://github.com/adibirzu/rlm-plugin/releases)
[![CI](https://github.com/adibirzu/rlm-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/adibirzu/rlm-plugin/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

RLM is an Agent Skill for analyzing repositories, logs, and document sets that are too large to read in one pass. It keeps raw content outside the context window, explores it with commands, partitions the work inside a budget that depends on the model, and validates findings before reporting them.

The approach follows ["Recursive Language Models"](https://arxiv.org/abs/2512.24601) by Zhang, Kraska, and Khattab, adjusted for what later reproduction work found about depth and cost. See [the research basis](skills/rlm/references/research-basis.md).

## What is new in 4.0.0

- **Print Contract.** Raw dumps stay in files under `.rlm/<topic>/`. Only bounded summaries are printed into the context.
- **Model-tier budgets.** Frontier, mid, and small models get different ceilings for depth, partitions, and sub-calls, so a small or local model stops instead of spiraling.
- **Deterministic helpers.** `rlm_inventory.py` builds a bounded inventory and chunk worklist. `rlm_ledger.py` rejects worker results with missing sections, empty or invented citations, or depth beyond the budget.
- **Selective verification.** High-impact claims with conflicting or weak evidence get one independent check, from a different model family when one is available.
- **Evals.** Seven benchmark and regression cases cover the behaviors above.
- **Every harness.** One skill directory serves Claude Code, Codex, Gemini CLI, Antigravity, Cursor, OpenCode, Pi, Grok, and Cline. `install.sh` reports drift and links them.

The worker result format gained `Budget` and `Verification` sections, which is why this is a major version.

## Install

### Claude Code

```bash
claude plugin marketplace add adibirzu/adibirzu-plugins
claude plugin install rlm@adibirzu-plugins --scope user
```

Or run the wrapper, which does the same through the supported CLI:

```bash
git clone https://github.com/adibirzu/rlm-plugin.git
bash rlm-plugin/install.sh
```

Apply the plugin in a running session with `/reload-plugins`.

### Codex

The repository includes `.codex-plugin/plugin.json`. Install it from a local Codex marketplace entry:

```bash
codex plugin add rlm@<personal-marketplace-name>
```

### Every harness at once

From a checkout, link the shared skill into each harness skill directory that exists on the machine:

```bash
./install.sh --check            # read-only report, add --json for machine output
./install.sh --sync-harnesses   # create or repair the symlinks
```

| Option | Effect |
|---|---|
| `--source <skill-dir>` | Skill directory to link (default: `skills/rlm` next to the script) |
| `--home <home-dir>` | Home directory to inspect (default: `$HOME`) |
| `--backup` | Let the sync move a differing local copy aside |
| `--json` | Print the `--check` report as JSON |

The sync covers `~/.claude/skills`, `~/.codex/skills`, `~/.gemini/skills`, `~/.gemini/config/skills`, `~/.agents/skills`, `~/.cursor/skills`, `~/.config/opencode/skills`, `~/.opencode/skills`, `~/.pi/skills`, `~/.grok/skills`, and `~/.cline/skills`. It skips harnesses that are not installed, treats a skill directory that is a symlink to another one (such as `~/.agents/skills` pointing at `~/.codex/skills`) as an alias, replaces an identical copy with a symlink, and refuses a copy that differs unless `--backup` is given. Replaced directories are moved to `~/.rlm-skill-backups/`. Nothing is deleted.

`--check` exits 0 when every present harness is linked and 3 when any has drifted. `--sync-harnesses` exits 1 when it refused a directory.

## Usage

In Claude Code:

```text
/rlm:rlm <task> [path]
```

```text
/rlm:rlm "find the authentication middleware" src/
/rlm:rlm "review the current branch for correctness and missing tests" .
/rlm:rlm "perform a repository-wide security and maintainability audit" .
```

In other harnesses, invoke the `rlm` skill the way that harness invokes skills (`$rlm` in Codex, `/rlm` in Gemini CLI, Cursor, and Grok, plain language elsewhere). [Harness adapters](skills/rlm/references/harness-adapters.md) lists invocation, delegation, scratchpad, and fallback behavior for each one.

RLM picks the smallest sufficient mode from scope, risk, and evidence, not from the first verb in the request.

## How it works

```text
request
  -> establish scope, trust boundaries, and available capabilities
  -> choose focused, standard, or deep mode and set an effort contract for the model tier
  -> measure and query the context with commands, printing only bounded summaries
  -> inventory, pilot, and partition independent surfaces when the scope is large
  -> validate each worker ledger, then verify uncertain high-impact claims independently
  -> synthesize findings with path:line evidence, coverage, and proof gaps
```

## Helper scripts

Both scripts need Python 3.11 or newer and only the standard library.

```bash
python3 skills/rlm/scripts/rlm_inventory.py . --manifest .rlm/audit/manifest.json
python3 skills/rlm/scripts/rlm_ledger.py .rlm/audit/worker-01.md --root . --tier mid
```

`rlm_inventory.py` skips dependency, cache, and build directories and symbolic links, prints a summary capped by `--max-output-bytes`, says whether coverage was complete, and writes the full chunk list to the manifest. `rlm_ledger.py` exits 1 when a worker result breaks the contract and lists each error with a code.

## Evals

`skills/rlm/evals/rlm_eval_cases.json` holds the benchmark cases: focused lookup without recursion, Print Contract log slicing, depth-1 partitioning, depth-2 escalation for a named dependency, a small-model budget halt, and cross-family verification. Run each prompt with and without the skill and grade the assertions. The `ledger_checks` in each case run in the unit tests.

## Development

Requirements: Python 3.11+, Bash, ShellCheck, and Claude Code for plugin validation.

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh
shellcheck install.sh
claude plugin validate . --strict
```

The tests use only the standard library. They stub the `claude` executable and run every harness sync against a temporary home directory, so they never touch a developer's configuration.

See [IMPLEMENTATION.md](IMPLEMENTATION.md) for the design and [EXAMPLES.md](EXAMPLES.md) for more invocations.

## Uninstall

```bash
claude plugin uninstall rlm@adibirzu-plugins --scope user
```

Or `bash install.sh --uninstall`. To remove a harness link, delete the `rlm` symlink in that harness's skill directory.

## License

[MIT](LICENSE)
