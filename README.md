# RLM Plugin v3.0 — Recursive Language Models for Claude Code

Enhanced for **Claude Opus 4.5** with dual execution modes, git-aware incremental analysis, memory persistence, token-aware processing, and structured sub-agent output.

Based on "Recursive Language Models" by Zhang, Kraska, and Khattab (arXiv:2512.24601).

## What's New in v3.0

### Dual Execution Modes (E1)
- **Quick Scan**: For "find X", "where is", "list" queries. Single-pass Grep + targeted Read. ~5K tokens. No report file, no checkpoints.
- **Deep Audit**: For "review", "audit", "analyze" tasks. Full 5-phase pipeline with sub-agents, checkpoints, and report file. ~30-60K tokens.

### Smart Directory Pruning (E2)
Auto-excludes `.git`, `node_modules`, `.venv`, `dist`, `build`, `__pycache__`, and 10+ more noise directories. Prevents scanning thousands of dependency files.

### Git-Aware Incremental Mode (E3)
Stores last-analyzed commit SHA in memory. On re-analysis, runs `git diff` to find changed files. Only analyzes changed files + their importers. Produces differential reports (new/resolved/unchanged).

### Timestamped Checkpoints (E4)
Uses `.rlm/<YYYY-MM-DD>/` directories instead of flat `.rlm/`. Auto-cleans checkpoints older than 7 days. Auto-adds `.rlm/` to `.gitignore`.

### CLAUDE.md Awareness (E5)
Reads project-level `CLAUDE.md` files to understand tech stack and structure before analysis, skipping redundant structure discovery.

### FINAL Output Protocol (E6)
Sub-agents return findings in a standardized structured format. Enables clean deduplication, consistent severity classification, and no intermediate reasoning leakage.

### Background Scanning (E7)
For repos with >500 files, inventory agents run in background (`run_in_background: true`) while main assessment continues. Reduces wall-clock time.

### Adaptive Sub-Agent Budgets (E8)
Automatically splits work when a single agent would handle >500 files or >50K lines. Prevents sub-agent context overflow.

### Binary File Filtering (E9)
Skips 30+ binary extensions (.jpg, .pyc, .zip, .lock, etc.) from all Read and Grep operations. No more wasted tokens on unreadable files.

## Installation

### Fresh Install
```bash
bash install.sh
```

### Verify
```bash
ls ~/.claude/plugins/repos/rlm-plugin/commands/rlm.md
cat ~/.claude/settings.json | grep rlm
# Restart Claude Code
```

## Migration to Another Computer

### Option A: Tarball
```bash
# Source machine
tar czf ~/rlm-plugin.tar.gz -C ~/.claude/plugins/repos rlm-plugin

# Target machine
mkdir -p ~/.claude/plugins/repos
tar xzf ~/rlm-plugin.tar.gz -C ~/.claude/plugins/repos/
bash ~/.claude/plugins/repos/rlm-plugin/install.sh
```

### Option B: Git
```bash
# Source: push to GitHub
cd ~/.claude/plugins/repos/rlm-plugin
git remote add origin git@github.com:YOUR_USER/rlm-plugin.git
git push -u origin main

# Target: clone + install
cd ~/.claude/plugins/repos
git clone git@github.com:YOUR_USER/rlm-plugin.git
bash rlm-plugin/install.sh
```

### What Gets Migrated
| Component | Location | Auto-regenerated? |
|-----------|----------|-------------------|
| Plugin source | `~/.claude/plugins/repos/rlm-plugin/` | No — must copy |
| Plugin cache | `~/.claude/plugins/cache/local-plugins/rlm/` | Yes — on restart |
| Settings entry | `~/.claude/settings.json` | No — install.sh handles it |
| Memory data | MCP memory server | No — per-machine |

## Usage

```
/rlm <task description> <context path>
```

### Quick Scan Examples
```
/rlm "find all TODO comments" src/
/rlm "where is the auth middleware defined?" .
/rlm "list all API endpoints" backend/
/rlm "how many test files are there?" .
```

### Deep Audit Examples
```
/rlm "full review of the project — deployment, code quality, security" .
/rlm "audit for OWASP top 10 vulnerabilities" backend/
/rlm "analyze architecture and find coupling issues" src/
/rlm "compare v1 and v2 implementations" src/api/
/rlm "summarize what this codebase does" ~/projects/unknown-repo
```

## How It Works

### Quick Scan Pipeline (~5K tokens)
1. Memory recall → 2. Grep with head_limit → 3. Read top hits → 4. Inline answer

### Deep Audit Pipeline (~30-60K tokens)
1. **Assessment** — Memory recall, CLAUDE.md, git check, scope sizing
2. **Exploration** — Peek, grep counts, write `.rlm/<date>/scan_results.md`
3. **Decomposition** — Parallel sub-agents with FINAL protocol, adaptive budgets
4. **Synthesis** — Dedup, cross-reference, rank, write `.rlm/<date>/synthesis.md`
5. **Output** — Report file, memory store, checkpoint cleanup, gitignore check

### Strategy Selection
| Task Type | Primary | Secondary |
|-----------|---------|-----------|
| "Find X" | Grepping | Peek |
| "Analyze X" | Partition+Map | Iterative Refinement |
| "Summarize X" | Summarization | Peek |
| "Audit X" | Iterative Refinement | Cross-Reference |
| "Compare X vs Y" | Partition+Map | Cross-Reference |
| "Debug X" | Grepping | Iterative Refinement |
| "Review X" | Iterative Refinement | Partition+Map |

## Token Budget
| Action | Cost |
|--------|------|
| Glob | ~10 tokens/file |
| Grep count | ~10 tokens/file |
| Grep content (head_limit:50) | ~2K tokens |
| Read (limit:100) | ~4K tokens |
| Task sub-agent | 0 in parent |

## References
- Paper: [Recursive Language Models](https://arxiv.org/abs/2512.24601)
- Implementation: [github.com/alexzhang13/rlm](https://github.com/alexzhang13/rlm)

## License
Based on open research. Implementation follows Claude Code plugin conventions.
