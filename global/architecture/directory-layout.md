# Directory Layout

## Purpose

This document defines the intended directory structure for the shared global layer in this Hermes environment.

## Global Root

```text
~/.hermes/
  global/
    README.md
    architecture/
    policies/
    specs/
    scripts/
    state/
    config/
```

## Directory Roles

### `architecture/`

High-level system design and structural concepts.

Examples:
- system boundaries
- ownership model
- profile isolation model
- root/global conventions

### `policies/`

Normative placement and operational rules.

Examples:
- global vs personal classification
- automation placement rules
- naming conventions
- state ownership rules

### `specs/`

Concrete specifications for shared systems and features.

Examples:
- codex quota monitor
- shared notification rules
- memory architecture notes
- future shared services

### `scripts/`

Executable shared automation code.

Examples:
- monitor scripts
- maintenance scripts
- reporting scripts

### `state/`

Runtime state for shared automations.

Examples:
- cached API observations
- alert threshold state
- deduplication state

### `config/`

Configuration files for shared automations.

Examples:
- monitor config
- shared routing config
- feature-specific thresholds

## Placement Rule

Use this layout when the asset is shared and should be understood as belonging to the root/global layer rather than any one profile.

If a file or automation is owned by a specific profile, place it under that profile instead of under `global/`.

## Current Shared Assets

The following shared assets already exist:
- `global/scripts/codex_quota_monitor.py`
- `global/state/codex_quota_state.json`
- `global/config/codex_quota_monitor.json`

These are considered shared because the monitored Codex account is currently treated as one shared account across profiles.
