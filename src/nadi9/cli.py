"""Command line entry. Mock mode is the default and needs no API key."""

import argparse
from pathlib import Path

from nadi9.pipeline import run_episode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evidence-grounded subtitle agent for the fictional dialect Nadi-9."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Learn from the pack and write subtitle decisions")
    run.add_argument("--data", default="data/synthetic", help="Evidence pack directory")
    run.add_argument("--out", default="sample_run", help="Directory for SRT, JSON, and the report")
    run.add_argument("--mode", choices=["mock", "live"], default="mock")
    run.add_argument("--max-model-calls", type=int, default=25)
    run.add_argument("--max-tool-calls", type=int, default=50)

    inspect = sub.add_parser("inspect", help="Show sources, quarantines, and rule statuses")
    inspect.add_argument("--data", default="data/synthetic")
    inspect.add_argument("--max-model-calls", type=int, default=25)
    inspect.add_argument("--max-tool-calls", type=int, default=50)

    explain = sub.add_parser("explain", help="Demonstrate one subtitle decision from evidence to output")
    explain.add_argument("--subtitle", default="S001", help="Subtitle ID to explain (e.g. S001, S008, S012)")
    explain.add_argument("--data", default="data/synthetic", help="Evidence pack directory")
    explain.add_argument("--max-model-calls", type=int, default=25)
    explain.add_argument("--max-tool-calls", type=int, default=50)

    args = parser.parse_args(argv)
    if args.command == "inspect":
        result = run_episode(
            args.data,
            out_dir=None,
            mode="mock",
            max_model_calls=args.max_model_calls,
            max_tool_calls=args.max_tool_calls,
        )
        print("SYNTHETIC DEMO. Nadi-9 is fictional.")
        print(f"Quarantined: {', '.join(sorted(result.quarantined_ids)) or 'none'}")
        print(f"Outliers: {', '.join(result.learned.outlier_examples) or 'none'}")
        for rule in result.learned.rules.values():
            print(f"{rule['id']}: {rule['status']} {rule.get('value') or ''}")
        return 0

    if args.command == "explain":
        result = run_episode(
            args.data,
            out_dir=None,
            mode="mock",
            max_model_calls=args.max_model_calls,
            max_tool_calls=args.max_tool_calls,
        )
        try:
            decision = result.by_id(args.subtitle)
        except KeyError:
            print(f"Error: Subtitle {args.subtitle} not found.")
            valid_ids = [d["subtitle_id"] for d in result.decisions]
            print(f"Available subtitles: {', '.join(valid_ids)}")
            return 1

        speaker = decision.get("speaker") or "Unknown"
        addressee = decision.get("addressee") or "Unknown"
        scene = decision.get("scene") or "Unknown"

        print("=" * 64)
        print(f"SUBTITLE DECISION WALKTHROUGH: {decision['subtitle_id']}")
        print("=" * 64)
        print(f"Source Text        : \"{decision['source_text']}\"")
        print(f"Timing             : {decision['start']} --> {decision['end']}")
        print(f"Speaker Context    : {speaker} -> {addressee} (scene: {scene})")
        print(f"Detected Features  : {', '.join(decision['features']) or 'none'}")
        print("-" * 64)
        print(f"First-Pass Decision: {decision.get('first_pass_decision', 'N/A')}")
        print(f"Reprocessed Event  : {'Yes (after linguist correction C01)' if decision.get('reprocessed') else 'No (untouched by correction)'}")
        print(f"Revision Number    : {decision.get('revision', 1)}")
        print("-" * 64)
        print(f"Final Decision     : {decision['decision']}")
        print(f"Nadi-9 Translation : {decision['nadi_9_text'] or '[EMPTY / ABSTAINED]'}")
        print(f"Confidence Score   : {decision['confidence']:.2f}")
        print(f"Confidence Reason  : {decision['confidence_reason']}")
        if decision.get("review_question"):
            print(f"Review Question    : {decision['review_question']}")
        print("-" * 64)
        print("Evidence Citations :")
        if decision['evidence']:
            for ev in decision['evidence']:
                print(f"  * {ev}")
        else:
            print("  (None - insufficient evidence)")
        if decision.get('assumptions'):
            print("Linguistic Assumptions:")
            for asm in decision['assumptions']:
                print(f"  * {asm}")
        if decision.get('conflicts'):
            print("Blocking Conflicts :")
            for conf in decision['conflicts']:
                print(f"  * {conf}")
        if decision.get('non_blocking_conflicts'):
            print("Non-Blocking Notes :")
            for nb in decision['non_blocking_conflicts']:
                print(f"  * {nb}")
        verifier = decision.get("verifier", {})
        print(f"Verifier Status    : {'PASSED' if verifier.get('passed') else 'FAILED / REJECTED'}")
        if verifier.get("issues"):
            print(f"Verifier Issues    : {'; '.join(verifier['issues'])}")
        print("=" * 64)
        return 0

    result = run_episode(
        args.data,
        args.out,
        mode=args.mode,
        max_model_calls=args.max_model_calls,
        max_tool_calls=args.max_tool_calls,
    )
    approved = sum(1 for item in result.decisions if item["decision"] == "APPROVE")
    review = sum(1 for item in result.decisions if item["decision"] == "HUMAN_REVIEW")
    print(f"Recommendation: DO_NOT_RELEASE ({review} line(s) need review, {approved} approved)")
    print(f"Model calls: {result.model_calls}  Tool calls: {result.tool_calls}")
    print(f"Reprocessed: {', '.join(result.reprocessed_ids) or 'none'}")
    print(f"Wrote artifacts to {Path(args.out).resolve()}")
    return 0
