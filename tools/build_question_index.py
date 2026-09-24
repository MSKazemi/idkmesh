#!/usr/bin/env python3
"""Generate the public 100-question discovery map from the canonical topic pages."""

from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "seo-topics-v1.json"
OUTPUT = ROOT / "docs" / "questions.md"

QUESTION_RE = re.compile(r"^### (.+\?)$", re.MULTILINE)


class QuestionIndexError(ValueError):
    """The topic/question architecture cannot be rendered safely."""


def load_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def question_entries() -> list[dict[str, object]]:
    payload = load_config()
    entries: list[dict[str, object]] = []
    seen: set[str] = set()

    for cluster in payload["clusters"]:
        source = ROOT / cluster["path"]
        source_text = source.read_text(encoding="utf-8")
        questions = QUESTION_RE.findall(source_text)
        if len(questions) != 10:
            raise QuestionIndexError(
                f"{cluster['id']}: expected 10 questions, found {len(questions)}"
            )

        for question_number, question in enumerate(questions, start=1):
            if question in seen:
                raise QuestionIndexError(f"duplicate question: {question}")
            seen.add(question)
            anchor = f"q{question_number:02d}"
            expected = f'<a id="{anchor}"></a>\n### {question}'
            if expected not in source_text:
                raise QuestionIndexError(
                    f"{cluster['id']}: {question!r} is missing stable anchor #{anchor}"
                )

        entries.append(
            {
                "id": cluster["id"],
                "title": cluster["title"],
                "url": cluster["url"],
                "questions": questions,
            }
        )

    total = sum(len(entry["questions"]) for entry in entries)
    if len(entries) != 10 or total != 100:
        raise QuestionIndexError(
            f"expected 10 clusters / 100 questions, found {len(entries)} / {total}"
        )
    return entries


def render() -> str:
    payload = load_config()
    entries = question_entries()
    lines = [
        "---",
        'title: "100 Questions About AI Agent Verification, Orchestration, and Trust — IDKMesh"',
        'description: "A navigable map of 100 practical questions about AI agent verification, orchestration, code review, evaluator reliability, governance, provenance, interoperability, and scaling."',
        'image: "/assets/idkmesh-social.png"',
        "---",
        "",
        "# 100 questions about AI agent verification, orchestration, and trust",
        "",
        "This page is a **question map**, not a collection of thin duplicate answers.",
        "Each question links to one of ten substantial IDKMesh topic guides where the",
        "answer is explained with the relevant architecture, contracts, experiments,",
        "limitations, and repository evidence.",
        "",
        "The questions are generated from the actual question headings in the topic",
        "guides. The machine-readable 100-intent map remains",
        "[`config/seo-topics-v1.json`](https://github.com/MSKazemi/idkmesh/blob/main/config/seo-topics-v1.json).",
        "",
        "Use this page when you know the question you want to ask; use the",
        "[topic hub](https://mskazemi.com/idkmesh/topics/) when you want to browse by",
        "problem area.",
        "",
    ]

    number = 1
    for entry in entries:
        lines.extend(
            [
                f"## {entry['title']}",
                "",
                f"Detailed guide: [{entry['title']}]({entry['url']})",
                "",
            ]
        )
        for question_number, question in enumerate(entry["questions"], start=1):
            anchor = f"q{question_number:02d}"
            lines.append(f"{number}. [{question}]({entry['url']}#{anchor})")
            number += 1
        lines.append("")

    lines.extend(
        [
            "## How this map is maintained",
            "",
            "- The ten topic pages remain the answer sources; this page only indexes them.",
            "- A question appears here only if it is an actual `### ...?` heading on a topic page.",
            "- Each question has a stable `#q01` through `#q10` anchor on its pillar so the map links directly to the answer passage.",
            "- CI requires exactly 100 unique questions across exactly ten topic clusters.",
            "- Exact-match keyword repetition and one-page-per-query doorway patterns are intentionally avoided.",
            "- Search visibility is measured separately from crawlability; see the",
            "  [search and answer-engine visibility evidence](https://github.com/MSKazemi/idkmesh/tree/main/evidence/search-visibility).",
            "",
            f"**Last reviewed:** {payload['reviewed_at']}.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    OUTPUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
