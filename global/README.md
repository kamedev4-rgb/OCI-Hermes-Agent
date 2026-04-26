# Global Shared Specs

This directory is the shared, global layer for this Hermes environment.

Role:
- Holds architecture notes, policies, and specifications shared across users/profiles.
- Is not an always-injected prompt layer.
- Should be read when implementation or placement decisions need specification confirmation.

Interpretation used in this environment:
- `~/.hermes/` = global/shared
- `~/.hermes/profiles/<name>/` = personal/subset-specific

Recommended reading flow:
- Check `architecture/` for structural rules and directory intent.
- Check `policies/` for placement and scope rules.
- Check `specs/` for concrete feature/system specifications.
