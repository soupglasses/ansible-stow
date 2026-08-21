# Ansible collection: `soupglasses.stow`

Manage GNU Stow packages with Ansible. The collection provides the
`soupglasses.stow.stow` module with check-mode support, conflict handling,
directory folding control, and idempotent change reporting.

## Requirements

- `ansible-core >= 2.19`
- [GNU Stow](https://www.gnu.org/software/stow/) on the managed host

## Installation

Install the released collection from Ansible Galaxy:

```bash
ansible-galaxy collection install soupglasses.stow
```

Or add it to a `requirements.yml` file:

```yaml
---
collections:
  - name: soupglasses.stow
    version: ">=1.0.0"
```

## Usage

```yaml
---
- name: Install dotfiles
  hosts: all
  tasks:
    - name: Stow shell configuration
      soupglasses.stow.stow:
        src: "{{ ansible_env.HOME }}/dotfiles"
        dest: "{{ ansible_env.HOME }}"
        package:
          - shell
          - git
        folding: false
```

`state` accepts `present`, `absent`, or `latest`. The `latest` state restows a
package, pruning links whose files were removed from its source. Set `force:
true` to replace conflicting files or symlinks. Directories are never removed
by `force`.

Use `ansible-doc soupglasses.stow.stow` after installation for the complete
module documentation.

## Development

Ansible requires collection checkouts to live below an
`ansible_collections/<namespace>/<collection>` path when running
`ansible-test`. This repository's CI checks out into that layout.

From a correctly placed checkout, run:

```bash
ansible-test sanity
ansible-test units
ansible-test integration stow
ansible-galaxy collection build
```

The integration tests require GNU Stow.

See [PUBLISHING.md](PUBLISHING.md) for release and Galaxy configuration.

## License

GPL-3.0-or-later. The module was adapted from
[`caian-org/ansible-stow`](https://github.com/caian-org/ansible-stow), whose
code was released under CC0.
