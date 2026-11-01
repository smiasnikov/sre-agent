# Repository working agreements

## Scope and communication

- Keep changes small and explain the design decision before expanding the implementation.
- Separate requirements, recommendations, implemented behavior, and future work.
- Follow `docs/scope.md`. Finish the current capabilities before adding frameworks or real integrations.

## Implementation

- Prefer the simplest design that supports current behavior. Add a layer, dependency, or framework only when it solves a concrete problem.
- Keep dependencies pointing inward. Domain logic must not depend on the CLI, filesystem, fixtures, or provider implementations. Connect these components at application startup.
- Keep application code in `agent/`, scenario checks in `evals/`, and tests in `tests/`.
- Keep the engine independent of fixture loading, provider setup, and filesystem paths.
- Store runtime agent guidance in `harness/*.md`; do not embed model instructions in Python.
- Use shared enums or constants for finite statuses, decision types, tool names, and error codes.
- Keep JSON field names readable. Use typed schemas internally and runtime validation at external boundaries.
- Preserve the distinction between evidence, hypotheses, catalogue metadata, and reviewed knowledge.
- Enforce tenant scope and permissions in code; prompt guidance is not an authorization boundary.
- Keep external tools mocked unless the user requests a real integration. Never execute an unapproved action.
- Keep restart recovery local and explicit. Do not claim exactly-once execution or production durability.

## Verification and review

- Run `python3 -m unittest -v` and `python3 -m evals` after relevant code changes.
- Use focused tests for meaningful failure modes; do not increase test counts without useful coverage.
- Run a static type check when changing schemas or component interfaces, if the tool is available.
- For restart changes, test a fresh agent and storage reload, fresh per-run limits, and completed-call handling.
- Label synthetic fixtures, recorded real interactions, model benchmarks, and semantic judgment separately.
- Keep the README short and link to detailed design and testing notes.
- Report what was actually run and any material limits. Saved files do not prove future instruction loading.
- For instruction-file changes, show a `File | Why` table with verified absolute file links, followed by the complete unified diff for each changed file. Report `Files` and `Rendering` checks separately; distinguish saved content from verified behavior.
