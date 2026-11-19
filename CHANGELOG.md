# Changelog

All notable changes to this collection are documented here. Versions follow
[Semantic Versioning](https://semver.org/).

## Unreleased

### Fixed

- A failed task reports `changed` when `force` already removed conflicting
  paths or earlier packages were already stowed, and returns the `commands`
  that ran.

## 1.0.0 - 2026-08-21

### Added

- Initial `soupglasses.stow.stow` module.
- Check-mode support and idempotent change reporting.
- Optional conflict replacement and directory-folding control.
