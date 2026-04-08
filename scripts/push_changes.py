#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
GOAL_FILES = [
    REPO_ROOT / "TODOS.md",
    *sorted((REPO_ROOT / "docs" / "superpowers" / "plans").glob("*.md")),
]
STOPWORDS = {
    "a", "about", "after", "all", "an", "and", "any", "are", "as", "at", "be",
    "before", "by", "can", "current", "do", "done", "for", "from", "get", "give",
    "has", "have", "if", "in", "into", "is", "it", "its", "just", "like", "may",
    "more", "new", "no", "none", "not", "of", "on", "or", "our", "out", "per",
    "run", "same", "self", "so", "specific", "still", "that", "the", "their",
    "them", "then", "there", "this", "to", "today", "under", "up", "use", "uses",
    "using", "via", "we", "what", "when", "which", "why", "with", "without",
    "work", "write", "yet", "you", "your",
}
CODE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".toml", ".json", ".yaml", ".yml"}
TEST_MARKERS = ("/tests/", "__tests__", "test_")
SUPPORT_FILES = {"README.md", "TODOS.md", "Justfile"}
IGNORED_ANALYSIS_PATHS = {".claude/settings.local.json"}


@dataclass
class DiffSnapshot:
    source_label: str
    files: list[str]
    patch_text: str
    additions: int
    deletions: int
    untracked: list[str]


@dataclass
class GoalSection:
    source_path: str
    title: str
    hierarchy: list[str]
    body: str

    @property
    def title_path(self) -> str:
        return " > ".join(self.hierarchy)

    @property
    def title_tokens(self) -> set[str]:
        return tokenize(self.title_path)

    @property
    def body_tokens(self) -> set[str]:
        return tokenize(self.body)

    @property
    def full_text(self) -> str:
        return f"{self.title_path}\n{self.body}"


@dataclass
class GoalMatch:
    section: GoalSection
    score: int
    title_overlap: set[str]
    body_overlap: set[str]
    path_hits: list[str]


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=check,
        text=True,
        capture_output=True,
    )


def tokenize(text: str) -> set[str]:
    tokens: set[str] = set()
    for token in re.findall(r"[a-z0-9_/-]+", text.lower()):
        normalized = token.strip("_-/")
        if not normalized:
            continue
        for piece in re.split(r"[_/-]", normalized):
            if len(piece) < 3 or piece in STOPWORDS or piece.isdigit():
                continue
            tokens.add(piece)
    return tokens


def detect_diff_source() -> DiffSnapshot:
    status = git("status", "--porcelain").stdout.splitlines()
    untracked = sorted(expand_status_path(line[3:]) for line in status if line.startswith("?? "))
    untracked = flatten_paths(untracked)
    untracked = [path for path in untracked if path not in IGNORED_ANALYSIS_PATHS]

    if status:
        tracked_patch = git("diff", "HEAD", "--find-renames", "--unified=0").stdout
        tracked_numstat = git("diff", "HEAD", "--numstat").stdout
        files = [path for path in parse_numstat_paths(tracked_numstat) if path not in IGNORED_ANALYSIS_PATHS]
        additions, deletions = parse_numstat_totals(tracked_numstat)
        untracked_patch = []
        for path in untracked:
            untracked_abs = REPO_ROOT / path
            if untracked_abs.is_file():
                diff_proc = git("diff", "--no-index", "--", "/dev/null", path, check=False)
                untracked_patch.append(diff_proc.stdout)
                added_lines = untracked_abs.read_text(encoding="utf-8", errors="ignore").splitlines()
                additions += len(added_lines)
            files.append(path)
        return DiffSnapshot(
            source_label="working tree changes",
            files=sorted(set(files)),
            patch_text=tracked_patch + "\n".join(untracked_patch),
            additions=additions,
            deletions=deletions,
            untracked=untracked,
        )

    rev_parse = git("rev-parse", "--verify", "HEAD", check=False)
    if rev_parse.returncode != 0:
        return DiffSnapshot(
            source_label="no git history",
            files=[],
            patch_text="",
            additions=0,
            deletions=0,
            untracked=[],
        )

    patch_text = git("show", "--find-renames", "--format=medium", "--unified=0", "HEAD").stdout
    numstat = git("show", "--numstat", "--format=", "HEAD").stdout
    additions, deletions = parse_numstat_totals(numstat)
    return DiffSnapshot(
        source_label="last commit (HEAD)",
        files=[path for path in parse_numstat_paths(numstat) if path not in IGNORED_ANALYSIS_PATHS],
        patch_text=patch_text,
        additions=additions,
        deletions=deletions,
        untracked=[],
    )


def parse_numstat_totals(text: str) -> tuple[int, int]:
    additions = 0
    deletions = 0
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        add_str, del_str, _ = parts[:3]
        if add_str.isdigit():
            additions += int(add_str)
        if del_str.isdigit():
            deletions += int(del_str)
    return additions, deletions


def parse_numstat_paths(text: str) -> list[str]:
    paths: list[str] = []
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        paths.append(parts[2])
    return paths


def expand_status_path(path: str) -> list[str]:
    candidate = REPO_ROOT / path
    if candidate.is_dir():
        return [
            str(child.relative_to(REPO_ROOT))
            for child in sorted(candidate.rglob("*"))
            if child.is_file()
        ]
    return [path]


def flatten_paths(items: list[list[str]]) -> list[str]:
    flattened: list[str] = []
    for item in items:
        flattened.extend(item)
    return flattened


def parse_goal_sections() -> list[GoalSection]:
    sections: list[GoalSection] = []
    for path in GOAL_FILES:
        if not path.exists():
            continue
        for section in parse_markdown_sections(path):
            if is_actionable_section(section):
                sections.append(section)
    return sections


def parse_markdown_sections(path: Path) -> list[GoalSection]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    sections: list[GoalSection] = []
    heading_stack: list[tuple[int, str]] = []
    current_title: str | None = None
    current_level = 0
    body_lines: list[str] = []

    def flush() -> None:
        nonlocal current_title, body_lines, current_level
        if not current_title:
            return
        body = "\n".join(body_lines).strip()
        hierarchy = [title for _, title in heading_stack[:-1]] + [current_title]
        if current_level >= 2 and body:
            sections.append(
                GoalSection(
                    source_path=str(path.relative_to(REPO_ROOT)),
                    title=current_title,
                    hierarchy=hierarchy,
                    body=body,
                )
            )
        current_title = None
        body_lines = []

    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
        if match:
            flush()
            level = len(match.group(1))
            title = match.group(2).strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
            current_title = title
            current_level = level
            body_lines = []
        else:
            body_lines.append(line)

    flush()
    return sections


def is_actionable_section(section: GoalSection) -> bool:
    source = section.source_path.lower()
    title = section.title_path.lower()
    if source.startswith("docs/superpowers/plans/"):
        return "task " in title
    if "completed" in title and section.source_path == "TODOS.md":
        return False
    return True


def build_diff_tokens(diff: DiffSnapshot) -> set[str]:
    tokens = set()
    for path in diff.files:
        tokens.update(tokenize(path))

    relevant_lines = []
    for line in diff.patch_text.splitlines():
        if line.startswith(("+++", "---", "@@", "diff --git", "index ")):
            continue
        if line.startswith(("+", "-")):
            relevant_lines.append(line[1:])
    tokens.update(tokenize("\n".join(relevant_lines)))
    return tokens


def score_goal(diff: DiffSnapshot, diff_tokens: set[str], section: GoalSection) -> GoalMatch:
    body_overlap = diff_tokens & section.body_tokens
    title_overlap = diff_tokens & section.title_tokens
    section_text = section.full_text.lower()
    path_hits = []
    for path in diff.files:
        basename = Path(path).name.lower()
        stem = Path(path).stem.lower()
        if basename and basename in section_text:
            path_hits.append(path)
        elif stem and len(stem) >= 4 and stem in section_text:
            path_hits.append(path)

    body_score = min(len(body_overlap), 8)
    core_path_hits = [path for path in path_hits if not is_support_file(path)]
    support_path_hits = [path for path in path_hits if is_support_file(path)]
    length_penalty = min(len(section.body_tokens) // 40, 6)
    score = body_score + (len(title_overlap) * 5) + (len(core_path_hits) * 10) + (len(support_path_hits) * 2) - length_penalty
    return GoalMatch(
        section=section,
        score=score,
        title_overlap=title_overlap,
        body_overlap=body_overlap,
        path_hits=sorted(set(path_hits)),
    )


def is_support_file(path: str) -> bool:
    if path in SUPPORT_FILES or path.endswith(".md"):
        return True
    return path.startswith(".claude/")


def classify_progress(diff: DiffSnapshot, matches: list[GoalMatch]) -> tuple[str, str]:
    changed_code = [path for path in diff.files if Path(path).suffix in CODE_EXTENSIONS]
    tests_touched = any(any(marker in path for marker in TEST_MARKERS) for path in diff.files)
    docs_touched = any(path.endswith(".md") for path in diff.files)
    todo_touched = any(path == "TODOS.md" for path in diff.files)
    max_score = matches[0].score if matches else 0

    if max_score >= 35 and changed_code and tests_touched:
        return ("strong", "roughly 50-75% closer on the matched slice")
    if max_score >= 20 and changed_code:
        return ("material", "roughly 25-50% closer on the matched slice")
    if docs_touched or todo_touched:
        return ("light", "roughly 10-25% closer by clarifying or locking the workflow")
    return ("light", "somewhat closer, but the end-state still looks meaningfully incomplete")


def is_specific_match(match: GoalMatch) -> bool:
    core_path_hits = [path for path in match.path_hits if not is_support_file(path)]
    if core_path_hits:
        return True
    if len(match.title_overlap) >= 2:
        return True
    if match.section.source_path == "TODOS.md" and len(match.body_overlap) >= 4:
        return True
    return False


def print_report(diff: DiffSnapshot, matches: list[GoalMatch], ad_hoc_goal: str | None) -> None:
    if not diff.files and not diff.patch_text.strip():
        print("Push Changes Report")
        print("===================")
        print("No changes found to analyze.")
        return

    progress_label, progress_band = classify_progress(diff, matches)
    code_files = [path for path in diff.files if Path(path).suffix in CODE_EXTENSIONS]
    test_files = [path for path in diff.files if any(marker in path for marker in TEST_MARKERS)]
    doc_files = [path for path in diff.files if path.endswith(".md")]

    print("Push Changes Report")
    print("===================")
    print(f"Diff source: {diff.source_label}")
    print(f"Files changed: {len(diff.files)}")
    print(f"Line delta: +{diff.additions} / -{diff.deletions}")
    if diff.untracked:
        print(f"Untracked files included: {', '.join(diff.untracked)}")
    print()

    if ad_hoc_goal:
        print("Ad Hoc Goal")
        print("-----------")
        print(ad_hoc_goal)
        print()

    if matches:
        top = matches[0]
        print("Closest Goal")
        print("------------")
        print(f"{top.section.title_path} [{top.section.source_path}]")
        print(f"Match confidence: {progress_label} (score={top.score})")
        print(f"Estimated lift: {progress_band}")
        if top.path_hits:
            print(f"Goal/file overlap: {', '.join(top.path_hits[:5])}")
        shared_terms = sorted((top.title_overlap | set(list(top.body_overlap)[:6])))
        if shared_terms:
            print(f"Shared terms: {', '.join(shared_terms[:8])}")
        print()

        if len(matches) > 1:
            print("Other Relevant Goals")
            print("--------------------")
            for match in matches[1:3]:
                print(f"- {match.section.title_path} [{match.section.source_path}] score={match.score}")
            print()
    else:
        print("Closest Goal")
        print("------------")
        print("No strong TODO/spec match found. Treating this as an ad hoc task.")
        print(f"Estimated lift: {progress_band}")
        print()

    print("Diff Shape")
    print("----------")
    if code_files:
        print(f"- Code touched: {', '.join(code_files[:6])}")
    if test_files:
        print(f"- Tests touched: {', '.join(test_files[:4])}")
    if doc_files:
        print(f"- Docs touched: {', '.join(doc_files[:4])}")
    if not (code_files or test_files or doc_files):
        print(f"- Files: {', '.join(diff.files[:8])}")
    print()

    print("Progress Read")
    print("-------------")
    if code_files and test_files:
        print("- This change looks implementation-backed and tested, which usually means real forward motion rather than planning churn.")
    elif code_files:
        print("- This change appears to move working code forward, but confidence would improve with tests.")
    elif doc_files:
        print("- This mostly improves process clarity or scope alignment rather than shipping product behavior directly.")
    else:
        print("- This is a support change; it likely unblocks work more than it completes the end goal itself.")

    if matches and matches[0].section.source_path == "TODOS.md":
        print("- It lines up with an explicit TODO, so it likely reduces known project debt rather than creating a parallel track.")
    elif matches:
        print("- It appears aligned with a project plan/spec, so it should make the target workstream more coherent.")
    else:
        print("- Because no documented goal matched strongly, you may want to pass an ad hoc goal note when you run this for better framing.")

    if not test_files and code_files:
        print("- Remaining gap: no test files changed in this diff, so the completion signal is still partial.")
    if not doc_files and matches:
        print("- Remaining gap: no roadmap/spec doc changed, so the repo's written state may still lag the implementation.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze the current diff against TODOs and plan docs, then summarize progress toward a goal."
    )
    parser.add_argument(
        "--goal",
        help="Optional ad hoc goal description to frame the analysis when the work is not clearly tied to an existing TODO/spec.",
    )
    args = parser.parse_args()

    diff = detect_diff_source()
    diff_tokens = build_diff_tokens(diff)
    goal_sections = parse_goal_sections()
    matches = sorted(
        (score_goal(diff, diff_tokens, section) for section in goal_sections),
        key=lambda item: item.score,
        reverse=True,
    )
    matches = [match for match in matches if match.score >= 8 and is_specific_match(match)][:3]
    if args.goal:
        ad_hoc_section = GoalSection(
            source_path="--goal",
            title="Ad hoc goal",
            hierarchy=["Ad hoc goal"],
            body=args.goal,
        )
        ad_hoc_match = score_goal(diff, diff_tokens, ad_hoc_section)
        ad_hoc_match.score += 1000
        matches = sorted([ad_hoc_match, *matches], key=lambda item: item.score, reverse=True)[:3]

    print_report(diff, matches, args.goal)
    return 0


if __name__ == "__main__":
    sys.exit(main())
