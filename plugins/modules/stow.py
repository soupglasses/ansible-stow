#!/usr/bin/python

# Copyright: (c) 2026, Sofie Finnes
# GNU General Public License v3.0+ (see COPYING or
# https://www.gnu.org/licenses/gpl-3.0.txt)
#
# Originally adapted from github.com/caian-org/ansible-stow (CC0 / public
# domain). Differences from that implementation include:
#
#   - No stow version allowlist. Upstream hard-fails on any version not
#     literally enumerated in its table, overly cautious.
#   - Commands are built as argv lists rather than shell strings, so paths
#     containing spaces (~/Library/Application Support/...) work.
#   - `folding` is surfaced per package, `state` is the conventional
#     present/absent/latest, and conflict purging moved to `force`.
#   - check_mode is honoured.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: stow
version_added: "1.0.0"
short_description: Manage dotfiles with GNU Stow
description:
  - Symlinks a GNU Stow package from a source directory into a target
    directory, using stow's own conflict detection and tree (un)folding.
options:
  src:
    description: Directory holding the stow packages.
    type: path
    required: true
    aliases: [dir]
  dest:
    description: Directory the package is symlinked into.
    type: path
    required: true
    aliases: [target]
  package:
    description: Names of the packages under I(src) to act on.
    type: list
    elements: str
    required: true
    aliases: [pkg]
  state:
    description:
      - C(present) stows, C(absent) unstows, C(latest) restows (unstow then
        stow, which prunes links that no longer exist in the package).
    type: str
    default: present
    choices: [present, absent, latest]
  folding:
    description:
      - When true (stow's default), a directory that exists only in the
        package is symlinked wholesale into the target - one link for the
        whole subtree.
      - When false, directories are created for real and only leaf files are
        symlinked. Use this whenever something other than this repository
        also writes into the target directory, so those foreign writes cannot
        land inside the repository.
    type: bool
    default: true
  force:
    description:
      - Delete pre-existing files or symlinks that conflict with the package.
        Only applies to file conflicts; a directory in the way is always a
        hard failure.
    type: bool
    default: false
author:
  - Caian R. Ertl (@caian)
  - Sofie Finnes (@soupglasses)
requirements:
  - GNU Stow
"""

EXAMPLES = r"""
- name: Stow neovim, letting stow fold the whole tree
  soupglasses.stow.stow:
    src: "{{ role_path }}/files"
    dest: "{{ ansible_env.HOME }}"
    package: [neovim]

- name: Stow git without folding, as other tools write into ~/.config/git
  soupglasses.stow.stow:
    src: "{{ role_path }}/files"
    dest: "{{ ansible_env.HOME }}"
    package: [git]
    folding: false
"""

RETURN = r"""
commands:
  description: The stow invocations that were run.
  returned: always
  type: list
  elements: str
  sample:
    - /usr/bin/stow --stow git --dir /home/user/dotfiles --target /home/user --verbose --simulate
"""

import os
import re

from ansible.module_utils.basic import AnsibleModule


# Recoverable, per-file conflicts. stow's wording has changed across releases,
# so every known phrasing is tried and the first that matches wins. Adding a
# pattern here is enough to support a new release.
CONFLICT_PATTERNS = [
    # stow >= 2.4.0
    r"cannot stow .+ over existing target (?P<path>.+?) since neither a link"
    r" nor a directory and --adopt not specified",
    # stow 2.3.x
    r"existing target is neither a link nor a directory: (?P<path>.+)",
    # target is a symlink pointing somewhere stow does not manage
    r"existing target is not owned by stow: (?P<path>.+)",
    # target belongs to another package
    r"existing target is stowed to a different package: (?P<path>.+?) =>",
]

# A directory sitting where the package wants to place one cannot be resolved
# safely (removing it could destroy user data), so it is never auto-purged.
UNRECOVERABLE_PATTERN = r"existing target is a directory"

LINK_RE = re.compile(r"^LINK: (?P<path>.+?) =>")
UNLINK_RE = re.compile(r"^UNLINK: (?P<path>.+)$")

STATE_FLAGS = {
    "present": "--stow",
    "absent": "--delete",
    "latest": "--restow",
}


def build_command(stow_bin, params, package, simulate):
    """Assemble a stow invocation as an argv list."""
    cmd = [
        stow_bin,
        STATE_FLAGS[params["state"]],
        package,
        "--dir",
        params["src"],
        "--target",
        params["dest"],
        "--verbose",
    ]

    if not params["folding"]:
        cmd.append("--no-folding")

    if simulate:
        cmd.append("--simulate")

    return cmd


def parse_conflicts(stderr, target):
    """Split stow's refusal into (recoverable_paths, unrecoverable_reasons)."""
    paths = []
    blockers = []

    for line in stderr.splitlines():
        line = line.strip().lstrip("*").strip()

        if re.search(UNRECOVERABLE_PATTERN, line):
            blockers.append(line)
            continue

        for pattern in CONFLICT_PATTERNS:
            match = re.search(pattern, line)
            if match:
                path = os.path.abspath(
                    os.path.join(target, match.group("path").strip())
                )
                target_path = os.path.abspath(target)
                try:
                    contained = os.path.commonpath((target_path, path)) == target_path
                except ValueError:
                    contained = False

                if not contained:
                    blockers.append(
                        'refusing to remove path outside target: "%s"' % path
                    )
                elif path not in paths:
                    paths.append(path)
                break

    return paths, blockers


def purge(paths):
    """Remove conflicting files/symlinks. Returns an error string or None."""
    for path in paths:
        try:
            if os.path.islink(path):
                os.unlink(path)
            else:
                os.remove(path)
        except OSError as err:
            return 'unable to remove conflicting path "%s": %s' % (path, err)

    return None


def links_changed(stderr):
    """Whether stow's output describes a net change to the filesystem.

    A restow of an already-correct package emits an UNLINK and a matching LINK
    for every file, which nets out to no change.
    """
    linked = set()
    unlinked = set()

    for line in stderr.splitlines():
        line = line.strip()

        match = LINK_RE.match(line)
        if match:
            linked.add(match.group("path"))
            continue

        match = UNLINK_RE.match(line)
        if match:
            unlinked.add(match.group("path"))

    return linked != unlinked


def run_package(module, stow_bin, package, commands):
    """Apply one package. Returns True when the filesystem changed."""
    params = module.params

    dry_cmd = build_command(stow_bin, params, package, simulate=True)
    commands.append(" ".join(dry_cmd))
    rc, _dry_stdout, dry_stderr = module.run_command(dry_cmd)

    if rc != 0:
        paths, blockers = parse_conflicts(dry_stderr, params["dest"])

        if blockers:
            module.fail_json(
                msg='cannot stow package "%s" into "%s": %s'
                % (package, params["dest"], "; ".join(blockers)),
                stderr=dry_stderr,
            )

        if not paths:
            module.fail_json(
                msg='stow refused to act on package "%s"' % package,
                rc=rc,
                stderr=dry_stderr,
            )

        if not params["force"]:
            module.fail_json(
                msg='conflicting paths for package "%s" (set force=true to '
                "replace them): %s" % (package, ", ".join(paths)),
                conflicts=paths,
                stderr=dry_stderr,
            )

        if module.check_mode:
            return True

        err = purge(paths)
        if err:
            module.fail_json(msg=err)

        commands.append(" ".join(dry_cmd))
        rc, _dry_stdout, dry_stderr = module.run_command(dry_cmd)
        if rc != 0:
            module.fail_json(
                msg='package "%s" still conflicts after removing conflicting '
                "paths" % package,
                rc=rc,
                stderr=dry_stderr,
                changed=True,
            )

        if module.check_mode:
            return True

        real_cmd = build_command(stow_bin, params, package, simulate=False)
        commands.append(" ".join(real_cmd))
        rc, _stdout, stderr = module.run_command(real_cmd)
        if rc != 0:
            module.fail_json(
                msg='stow failed for package "%s"' % package, rc=rc, stderr=stderr
            )

        return True

    # stow reports its actions on stderr under --verbose; with --simulate
    # nothing has been written yet, so this doubles as the change prediction.
    if not links_changed(dry_stderr):
        return False

    if module.check_mode:
        return True

    real_cmd = build_command(stow_bin, params, package, simulate=False)
    commands.append(" ".join(real_cmd))
    rc, _stdout, stderr = module.run_command(real_cmd)
    if rc != 0:
        module.fail_json(
            msg='stow failed for package "%s"' % package, rc=rc, stderr=stderr
        )

    return links_changed(stderr)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            src=dict(type="path", required=True, aliases=["dir"]),
            dest=dict(type="path", required=True, aliases=["target"]),
            package=dict(type="list", elements="str", required=True, aliases=["pkg"]),
            state=dict(
                type="str", default="present", choices=["present", "absent", "latest"]
            ),
            folding=dict(type="bool", default=True),
            force=dict(type="bool", default=False),
        ),
        supports_check_mode=True,
    )

    stow_bin = module.get_bin_path("stow", required=True)

    for key in ("src", "dest"):
        if not os.path.isdir(module.params[key]):
            module.fail_json(
                msg='%s "%s" does not exist or is not a directory'
                % (key, module.params[key])
            )

    changed = False
    commands = []

    for package in module.params["package"]:
        changed = run_package(module, stow_bin, package, commands) or changed

    module.exit_json(changed=changed, commands=commands)


if __name__ == "__main__":
    main()
