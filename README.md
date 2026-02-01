# RLM Plugin v3.0 — Recursive Language Models for Claude Code

[![Version](https://img.shields.io/badge/version-3.0.0-blue.svg)](https://github.com/adibirzu/rlm-plugin/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude_Code-Plugin-purple.svg)](https://claude.ai/code)

Enhanced for **Claude Opus 4.5** with dual execution modes, git-aware incremental analysis, memory persistence, token-aware processing, and structured sub-agent output.

Based on ["Recursive Language Models"](https://arxiv.org/abs/2512.24601) by Zhang, Kraska, and Khattab (2025).

## Architecture

```
                        /rlm <task> <path>
                              |
                        Phase 0: Mode Detection
                        ┌─────┴──────┐
                        │            │
                  Quick Scan    Deep Audit
                   (~5K tok)   (~30-60K tok)
                        │            │
                  ┌─────┘     ┌──────┴──────────┐
                  │           │                  │
            memory_recall   Phase 1            Phase 1
                  │         Assessment         Assessment
            Grep+Read      ┌────┴────┐       ┌────┴────┐
            (bounded)      │  memory  │      │ CLAUDE.md │
                  │        │  recall  │      │  git diff │
            Inline        │  glob    │      │  bg scan  │
            Answer        └────┬────┘      └────┬────┘
                               │                  │
                         Phase 2: Explore    Phase 2: Explore
                         Peek + Grep count   Peek + Grep count
                         .rlm/<date>/        .rlm/<date>/
                               │                  │
                         Phase 3: Decompose ──────┘
                         Parallel sub-agents
                         FINAL protocol
                         Adaptive budgets
                               │
                         Phase 4: Synthesize
                         Dedup + rank + cross-ref
                               │
                         Phase 5: Output
                         Report + memory_store
                         Checkpoint cleanup
```

## What's New in v3.0

| # | Enhancement | Impact |
|---|-------------|--------|
| E1 | **Dual Execution Modes** — Quick Scan vs Deep Audit | 87% fewer tokens for simple queries |
| E2 | **Smart Directory Pruning** — auto-exclude noise dirs | 30-50% scan reduction |
| E3 | **Git-Aware Incremental** — diff-based re-analysis | 80-90% faster on repeats |
| E4 | **Timestamped Checkpoints** — `.rlm/<date>/` | Multi-session resilience |
| E5 | **CLAUDE.md Awareness** — skip structure discovery | ~10K tokens saved |
| E6 | **FINAL Output Protocol** — structured sub-agent output | Reliable dedup + ranking |
| E7 | **Background Scanning** — parallel inventory | 20-30% wall-clock reduction |
| E8 | **Adaptive Budgets** — auto-split large scopes | Prevents context overflow |
| E9 | **Binary Filtering** — skip 30+ binary extensions | Clean results |

## Quick Start

### Installation

```bash
# Clone
git clone https://github.com/adibirzu/rlm-plugin.git ~/.claude/plugins/repos/rlm-plugin

# Install (creates settings entry, clears cache)
bash ~/.claude/plugins/repos/rlm-plugin/install.sh

# Restart Claude Code
```

### Verify

```bash
ls ~/.claude/plugins/repos/rlm-plugin/commands/rlm.md
grep rlm ~/.claude/settings.json
```

### Usage

```
/rlm <task description> <context path>
```

**Quick Scan** (simple queries, ~5K tokens):
```
/rlm "find all TODO comments" src/
/rlm "where is the auth middleware defined?" .
/rlm "list all API endpoints" backend/
/rlm "how many test files are there?" .
```

**Deep Audit** (comprehensive analysis, ~30-60K tokens):
```
/rlm "full review of the project — deployment, code quality, security" .
/rlm "audit for OWASP top 10 vulnerabilities" backend/
/rlm "analyze architecture and find coupling issues" src/
/rlm "review what changed since the last analysis" .
```

## How It Works

### Quick Scan Pipeline
1. `memory_recall` — check for known project structure
2. `Grep` with `head_limit: 50` — find matches
3. `Read` with `limit: 100` — examine top hits
4. Return inline answer with `file:line` citations

### Deep Audit Pipeline
1. **Assessment** — Memory recall, CLAUDE.md, git check, scope sizing
2. **Exploration** — Peek, grep counts, write `.rlm/<date>/scan_results.md`
3. **Decomposition** — Parallel sub-agents with FINAL protocol, adaptive budgets
4. **Synthesis** — Dedup, cross-reference, rank, write `.rlm/<date>/synthesis.md`
5. **Output** — Report file, memory store, checkpoint cleanup, gitignore check

### Strategy Selection

| Task Type | Primary Strategy | Secondary |
|-----------|-----------------|-----------|
| "Find X" | Grepping | Peek |
| "Analyze X" | Partition+Map | Iterative Refinement |
| "Summarize X" | Summarization | Peek |
| "Audit X" | Iterative Refinement | Cross-Reference |
| "Compare X vs Y" | Partition+Map | Cross-Reference |
| "Debug X" | Grepping | Iterative Refinement |
| "Review X" | Iterative Refinement | Partition+Map |

### Multi-Model Dispatch

| Sub-task | Model | Agent Type |
|----------|-------|------------|
| File inventory | `haiku` | `Explore` |
| Code analysis | `sonnet` | `Explore` / domain-specific |
| Security review | default | `security-compliance` |
| Final synthesis | default (opus) | Main conversation |

## Token Budget

| Action | Cost |
|--------|------|
| Glob | ~10 tokens/file |
| Grep count | ~10 tokens/file |
| Grep content (head_limit:50) | ~2K tokens |
| Read (limit:100) | ~4K tokens |
| Task sub-agent | 0 in parent |

## Migration

### Option A: Git (Recommended)
```bash
# Target machine
git clone https://github.com/adibirzu/rlm-plugin.git ~/.claude/plugins/repos/rlm-plugin
bash ~/.claude/plugins/repos/rlm-plugin/install.sh
```

### Option B: Tarball
```bash
# Source machine
tar czf ~/rlm-plugin.tar.gz -C ~/.claude/plugins/repos rlm-plugin

# Target machine
mkdir -p ~/.claude/plugins/repos
tar xzf ~/rlm-plugin.tar.gz -C ~/.claude/plugins/repos/
bash ~/.claude/plugins/repos/rlm-plugin/install.sh
```

### What Gets Migrated

| Component | Location | Auto-regenerated? |
|-----------|----------|-------------------|
| Plugin source | `~/.claude/plugins/repos/rlm-plugin/` | No — must copy |
| Plugin cache | `~/.claude/plugins/cache/local-plugins/rlm/` | Yes — on restart |
| Settings entry | `~/.claude/settings.json` | No — install.sh handles it |
| Memory data | MCP memory server | No — per-machine |

## Uninstall

```bash
bash ~/.claude/plugins/repos/rlm-plugin/install.sh --uninstall
```

## File Structure

```
rlm-plugin/
├── .claude-plugin/
│   └── plugin.json          # Plugin metadata
├── commands/
│   └── rlm.md               # Core skill definition (460 lines)
├── CHANGELOG.md              # Version history
├── EXAMPLES.md               # Usage examples with expected behavior
├── IMPLEMENTATION.md         # Deep technical documentation
├── install.sh                # Portable installer/uninstaller
├── LICENSE                   # MIT License
└── README.md                 # This file
```

## References

- Paper: [Recursive Language Models](https://arxiv.org/abs/2512.24601) (Zhang, Kraska, Khattab 2025)
- Reference implementation: [github.com/alexzhang13/rlm](https://github.com/alexzhang13/rlm)

## License

[MIT](LICENSE)
