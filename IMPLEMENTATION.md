# RLM v3.0 Implementation Guide

## Architecture Overview

```
/rlm invocation
    |
    v
Phase 0: Mode Detection
    ├── Parse task description for trigger keywords
    ├── Quick Scan: "find", "where is", "list", "show me", "how many"
    └── Deep Audit: "review", "audit", "analyze", "compare", "summarize"
    |
    v (Quick Scan)                    v (Deep Audit)
Quick Scan Pipeline                 Phase 1: Assessment
├── memory_recall                   ├── memory_recall (prior analysis?)
├── Grep (head_limit:50)            ├── CLAUDE.md check
├── Read top hits (limit:100)       ├── Git status (incremental check)
└── Inline answer                   ├── Glob (file count by type)
                                    ├── Background inventory (if >500 files)
                                    └── Strategy selection
                                    |
                                    v
                                  Phase 2: Exploration
                                    ├── Peek entry points (limit:50)
                                    ├── Grep count mode (sizing)
                                    ├── Create .rlm/<date>/ directory
                                    ├── Write scan_results.md
                                    └── memory_store (project structure)
                                    |
                                    v
                                  Phase 3: Decomposition
                                    ├── Calculate adaptive budgets
                                    ├── Parallel Task agents (FINAL protocol)
                                    │   ├── Max 500 files / 50K lines per agent
                                    │   └── Structured findings output
                                    └── Append to agent_findings.md
                                    |
                                    v
                                  Phase 4: Synthesis
                                    ├── Read agent_findings.md (if compacted)
                                    ├── Parse FINAL-format findings
                                    ├── Deduplicate by file:line
                                    ├── Cross-reference + rank severity
                                    └── Write synthesis.md
                                    |
                                    v
                                  Phase 5: Output
                                    ├── Write rlm_*_report.md
                                    ├── memory_store (summary + commit SHA)
                                    ├── Cleanup old checkpoints (>7 days)
                                    ├── Auto-add .rlm/ to .gitignore
                                    └── Present concise findings to user
```

## Dual Execution Modes (E1)

### Quick Scan Mode
- **Triggers**: "find", "where is", "list", "show me", "how many", "which files", "what is"
- **Token budget**: ~5-10K tokens total
- **Pipeline**: memory_recall -> Grep (head_limit:50) -> Read top hits (limit:100) -> inline answer
- **No**: checkpoints, report file, sub-agents (unless escalated), memory_store

### Deep Audit Mode
- **Triggers**: "review", "audit", "analyze", "compare", "summarize", "check", "security", "refactor", "assess", "examine", or complex multi-part requests
- **Token budget**: ~30-60K tokens total
- **Pipeline**: Full Phase 0-5 with checkpoints, memory, sub-agents, and report file

### Mode Escalation
Quick Scan can escalate to Deep Audit when:
- Grep count reveals >100 matches across >50 files
- Task complexity exceeds single-pass analysis
- User request contains multiple sub-tasks

## Directory Pruning (E2)

### Default Exclude List
Always excluded from Glob and Grep operations:
```
.git, node_modules, .venv, venv, __pycache__, .pytest_cache,
dist, build, .next, .nuxt, .cache, .parcel-cache,
coverage, .nyc_output, .tox, .eggs, *.egg-info,
vendor (if not primary code), bower_components, jspm_packages
```

### Implementation
- Grep: Use `glob` parameter to exclude (e.g., `glob: "!node_modules/**"`)
- Grep: Use `type` parameter to target source files (e.g., `type: "py"`, `type: "ts"`)
- Glob: Prefer specific patterns (`src/**/*.ts`) over broad patterns (`**/*.ts`)

## Binary File Filtering (E9)

### Skip List
Never Read or Grep these extensions:
```
Images:   .jpg, .jpeg, .png, .gif, .bmp, .ico, .svg, .webp, .tiff
Fonts:    .woff, .woff2, .ttf, .otf, .eot
Compiled: .pyc, .pyo, .class, .o, .so, .dylib, .dll, .exe, .wasm
Archives: .zip, .tar, .gz, .bz2, .xz, .rar, .7z, .jar, .war
Media:    .mp3, .mp4, .wav, .avi, .mov, .flv, .webm
Data:     .sqlite, .db, .bin, .dat, .pkl, .npy, .h5, .parquet
Maps:     .map (source maps)
Locks:    package-lock.json, yarn.lock, pnpm-lock.yaml, Pipfile.lock, poetry.lock
```

### Enforcement
- Use `type` parameter in Grep to auto-filter to source files
- Pre-check file extensions before Read operations
- Glob patterns should exclude binary extensions

## Git-Aware Incremental Analysis (E3)

### Workflow
```
1. memory_recall("RLM analysis of <project-path>")
   → Extract: last commit SHA, report path, findings count

2. git -C <path> log --oneline -1  → current HEAD SHA
   git -C <path> diff --name-only <last-sha>..HEAD → changed files

3. Decision:
   - No prior analysis → Full analysis
   - >50% files changed → Full analysis
   - <50% files changed → Incremental (changed files + importers)
   - 0 files changed → "No changes since last analysis"

4. After analysis:
   memory_store(
     content="RLM analysis of <path> at commit <SHA>. Report: <path>. Files: N. Findings: N",
     type="fact", importance=8, tags=["rlm", "<project>", "commit"]
   )
```

### Incremental Report Format
```markdown
## Changes Since Last Analysis (commit abc123..def456)
### New Issues (N)
...
### Resolved Issues (N)
...
### Unchanged Issues (N)
(see previous report at rlm_topic_report.md)
```

## CLAUDE.md Awareness (E5)

### Purpose
Skip redundant structure discovery when project documentation exists.

### Workflow
```
1. Glob: <project-path>/CLAUDE.md
2. If found: Read (limit: 200)
3. Extract: tech stack, key directories, build commands, conventions
4. Use to inform strategy selection — skip Peeking phase if sufficient
```

### Token Savings
- Without CLAUDE.md: Full Peek phase (~15K tokens)
- With CLAUDE.md: Read CLAUDE.md (~4K tokens) + skip structure discovery

## Token Budget System

### Budget Rules

| Action | Token Cost | When to Use |
|--------|-----------|-------------|
| `Glob` | ~10 tokens/file | Always safe, use freely |
| `Grep` count mode | ~10 tokens/file | Size the problem first |
| `Grep` files_with_matches | ~30 tokens/file | Find relevant files |
| `Grep` content, `head_limit: 50` | ~2K tokens | Targeted extraction |
| `Read` with `limit: 100` | ~4K tokens | Peeking |
| `Read` full file (500 lines) | ~20K tokens | Only critical files <300 lines |
| `Task` sub-agent | 0 tokens in parent | Bulk analysis (>200 lines) |

### Key Rules
- **>200 lines from a file** -> delegate to Task sub-agent
- **Always count before content**: Grep count mode first
- **Cap all Grep**: head_limit: 20 (discovery), 50 (extraction), 100 (max)
- **Read discipline**: Peek (limit:50-100), Section (limit:200 + offset), Full (only if <300 lines and critical)

### Budget Allocation (Deep Audit)
```
Assessment:     ~5K tokens  (Globs + Grep counts + CLAUDE.md)
Exploration:   ~15K tokens  (3-4 peeks + targeted greps)
Decomposition: ~10K tokens  (sub-agent summaries only)
Synthesis:      ~5K tokens  (internal reasoning)
Output:         ~5K tokens  (report to user)
Total:         ~40K tokens  (target ceiling)
```

### Token-Saving Patterns

**Pattern 1: Count before content**
```
# Bad: Unknown result set size
Grep(pattern="TODO", output_mode="content")

# Good: Count first, then bounded fetch
Grep(pattern="TODO", output_mode="count")        # → 847 matches
Grep(pattern="TODO", output_mode="content", head_limit=30)
```

**Pattern 2: Delegate bulk reads**
```
# Bad: 2000-line file in main context (80K tokens!)
Read("/path/to/large_file.py")

# Good: Sub-agent (0 tokens in parent)
Task(subagent_type="Explore", model="haiku",
     prompt="Read /path/to/large_file.py and list all function signatures")
# Returns ~500 token summary
```

**Pattern 3: Progressive narrowing**
```
# Bad: Read all files
for f in files: Read(f)

# Good: Narrow first
Grep(pattern="authenticate", output_mode="files_with_matches")  # → 5 files
# Now only read the 5 relevant files
```

## Adaptive Sub-Agent Budgets (E8)

### Scope Limits
```
Max per agent: 500 files OR 50K lines
Target per agent: 5-15 files OR 5-30K lines
```

### Auto-Split Logic
```
1. Estimate scope: number_of_files x avg_lines_per_file
2. If scope > 50K lines: split into ceil(scope / 30K) agents
3. If files > 500: split by directory
4. Each split gets its own Task agent with bounded scope
```

### Example
```
2,500 files total → prune to 2,000 → split into 8 agents (~250 files each)
Each agent processes its partition independently
Results merged in Phase 4
```

## Background Scanning (E7)

### Trigger
Phase 1 Glob count reveals >500 files.

### Implementation
```
1. Launch inventory agents with run_in_background: true
   Task(subagent_type="Explore", model="haiku", run_in_background=true,
        prompt="List all source files in <path>/src with line counts.")

2. Continue Phase 1 assessment in main conversation

3. Collect results with TaskOutput or Read(output_file) before Phase 3
```

### Benefit
Overlaps inventory with assessment, reducing wall-clock time by 20-30%.

## FINAL Output Protocol (E6)

### Required Format for All Sub-Agents
Every sub-agent prompt must include:

```
Return your findings in this EXACT format:

## FINDINGS: <count>

### [CRITICAL/HIGH/MEDIUM/LOW] <Title>
- **File**: <path>:<line>
- **Evidence**: <what you found>
- **Impact**: <why it matters>

(repeat for each finding)

## SUMMARY
<1-2 sentence summary>

Do NOT include reasoning, exploration steps, or intermediate thoughts.
Only report confirmed findings with evidence.
```

### Benefits
- Machine-parseable sub-agent results
- Clean deduplication across agents (match by file:line)
- No intermediate reasoning leaking into findings
- Consistent severity classification (CRITICAL/HIGH/MEDIUM/LOW)

## Timestamped Checkpoints (E4)

### Directory Structure
```
project/
├── .rlm/
│   ├── 2026-02-01/
│   │   ├── scan_results.md      ← Phase 2 output
│   │   ├── agent_findings.md    ← Phase 3 output (append per agent)
│   │   └── synthesis.md         ← Phase 4 output
│   └── 2026-01-25/              ← previous run (auto-cleanup if >7 days)
├── rlm_topic_report.md          ← Phase 5 final report
└── .gitignore                   ← should contain .rlm/
```

### Cleanup Rule
Before creating a new checkpoint:
```bash
find <project>/.rlm -maxdepth 1 -type d -mtime +7 -exec rm -rf {} +
```

### Recovery After Compaction
If conversation was compacted mid-analysis:
```
Read: <project>/.rlm/<date>/agent_findings.md
```
This recovers all sub-agent findings for synthesis.

### Auto-Gitignore
After creating `.rlm/`:
```bash
grep -q "^\.rlm/$" <project>/.gitignore 2>/dev/null || echo ".rlm/" >> <project>/.gitignore
```

## Memory Integration

### MCP Memory Tools
- `memory_store(content, type, importance, tags)` — persist findings
- `memory_recall(query, limit, max_tokens)` — retrieve past findings

### Memory Lifecycle

```
Session 1: /rlm "review project" ~/project
  Phase 1: memory_recall("RLM analysis of ~/project")  → empty
  Phase 2: memory_store("~/project is Flask+React, 120 files", type="fact", tags=["rlm","project"])
  Phase 5: memory_store("Report at rlm_review_report.md, commit abc123, 5 findings", type="fact", importance=9)

Session 2: /rlm "check what changed" ~/project
  Phase 0: memory_recall → gets Flask+React structure + commit abc123
  Phase 1: git diff abc123..HEAD → 5 files changed
  → Incremental mode: analyzes 5 files only
  Phase 5: memory_store with new commit SHA
```

### What to Store

| When | Content | Type | Importance |
|------|---------|------|------------|
| After Phase 1 | Project structure + tech stack | `fact` | 7 |
| After findings | Critical findings with locations | `fact` | 8 |
| After report | Executive summary + report path + commit SHA | `fact` | 9 |
| Architecture | Module/service relationships | `relationship` | 6 |

### Memory Tags
Always include: `["rlm", "<project-directory-name>"]` plus topic-specific tags.

## Sub-Agent Orchestration

### Agent Type Selection

| Analysis Type | Agent Type | Model |
|---------------|-----------|-------|
| File inventory | `Explore` | `haiku` |
| Code pattern search | `Explore` | `haiku` |
| Python code review | `python-engineer` | default |
| TypeScript review | `typescript-engineer` | default |
| Security audit | `security-compliance` | default |
| General code review | `code-reviewer` | default |
| Architecture analysis | `Explore` | `sonnet` |
| Cross-file tracing | `general-purpose` | default |

### Prompt Economy
Sub-agent prompts should be under 500 words:
```
You are analyzing [scope] for [task].

Files to examine:
- /path/to/file1.py (lines 1-200)
- /path/to/file2.py (focus on class AuthHandler)

Look for:
1. [Specific thing 1]
2. [Specific thing 2]

[FINAL protocol format here]

Do NOT read files outside the listed scope.
```

### Parallel Launch
Always launch independent agents in a single message:
```
Task(subagent_type="Explore", model="haiku", prompt="Inventory .py files in backend/")
Task(subagent_type="Explore", model="haiku", prompt="Inventory .tsx files in src/")
Task(subagent_type="code-reviewer", prompt="Review deploy scripts for issues")
```

## Strategy Implementation Details

### Peeking
```
1. Glob for entry points (package.json, main.py, Dockerfile)
2. Read first 50 lines of each (limit:50)
3. Examine directory tree
4. Decision: which deeper strategy applies?
Token cost: ~5K
```

### Grepping
```
1. Derive patterns from task description
2. Grep count mode → size the problem
3. If <100 matches: Grep content with head_limit:50
4. If >100 matches: partition by file, delegate to sub-agents
Token cost: ~2-5K
```

### Partition+Map
```
1. Identify partition boundaries (directory or file groups)
2. Calculate adaptive budget per partition
3. Launch all agents in parallel with FINAL protocol
4. Each agent: reads files, extracts findings, returns structured output
5. Collect, merge, deduplicate by file:line
Token cost: ~10K (summaries only)
```

### Summarization
```
Level 1: haiku agents summarize individual files
Level 2: sonnet agent summarizes groups
Level 3: opus synthesizes executive summary
Token cost: ~8K (progressive reduction)
```

### Iterative Refinement
```
Pass 1: Grep count + files_with_matches → hot spots (~3K)
Pass 2: Sub-agents deep-dive on hot spots → findings (~5K)
Pass 3: Targeted Read on flagged locations → verify (~5K)
Pass 4: Cross-validate against tests/docs → confidence (~3K)
Total: ~16K tokens
```

### Cross-Reference
```
Step 1: Grep for exports/definitions → symbol table
Step 2: Grep for imports/usages → reference table
Step 3: Sub-agent matches references to definitions
Step 4: Report orphans, cycles, violations
Token cost: ~10K
```

### Adaptive Context Selection
```
Step 1: Grep count per file → relevance score
Step 2: Sort files by score descending
Step 3: Read top N within token budget
Step 4: Skip zero-score and binary files
Token cost: ~2K (counting) + variable (reads)
```

## Error Recovery

| Error | Recovery |
|-------|----------|
| Sub-agent empty result | Retry with broader scope or escalate model (haiku → sonnet) |
| Too many files (>500) | Apply directory pruning + adaptive budgets |
| Context filling up | Delegate more to sub-agents, tighten head_limit |
| Compaction during analysis | Read `.rlm/<date>/` checkpoint files to recover |
| Conflicting findings | Launch verification sub-agent with targeted reads |
| Memory recall empty | First analysis — proceed with full pipeline |
| Quick Scan overwhelmed | Escalate to Deep Audit mode |

## Strategy Selection Matrix

| Task Type | Primary | Secondary |
|-----------|---------|-----------|
| "Find X" | Grepping | Peek |
| "Analyze X" | Partition+Map | Iterative Refinement |
| "Summarize X" | Summarization | Peek |
| "Audit X" | Iterative Refinement | Cross-Reference |
| "Compare X vs Y" | Partition+Map | Cross-Reference |
| "Debug X" | Grepping | Iterative Refinement |
| "Review X" | Iterative Refinement | Partition+Map |

## References

- Original Paper: [Recursive Language Models (Zhang et al., 2025)](https://arxiv.org/abs/2512.24601)
- Claude Code MCP Memory: `memory_store`, `memory_recall`, `memory_forget`
- Task tool agent types: Explore, general-purpose, code-reviewer, backend-engineer, frontend-engineer, python-engineer, typescript-engineer, security-compliance
