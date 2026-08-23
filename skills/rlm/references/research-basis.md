# Research basis and tuning guidance

Read this reference when planning a deep audit, tuning recursion, or making claims about RLM performance. It is not required for focused lookups.

## Primary sources

- Zhang, Kraska, and Khattab, [Recursive Language Models](https://arxiv.org/abs/2512.24601), and the [official implementation](https://github.com/alexzhang13/rlm). The core mechanism keeps the large prompt in an external environment, lets the model inspect it programmatically, and permits recursive calls over selected snippets.
- Wang, [Think, But Don't Overthink: Reproducing Recursive Language Models](https://arxiv.org/abs/2603.02615). Its reported experiments found depth-1 useful for complex reasoning, while depth-2 and recursion on simple retrieval could degrade quality and sharply increase execution time and token cost.
- Alizadeh et al., [Recursive Language Models Meet Uncertainty](https://arxiv.org/abs/2603.15653). This work studies uncertainty-aware self-reflection using consistency, reasoning length, and verbalized confidence signals.

These are research results, not universal provider guarantees. Revalidate version-sensitive claims before publishing them and measure the target harness and model rather than copying benchmark numbers into an operational claim.

## Operational interpretation

1. Use direct source lookup for sparse retrieval.
2. Use programmatic exploration without recursive sub-calls when local search and aggregation are sufficient.
3. Default to one recursive layer for dense cross-partition reasoning.
4. Permit deeper recursion only for a named unresolved dependency, within an explicit effort ceiling.
5. Treat the first decomposition as a hypothesis: pilot it before scaling.
6. Use independent evidence checks for uncertain, high-impact conclusions; do not multiply calls for already-supported facts.
7. Capture cost, latency, coverage, and answer quality separately. A longer trajectory is not evidence of a better result.
