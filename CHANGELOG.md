# Changelog

All notable changes to this collection are documented here. Versions follow
[Semantic Versioning](https://semver.org/).

## 1.0.1 - 2026-11-19

### Fixed

- A failed task reports `changed` when `force` already removed conflicting
  paths or earlier packages were already stowed, and returns the `commands`
  that ran.
- `commands` includes the second simulation that `force` runs after removing
  conflicting paths.

## 1.0.0 - 2026-08-21

### Added

- Initial `soupglasses.stow.stow` module.
- Check-mode support and idempotent change reporting.
- Optional conflict replacement and directory-folding control.
