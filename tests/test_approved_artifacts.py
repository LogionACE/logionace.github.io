"""
The approved-artifact manifest, offline.

The site's public numbers and its downloadable reports are only as trustworthy
as the claim "these bytes are the bytes that were approved". This module tests
the half of that claim that runs without a browser: the builder is
deterministic, the checker recomputes every digest rather than trusting the
manifest's word, and each way a manifest can be wrong is refused rather than
worked around.

The four failures the brief names -- a hash that does not match, a path trying to
escape the site, a manifest that is not approved, and a draft substituted for the
approved snapshot -- each get a test, because each is a way a reader could be
shown a number nobody stands behind.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from conftest import SITE_ROOT
from tools import ace_artifacts as artifacts


# -- a small, complete site tree --------------------------------------------

LEADERBOARD = {
    "protocol": "ACE-1.1",
    "models": [
        {
            "label": "model-a",
            "vendor": "Vendor A",
            "bare": {
                "overall": 71.2,
                "grade": "B",
                "verdict": "ACE Ready",
                "critical_exception_count": 3,
                "domains": {"DP": {"score": 80}, "RF": {"score": 62}},
            },
        },
        {
            "label": "model-b",
            "vendor": "Vendor B",
            "bare": {
                "overall": 55.0,
                "grade": "C",
                "verdict": "Not Ready",
                "critical_exception_count": 9,
                "domains": {"DP": {"score": 40}, "MR": {"score": 51}},
            },
        },
        # A model with no scored run is not an evaluated system.
        {"label": "model-c", "vendor": "Vendor C"},
    ],
}

AGENT_LEADERBOARD = {"protocol": "ACE-1.1", "models": []}


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    (tmp_path / "ace-leaderboard.json").write_text(
        json.dumps(LEADERBOARD, indent=2), "utf-8"
    )
    (tmp_path / "agent-leaderboard.json").write_text(
        json.dumps(AGENT_LEADERBOARD, indent=2), "utf-8"
    )
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "ACE_Report_model-a.pdf").write_bytes(b"%PDF-1.7\nmodel a report\n")
    (reports / "ACE_Report_model-b.pdf").write_bytes(b"%PDF-1.7\nmodel b report\n")
    return tmp_path


def build(tree: Path) -> dict:
    manifest = artifacts.build_manifest(tree)
    (tree / artifacts.MANIFEST_NAME).write_bytes(artifacts.canonical_bytes(manifest))
    return manifest


def write(tree: Path, manifest: dict) -> None:
    (tree / artifacts.MANIFEST_NAME).write_bytes(artifacts.canonical_bytes(manifest))


def entry_for(manifest: dict, role: str) -> dict:
    return next(e for e in manifest["artifacts"] if e["role"] == role)


# -- building ---------------------------------------------------------------

def test_a_build_describes_every_publishable_file_and_nothing_else(tree: Path):
    manifest = artifacts.build_manifest(tree)
    paths = sorted(entry["path"] for entry in manifest["artifacts"])
    assert paths == [
        "ace-leaderboard.json",
        "agent-leaderboard.json",
        "reports/ACE_Report_model-a.pdf",
        "reports/ACE_Report_model-b.pdf",
    ]
    assert manifest["state"] == "approved"
    assert manifest["provenance"]["kind"] == "git_commit"
    assert manifest["provenance"]["commit"] == artifacts.PROVENANCE_COMMIT


def test_a_stray_file_does_not_become_publishable_by_existing(tree: Path):
    (tree / "draft-leaderboard.json").write_text("{}", "utf-8")
    (tree / "reports" / "internal-notes.txt").write_text("not a report", "utf-8")
    manifest = artifacts.build_manifest(tree)
    listed = {entry["path"] for entry in manifest["artifacts"]}
    assert "draft-leaderboard.json" not in listed
    assert "reports/internal-notes.txt" not in listed


def test_the_build_is_byte_for_byte_deterministic(tree: Path):
    first = artifacts.canonical_bytes(artifacts.build_manifest(tree))
    second = artifacts.canonical_bytes(artifacts.build_manifest(tree))
    assert first == second
    assert first.endswith(b"\n")


def test_the_recorded_digest_is_the_real_digest(tree: Path):
    manifest = artifacts.build_manifest(tree)
    for entry in manifest["artifacts"]:
        raw = (tree / entry["path"]).read_bytes()
        assert entry["sha256"] == hashlib.sha256(raw).hexdigest()
        assert entry["bytes"] == len(raw)


def test_the_protocol_is_taken_from_the_data_not_asserted(tree: Path):
    board = json.loads((tree / "ace-leaderboard.json").read_text("utf-8"))
    board["protocol"] = "ACE-9.9"
    (tree / "ace-leaderboard.json").write_text(json.dumps(board), "utf-8")
    assert artifacts.build_manifest(tree)["protocol"] == "ACE-9.9"


def test_the_check_accepts_another_pin_only_when_told_to(tree: Path):
    """`--commit` exists so the snapshot can be re-pinned deliberately."""
    other = "1" * 40
    write(tree, artifacts.build_manifest(tree, commit=other))
    assert artifacts.check_manifest(tree, expected_commit=other) == []
    assert artifacts.check_manifest(tree) != []


def test_a_provenance_commit_must_be_a_git_sha(tree: Path):
    with pytest.raises(artifacts.ManifestError, match="40-hex"):
        artifacts.build_manifest(tree, commit="main")


def test_a_declared_artifact_that_is_missing_stops_the_build(tree: Path):
    (tree / "agent-leaderboard.json").unlink()
    with pytest.raises(artifacts.ManifestError, match="missing from the tree"):
        artifacts.build_manifest(tree)


# -- checking: the four ways a manifest goes wrong -------------------------

def test_a_clean_tree_checks_out(tree: Path):
    build(tree)
    assert artifacts.check_manifest(tree) == []


def test_a_changed_file_is_caught_by_its_hash(tree: Path):
    build(tree)
    report = tree / "reports" / "ACE_Report_model-a.pdf"
    report.write_bytes(report.read_bytes() + b"appended after approval\n")
    problems = artifacts.check_manifest(tree)
    assert any("sha256 is" in problem for problem in problems)


def test_a_file_of_the_same_length_is_still_caught(tree: Path):
    """Length is a cheap pre-check, not the check."""
    build(tree)
    report = tree / "reports" / "ACE_Report_model-a.pdf"
    original = report.read_bytes()
    tampered = original[:-2] + b"X\n"
    assert len(tampered) == len(original)
    report.write_bytes(tampered)
    problems = artifacts.check_manifest(tree)
    assert problems and all("bytes on disk" not in problem for problem in problems)


def test_a_deleted_file_is_reported_rather_than_dropped(tree: Path):
    build(tree)
    (tree / "reports" / "ACE_Report_model-b.pdf").unlink()
    problems = artifacts.check_manifest(tree)
    assert any("missing" in problem for problem in problems)


def test_a_publishable_file_nobody_declared_is_a_problem(tree: Path):
    build(tree)
    (tree / "reports" / "ACE_Report_model-c.pdf").write_bytes(b"%PDF-1.7\nlate\n")
    problems = artifacts.check_manifest(tree)
    assert any("not declared" in problem for problem in problems)


@pytest.mark.parametrize(
    "path",
    [
        "../secrets.json",
        "/etc/passwd",
        "reports/../../etc/passwd",
        "reports//nested.pdf",
        "reports\\windows.pdf",
        "https://elsewhere.example/report.pdf",
        "//elsewhere.example/report.pdf",
        ".hidden.json",
        "",
        "  reports/leading-space.pdf",
    ],
)
def test_a_path_that_escapes_the_site_is_refused(path: str):
    assert not artifacts.is_safe_relative_path(path)


def test_a_manifest_carrying_an_escaping_path_does_not_validate(tree: Path):
    manifest = build(tree)
    manifest["artifacts"][0]["path"] = "../../etc/passwd"
    write(tree, manifest)
    problems = artifacts.check_manifest(tree)
    assert any("unsafe or malformed" in problem for problem in problems)


def test_a_manifest_that_is_not_approved_is_refused(tree: Path):
    manifest = build(tree)
    manifest["state"] = "draft"
    write(tree, manifest)
    problems = artifacts.check_manifest(tree)
    assert problems and "state must be 'approved'" in problems[0]


def test_a_draft_substituted_for_the_snapshot_is_refused(tree: Path):
    """The classic failure: a draft leaderboard, a manifest rebuilt around it.

    The manifest is internally consistent -- every digest matches the file it
    describes -- and it is still not the approved snapshot, because it claims a
    provenance commit that is not the one the site is pinned to. `check` catches
    the state; the browser catches the commit, and that is asserted in the
    Playwright suite.
    """
    board = json.loads((tree / "ace-leaderboard.json").read_text("utf-8"))
    board["models"][0]["bare"]["critical_exception_count"] = 0
    board["models"][0]["bare"]["verdict"] = "ACE Ready"
    (tree / "ace-leaderboard.json").write_text(json.dumps(board, indent=2), "utf-8")

    draft = artifacts.build_manifest(tree)
    draft["state"] = "draft"
    write(tree, draft)
    assert artifacts.check_manifest(tree)

    # Marked approved and internally consistent -- every digest matches the file
    # it describes -- but built against a commit nobody pinned the site to.
    forged = artifacts.build_manifest(tree, commit="0" * 40)
    forged["state"] = "approved"
    write(tree, forged)
    problems = artifacts.check_manifest(tree)
    assert any("pinned to" in problem for problem in problems), problems


def test_a_manifest_missing_a_leaderboard_role_is_refused(tree: Path):
    manifest = build(tree)
    manifest["artifacts"] = [
        entry for entry in manifest["artifacts"] if entry["role"] != "leaderboard_agent"
    ]
    write(tree, manifest)
    problems = artifacts.check_manifest(tree)
    assert any("leaderboard_agent" in problem for problem in problems)


def test_two_artifacts_cannot_claim_one_leaderboard_role(tree: Path):
    manifest = build(tree)
    duplicate = dict(entry_for(manifest, "leaderboard_llm"))
    duplicate["path"] = "agent-leaderboard.json"
    manifest["artifacts"] = [duplicate, entry_for(manifest, "leaderboard_llm")]
    write(tree, manifest)
    problems = artifacts.check_manifest(tree)
    assert problems


@pytest.mark.parametrize(
    "mutation,expected",
    [
        ({"manifest_version": 2}, "manifest_version"),
        ({"provenance": {"kind": "human", "commit": "a" * 40}}, "git commit"),
        ({"provenance": {"kind": "git_commit", "commit": "nope"}}, "40-hex"),
        ({"artifacts": []}, "no artifacts"),
        ({"artifacts": ["not-an-object"]}, "must be an object"),
    ],
)
def test_a_malformed_manifest_is_refused(tree: Path, mutation: dict, expected: str):
    manifest = build(tree)
    manifest.update(mutation)
    write(tree, manifest)
    problems = artifacts.check_manifest(tree)
    assert any(expected in problem for problem in problems), problems


def test_a_missing_manifest_is_a_failure_not_an_empty_site(tree: Path):
    problems = artifacts.check_manifest(tree)
    assert problems and "does not exist" in problems[0]


def test_a_manifest_that_is_not_json_is_a_failure(tree: Path):
    (tree / artifacts.MANIFEST_NAME).write_text("{ not json", "utf-8")
    problems = artifacts.check_manifest(tree)
    assert problems and "not valid JSON" in problems[0]


def test_a_digest_recorded_as_something_else_entirely_is_refused(tree: Path):
    manifest = build(tree)
    entry_for(manifest, "leaderboard_llm")["sha256"] = "not-a-digest"
    write(tree, manifest)
    problems = artifacts.check_manifest(tree)
    assert any("sha256" in problem for problem in problems)


# -- derived figures --------------------------------------------------------

def test_the_public_counts_are_derived_from_the_leaderboard():
    counts = artifacts.public_counts(LEADERBOARD)
    assert counts == {
        "systems_evaluated": 2,      # model-c has no scored run
        "critical_failures": 12,     # 3 + 9
        "ace_ready": 1,
        "trust_domains": 3,          # DP, RF, MR
    }


def test_an_unscored_model_changes_nothing():
    board = json.loads(json.dumps(LEADERBOARD))
    board["models"].append({"label": "model-d", "vendor": "Vendor D"})
    assert artifacts.public_counts(board) == artifacts.public_counts(LEADERBOARD)


# -- the real tree ----------------------------------------------------------

def test_the_committed_manifest_describes_the_committed_site():
    """The published tree, checked the way the browser will check it."""
    problems = artifacts.check_manifest(SITE_ROOT)
    assert problems == [], problems


def test_the_committed_manifest_is_pinned_to_the_baseline_commit():
    manifest = artifacts.load_manifest(SITE_ROOT)
    assert manifest["provenance"]["commit"] == artifacts.PROVENANCE_COMMIT
    assert manifest["state"] == "approved"
    # Quoted in the task report, so it has to be reproducible from the tree.
    assert artifacts.manifest_digest(manifest) == hashlib.sha256(
        artifacts.canonical_bytes(manifest)
    ).hexdigest()


def test_the_browser_and_the_builder_agree_on_what_a_safe_path_is():
    """Two implementations of one rule; the risk is that they diverge."""
    js = (SITE_ROOT / "ace-artifacts.js").read_text("utf-8")
    python = (SITE_ROOT / "tools" / "ace_artifacts.py").read_text("utf-8")
    pattern = r"[A-Za-z0-9][A-Za-z0-9._-]*"
    assert pattern in js and pattern in python
    for rule in ("'\\\\'", "'..'", "'//'"):
        assert rule in js, rule
    assert "300" in js and "300" in python


def test_the_cli_reports_a_clean_tree_and_a_dirty_one(tmp_path: Path, capsys):
    site = tmp_path / "site"
    site.mkdir()
    for name in ("ace-leaderboard.json", "agent-leaderboard.json"):
        shutil.copy(SITE_ROOT / name, site / name)
    (site / "reports").mkdir()

    assert artifacts.main(["build", "--root", str(site)]) == 0
    assert "wrote" in capsys.readouterr().out

    assert artifacts.main(["check", "--root", str(site)]) == 0
    assert "verified" in capsys.readouterr().out

    (site / "ace-leaderboard.json").write_text("{}", "utf-8")
    assert artifacts.main(["check", "--root", str(site)]) == 1
    out = capsys.readouterr().out
    assert "does not describe this tree" in out

    assert artifacts.main(["digest", "--root", str(site)]) == 0
    assert len(capsys.readouterr().out.strip()) == 64
