import json
from pathlib import Path

from tools.research_notes.model import load_note, visible_word_count


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "research-notes" / "source"
EXPECTED = {
    "ACE-RN-2026-001": ("Authority Must Shrink, Not Grow", "DRAFT-DAC-01"),
    "ACE-RN-2026-002": ("Revoked Here, Active There", "DRAFT-DAC-01"),
    "ACE-RN-2026-003": ("Replay Without Authority", "DRAFT-DAC-01"),
    "ACE-RN-2026-004": ("Who Did the Agent Act For?", "DRAFT-AID-01"),
    "ACE-RN-2026-005": ("One API Key, Many Agents", "DRAFT-AID-01"),
    "ACE-RN-2026-006": ("Tool Access Is Not Data Authority", "DRAFT-TDA-01"),
    "ACE-RN-2026-007": ("The Over-Tooled Agent", "DRAFT-TDA-01"),
    "ACE-RN-2026-008": (
        "When Tool Metadata Becomes an Instruction",
        "DRAFT-TDA-01",
    ),
    "ACE-RN-2026-009": ("A Decision Without Its Evidence", "DRAFT-DEC-01"),
    "ACE-RN-2026-010": (
        "A Real Citation Can Still Support the Wrong Claim",
        "DRAFT-DEC-01",
    ),
    "ACE-RN-2026-011": ("Logs Are Not Proof", "DRAFT-DEC-01"),
    "ACE-RN-2026-012": (
        "Explanations That Did Not Cause the Decision",
        "DRAFT-DEC-01",
    ),
    "ACE-RN-2026-013": (
        "The Approval Button Is Not Authorization",
        "DRAFT-HITL-01",
    ),
    "ACE-RN-2026-014": (
        "Synthetic Reasoning Theft Without Reasoning Traces",
        "MR-3",
    ),
    "ACE-RN-2026-015": (
        "Encrypted Reasoning That Is Not Bound to Its Owner",
        "TA-3",
    ),
    "ACE-RN-2026-016": (
        "Safe Final Answer, Hazardous Hidden Reasoning",
        "MR-3",
    ),
    "ACE-RN-2026-017": (
        "Private Data Hidden Inside Published Agent Traces",
        "DP-2",
    ),
    "ACE-RN-2026-018": (
        "Invisible Prompt Injection Inside Encrypted Reasoning",
        "AG-5",
    ),
    "ACE-RN-2026-019": ("Refusal Is Not Unlearning", "DP-2"),
    "ACE-RN-2026-020": (
        "A Model That Refuses Everything Is Not Safe",
        "MR-3",
    ),
}


def test_initial_series_contains_exactly_the_approved_twenty_notes():
    paths = sorted(SOURCE.glob("ace-rn-2026-*.json"))
    assert len(paths) == 20
    notes = [load_note(path) for path in paths]
    assert {note["id"] for note in notes} == set(EXPECTED)
    for note in notes:
        title, control = EXPECTED[note["id"]]
        assert note["title"] == title
        assert note["primary_control"] == control
        assert note["author"] == "Chris Ma"
        assert note["status"] == "published"
        assert 800 <= visible_word_count(note) <= 1500


def test_initial_series_covers_all_five_draft_control_tracks():
    controls = set()
    for path in SOURCE.glob("ace-rn-2026-*.json"):
        note = load_note(path)
        controls.add(note["primary_control"])
        controls.update(note["secondary_controls"])
    assert {
        "DRAFT-DAC-01",
        "DRAFT-AID-01",
        "DRAFT-TDA-01",
        "DRAFT-DEC-01",
        "DRAFT-HITL-01",
    } <= controls


def test_initial_series_has_one_x_post_per_note():
    posts = json.loads(
        (ROOT / "research-notes" / "social" / "initial-20-x-posts.json").read_text(
            "utf-8"
        )
    )
    assert {post["id"] for post in posts} == set(EXPECTED)
    for post in posts:
        assert len(post["text"]) <= 280
        assert post["url"].startswith("https://logionace.com/research-notes/")


def test_initial_series_release_schedule_covers_four_notes_per_day():
    schedule = json.loads(
        (
            ROOT
            / "research-notes"
            / "social"
            / "initial-20-release-schedule.json"
        ).read_text("utf-8")
    )
    assert len(schedule) == 5
    assert all(len(day["notes"]) == 4 for day in schedule)
    scheduled = [note_id for day in schedule for note_id in day["notes"]]
    assert len(scheduled) == len(set(scheduled))
    assert set(scheduled) == set(EXPECTED)
