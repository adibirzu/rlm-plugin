# Research basis and tuning guidance

Read this reference when planning a deep audit, tuning budgets, or making claims about RLM performance. It is not needed for focused lookups.

Sources were re-read on 2026-11-20. Numbers below are quoted from the papers. Everything under "Operating policy" is this project's interpretation and is labeled as such.

## Primary sources

- Zhang, Kraska, and Khattab, [Recursive Language Models](https://arxiv.org/abs/2512.24601) (v3, May 2026), and the [official implementation](https://github.com/alexzhang13/rlm).
- Wang, [Think, But Don't Overthink: Reproducing Recursive Language Models](https://arxiv.org/abs/2603.02615) (v1, March 2026).
- Alizadeh, Shojaee, Cho, and Farajtabar, [Recursive Language Models Meet Uncertainty](https://arxiv.org/abs/2603.15653) (v1, March 2026).
- The [Agent Skills specification](https://agentskills.io/specification) and its guides on [best practices](https://agentskills.io/skill-creation/best-practices), [scripts](https://agentskills.io/skill-creation/using-scripts), and [evaluation](https://agentskills.io/skill-creation/evaluating-skills).

These are research results and authoring guidance, not provider guarantees. Measure the target harness and model before turning a benchmark number into an operational claim.

## What the RLM paper establishes

- The prompt is stored as a variable in a REPL. The root model sees constant-size metadata about it (its length and a short prefix), not the text.
- The model may print from the REPL, and that output is truncated before it returns to the model. Only constant-size metadata about standard output is appended to the history.
- Sub-calls are functions inside the REPL: `llm_query` for a plain sub-model call and `rlm_query` for a recursive one. The system prompt asks the model to batch work into few calls.
- The run ends when the model sets a final variable, so a long answer can be built outside the window and returned whole.
- Experiments assume depth 1 unless stated.
- Reported gains at depth 1 over the base model (Table 1): GPT-5 on CodeQA 24.0 to 62.0, BrowseComp+ 0.0 to 91.3, OOLONG 44.0 to 56.0, OOLONG-Pairs 0.1 to 58.0. Qwen3-Coder-480B on the same four: 20.0 to 56.0, 0.0 to 44.7, 36.0 to 48.0, 0.1 to 23.1.
- Reported failure modes: a weaker coding model made many more syntax errors in the REPL. Without an explicit warning the model issued a sub-call for everything, reaching thousands of calls on basic tasks. The median run was cheaper than the base model, while the mean was higher because of outlier trajectories.
- The implementation offers a persistent session option, so variables survive across turns.

The **Print Contract** in `SKILL.md` is this project's name for the first two points applied to a coding harness: raw content lives in files or variables, and only bounded summaries are printed into the context. The paper does not use that term. The persistent scratchpad under `.rlm/<topic>/` plays the role of the persistent REPL in harnesses whose shell state does not survive between calls.

## What the reproduction establishes

Wang tested DeepSeek v3.2 and Kimi K2, with 20 samples per condition and one run each.

- OOLONG: DeepSeek 0.0% base, 42.1% at depth 1, 33.7% at depth 2. Kimi K2 86.6% base, 60.0% at depth 1, 55.0% at depth 2.
- Simple retrieval (S-NIAH): both base models scored 100%. DeepSeek fell to 85.0% at depth 1 and 70.0% at depth 2. Kimi fell to 90.0% at depth 1.
- Latency for DeepSeek on S-NIAH: 3.6 s base, 89.3 s at depth 1, 344.5 s at depth 2.
- Failure modes: answering from memory instead of the context, formatting collapse in the REPL, and endless re-verification.

Two conclusions follow. Recursion on a task the base model already solves makes the result worse and slower. Whether depth 1 helps depends on the model, and depth 2 was worse than depth 1 in every condition tested. The paper does not publish per-model budgets.

## What the uncertainty paper establishes

Alizadeh et al. sample eight candidate programs, keep the plurality answer, and rank the consistent candidates by verbalized confidence and reasoning length.

- Against their own RLM replication (CodeQA / BrowseComp+ / OOLONG): Qwen3-Coder-480B 59.8 / 37.1 / 45.7 becomes 64.9 / 59.7 / 51.8. GPT-5 59.5 / 86.0 / 53.0 becomes 68.9 / 92.4 / 65.5.
- With GPT-5, adding recursion hurt. With Qwen3-Coder it helped.
- High confidence or a short trace alone did not reliably indicate a correct answer. The combined signal did better than any single one.

The paper studies reflection inside one model and does not study a second model as verifier. The paper's scoring formula and its selection rule disagree on sign, so this skill copies no formula.

## What the Agent Skills guidance establishes

- `name` (lowercase, hyphens, equal to the directory) and `description` (at most 1024 characters, saying what the skill does and when to use it) are the only required frontmatter.
- Three loading tiers: metadata always, the `SKILL.md` body on activation (under 500 lines and 5,000 tokens), and `scripts/`, `references/`, `assets/` on demand. References stay one level deep and the body says when to load each.
- Scripts are non-interactive, document themselves with `--help`, print data to standard output and diagnostics to standard error, prefer structured output, are idempotent, use documented exit codes, and bound their output because harnesses truncate long results.
- Evals carry a prompt, an expected output, and checkable assertions, and are run with and without the skill.

## Operating policy

This section is inference from the evidence above, not a published result.

1. Use direct lookup for sparse retrieval. Recursion there costs accuracy and time.
2. Prefer programmatic exploration at depth 0 when search and aggregation are enough.
3. Default to one recursive layer for dense cross-partition reasoning.
4. Budget by model tier. The same recursion lifted one model and sank another, and weaker models fail in the REPL more often, so smaller models get a lower ceiling, fewer partitions, and script-built decomposition. The numbers live in `scripts/rlm_ledger.py` and are mirrored in `SKILL.md`.
5. Allow depth 2 only for a named unresolved dependency inside the budget. No tested condition showed depth 2 beating depth 1.
6. Cap re-verification at one round. Endless re-verification is a documented failure mode.
7. Treat the first decomposition as a hypothesis and pilot it.
8. Verify selectively. Agreement between independent attempts is evidence, a confidence score is not. For high-impact, conflicting, or low-confidence claims, extend that independence to a reviewer from a different model family. This extension is policy, chosen because a different family is less likely to share the first model's blind spots.
9. Record cost, latency, coverage, and answer quality separately. A longer trajectory is not evidence of a better result.

Revisit the tier numbers with `evals/rlm_eval_cases.json` when the models in use change.
