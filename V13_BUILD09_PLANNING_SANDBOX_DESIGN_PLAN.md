# v1.3 Build 09 - Planning Sandbox Design Only

## Summary

Document the future Planning Sandbox and Timeline Template system. Do not implement it in initial v1.3.

This build is intentionally design-only because templates, overlaps, dependencies, and auto-deadline calculation are a separate system.

## Design Topics

- Timeline templates:
  - Simple OEM Knife
  - Standard Folding Knife
  - New Mechanism Knife
  - Gift Set / Combo Pack
  - Packaging-heavy Retail Product
  - Amazon Launch Product
- Module model:
  - name
  - default duration
  - owner
  - can overlap
  - dependencies
  - deliverable
  - exit criteria
- Sandbox behavior:
  - apply template
  - edit durations
  - set dependencies
  - allow overlapping phases
  - calculate estimated launch
  - save current timeline as template
- Migration questions:
  - whether templates are database records or static config first
  - whether dependencies require a join table
  - whether phase modules are copied into project phases

## Deliverable

- A future implementation plan file, not code.
- Architecture Review for likely schema if the user approves implementation later.
- Clear deferral list and risk notes.

## Explicit Non-Scope

- No schema migration.
- No template UI.
- No drag/drop UI.
- No dependency engine.
- No route changes.

## Tests

- Documentation-only build can be verified by static checks:
  - plan file exists
  - no app code changed
  - `python3 test_build_v121.py` baseline still passes if requested

## Acceptance Criteria

- The team has a reviewable future design for timeline templates without risking the v1.3 command-center implementation.
