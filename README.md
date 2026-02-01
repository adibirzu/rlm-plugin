# RLM Plugin v2.1 — Recursive Language Models for Claude Code

Enhanced for **Claude Opus 4.5** with memory persistence, token-aware processing, and multi-agent orchestration.

Based on the paper "Recursive Language Models" by Zhang, Kraska, and Khattab (arXiv:2512.24601).

## What's New in v2.1

### Memory Persistence
- Stores findings in Claude's MCP memory system (`memory_store`/`memory_recall`)
- Previous analyses are recalled at the start of new invocations — no re-analyzing known structure
- Report file paths are stored so you can ask "what did the last RLM analysis find?" in a future session

### Token Budget Management
- Concrete token cost estimates per tool action (1 line ≈ 40 tokens)
- Grep discipline: always uses `head_limit` to cap result sizes
- Read discipline: `limit: 50-100` for peeking, sub-agent delegation for >200 lines
- Sub-agent economy: bulk reads happen in sub-agent context (0 parent tokens)

### Compaction Resilience
- Intermediate results written to `.rlm/` directory in project root
- Survives conversation compaction — can be read back to recover context
- Three checkpoint files: `scan_results.md`, `agent_findings.md`, `synthesis.md`

### Multi-Model Orchestration
- `haiku` for scanning/counting (fast, cheap)
- `sonnet` for code analysis (balanced)
- `opus` for synthesis and judgment (highest quality)

### 7 Strategies
| # | Strategy | Purpose |
|---|----------|---------|
| 1 | Peeking | Structure discovery |
| 2 | Grepping | Pattern-based filtering |
| 3 | Partition+Map | Parallel decomposition |
| 4 | Summarization | Hierarchical reduction |
| 5 | Iterative Refinement | Multi-pass analysis with verification |
| 6 | Cross-Reference | Dependency tracing and impact analysis |
| 7 | Adaptive Context Selection | Smart file prioritization |

## Installation

### Fresh Install

```bash
# Create plugin directory
mkdir -p ~/.claude/plugins/repos/rlm-plugin/.claude-plugin
mkdir -p ~/.claude/plugins/repos/rlm-plugin/commands

# Copy plugin files (from wherever you have them)
cp plugin.json ~/.claude/plugins/repos/rlm-plugin/.claude-plugin/
cp commands/rlm.md ~/.claude/plugins/repos/rlm-plugin/commands/
cp README.md IMPLEMENTATION.md EXAMPLES.md ~/.claude/plugins/repos/rlm-plugin/

# Enable the plugin in settings
# Add to ~/.claude/settings.json under "enabledPlugins":
#   "rlm@local-plugins": true
```

### Using the Install Script

```bash
# Run the install script (copies files + updates settings)
bash install.sh
```

### Verify Installation

```bash
# Check files exist
ls ~/.claude/plugins/repos/rlm-plugin/commands/rlm.md

# Check plugin is enabled
cat ~/.claude/settings.json | grep rlm

# Restart Claude Code to load the plugin
```

## Migration to Another Computer

### Option A: Using the Install Script (Recommended)

1. Copy the entire `rlm-plugin/` directory to the target machine
2. Run `bash install.sh` on the target machine
3. Restart Claude Code

### Option B: Manual Migration

1. **Copy the plugin source**:
```bash
# On source machine: create a tarball
tar czf rlm-plugin.tar.gz -C ~/.claude/plugins/repos rlm-plugin

# Transfer to target machine (scp, USB, cloud drive, etc.)
scp rlm-plugin.tar.gz user@target:~/
```

2. **Install on target**:
```bash
# On target machine
mkdir -p ~/.claude/plugins/repos
tar xzf ~/rlm-plugin.tar.gz -C ~/.claude/plugins/repos/
```

3. **Enable the plugin**:
```bash
# If ~/.claude/settings.json doesn't exist, create it:
echo '{"enabledPlugins":{"rlm@local-plugins":true}}' > ~/.claude/settings.json

# If it exists, add "rlm@local-plugins": true to enabledPlugins
# (or use the install.sh script which handles this)
```

4. **Restart Claude Code** — the plugin cache is auto-generated on startup

### Option C: Git-Based Migration

```bash
# On source machine: init git in plugin dir (if not already)
cd ~/.claude/plugins/repos/rlm-plugin
git init && git add -A && git commit -m "RLM plugin v2.1.0"
git remote add origin git@github.com:YOUR_USER/rlm-plugin.git
git push -u origin main

# On target machine:
mkdir -p ~/.claude/plugins/repos
cd ~/.claude/plugins/repos
git clone git@github.com:YOUR_USER/rlm-plugin.git
bash rlm-plugin/install.sh
```

### What Gets Migrated

| Component | Location | Auto-regenerated? |
|-----------|----------|-------------------|
| Plugin source | `~/.claude/plugins/repos/rlm-plugin/` | No — must copy |
| Plugin cache | `~/.claude/plugins/cache/local-plugins/rlm/` | Yes — on restart |
| Settings entry | `~/.claude/settings.json` | No — must configure |
| Memory data | MCP memory server | No — per-machine |

**Note**: Memory data (stored findings, report paths) is per-machine. The first `/rlm` run on a new machine will build fresh memory.

## Usage

```
/rlm <task description> <context path>
```

### Examples

```
/rlm "Full review of the project — check deployment, code quality, security" .
/rlm "Find all API endpoints and their auth requirements" src/
/rlm "Audit for OWASP top 10 vulnerabilities" backend/
/rlm "Summarize what this codebase does" ~/projects/unknown-repo
/rlm "Compare v1 and v2 implementations" src/api/
/rlm "Find all error patterns and recommend fixes" /var/log/app/
```

## How It Works

### 5-Phase Pipeline

1. **Assessment** — Recall memory, count files, classify task, select strategies
2. **Exploration** — Peek at structure, grep for anchors, write to `.rlm/scan_results.md`
3. **Decomposition** — Parallel sub-agents process chunks, results to `.rlm/agent_findings.md`
4. **Synthesis** — Deduplicate, cross-reference, rank, write to `.rlm/synthesis.md`
5. **Output** — Write `rlm_*_report.md`, store in memory, present summary

### Token Budget

The skill actively manages token consumption:
- Glob and Grep counts are near-free
- Content reads are capped with `head_limit` and `limit`
- Bulk processing delegated to sub-agents (0 tokens in parent)
- Target: keep main conversation under 100K tokens during RLM execution

## References

- Paper: [Recursive Language Models](https://arxiv.org/abs/2512.24601)
- Official Implementation: [github.com/alexzhang13/rlm](https://github.com/alexzhang13/rlm)

## License

Based on open research. Implementation follows Claude Code plugin conventions.
