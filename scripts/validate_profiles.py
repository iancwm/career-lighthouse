#!/usr/bin/env python3
"""
Sprint 2 pre-validation: test whether YAML career profiles improve answer quality.

Usage:
    cd /home/iancwm/git/career-lighthouse
    uv run python scripts/validate_profiles.py investment_banking
    uv run python scripts/validate_profiles.py consulting
    uv run python scripts/validate_profiles.py tech_product

    # Compare with/without profile side-by-side:
    uv run python scripts/validate_profiles.py investment_banking --compare

The script calls Claude directly (no Qdrant, no KB chunks) to isolate the
profile's contribution. The question is: does structured YAML context alone
produce meaningfully better answers than the bare system prompt?

If yes → build the retrieval pipeline.
If no → redesign the schema before investing in the pipeline.
"""

import argparse
import os
import sys
import textwrap
from pathlib import Path

import yaml

# Import canonical formatter from the API service layer so the validation script
# and production code use identical context block formatting.
sys.path.insert(0, str(Path(__file__).parent.parent / "api"))
from services.career_profiles import profile_to_context_block  # noqa: E402

# ---------------------------------------------------------------------------
# Questions — realistic messages a target student would actually send
# ---------------------------------------------------------------------------
QUESTIONS_BY_TRACK = {
    "investment_banking": [
        "Which banks in Singapore actually hire international students? I'm worried about EP sponsorship.",
        "I'm from India with a finance degree. What's my realistic chance of breaking into IBD here?",
        "When should I start applying for summer internships if I want Goldman or JPMorgan?",
        "What's the starting salary for an analyst at a bulge bracket in Singapore?",
        "Do I need to worry about COMPASS scoring? My friend said it could block my EP.",
        "Is DBS IBD a good option for international students, or do they prefer locals?",
        "I don't have a finance degree — I studied Computer Science. Can I still get into investment banking?",
        "What's the difference between working at a BB versus DBS or OCBC?",
        "How many interview rounds does Goldman Sachs typically do for their Singapore IBD internship?",
        "What's the most common reason international students fail to get EP sponsorship in finance?",
    ],
    "consulting": [
        "I want to work at McKinsey Singapore. What are my chances as an international student?",
        "When do MBB applications open and how much time do I need to prepare for case interviews?",
        "What's the salary difference between MBB and Big 4 consulting in Singapore?",
        "I'm not from a business school — I studied engineering. Can I still get into BCG?",
        "Will EP sponsorship be a problem if I get an offer from Bain?",
        "How many cases should I practice before applying to MBB?",
        "Is Oliver Wyman different from McKinsey in terms of what kind of work you do?",
        "What clubs or activities at SMU help most for getting into consulting?",
        "I got rejected by MBB last year. What should I do differently this year?",
        "What's the realistic timeline from application to offer at McKinsey Singapore?",
    ],
    "tech_product": [
        "I want to work at Google Singapore after graduation. What's the process?",
        "Is Grab or Sea a good option compared to FAANG for international students?",
        "What salary should I expect at a tech MNC in Singapore as a fresh grad SWE?",
        "I'm targeting product management roles. What's the realistic path at SMU?",
        "Will small startups sponsor my EP or is that too risky to count on?",
        "How much LeetCode do I actually need to get into Google or Meta?",
        "What's the difference between an APM programme and a regular PM hire?",
        "I studied Information Systems, not Computer Science. Does that matter for tech roles?",
        "When do tech companies start hiring for grad roles — is there a specific season?",
        "I received a remote offer from a tech company. Does that count for EP purposes?",
    ],
}

SYSTEM_PROMPT_BASE = (
    "You are a knowledgeable career advisor at SMU (Singapore Management University). "
    "Answer questions using the provided knowledge base and any career context provided. "
    "Always cite which document or source your advice comes from. "
    "Be specific to this school's career paths and recruiting relationships. "
    "If you don't have relevant information, say so honestly."
)


def load_profile(track: str) -> dict:
    profiles_dir = Path(__file__).parent.parent / "knowledge" / "career_profiles"
    path = profiles_dir / f"{track}.yaml"
    if not path.exists():
        print(f"ERROR: Profile not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        return yaml.safe_load(f)



def ask_claude(client, system: str, question: str) -> str:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=system,
        messages=[{"role": "user", "content": question}],
    )
    return response.content[0].text


def run_questions(client, system: str, questions: list[str],
                  label: str) -> list[str]:
    answers = []
    for i, q in enumerate(questions, 1):
        print(f"\n  [{label}] Q{i}: {q}")
        answer = ask_claude(client, system, q)
        print(f"  A{i}: {textwrap.fill(answer, width=90, initial_indent='     ',
                                        subsequent_indent='     ')}")
        answers.append(answer)
    return answers


def run_threshold_check(threshold: float = 0.70) -> None:
    """Check cosine similarity between all 20-question sets and all 5 career type name vectors.

    Used to validate that the CAREER_TYPE_MATCH_THRESHOLD in chat_router.py is reasonable:
    - Messages that clearly reference a career track should score >= threshold against it
    - Messages that reference a different track should score lower

    Run before implementing the cosine matching logic in chat_router.py:
        uv run python scripts/validate_profiles.py --threshold-check
        uv run python scripts/validate_profiles.py --threshold-check --threshold 0.60
    """
    try:
        import numpy as np
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("ERROR: sentence-transformers not installed. Run: pip install sentence-transformers", file=sys.stderr)
        sys.exit(1)

    profiles_dir = Path(__file__).parent.parent / "knowledge" / "career_profiles"
    # display_names: shown in output. match_texts: embedded for cosine comparison (matches service).
    display_names: dict[str, str] = {}
    match_texts: dict[str, str] = {}
    for yaml_path in sorted(profiles_dir.glob("*.yaml")):
        with open(yaml_path) as f:
            profile = yaml.safe_load(f)
        slug = yaml_path.stem
        if not profile.get("match_cosine", True):
            continue  # excluded from cosine switching — skip in threshold check
        display_names[slug] = str(profile.get("career_type", slug))
        match_texts[slug] = str(profile.get("match_description") or profile.get("career_type", slug)).strip()

    if not display_names:
        print("ERROR: No career profiles found in knowledge/career_profiles/", file=sys.stderr)
        sys.exit(1)

    print(f"\nLoading all-MiniLM-L6-v2 for threshold check (threshold={threshold})...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    slugs = list(display_names.keys())
    texts_to_embed = [match_texts[s] for s in slugs]
    name_vecs = model.encode(texts_to_embed, normalize_embeddings=True)  # shape: (n_types, 384)

    print(f"\n{'='*80}")
    print(f"COSINE THRESHOLD CHECK: threshold={threshold}")
    print(f"Career types: {', '.join(display_names[s] for s in slugs)}")
    print(f"{'='*80}\n")

    all_pass = True
    for track_slug, questions in QUESTIONS_BY_TRACK.items():
        track_display = display_names.get(track_slug, track_slug)
        target_idx = slugs.index(track_slug) if track_slug in slugs else -1
        print(f"\n── {track_display} ({len(questions)} questions) ──")

        pass_count = 0
        for q in questions:
            q_vec = model.encode(q, normalize_embeddings=True)
            scores = np.dot(name_vecs, q_vec)  # cosine similarity (normalized)
            best_idx = int(np.argmax(scores))
            best_score = float(scores[best_idx])
            best_name = display_names[slugs[best_idx]]
            correct = target_idx >= 0 and best_idx == target_idx and best_score >= threshold
            if correct:
                pass_count += 1
            status = "PASS" if correct else "FAIL"
            print(f"  [{status}] score={best_score:.3f} matched={best_name!r:30s} | {q[:60]}")

        track_pass_rate = pass_count / len(questions) if questions else 0
        if track_pass_rate < 0.7:
            all_pass = False
        print(f"  → {pass_count}/{len(questions)} questions matched correct track at threshold {threshold}")

    print(f"\n{'='*80}")
    if all_pass:
        print(f"THRESHOLD OK: threshold={threshold} looks reasonable for these question sets.")
    else:
        print(f"THRESHOLD WARNING: Some tracks scored poorly at threshold={threshold}.")
        print("Consider: lowering the threshold, OR embedding richer description strings")
        print("instead of just career type names (e.g., 'Investment Banking finance analyst Goldman').")
    print(f"{'='*80}\n")


def main():
    parser = argparse.ArgumentParser(description="Validate career profile YAML quality")
    parser.add_argument("track", nargs="?", choices=list(QUESTIONS_BY_TRACK.keys()),
                        help="Career track to test (required unless --threshold-check)")
    parser.add_argument("--compare", action="store_true",
                        help="Run questions both WITH and WITHOUT the profile for side-by-side comparison")
    parser.add_argument("--questions-only", action="store_true",
                        help="Print questions for this track and exit (no API calls)")
    parser.add_argument("--threshold-check", action="store_true",
                        help="Check cosine similarity scores across all question sets to validate the "
                             "CAREER_TYPE_MATCH_THRESHOLD before implementing chat_router.py cosine logic")
    parser.add_argument("--threshold", type=float, default=0.70,
                        help="Threshold value to validate against (default: 0.70)")
    args = parser.parse_args()

    if args.threshold_check:
        run_threshold_check(threshold=args.threshold)
        return

    if not args.track:
        parser.error("track is required unless --threshold-check is used")

    questions = QUESTIONS_BY_TRACK[args.track]  # type: ignore[index]

    if args.questions_only:
        print(f"\n10 questions for '{args.track}':")
        for i, q in enumerate(questions, 1):
            print(f"  {i}. {q}")
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        # Try reading from .env in repo root
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set. Add to .env or export it.", file=sys.stderr)
        sys.exit(1)

    import anthropic  # noqa: PLC0415 — lazy import; not needed for --threshold-check
    client = anthropic.Anthropic(api_key=api_key)
    profile = load_profile(args.track)
    context_block = profile_to_context_block(profile)
    system_with_profile = f"{SYSTEM_PROMPT_BASE}\n\n{context_block}"

    print(f"\n{'='*80}")
    print(f"PROFILE VALIDATION: {profile['career_type']}")
    print(f"{'='*80}")
    print(f"\nProfile injected ({len(context_block)} chars). Running {len(questions)} questions...\n")

    if args.compare:
        print("─── WITHOUT PROFILE (baseline) ───")
        run_questions(client, SYSTEM_PROMPT_BASE, questions, "BASE")
        print("\n─── WITH PROFILE ───")
        run_questions(client, system_with_profile, questions, "WITH")
    else:
        run_questions(client, system_with_profile, questions, "WITH")

    print(f"\n{'='*80}")
    print("DONE. Evaluate: are these answers meaningfully better than what ChatGPT would produce?")
    print("If yes → build the retrieval pipeline.")
    print("If no  → redesign the schema before investing further.")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
