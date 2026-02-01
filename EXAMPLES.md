# RLM v2.0 Skill Examples

Detailed examples of using the `/rlm` skill with Opus 4.5 enhancements.

## Example 1: Full Project Review with Deployment Fix

**Task**: Review an entire project, find deployment issues, and generate a fix report

**Command**:
```
/rlm "Do a full review of the project, check why the GCP publish script is not working properly, and correct it. Create a report with rlm_gcpdeploy_report.md" ~/projects/transport-app
```

**What RLM Does**:
1. **Assessment**: Glob to count files, classify as "review + audit" task
2. **Peek**: Read Dockerfile, deploy scripts, nginx.conf, package.json
3. **Strategy**: Iterative Refinement (multi-pass) + Cross-Reference
4. **Pass 1 — Broad scan**:
   - Launch parallel Explore agents (haiku) to scan:
     - Docker build pipeline (Dockerfile, .dockerignore, .gcloudignore)
     - Deploy scripts (*.sh)
     - Backend configuration (requirements.txt, main_app.py)
     - Frontend configuration (vite.config, env files)
5. **Pass 2 — Deep dive**:
   - Launch domain-specific agents:
     - `backend-engineer` to review Python backend
     - `frontend-engineer` to review React frontend
     - `code-reviewer` to check deploy scripts
6. **Pass 3 — Verification**: Cross-reference findings across agents
7. **Output**: Write `rlm_gcpdeploy_report.md` with all findings and fixes

**Expected Output**:
```markdown
# RLM Analysis: GCP Deployment Pipeline Review

## Executive Summary
Found 10 critical bugs preventing successful deployment...

## Findings

### [CRITICAL] .dockerignore Excluded Production Backend Files
- **Location**: .dockerignore:93-101
- **Description**: Patterns like `backend/enhanced_*.py` excluded the main app
- **Impact**: Container runs in legacy mode
- **Confidence**: High

### [CRITICAL] nginx.conf Missing worker_processes
- **Location**: nginx.conf:1
- **Impact**: nginx refuses to start
- **Confidence**: High
...
```

## Example 2: Security Audit with Multi-Model Orchestration

**Task**: Comprehensive OWASP Top 10 security audit

**Command**:
```
/rlm "Audit for OWASP top 10 vulnerabilities, insecure configurations, and hardcoded secrets" ~/projects/web-api/src
```

**What RLM Does**:
1. **Assessment**: Classify as "security audit", select Iterative Refinement + Cross-Reference
2. **Scan Phase** (haiku agents):
   - Agent 1: Grep for SQL patterns (`SELECT`, `INSERT`, `cursor.execute`)
   - Agent 2: Grep for auth patterns (`authenticate`, `session`, `token`, `JWT`)
   - Agent 3: Grep for secret patterns (`API_KEY`, `password`, `secret`, `credential`)
   - Agent 4: Grep for input handling (`request.form`, `request.args`, `innerHTML`)
3. **Analysis Phase** (sonnet agents):
   - `security-compliance` agent: Analyze SQL injection vectors
   - `code-reviewer` agent: Review authentication flows
   - `Explore` agent: Trace data flow from input to output (XSS check)
4. **Verification Phase** (opus synthesis):
   - Cross-reference findings, remove false positives
   - Assess exploitability of each finding
5. **Output**: Structured security report with CVSS-style severity

## Example 3: Architecture Analysis with Dependency Tracing

**Task**: Understand codebase architecture and find coupling issues

**Command**:
```
/rlm "Analyze the architecture, map module dependencies, identify coupling issues and circular dependencies" ~/projects/monolith
```

**What RLM Does**:
1. **Strategy**: Cross-Reference Resolution + Partition+Map
2. **Phase 1**: Extract all exports/imports across codebase
   - haiku agents grep for `export`, `import`, `require`
3. **Phase 2**: Build dependency graph
   - sonnet agent processes symbol tables into graph
4. **Phase 3**: Analyze graph
   - Identify circular dependencies
   - Calculate coupling metrics per module
   - Find god modules (too many dependents)
5. **Output**: Architecture report with dependency diagram

**Expected Output**:
```markdown
# Architecture Analysis

## Module Dependency Map
- core/ (0 deps, 12 dependents) — Healthy hub
- services/ (3 deps, 8 dependents) — Good
- api/ (5 deps, 2 dependents) — Acceptable
- utils/ (1 dep, 15 dependents) — Review: possible god module

## Circular Dependencies Found
1. services/auth.ts → services/user.ts → services/auth.ts
   Recommendation: Extract shared logic to core/

## Coupling Metrics
- Average coupling: 3.2 (target: <5)
- Max coupling: utils/helpers.ts (15 dependents)
```

## Example 4: Large Log Analysis

**Task**: Analyze production logs to identify error patterns and root causes

**Command**:
```
/rlm "Find all unique error patterns, their frequency, root causes, and recommend fixes" /var/log/app/production-*.log
```

**What RLM Does**:
1. **Strategy**: Grepping + Partition+Map
2. **Scan** (haiku): Grep for ERROR, Exception, Failed, Traceback across all logs
3. **Partition**: Group by log file (time-based) or by error type
4. **Map** (sonnet agents): Each agent analyzes one time window/error category
5. **Synthesize**: Aggregate frequencies, identify trends, suggest fixes

**Expected Output**:
```markdown
# Error Analysis: Production Logs (15 files, 2.3M lines)

## Top 5 Error Patterns

### 1. Database Connection Timeout (2,847 occurrences)
- Pattern: `psycopg2.OperationalError: timeout expired`
- First seen: 2025-01-30 08:23:14
- Peak: 14:00-15:00 (1,204 errors)
- Root cause: Connection pool exhaustion during peak traffic
- Recommendation: Increase pool_size from 10 to 25

### 2. API Rate Limit Exceeded (1,632 occurrences)
- Pattern: `RateLimitError: 429 Too Many Requests`
- Endpoint: /api/v2/search
- Recommendation: Implement exponential backoff
...
```

## Example 5: Code Migration Assessment

**Task**: Assess effort to migrate from one framework to another

**Command**:
```
/rlm "Assess the migration effort from Express.js to Fastify, identify all breaking changes and affected files" ~/projects/api
```

**What RLM Does**:
1. **Strategy**: Cross-Reference + Partition+Map
2. **Inventory** (haiku): Count all Express-specific patterns
   - `app.get/post/put/delete` usages
   - `express.Router()` instances
   - Middleware patterns (`app.use`)
   - `req.body`, `req.params`, `req.query` access patterns
3. **Analysis** (sonnet): Per-module migration assessment
   - Which patterns have direct Fastify equivalents
   - Which require custom adapters
   - Which middleware needs replacement
4. **Synthesis** (opus): Migration plan with effort estimation

## Example 6: Test Coverage Gap Analysis

**Task**: Find untested code paths

**Command**:
```
/rlm "Identify all functions in src/ and check if they have corresponding tests in tests/. Report coverage gaps prioritized by risk." .
```

**What RLM Does**:
1. **Parallel Extraction** (haiku agents):
   - Agent 1: Grep for function/method definitions in src/
   - Agent 2: Grep for test function names in tests/
2. **Matching** (sonnet): Cross-reference source functions with test coverage
3. **Risk Assessment** (opus): Prioritize untested functions by:
   - Public API exposure
   - Security sensitivity (auth, payment, data handling)
   - Complexity (cyclomatic complexity heuristic)

## Example 7: Multi-File Comparison

**Task**: Compare implementation approaches across similar files

**Command**:
```
/rlm "Compare all PDF extractor implementations in backend/, identify strengths of each, and recommend consolidation" backend/
```

**What RLM Does**:
1. **Discovery** (haiku): Find all *extractor*.py files
2. **Parallel Analysis** (sonnet agents): Each reads and summarizes one extractor
3. **Comparison** (opus): Side-by-side feature comparison, identify overlap
4. **Recommendation**: Which to keep, which to merge, which to deprecate

## Best Practices (v2.0)

### 1. Be Specific in Task Description
**Good**: "Find SQL injection vulnerabilities in database query builders and ORM usage"
**Bad**: "Check the code"

### 2. Provide Context Paths
**Good**: `/rlm "analyze auth" ~/project/src/auth`
**Bad**: `/rlm "analyze auth"` (unclear where to look)

### 3. Specify Output Requirements
**Good**: "Create a report file with findings ranked by severity"
**Bad**: "Find problems" (no output structure)

### 4. Leverage Multi-Pass for Critical Tasks
**Good**: "Audit security with verification — confirm each finding against the actual code"
**Bad**: "Quick security scan" (for something critical)

### 5. Use RLM for Scale
**Good**: Processing 50+ files, 10k+ lines, cross-file analysis
**Not Needed**: Analyzing a single small file (use regular Read)

## Troubleshooting

**Issue**: RLM returns generic results
**Solution**: Be more specific in the task description. Add domain context.

**Issue**: Misses some files
**Solution**: Check if file patterns match. Specify file extensions or directories explicitly.

**Issue**: Too many false positives
**Solution**: Add "verify each finding against the actual code" to your task description. This triggers the verification pass in Iterative Refinement.

**Issue**: Results miss cross-file relationships
**Solution**: Explicitly request Cross-Reference Resolution: "trace dependencies across modules"
