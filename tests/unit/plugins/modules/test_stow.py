# Copyright: (c) 2026, Sofie Finnes
# SPDX-License-Identifier: GPL-3.0-or-later

import os

from ansible_collections.soupglasses.stow.plugins.modules import stow


def test_build_command_for_present_package():
    params = {
        "state": "present",
        "src": "/tmp/source with spaces",
        "dest": "/tmp/target",
        "folding": True,
    }

    assert stow.build_command("/usr/bin/stow", params, "shell", True) == [
        "/usr/bin/stow",
        "--stow",
        "shell",
        "--dir",
        "/tmp/source with spaces",
        "--target",
        "/tmp/target",
        "--verbose",
        "--simulate",
    ]


def test_build_command_for_unfolded_absent_package():
    params = {
        "state": "absent",
        "src": "/tmp/source",
        "dest": "/tmp/target",
        "folding": False,
    }

    command = stow.build_command("stow", params, "git", False)

    assert command[1] == "--delete"
    assert command[-1] == "--no-folding"
    assert "--simulate" not in command


def test_parse_conflicts_recognizes_supported_stow_messages(tmp_path):
    stderr = "\n".join(
        (
            "WARNING! stowing shell would cause conflicts:",
            "  * cannot stow shell/.zshrc over existing target .zshrc since neither a link nor a directory and --adopt not specified",
            "  * existing target is neither a link nor a directory: .config/git/config",
            "  * existing target is not owned by stow: .vimrc",
            "  * existing target is stowed to a different package: .profile => old/.profile",
        )
    )

    paths, blockers = stow.parse_conflicts(stderr, str(tmp_path))

    assert paths == [
        os.path.join(str(tmp_path), ".zshrc"),
        os.path.join(str(tmp_path), ".config/git/config"),
        os.path.join(str(tmp_path), ".vimrc"),
        os.path.join(str(tmp_path), ".profile"),
    ]
    assert blockers == []


def test_parse_conflicts_rejects_directories_and_paths_outside_target(tmp_path):
    stderr = "\n".join(
        (
            "existing target is a directory: .config",
            "existing target is neither a link nor a directory: ../../outside",
        )
    )

    paths, blockers = stow.parse_conflicts(stderr, str(tmp_path))

    assert paths == []
    assert len(blockers) == 2
    assert blockers[0] == "existing target is a directory: .config"
    assert blockers[1].startswith("refusing to remove path outside target:")


def test_parse_conflicts_deduplicates_paths(tmp_path):
    message = "existing target is neither a link nor a directory: .zshrc"

    paths, blockers = stow.parse_conflicts("\n".join((message, message)), str(tmp_path))

    assert paths == [os.path.join(str(tmp_path), ".zshrc")]
    assert blockers == []


def test_purge_removes_files_and_symlinks(tmp_path):
    regular_file = tmp_path / "regular"
    regular_file.write_text("content", encoding="utf-8")
    symlink = tmp_path / "link"
    symlink.symlink_to(regular_file)

    assert stow.purge([str(regular_file), str(symlink)]) is None
    assert not regular_file.exists()
    assert not symlink.is_symlink()


def test_purge_reports_directories_instead_of_removing_them(tmp_path):
    directory = tmp_path / "directory"
    directory.mkdir()

    error = stow.purge([str(directory)])

    assert error.startswith('unable to remove conflicting path "')
    assert directory.is_dir()


def test_links_changed_handles_stow_idempotence():
    assert not stow.links_changed("")
    assert stow.links_changed("LINK: .zshrc => ../dotfiles/shell/.zshrc")
    assert stow.links_changed("UNLINK: .zshrc")
    assert not stow.links_changed(
        "UNLINK: .zshrc\nLINK: .zshrc => ../dotfiles/shell/.zshrc"
    )
    assert stow.links_changed(
        "UNLINK: .old\nUNLINK: .zshrc\nLINK: .zshrc => ../dotfiles/shell/.zshrc"
    )
