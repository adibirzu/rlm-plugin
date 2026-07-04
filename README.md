# RLM Plugin v3.1 — Recursive analysis for Claude Code and Codex

[![Version](https://img.shields.io/badge/version-3.1.1-blue.svg)](https://github.com/adibirzu/rlm-plugin/releases)
[![CI](https://github.com/adibirzu/rlm-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/adibirzu/rlm-plugin/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

RLM helps Claude Code and Codex analyze repositories and document sets that are too large to read in one pass. It uses bounded discovery, recursive partitioning, evidence validation, and compact synthesis rather than pasting an entire context into the prompt.

The approach is inspired by [“Recursive Language Models”](https://arxiv.org/abs/2512.24601) by Zhang, Kraska, and Khattab.

## Why v3.1.1

This release updates the plugin for the current Claude Code plugin model:

- `skills/` is now the canonical workflow surface.
- Installation uses supported `claude plugin` commands and the adibirzu marketplace.
- Optional memory and sub-agent capabilities have explicit sequential fallbacks.
- Repository instructions and retrieved content are treated as untrusted data.
- Checkpoints are never deleted automatically.
- Lockfiles and text-based assets remain available to security and supply-chain reviews.
- Tests and CI validate packaging, installer behavior, shell quality, and plugin schema.
- Native `.codex-plugin` metadata makes the same shared skill installable in Codex.

## Install

### Claude Code

Add the marketplace and install the plugin:

```bash
claude plugin marketplace add adibirzu/adibirzu-plugins
claude plugin install rlm@adibirzu-plugins --scope user
```

Or run the convenience wrapper:

```bash
git clone https://github.com/adibirzu/rlm-plugin.git
bash rlm-plugin/install.sh
```

Apply the plugin in an active Claude Code session with `/reload-plugins`.

### Codex

RLM can also be installed from a local Codex marketplace entry:

```bash
codex plugin add rlm@<personal-marketplace-name>
```

The repository includes `.codex-plugin/plugin.json`; the marketplace name depends on the user's personal Codex catalog.

## Claude Code usage

```text
/rlm:rlm <task> [path]
```

Focused lookup:

```text
/rlm:rlm "find the authentication middleware" src/
/rlm:rlm "list API entry points" .
```

Standard analysis:

```text
/rlm:rlm "review the current branch for correctness and missing tests" .
/rlm:rlm "map the data flow from request validation to persistence" backend/
```

Deep audit:

```text
/rlm:rlm "perform a repository-wide security and maintainability audit" .
/rlm:rlm "compare this branch with main and validate every behavioral change" .
```

RLM selects the smallest sufficient mode based on scope, risk, and evidence—not only the first verb in the request.

In Codex, invoke the installed `rlm` skill by name or ask Codex to use RLM for the review.

## How it works

```text
request
  -> establish scope, trust boundaries, and available capabilities
  -> choose focused, standard, or deep mode
  -> inventory and progressively narrow the relevant context
  -> partition independent surfaces when the scope is large
  -> validate candidates against controls, sinks, and counterevidence
  -> synthesize findings with file:line evidence and coverage limits
```

Optional memory can retain non-sensitive analysis metadata, but recalled information is always revalidated. Optional sub-agents can process independent partitions in parallel; the same worklist runs sequentially when they are unavailable.

See [IMPLEMENTATION.md](IMPLEMENTATION.md) for the design and [EXAMPLES.md](EXAMPLES.md) for more invocations.

## Development

Requirements: Python 3, Bash, ShellCheck, and Claude Code.

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh
shellcheck install.sh
claude plugin validate . --strict
```

The test suite uses only the Python standard library. It stubs the `claude` executable when checking installer behavior, so it does not alter a developer’s plugin configuration.

## Uninstall

```bash
claude plugin uninstall rlm@adibirzu-plugins --scope user
```

Or:

```bash
bash install.sh --uninstall
```

## License

[MIT](LICENSE)
