# Domain Docs

How engineering skills should consume this control repo's domain documentation when exploring a feature or its nested source repositories.

## Before exploring, locate the feature context

Feature-specific domain documentation lives under `features/<feature>/`. Determine the active feature from the path named in the task and the checked-out control-repo branch, then read:

- **`features/<feature>/CONTEXT.md`** for the feature glossary and domain boundaries;
- **`features/<feature>/docs/adr/`** for accepted, rejected, and superseded decisions that affect the task.

If the task names a feature path, that explicit path defines the document scope. If the checked-out branch points at a different feature, report the mismatch instead of silently reading another feature's documents. Do not substitute root-level `docs/adr/` for the feature ADR directory.

Root-level `CONTEXT.md` and `docs/adr/` are optional and apply only to workspace-wide concepts or decisions. When changing code in `repos/*`, also follow that nested repository's own `AGENTS.md` and domain documentation when present; the control repo's feature context still defines the cross-repository feature contract.

If the relevant context or ADR directory does not exist, proceed without inventing one. The `domain-modeling` skill creates domain artifacts lazily when terminology or decisions are actually resolved.

## File structure

```text
/
|- CONTEXT.md                         # optional workspace-wide glossary
|- docs/adr/                          # optional workspace-wide decisions
|- features/
|  `- <feature>/
|     |- CONTEXT.md                   # feature glossary and boundaries
|     `- docs/adr/                    # feature decisions
`- repos/
   `- <source-repo>/                  # independent Git repository
```

Each feature directory is one domain-documentation context. Do not create `CONTEXT-MAP.md` merely to enumerate feature folders; the control repo's `features/` layout already provides that mapping.

## Use the glossary's vocabulary

When output names a domain concept in an issue title, design, refactor proposal, hypothesis, or test name, use the term from the active feature's `CONTEXT.md`. Do not drift to synonyms that its glossary explicitly avoids.

If the required concept is absent, first reconsider whether the term belongs to the feature. Record a genuine terminology gap through `domain-modeling` rather than silently defining competing language in an issue or design.

## Flag ADR conflicts

If output contradicts an applicable ADR, surface the conflict instead of silently overriding it. Follow explicit ADR status and replacement links; do not infer that a higher ADR number automatically supersedes an earlier decision. If two accepted ADRs conflict without a recorded replacement relationship, report the decision as unresolved before updating downstream spec, design, or issues.

> _Contradicts feature ADR-0007 (event-sourced orders); no superseding relationship is recorded._
