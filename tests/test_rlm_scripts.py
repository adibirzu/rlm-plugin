import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills/rlm"
INVENTORY = SKILL_DIR / "scripts/rlm_inventory.py"
LEDGER = SKILL_DIR / "scripts/rlm_ledger.py"
EVALS = SKILL_DIR / "evals/rlm_eval_cases.json"

REQUIRED_EVAL_CATEGORIES = {
    "focused-lookup",
    "print-contract-log-slicing",
    "depth-1-repo-partition",
    "depth-2-named-dependency",
    "small-model-budget-halt",
    "cross-family-verification",
}


def run_script(script, *args, stdin=None):
    return subprocess.run(
        [sys.executable, str(script), *map(str, args)],
        input=stdin,
        capture_output=True,
        text=True,
    )


def load_ledger_module():
    spec = importlib.util.spec_from_file_location("rlm_ledger", LEDGER)
    module = importlib.util.module_from_spec(spec)
    sys.modules["rlm_ledger"] = module
    spec.loader.exec_module(module)
    return module


def write(path, text="x\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name).resolve()
        self.repo = self.tmp / "repo"
        self.repo.mkdir()

    def inventory(self, *args):
        result = run_script(INVENTORY, self.repo, *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout), result

    def manifest_paths(self, *args):
        manifest = self.tmp / "scratch/manifest.json"
        summary, _ = self.inventory("--manifest", manifest, *args)
        data = json.loads(manifest.read_text())
        paths = [path for chunk in data["chunks"] for path in chunk["paths"]]
        return summary, data, paths

    def test_skips_noise_directories(self):
        write(self.repo / "src/app.py")
        write(self.repo / "docs/guide.md")
        for noise in (".git", "node_modules", ".venv", "build", "dist", "__pycache__"):
            write(self.repo / noise / "junk.txt")

        summary, _, paths = self.manifest_paths()

        self.assertEqual(sorted(paths), ["docs/guide.md", "src/app.py"])
        self.assertEqual(summary["totals"]["files"], 2)
        self.assertEqual(summary["skipped"]["noise_dirs"], 6)

    def test_include_noise_lists_generated_directories(self):
        write(self.repo / "build/out.js")

        _, _, paths = self.manifest_paths("--include-noise")

        self.assertEqual(paths, ["build/out.js"])

    def test_symlinks_that_escape_the_root_are_never_listed(self):
        outside = self.tmp / "outside"
        write(outside / "secret.txt", "TOP-SECRET-MARKER\n")
        write(self.repo / "src/app.py")
        os.symlink(outside, self.repo / "linked_dir")
        os.symlink(outside / "secret.txt", self.repo / "linked_file.txt")
        os.symlink(self.repo / "src/app.py", self.repo / "internal_link.py")

        summary, data, paths = self.manifest_paths()

        self.assertEqual(paths, ["src/app.py"])
        self.assertEqual(summary["skipped"]["symlink_escapes"], 2)
        self.assertEqual(summary["skipped"]["symlinks_internal"], 1)
        self.assertNotIn("secret", json.dumps(summary) + json.dumps(data))

    def test_never_prints_file_contents(self):
        write(self.repo / "src/app.py", "API_TOKEN = 'CONTENT-MARKER-123'\n")

        summary, data, _ = self.manifest_paths()

        self.assertNotIn("CONTENT-MARKER-123", json.dumps(summary) + json.dumps(data))

    def test_summary_stays_inside_the_output_budget(self):
        for index in range(300):
            write(self.repo / f"pkg/module_with_a_long_descriptive_name_{index:04d}.py")

        manifest = self.tmp / "scratch/manifest.json"
        result = run_script(
            INVENTORY, self.repo, "--max-output-bytes", 1500, "--chunk-bytes", 8,
            "--manifest", manifest,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLessEqual(len(result.stdout.encode()), 1500)
        summary = json.loads(result.stdout)
        self.assertTrue(summary["output_truncated"])
        self.assertEqual(summary["totals"]["files"], 300)
        self.assertGreater(summary["chunk_count"], len(summary["chunks"]))
        data = json.loads(manifest.read_text())
        self.assertEqual(sum(len(chunk["paths"]) for chunk in data["chunks"]), 300)
        self.assertEqual(len(data["chunks"]), summary["chunk_count"])

    def test_chunks_respect_the_byte_budget_and_cover_every_file_once(self):
        for index in range(10):
            write(self.repo / f"a/f{index}.txt", "x" * 400)
        write(self.repo / "b/huge.txt", "y" * 5000)

        summary, data, paths = self.manifest_paths("--chunk-bytes", 1000)

        self.assertEqual(len(paths), 11)
        self.assertEqual(len(set(paths)), 11)
        for chunk in data["chunks"]:
            if chunk["oversized"]:
                self.assertEqual(chunk["paths"], ["b/huge.txt"])
            else:
                self.assertLessEqual(chunk["bytes"], 1000)
        self.assertEqual(summary["totals"]["bytes"], 9000)
        self.assertEqual(summary["totals"]["est_tokens"], 2250)

    def test_binary_files_are_counted_but_not_partitioned(self):
        write(self.repo / "src/app.py")
        (self.repo / "src/blob.bin").write_bytes(b"\x00\x01\x02binary")

        summary, _, paths = self.manifest_paths()

        self.assertEqual(paths, ["src/app.py"])
        self.assertEqual(summary["skipped"]["binary"], 1)

    def test_manifest_symlink_does_not_overwrite_its_target(self):
        victim = write(self.tmp / "outside/victim.txt", "KEEP\n")
        write(self.repo / "src/app.py")
        manifest = self.repo / ".rlm/audit/manifest.json"
        manifest.parent.mkdir(parents=True)
        os.symlink(victim, manifest)

        result = run_script(INVENTORY, self.repo, "--manifest", manifest)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(victim.read_text(), "KEEP\n")
        self.assertFalse(manifest.is_symlink())
        self.assertEqual(len(json.loads(manifest.read_text())["chunks"]), 1)

    def test_manifest_cannot_leave_the_root_through_a_symlinked_directory(self):
        outside = self.tmp / "outside"
        outside.mkdir()
        write(self.repo / "src/app.py")
        os.symlink(outside, self.repo / ".rlm")

        result = run_script(
            INVENTORY, self.repo, "--manifest", self.repo / ".rlm/audit/manifest.json"
        )

        self.assertEqual(result.returncode, 3)
        self.assertIn("symlink", result.stderr)
        self.assertEqual(list(outside.iterdir()), [])

    def test_manifest_guard_sees_through_an_alias_of_the_root(self):
        outside = self.tmp / "outside"
        outside.mkdir()
        write(self.repo / "src/app.py")
        os.symlink(outside, self.repo / ".rlm")
        os.symlink(self.tmp, self.tmp / "alias")

        result = run_script(
            INVENTORY, self.repo,
            "--manifest", self.tmp / "alias/alias/repo/.rlm/audit/manifest.json",
        )

        self.assertEqual(result.returncode, 3)
        self.assertEqual(list(outside.iterdir()), [])

    def test_manifest_path_through_a_symlink_and_dotdot_lands_where_named(self):
        write(self.repo / "src/app.py")
        (self.tmp / "releases/v4").mkdir(parents=True)
        os.symlink(self.tmp / "releases/v4", self.tmp / "current")

        result = subprocess.run(
            [sys.executable, str(INVENTORY), str(self.repo),
             "--manifest", "current/../manifest.json"],
            cwd=self.tmp, capture_output=True, text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.tmp / "releases/manifest.json").is_file())
        self.assertFalse((self.tmp / "manifest.json").exists())

    def test_summary_always_says_whether_coverage_is_complete(self):
        write(self.repo / "top.py")
        complete, _ = self.inventory()
        write(self.repo / "a/b/deep.py")
        pruned, _ = self.inventory("--max-depth", 1)
        for index in range(300):
            write(self.repo / f"pkg/module_with_a_long_descriptive_name_{index:04d}.py")
        capped, _ = self.inventory("--max-files", 10)
        tiny, _ = self.inventory("--max-depth", 1, "--max-output-bytes", 512, "--chunk-bytes", 2)

        self.assertIs(complete["coverage_complete"], True)
        self.assertIs(pruned["coverage_complete"], False)
        self.assertIs(capped["coverage_complete"], False)
        self.assertIs(tiny["coverage_complete"], False)

    def test_max_depth_has_a_safe_upper_bound(self):
        result = run_script(INVENTORY, self.repo, "--max-depth", 2000)

        self.assertEqual(result.returncode, 2)
        self.assertIn("--max-depth", result.stderr)

    @unittest.skipIf(os.geteuid() == 0, "root can read every directory")
    def test_unreadable_directories_are_counted(self):
        write(self.repo / "src/app.py")
        locked = self.repo / "locked"
        write(locked / "hidden.py")
        locked.chmod(0)
        self.addCleanup(locked.chmod, 0o755)

        summary, _, paths = self.manifest_paths()

        self.assertEqual(paths, ["src/app.py"])
        self.assertGreaterEqual(summary["skipped"]["unreadable"], 1)
        self.assertIs(summary["coverage_complete"], False)

    def test_output_budget_holds_for_any_stdout_encoding(self):
        for index in range(40):
            write(self.repo / f"pkg/module_{index:03d}.py")

        result = subprocess.run(
            [sys.executable, str(INVENTORY), str(self.repo), "--max-output-bytes", "600"],
            env={**os.environ, "PYTHONIOENCODING": "utf-16-le"},
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertLessEqual(len(result.stdout), 600)
        self.assertEqual(json.loads(result.stdout)["totals"]["files"], 40)

    def test_very_deep_trees_are_bounded_by_default(self):
        deep = self.repo.joinpath(*["d"] * 70)
        write(deep / "bottom.py")
        write(self.repo / "top.py")

        summary, _, paths = self.manifest_paths()

        self.assertEqual(paths, ["top.py"])
        self.assertEqual(summary["skipped"]["depth_limited"], 1)

    def test_max_files_bounds_the_walk(self):
        for index in range(20):
            write(self.repo / f"src/f{index:02d}.py")

        summary, _, paths = self.manifest_paths("--max-files", 5)

        self.assertTrue(summary["truncated"])
        self.assertEqual(len(paths), 5)

    def test_max_depth_bounds_recursion(self):
        write(self.repo / "top.py")
        write(self.repo / "a/b/c/deep.py")

        summary, _, paths = self.manifest_paths("--max-depth", 1)

        self.assertEqual(paths, ["top.py"])
        self.assertGreaterEqual(summary["skipped"]["depth_limited"], 1)

    def test_output_is_deterministic(self):
        for name in ("z.py", "a.py", "m/k.py", "m/b.py"):
            write(self.repo / name)

        first = run_script(INVENTORY, self.repo).stdout
        second = run_script(INVENTORY, self.repo).stdout

        self.assertEqual(first, second)
        self.assertEqual(json.loads(first)["chunks"][0]["sample"][0], "a.py")

    def test_missing_root_is_a_usage_error(self):
        result = run_script(INVENTORY, self.tmp / "does-not-exist")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("not a directory", result.stderr)

    def test_help_documents_exit_codes(self):
        result = run_script(INVENTORY, "--help")

        self.assertEqual(result.returncode, 0)
        self.assertIn("--manifest", result.stdout)
        self.assertIn("Exit codes", result.stdout)


VALID_LEDGER = {
    "budget": {"tier": "mid", "depth": 1, "max_depth": 1},
    "coverage": {"reviewed": ["src/"], "deferred": []},
    "findings": [
        {
            "title": "Unbounded read",
            "severity": "medium",
            "location": "src/app.py:2",
            "evidence": "read() without a limit",
            "confidence": "high",
        }
    ],
    "counterevidence": ["Callers pass small files only in tests"],
    "verification": ["Ran the reader against a 1 GB file: memory grew linearly"],
}

VALID_MARKDOWN = """\
## Budget
- Tier: mid
- Depth: 1
- Max depth: 1

## Coverage
- Reviewed: src/
- Deferred: none

## Findings
### [MEDIUM] Unbounded read
- Location: `src/app.py:2`
- Evidence: read() without a limit
- Confidence: high

## Counterevidence
- Callers pass small files only in tests

## Verification
- Ran the reader against a 1 GB file: memory grew linearly
"""


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = pathlib.Path(self._tmp.name).resolve()
        self.repo = self.tmp / "repo"
        write(self.repo / "src/app.py", "line one\nline two\nline three\n")

    def validate(self, ledger, *args):
        if isinstance(ledger, str):
            path = write(self.tmp / "ledger.md", ledger)
        else:
            path = write(self.tmp / "ledger.json", json.dumps(ledger))
        result = run_script(LEDGER, path, "--json", *args)
        self.assertIn(result.returncode, (0, 1), result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["valid"], result.returncode == 0)
        return report

    def codes(self, ledger, *args):
        return {issue["code"] for issue in self.validate(ledger, *args)["errors"]}

    def mutated(self, **changes):
        ledger = json.loads(json.dumps(VALID_LEDGER))
        for key, value in changes.items():
            if value is None:
                ledger.pop(key)
            else:
                ledger[key] = value
        return ledger

    def with_location(self, location):
        ledger = self.mutated()
        ledger["findings"][0]["location"] = location
        return ledger

    def test_valid_json_ledger_passes(self):
        report = self.validate(VALID_LEDGER, "--root", self.repo)

        self.assertTrue(report["valid"])
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["summary"], {"findings": 1, "citations": 1})

    def test_valid_markdown_ledger_passes(self):
        report = self.validate(VALID_MARKDOWN, "--root", self.repo)

        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["summary"], {"findings": 1, "citations": 1})

    def test_each_required_section_is_enforced(self):
        for section in ("coverage", "findings", "counterevidence", "verification"):
            with self.subTest(format="json", section=section):
                report = self.validate(self.mutated(**{section: None}))
                self.assertIn(
                    {"code": "missing-section", "where": section},
                    [{"code": i["code"], "where": i["where"]} for i in report["errors"]],
                )
            with self.subTest(format="markdown", section=section):
                heading = f"## {section.capitalize()}"
                markdown = VALID_MARKDOWN.replace(heading, "## Other")
                self.assertIn("missing-section", self.codes(markdown))

    def test_empty_sections_are_rejected(self):
        self.assertIn("empty-section", self.codes(self.mutated(counterevidence=[])))
        self.assertIn("empty-section", self.codes(self.mutated(verification=["TBD"])))
        self.assertIn(
            "empty-section",
            self.codes(self.mutated(coverage={"reviewed": [], "deferred": []})),
        )

    def test_explicit_no_findings_is_valid_with_coverage(self):
        ledger = self.mutated(findings=[])
        markdown = re.sub(
            r"## Findings\n.*?\n## Counterevidence",
            "## Findings\n- None\n\n## Counterevidence",
            VALID_MARKDOWN,
            flags=re.S,
        )

        self.assertTrue(self.validate(ledger)["valid"])
        self.assertTrue(self.validate(markdown)["valid"])

    def test_empty_and_placeholder_citations_are_rejected(self):
        self.assertIn("empty-citation", self.codes(self.with_location("")))
        for placeholder in ("path:line", "<path>:<line>", "TBD", "https://example.com/x"):
            with self.subTest(placeholder=placeholder):
                self.assertIn(
                    "placeholder-citation", self.codes(self.with_location(placeholder))
                )

    def test_citations_need_a_line_or_a_url(self):
        self.assertIn("bad-citation", self.codes(self.with_location("src/app.py")))
        self.assertIn("bad-citation", self.codes(self.with_location("src/app.py:0")))
        self.assertTrue(
            self.validate(self.with_location("https://arxiv.org/abs/2512.24601"))["valid"]
        )
        self.assertTrue(
            self.validate(self.with_location("src/app.py:1-3, src/app.py:2"))["valid"]
        )

    def test_json_location_may_be_a_list_of_citations(self):
        report = self.validate(
            self.with_location(["src/app.py:1", "src/app.py:3"]), "--root", self.repo
        )

        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["summary"]["citations"], 2)
        self.assertIn("empty-citation", self.codes(self.with_location([])))

    def test_fabricated_citations_are_rejected_against_the_root(self):
        cases = {
            "src/missing.py:1": "fabricated-citation",
            "src/app.py:999": "fabricated-citation",
            "../outside.py:1": "citation-outside-root",
        }
        write(self.tmp / "outside.py")
        for location, code in cases.items():
            with self.subTest(location=location):
                self.assertIn(
                    code, self.codes(self.with_location(location), "--root", self.repo)
                )

    def test_symlinked_citation_cannot_escape_the_root(self):
        write(self.tmp / "outside.py")
        os.symlink(self.tmp / "outside.py", self.repo / "src/link.py")

        codes = self.codes(self.with_location("src/link.py:1"), "--root", self.repo)

        self.assertIn("citation-outside-root", codes)

    def test_depth_two_needs_a_named_dependency_and_a_budget(self):
        budget = {"tier": "frontier", "depth": 2, "max_depth": 2}
        named = {**budget, "named_dependency": "auth middleware order in src/app.py"}

        self.assertIn("depth-without-dependency", self.codes(self.mutated(budget=budget)))
        self.assertIn(
            "depth-without-dependency",
            self.codes(self.mutated(budget={**budget, "named_dependency": "TBD"})),
        )
        self.assertIn(
            "depth-unbudgeted",
            self.codes(self.mutated(budget={**named, "max_depth": 1})),
        )
        unbudgeted = {k: v for k, v in named.items() if k != "max_depth"}
        self.assertIn("depth-unbudgeted", self.codes(self.mutated(budget=unbudgeted)))
        self.assertTrue(self.validate(self.mutated(budget=named))["valid"])

    def test_depth_never_exceeds_the_declared_maximum(self):
        budget = {"tier": "small", "depth": 1, "max_depth": 0}

        self.assertEqual(self.codes(self.mutated(budget=budget)), {"depth-unbudgeted"})

    def test_non_text_and_evasive_sections_are_rejected(self):
        evasive = re.sub(
            r"## Findings\n.*?\n## Counterevidence",
            "## Findings\n- None of the files were reviewed\n\n## Counterevidence",
            VALID_MARKDOWN,
            flags=re.S,
        )
        honest = evasive.replace("None of the files were reviewed", "No findings.")

        self.assertIn("empty-section", self.codes(self.mutated(verification=False)))
        self.assertIn("empty-section", self.codes(self.mutated(verification=42)))
        self.assertIn(
            "empty-section", self.codes(self.mutated(verification={"check": False}))
        )
        self.assertTrue(
            self.validate(self.mutated(verification={"check": "ran the unit tests"}))["valid"]
        )
        self.assertIn("empty-section", self.codes(self.mutated(counterevidence=[True])))
        self.assertIn("empty-section", self.codes(evasive))
        self.assertTrue(self.validate(honest)["valid"])

    def test_malformed_values_are_reported_not_crashed_on(self):
        cases = {
            "http://[broken": "bad-citation",
            "src/a\x00b.py:1": "bad-citation",
            "src/app.py:" + "9" * 5000: "bad-citation",
        }
        for location, code in cases.items():
            with self.subTest(location=location[:20]):
                self.assertIn(
                    code, self.codes(self.with_location(location), "--root", self.repo)
                )
        os.symlink("loop", self.repo / "loop")
        self.assertIn(
            "fabricated-citation",
            self.codes(self.with_location("loop:1"), "--root", self.repo),
        )
        self.assertIn(
            "bad-budget", self.codes(self.mutated(budget={"depth": "\u00b2"}))
        )

    def test_url_citations_are_checked_and_kept_whole(self):
        for bad in ("https://two words.org/path", "https://github.com:bad/path"):
            with self.subTest(url=bad):
                self.assertIn("bad-citation", self.codes(self.with_location(bad)))
        for good in ("https://[2001:db8::1]/help", "https://host.org/a,b;c"):
            with self.subTest(url=good):
                report = self.validate(self.with_location(good))
                self.assertTrue(report["valid"], report["errors"])
                self.assertEqual(report["summary"]["citations"], 1)
        listed = self.validate(self.with_location(["https://host.org/a, b", "src/app.py:1"]))
        self.assertEqual(listed["summary"]["citations"], 2)

    def test_every_markdown_location_line_is_checked(self):
        markdown = VALID_MARKDOWN.replace(
            "- Location: `src/app.py:2`",
            "- Location: src/app.py:999999\n- Location: `src/app.py:2`",
        )

        report = self.validate(markdown, "--root", self.repo)

        self.assertEqual({i["code"] for i in report["errors"]}, {"fabricated-citation"})
        self.assertEqual(report["summary"]["citations"], 2)

    def test_backticked_citation_keeps_its_punctuation(self):
        write(self.repo / "src/report,2026.md", "one\n")
        markdown = VALID_MARKDOWN.replace(
            "`src/app.py:2`", "`src/report,2026.md:1` and `src/app.py:2`"
        )

        report = self.validate(markdown, "--root", self.repo)

        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["summary"]["citations"], 2)

    def test_named_dependency_must_be_text(self):
        budget = {"tier": "frontier", "depth": 2, "max_depth": 2}
        for dependency in ({}, [], 7, True):
            with self.subTest(dependency=dependency):
                ledger = self.mutated(budget={**budget, "named_dependency": dependency})
                self.assertIn("depth-without-dependency", self.codes(ledger))

    def test_bare_none_is_not_section_content(self):
        self.assertIn("empty-section", self.codes(self.mutated(verification=["None"])))
        self.assertIn("empty-section", self.codes(self.mutated(counterevidence=["none"])))
        self.assertIn(
            "empty-section",
            self.codes(VALID_MARKDOWN.replace(
                "- Ran the reader against a 1 GB file: memory grew linearly", "- None"
            )),
        )
        self.assertTrue(
            self.validate(
                self.mutated(verification=["None could run: the sandbox is read-only"])
            )["valid"]
        )

    def test_compact_citation_lists_are_split(self):
        report = self.validate(
            self.with_location("src/app.py:1,src/app.py:2;src/app.py:3"), "--root", self.repo
        )

        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["summary"]["citations"], 3)

    def test_tier_caps_are_enforced(self):
        dependency = "token refresh path in src/app.py"
        small = {"tier": "small", "depth": 2, "max_depth": 2, "named_dependency": dependency}
        deep = {"tier": "frontier", "depth": 3, "max_depth": 3, "named_dependency": dependency}
        untiered = {"depth": 3, "max_depth": 3, "named_dependency": dependency}

        self.assertIn("depth-over-tier", self.codes(self.mutated(budget=small)))
        self.assertIn("depth-over-tier", self.codes(self.mutated(budget=deep)))
        self.assertIn("depth-over-tier", self.codes(self.mutated(budget=untiered)))
        self.assertIn(
            "unknown-tier", self.codes(self.mutated(budget={"tier": "huge", "depth": 0}))
        )

    def test_coordinator_flags_override_the_declared_budget(self):
        frontier = {
            "tier": "frontier",
            "depth": 2,
            "max_depth": 2,
            "named_dependency": "session store contract in src/app.py",
        }

        self.assertIn(
            "depth-over-tier", self.codes(self.mutated(budget=frontier), "--tier", "small")
        )
        self.assertIn(
            "depth-without-dependency",
            self.codes(self.mutated(budget={"depth": 0}), "--depth", "2"),
        )

    def test_markdown_budget_is_parsed(self):
        markdown = VALID_MARKDOWN.replace("- Depth: 1", "- Depth: 2").replace(
            "- Tier: mid", "- Tier: small"
        )

        self.assertEqual(
            self.codes(markdown),
            {"depth-over-tier", "depth-without-dependency", "depth-unbudgeted"},
        )

    def test_text_output_and_stdin(self):
        valid = run_script(LEDGER, "-", stdin=json.dumps(VALID_LEDGER))
        invalid = run_script(LEDGER, "-", stdin=json.dumps(self.with_location("")))

        self.assertEqual(valid.returncode, 0)
        self.assertIn("OK", valid.stdout)
        self.assertEqual(invalid.returncode, 1)
        self.assertIn("empty-citation", invalid.stdout)

    def test_unreadable_input_is_a_usage_error(self):
        missing = run_script(LEDGER, self.tmp / "nope.json", "--json")
        garbage = run_script(LEDGER, "-", "--format", "json", stdin="{not json")
        huge = run_script(
            LEDGER, "-", "--json", stdin='{"budget": {"depth": ' + "9" * 5000 + "}}"
        )
        self.assertEqual(huge.returncode, 2)
        self.assertNotIn("Traceback", huge.stderr)
        nested = "[" * 600 + '"deep"' + "]" * 600
        deep = run_script(LEDGER, "-", "--json", stdin='{"verification": ' + nested + "}")
        self.assertIn(deep.returncode, (1, 2))
        self.assertNotIn("Traceback", deep.stderr)

        self.assertEqual(missing.returncode, 2)
        self.assertEqual(garbage.returncode, 2)
        self.assertEqual(missing.stdout, "")

    def test_help_documents_exit_codes(self):
        result = run_script(LEDGER, "--help")

        self.assertEqual(result.returncode, 0)
        self.assertIn("--root", result.stdout)
        self.assertIn("Exit codes", result.stdout)

    def test_skill_budget_table_matches_the_validator(self):
        budgets = load_ledger_module().TIER_BUDGETS
        skill = (SKILL_DIR / "SKILL.md").read_text()

        self.assertEqual(set(budgets), {"frontier", "mid", "small"})
        for tier, budget in budgets.items():
            with self.subTest(tier=tier):
                row = re.search(rf"^\| {tier} \|(.+)\|$", skill, flags=re.M)
                self.assertIsNotNone(row, f"SKILL.md has no budget row for {tier}")
                numbers = [int(n) for n in re.findall(r"\| (\d+) (?=\|)", row.group(0))]
                self.assertEqual(
                    numbers,
                    [
                        budget["default_depth"],
                        budget["max_depth"],
                        budget["max_fanout"],
                        budget["max_subcalls"],
                    ],
                )


class EvalCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.suite = json.loads(EVALS.read_text())
        cls.budgets = load_ledger_module().TIER_BUDGETS

    def test_suite_header(self):
        self.assertEqual(self.suite["skill_name"], "rlm")
        self.assertEqual(self.suite["schema_version"], 1)
        self.assertGreaterEqual(len(self.suite["evals"]), 6)

    def test_every_case_matches_the_schema(self):
        modes = {"focused", "standard", "deep"}
        seen = set()
        for case in self.suite["evals"]:
            with self.subTest(case=case.get("id")):
                self.assertEqual(
                    set(case),
                    {
                        "id", "category", "prompt", "expected_output", "files",
                        "budget", "assertions", "ledger_checks",
                    },
                )
                self.assertRegex(case["id"], r"^[a-z0-9]+(-[a-z0-9]+)*$")
                self.assertNotIn(case["id"], seen)
                seen.add(case["id"])
                self.assertIn(case["category"], REQUIRED_EVAL_CATEGORIES)
                self.assertGreater(len(case["prompt"]), 40)
                self.assertGreater(len(case["expected_output"]), 40)
                self.assertIsInstance(case["files"], list)
                self.assertGreaterEqual(len(case["assertions"]), 3)
                for assertion in case["assertions"]:
                    self.assertIsInstance(assertion, str)
                    self.assertGreater(len(assertion), 20)

                budget = case["budget"]
                self.assertEqual(
                    set(budget), {"tier", "mode", "max_depth", "max_subcalls"}
                )
                self.assertIn(budget["mode"], modes)
                tier = self.budgets[budget["tier"]]
                self.assertLessEqual(budget["max_depth"], tier["max_depth"])
                self.assertLessEqual(budget["max_subcalls"], tier["max_subcalls"])

                self.assertIsInstance(case["ledger_checks"], list)
                for check in case["ledger_checks"]:
                    self.assertEqual(set(check), {"name", "ledger", "valid", "error_codes"})
                    self.assertIsInstance(check["valid"], bool)
                    self.assertEqual(check["valid"], not check["error_codes"])

    def test_required_categories_are_covered(self):
        categories = {case["category"] for case in self.suite["evals"]}

        self.assertEqual(categories, REQUIRED_EVAL_CATEGORIES)

    def test_focused_lookup_forbids_recursion(self):
        for case in self.suite["evals"]:
            if case["category"] == "focused-lookup":
                self.assertEqual(case["budget"]["max_depth"], 0)
                self.assertEqual(case["budget"]["max_subcalls"], 0)

    def test_ledger_checks_agree_with_the_validator(self):
        checked = 0
        for case in self.suite["evals"]:
            for check in case["ledger_checks"]:
                with self.subTest(case=case["id"], check=check["name"]):
                    result = run_script(
                        LEDGER, "-", "--format", "json", "--json",
                        stdin=json.dumps(check["ledger"]),
                    )
                    report = json.loads(result.stdout)
                    self.assertEqual(report["valid"], check["valid"], report["errors"])
                    self.assertEqual(
                        sorted({issue["code"] for issue in report["errors"]}),
                        sorted(check["error_codes"]),
                    )
                    checked += 1
        self.assertGreaterEqual(checked, 6)


if __name__ == "__main__":
    unittest.main()
