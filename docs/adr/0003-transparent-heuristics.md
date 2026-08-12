# ADR 0003: Transparent heuristic ranking

- Status: accepted
- Date: 2026-08-12

## Context

There is no representative labeled incident corpus for this demonstration, and
operators need to understand why a cause is ranked.

## Decision

Use deterministic candidates with documented score contributions and evidence
IDs. Treat missing CPU saturation as weak counter-evidence, not proof. Cap each
rule so repeated events cannot dominate without bound.

## Alternatives considered

- Supervised ML: rejected because training labels and evaluation data are absent.
- LLM-generated RCA: rejected because reproducibility and factual grounding would
  depend on an external model and prompt.
- A single threshold tree: simpler, but unable to rank concurrent hypotheses.

## Consequences

Results are reproducible, testable, and interview-explainable. Rules require
maintenance and cannot discover unknown failure modes. Scores are relative
evidence weights, not calibrated probabilities.

