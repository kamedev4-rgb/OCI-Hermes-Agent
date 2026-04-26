# Global vs Personal

## Purpose

This document defines how files, automations, scripts, and state are classified in this Hermes environment.

## Core Mapping

- Global = `~/.hermes/`
- Personal = `~/.hermes/profiles/<name>/`

This is the authoritative interpretation for design decisions in this environment.

## Global

Use the global layer for anything that is shared across users, profiles, or responsibilities.

Examples:
- Shared architecture documents
- Cross-profile automation scripts
- Shared state for a single external account used by multiple profiles
- Global policies and directory-layout rules
- Monitoring that should not be "owned" by one profile

Recommended locations:
- `~/.hermes/global/architecture/`
- `~/.hermes/global/policies/`
- `~/.hermes/global/specs/`
- `~/.hermes/global/scripts/`
- `~/.hermes/global/state/`
- `~/.hermes/global/config/`

## Personal

Use the personal layer for anything that belongs to one profile or only a subset of users.

Examples:
- Profile-specific SOUL and behavior files
- User- or profile-specific memory/state
- Profile-specific scripts, plugins, and services
- Credentials or automations intended for one profile only

Recommended locations:
- `~/.hermes/profiles/<name>/scripts/`
- `~/.hermes/profiles/<name>/state/`
- `~/.hermes/profiles/<name>/plugins/`
- `~/.hermes/profiles/<name>/memories/`

## Decision Rule

When deciding placement, ask:

1. Is this shared across profiles or users?
2. Would placing this under one profile incorrectly suggest ownership by that profile?
3. Is the external system being monitored or controlled actually single-account and shared?

If the answer is yes, prefer global.

If it is clearly profile-owned or subset-specific, prefer personal.

## Prompt Behavior

The global layer is not an always-injected prompt source by default.

Its intended role is:
- specification storage
- architecture reference
- policy lookup when needed

This avoids unnecessary context growth while preserving clear design documentation.
