"""
Build and check the LogionACE approved-artifact manifest.

Usage:
    python3 -m tools.ace_artifacts build        # write the manifest and re-pin it
    python3 -m tools.ace_artifacts check        # verify it, exit 1 if it drifted
    python3 -m tools.ace_artifacts digest       # print the manifest's own SHA-256

The public site shows numbers -- how many systems were evaluated, how many
critical failures they had -- and offers evaluation reports for download. Those
numbers and those files are the only things a reader can check us on, so the
site must not be able to publish a figure that came from a draft, from an
internal projection, or from a file that changed after it was approved.

This module is the offline half of that. It walks a fixed set of public files,
records each one's SHA-256, and writes a manifest that names the state
(`approved`) and the provenance commit. `ace-artifacts.js` is the online half:
it re-hashes every file in the browser before anything is rendered or
downloaded, and fails closed if a single digest disagrees.

The manifest itself is anchored. `ace-approved-pin.js` holds the SHA-256 of the
manifest's canonical bytes and the provenance commit, and nothing else. The
browser hashes the manifest it received and compares it to that constant before
it parses a single field, so a manifest that is internally perfect -- correct
digests, `state: approved`, the pinned commit -- is still refused unless somebody
updated the pin in a reviewed commit. `check` enforces the same equality offline,
which is what stops a rebuild from silently becoming a publication.

What the pin is for, and what it is not: it stops an accidental or unapproved
feed -- a rebuilt manifest committed by mistake, a draft copied over the
approved one, a stale CDN object, a second manifest served from somewhere else.
It is not a defence against an attacker who owns this repository: they would
edit the pin in the same commit. That needs a key this repository does not hold,
and is out of scope here.

Two properties matter more than convenience:

  * The build is deterministic. No timestamp, no environment, no dict ordering:
    the same tree produces byte-identical output, so `check` is a real
    comparison and the manifest's own digest can be quoted in a report.
  * Provenance is a commit, not a person. Nobody signed these files off, and
    inventing an approver would be a worse lie than admitting the snapshot is
    "whatever was public on main at b8a00c8". The commit is recorded as the
    approver of record, and the browser refuses a manifest naming another one.

Exit codes: 0 success, 1 the manifest is missing or does not match the tree,
2 misuse.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Iterable, Optional

MANIFEST_NAME = "approved-artifacts.json"

#: The anchor: one small JavaScript file holding two constants and no logic, so
#: that moving the anchor is a one-line diff a reviewer cannot miss.
PIN_NAME = "ace-approved-pin.js"

MANIFEST_VERSION = 1
APPROVED_STATE = "approved"

#: The commit whose published tree is the approved snapshot. Recorded as
#: provenance rather than a human approver, because no human approved it.
PROVENANCE_COMMIT = "b8a00c8ce38c27152837380f50c2c817aa639dd6"
PROVENANCE_REPOSITORY = "logionace.github.io"

#: The public leaderboards. `role` is what the site is allowed to use the file
#: for; the browser looks a file up by role rather than by path, so a manifest
#: cannot quietly repoint "the LLM leaderboard" at some other file.
LEADERBOARDS: tuple[tuple[str, str], ...] = (
    ("leaderboard_llm", "ace-leaderboard.json"),
    ("leaderboard_agent", "agent-leaderboard.json"),
)

#: Downloadable public reports live here and nowhere else.
REPORTS_DIR = "reports"
REPORT_SUFFIX = ".pdf"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")

#: A path in the manifest is a plain relative path inside the published site.
#: Anything else -- absolute, parent-relative, backslashed, schemed,
#: protocol-relative -- is refused rather than normalised, because a path that
#: needs normalising is a path someone is trying something with.
_SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)*$")


class ManifestError(Exception):
    """The manifest, or the tree it describes, is not in a publishable state."""


# -- paths ------------------------------------------------------------------

def is_safe_relative_path(path: object) -> bool:
    """Whether `path` may appear in the manifest.

    Deliberately strict and purely syntactic: no filesystem is consulted, so
    the same rule can be applied byte-for-byte in the browser, where there is
    no filesystem to consult.
    """
    if not isinstance(path, str) or not path or len(path) > 300:
        return False
    if path != path.strip():
        return False
    if "\\" in path or ".." in path or "//" in path:
        return False
    if path.startswith("/") or path.startswith("."):
        return False
    if ":" in path:  # scheme, drive letter, or an alternate data stream
        return False
    return bool(_SAFE_PATH_RE.match(path))


def _require_safe_path(path: object) -> str:
    if not is_safe_relative_path(path):
        raise ManifestError(f"unsafe or malformed artifact path: {path!r}")
    return str(path)


# -- hashing ----------------------------------------------------------------

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(manifest: dict) -> bytes:
    """The manifest's one true serialization.

    `check` compares bytes and the report quotes a digest, so there has to be
    exactly one way to write a given manifest out.
    """
    return (
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def manifest_digest(manifest: dict) -> str:
    return sha256_bytes(canonical_bytes(manifest))


# -- the pin ----------------------------------------------------------------

_PIN_DIGEST_RE = re.compile(r"MANIFEST_SHA256:\s*'([0-9a-f]{64})'")
_PIN_COMMIT_RE = re.compile(r"PROVENANCE_COMMIT:\s*'([0-9a-f]{40})'")

PIN_HEADER = """/*
 * The approved publication anchor. Generated by `tools/ace_artifacts.py build`.
 *
 * MANIFEST_SHA256 is the SHA-256 of the canonical bytes of
 * `approved-artifacts.json`. The browser hashes the manifest it fetched and
 * compares it to this constant before parsing anything, so no manifest is read
 * as approved unless its digest was written here in a reviewed commit.
 *
 * Changing either constant republishes the site's numbers and downloads. Do it
 * deliberately: run `build`, review the diff, and say in the commit message what
 * was approved.
 *
 * Scope: this stops an accidental or unapproved feed -- a manifest rebuilt and
 * committed by mistake, a draft copied over the approved snapshot, a stale
 * cached object, a manifest served from somewhere else. It does not claim to
 * resist a compromised repository, where the same commit would move the pin.
 */
"""


def render_pin(digest: str, commit: str) -> str:
    """The pin file's one true text. Deterministic, so `build` is idempotent."""
    if not _SHA256_RE.match(str(digest or "")):
        raise ManifestError(f"pin digest must be a 64-hex sha256: {digest!r}")
    if not _COMMIT_RE.match(str(commit or "")):
        raise ManifestError(f"pin commit must be a 40-hex git sha: {commit!r}")
    return (
        PIN_HEADER
        + "window.ACE_APPROVED_PIN = Object.freeze({\n"
        + f"  MANIFEST_SHA256: '{digest}',\n"
        + f"  PROVENANCE_COMMIT: '{commit}'\n"
        + "});\n"
    )


def read_pin(root: Path) -> dict:
    """The two pinned constants, or a refusal. Never a default."""
    path = root / PIN_NAME
    if not path.is_file():
        raise ManifestError(f"{PIN_NAME} does not exist; run `build` first")
    body = path.read_text("utf-8")
    digest = _PIN_DIGEST_RE.search(body)
    commit = _PIN_COMMIT_RE.search(body)
    if not digest or not commit:
        raise ManifestError(
            f"{PIN_NAME} does not declare a 64-hex MANIFEST_SHA256 and a 40-hex "
            "PROVENANCE_COMMIT"
        )
    return {
        "manifest_sha256": digest.group(1),
        "provenance_commit": commit.group(1),
    }


def write_manifest(root: Path, manifest: dict) -> bytes:
    """Write the manifest in its canonical form and return the bytes written."""
    body = canonical_bytes(manifest)
    (root / MANIFEST_NAME).write_bytes(body)
    return body


def write_pin(root: Path, manifest: dict) -> str:
    """Move the anchor to `manifest`. Returns the digest now pinned."""
    digest = manifest_digest(manifest)
    (root / PIN_NAME).write_text(
        render_pin(digest, str(manifest["provenance"]["commit"])), "utf-8"
    )
    return digest


# -- building ---------------------------------------------------------------

def _report_paths(root: Path) -> list[str]:
    reports = root / REPORTS_DIR
    if not reports.is_dir():
        return []
    return sorted(
        f"{REPORTS_DIR}/{entry.name}"
        for entry in reports.iterdir()
        if entry.is_file() and entry.suffix.lower() == REPORT_SUFFIX
    )


def _artifact_entry(root: Path, relative: str, role: str) -> dict:
    _require_safe_path(relative)
    absolute = root / relative
    if not absolute.is_file():
        raise ManifestError(f"declared artifact is missing from the tree: {relative}")
    return {
        "path": relative,
        "role": role,
        "sha256": sha256_file(absolute),
        "bytes": absolute.stat().st_size,
    }


def build_manifest(
    root: Path,
    *,
    commit: str = PROVENANCE_COMMIT,
    protocol: Optional[str] = None,
) -> dict:
    """Walk the published tree and describe it.

    Only the files the public site is allowed to read: the two leaderboards and
    the report PDFs. Nothing is discovered recursively beyond `reports/`, so a
    stray file dropped into the repository does not become publishable by
    virtue of existing.
    """
    if not _COMMIT_RE.match(str(commit or "")):
        raise ManifestError(f"provenance commit must be a 40-hex git sha: {commit!r}")

    artifacts = [
        _artifact_entry(root, relative, role) for role, relative in LEADERBOARDS
    ]
    artifacts.extend(
        _artifact_entry(root, relative, "report") for relative in _report_paths(root)
    )

    if protocol is None:
        # Taken from the leaderboard rather than restated, so the manifest
        # cannot claim a protocol version the data was not produced under.
        primary = json.loads((root / LEADERBOARDS[0][1]).read_text("utf-8"))
        protocol = str(primary.get("protocol") or "")

    return {
        "manifest_version": MANIFEST_VERSION,
        "state": APPROVED_STATE,
        "protocol": protocol,
        "provenance": {
            "kind": "git_commit",
            "repository": PROVENANCE_REPOSITORY,
            "commit": commit,
            "basis": (
                "The files published on GitHub main at this commit are treated as "
                "the historical approved snapshot. The commit is the approver of "
                "record; no individual signed these artifacts off."
            ),
        },
        "artifacts": sorted(artifacts, key=lambda entry: entry["path"]),
    }


# -- checking ---------------------------------------------------------------

def validate_manifest_shape(manifest: object) -> dict:
    """Structural checks that do not need the tree.

    The same rules the browser applies, in the same order, so a manifest that
    the site would refuse also fails here -- at build time, where somebody is
    watching.
    """
    if not isinstance(manifest, dict):
        raise ManifestError("manifest must be a JSON object")
    if manifest.get("manifest_version") != MANIFEST_VERSION:
        raise ManifestError(
            f"unsupported manifest_version: {manifest.get('manifest_version')!r}"
        )
    if manifest.get("state") != APPROVED_STATE:
        raise ManifestError(
            f"manifest state must be {APPROVED_STATE!r}, not "
            f"{manifest.get('state')!r}"
        )

    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        raise ManifestError("manifest is missing its provenance")
    if provenance.get("kind") != "git_commit":
        raise ManifestError("provenance must be a git commit")
    if not _COMMIT_RE.match(str(provenance.get("commit") or "")):
        raise ManifestError("provenance commit must be a 40-hex git sha")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ManifestError("manifest lists no artifacts")

    seen_paths: set[str] = set()
    roles: set[str] = set()
    for entry in artifacts:
        if not isinstance(entry, dict):
            raise ManifestError("every artifact must be an object")
        path = _require_safe_path(entry.get("path"))
        if path in seen_paths:
            raise ManifestError(f"artifact listed twice: {path}")
        seen_paths.add(path)
        if not _SHA256_RE.match(str(entry.get("sha256") or "")):
            raise ManifestError(f"artifact {path} has no usable sha256")
        size = entry.get("bytes")
        if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise ManifestError(f"artifact {path} has no usable byte length")
        role = str(entry.get("role") or "")
        if not role:
            raise ManifestError(f"artifact {path} declares no role")
        if role.startswith("leaderboard_"):
            if role in roles:
                raise ManifestError(f"two artifacts claim the role {role}")
            roles.add(role)

    for role, _path in LEADERBOARDS:
        if role not in roles:
            raise ManifestError(f"manifest is missing the {role} artifact")
    return manifest


def load_manifest(root: Path) -> dict:
    path = root / MANIFEST_NAME
    if not path.is_file():
        raise ManifestError(f"{MANIFEST_NAME} does not exist; run `build` first")
    try:
        return json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"{MANIFEST_NAME} is not valid JSON: {exc}") from exc


def check_manifest(
    root: Path, *, expected_commit: str = PROVENANCE_COMMIT
) -> list[str]:
    """Verify the manifest on disk against the tree. Returns the problems found.

    Every digest is recomputed. A manifest that merely parses is not a manifest
    that describes these files.

    The provenance commit is compared against the one the site is pinned to, the
    same rule `ace-artifacts.js` applies. A manifest can be internally
    consistent -- rebuilt around a draft leaderboard, every digest correct -- and
    still not be the approved snapshot; the commit is what distinguishes them.
    """
    problems: list[str] = []
    try:
        manifest = validate_manifest_shape(load_manifest(root))
    except ManifestError as exc:
        return [str(exc)]

    # The pin first, because it is the check the browser makes first, and
    # because a manifest nobody pinned is not published however correct it is.
    raw = (root / MANIFEST_NAME).read_bytes()
    canonical = canonical_bytes(manifest)
    if raw != canonical:
        problems.append(
            f"{MANIFEST_NAME} is not in canonical form; the browser hashes the "
            "bytes it receives, so run `build` to rewrite it"
        )
    try:
        pin = read_pin(root)
    except ManifestError as exc:
        problems.append(str(exc))
    else:
        pinned = pin["manifest_sha256"]
        actual = sha256_bytes(canonical)
        if pinned != actual:
            problems.append(
                f"the pin in {PIN_NAME} is {pinned[:12]}, but this manifest is "
                f"{actual[:12]}; run `build` to move the anchor deliberately"
            )
        if pin["provenance_commit"] != str(manifest["provenance"]["commit"]):
            problems.append(
                f"the pin in {PIN_NAME} names commit "
                f"{pin['provenance_commit'][:12]}, the manifest names "
                f"{str(manifest['provenance']['commit'])[:12]}"
            )

    commit = str(manifest["provenance"]["commit"])
    if commit != expected_commit:
        problems.append(
            f"provenance commit is {commit[:12]}, but this site is pinned to "
            f"{expected_commit[:12]}"
        )

    for entry in manifest["artifacts"]:
        relative = str(entry["path"])
        absolute = root / relative
        if not absolute.is_file():
            problems.append(f"{relative}: listed in the manifest but missing")
            continue
        actual = sha256_file(absolute)
        if actual != entry["sha256"]:
            problems.append(
                f"{relative}: sha256 is {actual}, manifest says {entry['sha256']}"
            )
        size = absolute.stat().st_size
        if size != entry["bytes"]:
            problems.append(
                f"{relative}: {size} bytes on disk, manifest says {entry['bytes']}"
            )

    # Anything publishable that nobody declared is as much of a problem as a
    # bad digest: it would be a file on the public site that no approval covers.
    declared = {str(e["path"]) for e in manifest["artifacts"]}
    for role, relative in LEADERBOARDS:
        if relative not in declared:
            problems.append(f"{relative}: publishable but not declared ({role})")
    for relative in _report_paths(root):
        if relative not in declared:
            problems.append(f"{relative}: publishable but not declared (report)")

    rebuilt = build_manifest(
        root,
        commit=str(manifest["provenance"]["commit"]),
        protocol=str(manifest.get("protocol") or ""),
    )
    if canonical_bytes(rebuilt) != canonical_bytes(manifest):
        problems.append(
            "the manifest does not match a fresh build of this tree; "
            "run `build` and review the diff"
        )
    return problems


# -- derived figures --------------------------------------------------------

def public_counts(leaderboard: dict) -> dict:
    """The homepage figures, derived from the approved leaderboard.

    Kept here so the Python tests can assert the same arithmetic the browser
    does. Nothing is stored: a stored count is a count that can drift from the
    file it came from, which is the whole failure this manifest exists to
    prevent.
    """
    models = [m for m in (leaderboard.get("models") or []) if isinstance(m, dict)]
    scored = [m for m in models if isinstance(m.get("bare"), dict)]
    domains: set[str] = set()
    critical = 0
    ready = 0
    for model in scored:
        bare = model["bare"]
        critical += int(bare.get("critical_exception_count") or 0)
        verdict = str(bare.get("verdict") or "")
        if verdict == "ACE Ready":
            ready += 1
        for key in (bare.get("domains") or {}):
            domains.add(str(key))
    return {
        "systems_evaluated": len(scored),
        "critical_failures": critical,
        "ace_ready": ready,
        "trust_domains": len(domains),
    }


# -- CLI --------------------------------------------------------------------

def _print_problems(problems: Iterable[str]) -> None:
    for problem in problems:
        print(f"  - {problem}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m tools.ace_artifacts",
        description=__doc__.split("\n\n")[0],
    )
    parser.add_argument(
        "command", choices=("build", "check", "digest"),
    )
    parser.add_argument(
        "--root",
        default=".",
        help="the published site directory (default: the current one)",
    )
    parser.add_argument(
        "--commit",
        default=PROVENANCE_COMMIT,
        help="provenance commit to record when building, or to require when checking",
    )
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()

    try:
        if args.command == "build":
            manifest = build_manifest(root, commit=args.commit)
            validate_manifest_shape(manifest)
            try:
                previous = read_pin(root)["manifest_sha256"]
            except ManifestError:
                previous = None
            write_manifest(root, manifest)
            digest = write_pin(root, manifest)
            print(
                f"wrote {MANIFEST_NAME}: {len(manifest['artifacts'])} artifacts, "
                f"state={manifest['state']}, "
                f"provenance={manifest['provenance']['commit'][:12]}"
            )
            print(f"manifest sha256: {digest}")
            if previous is None:
                print(f"wrote the pin in {PIN_NAME}: {digest}")
            elif previous == digest:
                print(f"pin in {PIN_NAME} unchanged: {digest[:12]}")
            else:
                print(
                    f"MOVED the pin in {PIN_NAME}: {previous[:12]} -> "
                    f"{digest[:12]} -- this republishes the public numbers and "
                    "downloads; review the diff before committing"
                )
            return 0

        if args.command == "digest":
            print(manifest_digest(validate_manifest_shape(load_manifest(root))))
            return 0

        problems = check_manifest(root, expected_commit=args.commit)
        if problems:
            print(f"{MANIFEST_NAME} does not describe this tree:")
            _print_problems(problems)
            return 1
        manifest = load_manifest(root)
        print(
            f"{MANIFEST_NAME} verified: {len(manifest['artifacts'])} artifacts, "
            f"every sha256 recomputed."
        )
        print(f"manifest sha256: {manifest_digest(manifest)}")
        print(f"pin in {PIN_NAME} agrees.")
        return 0
    except ManifestError as exc:
        print(f"error: {exc}")
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
