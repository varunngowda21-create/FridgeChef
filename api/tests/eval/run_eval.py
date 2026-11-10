"""Command-line runner for the FridgeChef vision evaluation harness.

Usage:
    python tests/eval/run_eval.py [--mode {fixture,live}] [--report-file PATH] [--markdown-report PATH] [--verbose]

Default mode is 'fixture' (zero cost, deterministic).
'live' mode runs live Groq vision API calls and requires valid GROQ_API_KEY and DATABASE_URL.
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Add api root to sys.path so app and tests are importable
API_ROOT = Path(__file__).resolve().parents[2]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from tests.eval.metrics import EvaluationSummary, generate_markdown_report  # noqa: E402
from tests.eval.runner import EvaluationRunConfig, run_full_evaluation  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("fridgechef.eval.cli")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run FridgeChef Vision Evaluation against labeled scenarios."
    )
    parser.add_argument(
        "--mode",
        choices=["fixture", "live"],
        default="fixture",
        help="Evaluation mode: 'fixture' (deterministic baseline) or 'live' (live Groq API). Default: fixture.",
    )
    parser.add_argument(
        "--report-file",
        type=str,
        default=None,
        help="Path to save JSON summary report.",
    )
    parser.add_argument(
        "--markdown-report",
        type=str,
        default=None,
        help="Path to save human-readable Markdown evaluation report.",
    )
    parser.add_argument(
        "--precision-threshold",
        type=float,
        default=0.80,
        help="Target precision threshold (default: 0.80 per PRD 14.4).",
    )
    parser.add_argument(
        "--recall-threshold",
        type=float,
        default=0.60,
        help="Target recall threshold (default: 0.60 per PRD 14.4).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed scenario and ingredient breakdowns.",
    )
    return parser.parse_args()


def print_summary_table(summary: EvaluationSummary, verbose: bool = False) -> None:
    print("\n" + "=" * 70)
    print("FRIDGECHEF AI — VISION EVALUATION SUMMARY REPORT")
    print("=" * 70)
    print(f"Total Scenarios Evaluated:         {summary.total_scenarios} (Target >= 40)")
    print(f"Target Indian Ingredients:         {summary.covered_ingredients_count}/{summary.total_target_ingredients} covered (100%)")
    print("-" * 70)
    p_status = "PASS" if summary.micro_precision >= summary.target_precision_threshold else "FAIL"
    r_status = "PASS" if summary.micro_recall >= summary.target_recall_threshold else "FAIL"
    print(f"Micro Precision:                   {summary.micro_precision:.4f}  [Target >= {summary.target_precision_threshold:.2f}] -> [{p_status}]")
    print(f"Micro Recall:                      {summary.micro_recall:.4f}  [Target >= {summary.target_recall_threshold:.2f}] -> [{r_status}]")
    print(f"Micro F1 Score:                    {summary.micro_f1:.4f}")
    print(f"Macro Precision:                   {summary.macro_precision:.4f}")
    print(f"Macro Recall:                      {summary.macro_recall:.4f}")
    print(f"Macro F1 Score:                    {summary.macro_f1:.4f}")
    print("-" * 70)
    print(f"Avg False Positives / Scenario:    {summary.average_false_positives_per_scenario:.4f}")
    print(f"Scenarios Needing User Correction: {summary.percentage_scenarios_needing_user_correction:.1f}%")
    print(f"Overall Acceptance Target:         {'MET (PASSED)' if summary.meets_targets else 'FAILED'}")
    print("=" * 70)

    if verbose:
        print("\nPER-INGREDIENT PERFORMANCE (30 TARGET INGREDIENTS):")
        print(f"{'Ingredient':<22} {'TP':<4} {'FP':<4} {'FN':<4} {'Prec':<7} {'Rec':<7} {'F1':<7}")
        print("-" * 60)
        for ing_id, met in sorted(summary.per_ingredient_metrics.items()):
            print(
                f"{ing_id:<22} {met.true_positives:<4} {met.false_positives:<4} "
                f"{met.false_negatives:<4} {met.precision:<7.2f} {met.recall:<7.2f} {met.f1:<7.2f}"
            )
        print("=" * 70)


async def main_async() -> int:
    args = parse_args()
    config = EvaluationRunConfig(
        mode=args.mode,
        precision_threshold=args.precision_threshold,
        recall_threshold=args.recall_threshold,
        validate_image_bytes=True,
    )

    db_session = None
    if args.mode == "live":
        print("\n[INFO] Initializing live database session for Groq LLM tracking...")
        from app.db.session import SessionLocal
        db_session = SessionLocal()

    try:
        summary = await run_full_evaluation(config=config, db=db_session)
        print_summary_table(summary, verbose=args.verbose)

        # Save JSON report if requested
        if args.report_file:
            report_path = Path(args.report_file).resolve()
            report_path.parent.mkdir(parents=True, exist_ok=True)
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(summary.to_dict(), f, indent=2)
            print(f"[INFO] JSON report written to: {report_path}")

        # Save Markdown report if requested
        if args.markdown_report:
            md_path = Path(args.markdown_report).resolve()
            md_path.parent.mkdir(parents=True, exist_ok=True)
            md_content = generate_markdown_report(summary)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(md_content)
            print(f"[INFO] Markdown report written to: {md_path}")

        return 0 if summary.meets_targets else 1

    finally:
        if db_session is not None:
            db_session.close()


def main() -> None:
    code = asyncio.run(main_async())
    sys.exit(code)


if __name__ == "__main__":
    main()
