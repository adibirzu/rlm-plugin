import json
import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "install.sh"

HARNESS_DIRS = (
    ".claude/skills",
    ".codex/skills",
    ".gemini/skills",
    ".gemini/config/skills",
    ".agents/skills",
    ".cursor/skills",
    ".config/opencode/skills",
    ".opencode/skills",
    ".pi/skills",
    ".grok/skills",
    ".cline/skills",
)


def snapshot(directory):
    entries = []
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory).as_posix()
        if path.is_symlink():
            entries.append((relative, "link", os.readlink(path)))
        elif path.is_dir():
            entries.append((relative, "dir", ""))
        else:
            entries.append((relative, "file", path.read_text()))
    return entries


class HarnessSyncTests(unittest.TestCase):
    shell = "bash"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name).resolve()
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.source = self.tmp / "checkout/skills/rlm"
        self.write_skill(self.source, "canonical v4\n")

    def write_skill(self, directory, body):
        (directory / "references").mkdir(parents=True)
        (directory / "SKILL.md").write_text(f"---\nname: rlm\n---\n{body}")
        (directory / "references/notes.md").write_text("notes\n")

    def skills(self, harness):
        directory = self.home / harness
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def run_installer(self, *args, source=None, home=None, env=None):
        command = [self.shell, str(INSTALLER), *args]
        command += ["--source", str(source or self.source)]
        command += ["--home", str(home or self.home)]
        return subprocess.run(
            command,
            cwd=self.tmp,
            env={**os.environ, "PATH": "/usr/bin:/bin", **(env or {})},
            capture_output=True,
            text=True,
        )

    def check(self):
        result = self.run_installer("--check", "--json")
        report = json.loads(result.stdout)
        states = {entry["dir"]: entry["state"] for entry in report["harnesses"]}
        return result, report, states

    def sync(self, *args, env=None):
        return self.run_installer("--sync-harnesses", *args, env=env)

    def assert_linked(self, harness):
        target = self.home / harness / "rlm"
        self.assertTrue(target.is_symlink(), f"{target} is not a symlink")
        self.assertEqual(target.resolve(), self.source.resolve())

    def backups(self):
        root = self.home / ".rlm-skill-backups"
        if not root.is_dir():
            return []
        return sorted(
            harness / "rlm"
            for stamp in root.iterdir()
            for harness in stamp.iterdir()
            if os.path.lexists(harness / "rlm")
        )

    def test_check_reports_every_harness_directory(self):
        self.skills(".claude/skills")
        os.symlink(self.source, self.home / ".claude/skills/rlm")
        self.write_skill(self.skills(".gemini/config/skills") / "rlm", "canonical v4\n")
        self.write_skill(self.skills(".grok/skills") / "rlm", "local edits\n")
        self.skills(".cursor/skills")
        (self.home / ".pi").mkdir()

        result, report, states = self.check()

        self.assertEqual(result.returncode, 3)
        self.assertEqual(tuple(e["dir"] for e in report["harnesses"]), HARNESS_DIRS)
        self.assertEqual(report["source"], str(self.source))
        self.assertEqual(report["home"], str(self.home))
        self.assertFalse(report["in_sync"])
        self.assertEqual(states[".claude/skills"], "linked")
        self.assertEqual(states[".gemini/skills"], "missing")
        self.assertEqual(states[".gemini/config/skills"], "copy-identical")
        self.assertEqual(states[".grok/skills"], "copy-diverged")
        self.assertEqual(states[".cursor/skills"], "missing")
        self.assertEqual(states[".pi/skills"], "missing")
        self.assertEqual(states[".cline/skills"], "harness-absent")
        self.assertEqual(report["summary"]["missing"], 3)
        self.assertEqual(report["summary"]["harness-absent"], 5)
        self.assertEqual(
            sum(report["summary"].values()), len(HARNESS_DIRS)
        )
        for entry in report["harnesses"]:
            self.assertEqual(entry["path"], str(self.home / entry["dir"] / "rlm"))

    def test_check_never_writes(self):
        self.write_skill(self.skills(".grok/skills") / "rlm", "local edits\n")
        self.skills(".cursor/skills")
        (self.home / ".pi").mkdir()
        before = snapshot(self.home)

        self.run_installer("--check")
        self.run_installer("--check", "--json")

        self.assertEqual(snapshot(self.home), before)

    def test_check_text_output_and_exit_codes(self):
        self.skills(".cursor/skills")

        drift = self.run_installer("--check")
        self.sync()
        clean = self.run_installer("--check")

        self.assertEqual(drift.returncode, 3)
        self.assertRegex(drift.stdout, r"missing\s+\.cursor/skills")
        self.assertEqual(clean.returncode, 0)
        self.assertRegex(clean.stdout, r"linked\s+\.cursor/skills")

    def test_sync_links_present_harnesses_and_skips_absent_ones(self):
        self.skills(".cursor/skills")
        (self.home / ".pi").mkdir()
        (self.home / ".config/opencode").mkdir(parents=True)

        result = self.sync()

        self.assertEqual(result.returncode, 0, result.stderr)
        for harness in (".cursor/skills", ".pi/skills", ".config/opencode/skills"):
            self.assert_linked(harness)
        self.assertFalse((self.home / ".cline").exists())
        self.assertFalse((self.home / ".claude").exists())
        self.assertEqual(self.backups(), [])

    def test_sync_replaces_an_identical_copy_and_keeps_it_as_a_backup(self):
        copy = self.skills(".gemini/config/skills") / "rlm"
        self.write_skill(copy, "canonical v4\n")

        result = self.sync()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_linked(".gemini/config/skills")
        backups = self.backups()
        self.assertEqual(len(backups), 1)
        self.assertIn("canonical v4", (backups[0] / "SKILL.md").read_text())

    def test_identical_copy_ignores_python_cache_noise(self):
        copy = self.skills(".claude/skills") / "rlm"
        self.write_skill(copy, "canonical v4\n")
        (copy / "scripts").mkdir()
        (self.source / "scripts/__pycache__").mkdir(parents=True)
        (self.source / "scripts/__pycache__/x.pyc").write_text("cache")

        _, _, states = self.check()

        self.assertEqual(states[".claude/skills"], "copy-identical")

    def test_sync_refuses_a_diverged_copy_without_backup(self):
        diverged = self.skills(".grok/skills") / "rlm"
        self.write_skill(diverged, "local edits\n")
        self.skills(".cursor/skills")

        result = self.sync()

        self.assertEqual(result.returncode, 1)
        self.assertIn("--backup", result.stderr)
        self.assertFalse(diverged.is_symlink())
        self.assertIn("local edits", (diverged / "SKILL.md").read_text())
        self.assert_linked(".cursor/skills")
        self.assertEqual(self.backups(), [])

    def test_sync_with_backup_moves_a_diverged_copy_aside(self):
        diverged = self.skills(".grok/skills") / "rlm"
        self.write_skill(diverged, "local edits\n")

        result = self.sync("--backup")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_linked(".grok/skills")
        backups = self.backups()
        self.assertEqual(len(backups), 1)
        self.assertIn("local edits", (backups[0] / "SKILL.md").read_text())
        self.assertIn(str(backups[0]), result.stdout)

    def test_agents_alias_of_codex_is_synced_once(self):
        codex = self.skills(".codex/skills")
        (self.home / ".agents").mkdir()
        os.symlink(codex, self.home / ".agents/skills")

        _, _, before = self.check()
        result = self.sync()
        _, report, after = self.check()

        self.assertEqual(before[".codex/skills"], "missing")
        self.assertEqual(before[".agents/skills"], "alias")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_linked(".codex/skills")
        self.assertTrue((self.home / ".agents/skills").is_symlink())
        self.assertEqual(sorted(p.name for p in codex.iterdir()), ["rlm"])
        self.assertFalse((self.source / "rlm").exists())
        self.assertEqual(after[".agents/skills"], "alias")
        self.assertTrue(report["in_sync"])

    def test_sync_repoints_a_stale_or_broken_symlink(self):
        other = self.tmp / "old-checkout/skills/rlm"
        self.write_skill(other, "old\n")
        os.symlink(other, self.skills(".claude/skills") / "rlm")
        os.symlink(self.tmp / "gone", self.skills(".codex/skills") / "rlm")

        _, _, before = self.check()
        result = self.sync()

        self.assertEqual(before[".claude/skills"], "stale-link")
        self.assertEqual(before[".codex/skills"], "stale-link")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_linked(".claude/skills")
        self.assert_linked(".codex/skills")
        self.assertIn("old", (other / "SKILL.md").read_text())
        self.assertFalse((other / "rlm").exists())
        self.assertEqual(
            sorted(os.readlink(backup) for backup in self.backups()),
            sorted([str(other), str(self.tmp / "gone")]),
        )

    def test_failed_backup_aborts_without_linking(self):
        copy = self.skills(".claude/skills") / "rlm"
        self.write_skill(copy, "canonical v4\n")
        diverged = self.skills(".grok/skills") / "rlm"
        self.write_skill(diverged, "local edits\n")
        (self.home / ".rlm-skill-backups").write_text("blocks the backup directory\n")

        result = self.sync("--backup")

        self.assertEqual(result.returncode, 1)
        for directory in (copy, diverged):
            self.assertFalse(directory.is_symlink())
            self.assertTrue((directory / "SKILL.md").is_file())
            self.assertFalse(os.path.lexists(directory / "rlm"))
        self.assertIn("local edits", (diverged / "SKILL.md").read_text())

    def test_copy_that_contains_the_source_is_a_conflict(self):
        outer = self.skills(".claude/skills") / "rlm"
        self.write_skill(outer, "outer copy\n")
        nested = outer / "nested"
        self.write_skill(nested, "nested source\n")

        report = json.loads(
            self.run_installer("--check", "--json", source=nested).stdout
        )
        result = self.run_installer("--sync-harnesses", "--backup", source=nested)

        self.assertEqual(report["harnesses"][0]["state"], "conflict")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(outer.is_symlink())
        self.assertIn("nested source", (nested / "SKILL.md").read_text())
        self.assertEqual(self.backups(), [])

    def test_source_reached_by_another_name_is_never_moved(self):
        real = self.skills(".claude/skills") / "rlm"
        self.write_skill(real, "lives in the harness\n")
        alias = self.tmp / "alias-to-skill"
        os.symlink(real, alias)
        hardlink_view = self.tmp / "view"
        os.symlink(self.home / ".claude/skills", hardlink_view)

        for source in (alias, hardlink_view / "rlm"):
            with self.subTest(source=source.name):
                result = self.run_installer("--sync-harnesses", "--backup", source=source)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(real.is_symlink())
                self.assertIn("lives in the harness", (real / "SKILL.md").read_text())
                self.assertEqual(self.backups(), [])

    def test_source_spelled_in_another_case_is_never_moved(self):
        real = self.skills(".claude/skills") / "rlm"
        self.write_skill(real, "lives in the harness\n")
        other_case = real.with_name("RLM")
        if not other_case.exists():
            self.skipTest("case-sensitive file system")

        result = self.run_installer("--sync-harnesses", "--backup", source=other_case)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(real.is_symlink())
        self.assertIn("lives in the harness", (real / "SKILL.md").read_text())
        self.assertEqual(self.backups(), [])

    def test_skills_directory_inside_the_source_is_a_conflict(self):
        (self.home / ".cursor").mkdir()
        os.symlink(self.source / "references", self.home / ".cursor/skills")

        _, _, states = self.check()
        result = self.sync()

        self.assertEqual(states[".cursor/skills"], "conflict")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(os.path.lexists(self.source / "references/rlm"))

    def test_failed_link_restores_the_original_entry(self):
        copy = self.skills(".claude/skills") / "rlm"
        self.write_skill(copy, "canonical v4\n")
        fake_bin = self.tmp / "fake-bin"
        fake_bin.mkdir()
        (fake_bin / "ln").write_text("#!/bin/sh\nexit 1\n")
        (fake_bin / "ln").chmod(0o755)

        result = self.sync(env={"PATH": f"{fake_bin}:/usr/bin:/bin"})

        self.assertEqual(result.returncode, 1)
        self.assertFalse(copy.is_symlink())
        self.assertIn("canonical v4", (copy / "SKILL.md").read_text())
        self.assertEqual(self.backups(), [])
        self.assertIn("restored", result.stderr)

    def test_symlink_targets_are_part_of_copy_equality(self):
        copy = self.skills(".claude/skills") / "rlm"
        self.write_skill(copy, "canonical v4\n")
        for directory, name in ((self.source, "one.md"), (copy, "two.md")):
            (self.tmp / name).write_text("same bytes\n")
            os.symlink(self.tmp / name, directory / "references/linked.md")

        _, _, states = self.check()

        self.assertEqual(states[".claude/skills"], "copy-diverged")

    def test_home_is_resolved_physically(self):
        (self.home / ".cursor/skills").mkdir(parents=True)
        os.symlink(self.home / ".cursor", self.tmp / "shortcut")

        result = self.run_installer("--check", "--json", home=self.tmp / "shortcut/..")

        self.assertEqual(json.loads(result.stdout)["home"], str(self.home))

    def test_home_inside_the_source_is_a_usage_error(self):
        home = self.source / "home"
        (home / ".cursor/skills").mkdir(parents=True)

        result = self.run_installer("--sync-harnesses", home=home)

        self.assertEqual(result.returncode, 2)
        self.assertFalse(os.path.lexists(home / ".cursor/skills/rlm"))

    def test_cdpath_does_not_corrupt_relative_paths(self):
        self.skills(".cursor/skills")

        result = subprocess.run(
            [self.shell, str(INSTALLER), "--check", "--json",
             "--source", "checkout/skills/rlm", "--home", "home"],
            cwd=self.tmp,
            env={**os.environ, "PATH": "/usr/bin:/bin", "CDPATH": str(self.tmp)},
            capture_output=True, text=True,
        )
        report = json.loads(result.stdout)

        self.assertEqual(report["source"], str(self.source))
        self.assertEqual(report["home"], str(self.home))

    def test_separator_characters_in_paths_do_not_fake_an_alias(self):
        for harness, name in ((".claude", "shared|old"), (".codex", "shared")):
            (self.tmp / name).mkdir()
            (self.home / harness).mkdir()
            os.symlink(self.tmp / name, self.home / harness / "skills")

        _, _, states = self.check()

        self.assertEqual(states[".claude/skills"], "missing")
        self.assertEqual(states[".codex/skills"], "missing")

    def test_control_characters_in_paths_stay_valid_json(self):
        home = self.tmp / "ho\x01me"
        (home / ".cursor/skills").mkdir(parents=True)

        result = self.run_installer("--check", "--json", home=home)

        self.assertEqual(json.loads(result.stdout)["home"], str(home))

    def test_installer_needs_no_temporary_files(self):
        self.assertNotIn("<<", INSTALLER.read_text())

    def test_sync_is_idempotent(self):
        self.write_skill(self.skills(".claude/skills") / "rlm", "canonical v4\n")
        self.skills(".cursor/skills")
        self.sync()
        before = snapshot(self.home)

        result = self.sync()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(snapshot(self.home), before)

    def test_source_inside_a_harness_directory_is_left_alone(self):
        source = self.skills(".claude/skills") / "rlm"
        self.write_skill(source, "lives in the harness\n")
        self.skills(".cursor/skills")

        result = self.run_installer("--sync-harnesses", source=source)
        report = json.loads(self.run_installer("--check", "--json", source=source).stdout)
        states = {entry["dir"]: entry["state"] for entry in report["harnesses"]}

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(source.is_symlink())
        self.assertIn("lives in the harness", (source / "SKILL.md").read_text())
        self.assertEqual(states[".claude/skills"], "source")
        self.assertEqual((self.home / ".cursor/skills/rlm").resolve(), source.resolve())
        self.assertTrue(report["in_sync"])

    def test_non_directory_targets_are_conflicts(self):
        (self.skills(".claude/skills") / "rlm").write_text("a file\n")
        (self.home / ".cursor").mkdir()
        (self.home / ".cursor/skills").write_text("not a directory\n")

        _, _, states = self.check()
        result = self.sync("--backup")

        self.assertEqual(states[".claude/skills"], "conflict")
        self.assertEqual(states[".cursor/skills"], "conflict")
        self.assertEqual(result.returncode, 1)
        self.assertEqual((self.home / ".claude/skills/rlm").read_text(), "a file\n")

    def test_paths_with_spaces_and_quotes_survive_json(self):
        home = self.tmp / 'ho me "x"'
        (home / ".cursor/skills").mkdir(parents=True)

        result = self.run_installer("--check", "--json", home=home)
        report = json.loads(result.stdout)
        sync = self.run_installer("--sync-harnesses", home=home)

        self.assertEqual(report["home"], str(home))
        self.assertEqual(sync.returncode, 0, sync.stderr)
        self.assertEqual((home / ".cursor/skills/rlm").resolve(), self.source.resolve())

    def test_invalid_source_or_home_is_a_usage_error(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        self.skills(".cursor/skills")
        before = snapshot(self.home)

        bad_source = self.run_installer("--sync-harnesses", source=empty)
        bad_home = self.run_installer("--check", home=self.tmp / "nope")
        missing_value = subprocess.run(
            [self.shell, str(INSTALLER), "--check", "--source"],
            capture_output=True, text=True,
        )
        unknown = subprocess.run(
            [self.shell, str(INSTALLER), "--sync-harnesses", "--force"],
            capture_output=True, text=True,
        )
        json_sync = self.run_installer("--sync-harnesses", "--json")

        for result in (bad_source, bad_home, missing_value, unknown, json_sync):
            self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("SKILL.md", bad_source.stderr)
        self.assertEqual(snapshot(self.home), before)

    def test_default_source_is_the_packaged_skill(self):
        result = subprocess.run(
            [self.shell, str(INSTALLER), "--check", "--json", "--home", str(self.home)],
            cwd=self.tmp, capture_output=True, text=True,
        )

        self.assertEqual(json.loads(result.stdout)["source"], str(ROOT / "skills/rlm"))

    def test_help_documents_the_harness_modes(self):
        result = subprocess.run(
            [self.shell, str(INSTALLER), "--help"], capture_output=True, text=True
        )

        self.assertEqual(result.returncode, 0)
        for flag in ("--sync-harnesses", "--check", "--backup", "--source", "--home"):
            self.assertIn(flag, result.stdout)


@unittest.skipUnless(os.path.exists("/bin/bash"), "no system bash")
class SystemBashHarnessSyncTests(HarnessSyncTests):
    shell = "/bin/bash"


if __name__ == "__main__":
    unittest.main()
