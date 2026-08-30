"""Turn the starter-task catalogue into ready-to-file GitHub issues.

`docs/community/STARTER_TASKS.md` exists because every newcomer-labelled issue
in this repository was an independent-review request, which is a bootstrapping
deadlock: the one advertised way in requires exactly the person the project is
trying to attract. The catalogue opens other doors — but a document is not a
door. Nobody browsing the issue list ever sees it.

This tool closes that gap without hand-copying nine sections into a web form,
and without letting a script file issues on its own initiative.

**It prints a plan and stops.** Filing anything requires `--post`, an explicit
choice a person makes after reading the plan. There is no configuration, flag
combination, or environment variable that makes posting the default.

Two tasks are never filed:

- any task whose section already names a tracking issue, which is how `V1`
  stays pointed at issue 167 instead of forking a duplicate of it;
- any task whose rendered title already matches an open issue, so a second run
  after a partial failure files only the remainder.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = REPO_ROOT / "docs/community/STARTER_TASKS.md"
BLOB_ROOT = "https://github.com/MSKazemi/idkmesh/blob/main"
CATALOGUE_DIR = "docs/community"
CATALOGUE_URL = f"{BLOB_ROOT}/{CATALOGUE_DIR}/STARTER_TASKS.md"

# Every starter task is newcomer-facing by construction, so these two are
# unconditional. The discipline label is additive and only used where the
# repository already has a matching label; no label is ever created.
BASE_LABELS = ("good first issue", "help wanted")
DISCIPLINE_LABELS = {
    "Documentation": ("documentation",),
    "Research": ("research",),
    "Tooling": ("enhancement",),
}

_MARKDOWN_LINK = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<target>[^)\s]+)\)")
_SECTION = re.compile(r"^### (?P<id>[A-Z]+\d+) — (?P<title>.+)$")
_DISCIPLINE = re.compile(r"^## (?P<name>.+)$")
_TRACKED = re.compile(r"Tracked as issue `#(?P<number>\d+)`")


def absolutise_links(markdown: str, *, source_dir: str = CATALOGUE_DIR) -> str:
    """Rewrite the catalogue's relative links so they survive in an issue body.

    A relative markdown target in a file resolves against that file's
    directory. The same text in a GitHub issue body resolves against the
    repository root, so every link in `docs/community/STARTER_TASKS.md` would
    arrive broken — `onboarding-tests/x.md` would point at a path that does not
    exist. Absolute blob URLs are the only form that means the same thing in
    both places.
    """

    def replace(match: re.Match[str]) -> str:
        target = match.group("target")
        if target.startswith(("http://", "https://", "#", "mailto:")):
            return match.group(0)
        path, _, fragment = target.partition("#")
        resolved = PurePosixPath(source_dir).joinpath(path)
        # PurePosixPath keeps '..' segments verbatim, so collapse them by hand.
        parts: list[str] = []
        for part in resolved.parts:
            if part == "..":
                if parts:
                    parts.pop()
            elif part not in (".", ""):
                parts.append(part)
        url = f"{BLOB_ROOT}/{'/'.join(parts)}"
        if fragment:
            url = f"{url}#{fragment}"
        return f"[{match.group('text')}]({url})"

    return _MARKDOWN_LINK.sub(replace, markdown)


@dataclass(frozen=True)
class Task:
    identifier: str
    heading: str
    discipline: str
    body: str
    tracked_issue: int | None = None
    labels: tuple[str, ...] = field(default_factory=tuple)

    @property
    def issue_title(self) -> str:
        # Backticks read badly in an issue list and carry no meaning there.
        return f"Starter task {self.identifier}: {self.heading.replace('`', '')}"

    @property
    def anchor(self) -> str:
        slug = re.sub(r"[^a-z0-9 -]", "", self.heading.lower()).replace(" ", "-")
        return f"{self.identifier.lower()}--{slug}"

    @property
    def issue_body(self) -> str:
        return (
            f"{absolutise_links(self.body).strip()}\n\n"
            "---\n\n"
            f"Catalogued as **{self.identifier}** under *{self.discipline}* in "
            f"[`docs/community/STARTER_TASKS.md`]({CATALOGUE_URL}). That file is "
            "the authority — it is checked against the repository by "
            "`tests/test_starter_tasks.py`, so if the two disagree, the "
            "catalogue is right and this issue is stale.\n\n"
            "Please read [`CONTRIBUTING.md`](https://github.com/MSKazemi/idkmesh/blob/main/CONTRIBUTING.md) "
            "before opening a pull request, in particular the closing-keyword "
            "rule: reference this issue with `Refs:`, never with a closing "
            "keyword.\n\n"
            "Negative results count. If you attempt this and conclude it should "
            "not be done, that write-up is the contribution."
        )


def parse_catalogue(text: str) -> list[Task]:
    tasks: list[Task] = []
    discipline = ""
    identifier = heading = None
    buffer: list[str] = []

    def flush() -> None:
        if identifier is None or heading is None:
            return
        body = "\n".join(buffer).strip()
        tracked = _TRACKED.search(body)
        labels = BASE_LABELS + DISCIPLINE_LABELS.get(discipline, ())
        tasks.append(
            Task(
                identifier=identifier,
                heading=heading,
                discipline=discipline,
                body=body,
                tracked_issue=int(tracked.group("number")) if tracked else None,
                labels=labels,
            )
        )

    for line in text.splitlines():
        if line.strip() == "---":
            # A horizontal rule ends a section without opening a new one.
            flush()
            identifier = heading = None
            buffer = []
            continue
        section = _SECTION.match(line)
        if section:
            flush()
            identifier = section.group("id")
            heading = section.group("title").strip()
            buffer = []
            continue
        discipline_match = _DISCIPLINE.match(line)
        if discipline_match:
            flush()
            identifier = heading = None
            buffer = []
            discipline = discipline_match.group("name").strip()
            continue
        if identifier is not None:
            buffer.append(line)
    flush()
    return tasks


def open_issue_titles() -> set[str]:
    result = subprocess.run(
        [
            "gh",
            "issue",
            "list",
            "--state",
            "open",
            "--limit",
            "200",
            "--json",
            "title",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return {row["title"] for row in json.loads(result.stdout)}


def plan(tasks: list[Task], existing: set[str]) -> tuple[list[Task], list[str]]:
    fileable: list[Task] = []
    skipped: list[str] = []
    for task in tasks:
        if task.tracked_issue is not None:
            skipped.append(
                f"{task.identifier}: already tracked as issue "
                f"#{task.tracked_issue}"
            )
        elif task.issue_title in existing:
            skipped.append(f"{task.identifier}: an open issue already has this title")
        else:
            fileable.append(task)
    return fileable, skipped


def create_issue(task: Task) -> str:
    command = [
        "gh",
        "issue",
        "create",
        "--title",
        task.issue_title,
        "--body",
        task.issue_body,
    ]
    for label in task.labels:
        command += ["--label", label]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python tools/publish_starter_tasks.py",
        description=(
            "Print the issues the starter-task catalogue would file. Filing "
            "them requires --post."
        ),
    )
    parser.add_argument(
        "--post",
        action="store_true",
        help="actually create the issues; without it this only prints the plan",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="print each rendered issue body in the plan, not just its title",
    )
    args = parser.parse_args()

    tasks = parse_catalogue(CATALOGUE.read_text(encoding="utf-8"))
    existing = open_issue_titles() if args.post else set()
    fileable, skipped = plan(tasks, existing)

    print(f"catalogue: {len(tasks)} tasks; would file {len(fileable)}")
    for note in skipped:
        print(f"  skip  {note}")
    for task in fileable:
        print(f"  file  {task.issue_title}")
        print(f"        labels: {', '.join(task.labels)}")
        if args.full:
            print()
            print(task.issue_body)
            print()

    if not args.post:
        print()
        print("Nothing was filed. Re-run with --post to create these issues.")
        return 0

    for task in fileable:
        print(create_issue(task))
    return 0


if __name__ == "__main__":
    sys.exit(main())
