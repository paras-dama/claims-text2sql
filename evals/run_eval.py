"""
Runs the eval question set against the pipeline for a given provider,
scores ambiguity-detection accuracy, and prints a summary report.

Usage:
    python -m evals.run_eval --provider groq
    python -m evals.run_eval --provider groq --provider gemini --provider openai
"""

import argparse
import json
import time
from pathlib import Path

from app.orchestrator.pipeline import run_pipeline

QUESTIONS_PATH = Path(__file__).parent / "test_questions.json"


def load_questions() -> list[dict]:
    with open(QUESTIONS_PATH) as f:
        return json.load(f)


def run_single_eval(question_item: dict, provider: str) -> dict:
    start = time.time()
    try:
        result = run_pipeline(question_item["question"], provider=provider)
        actual_status = result["status"]
        error = None
    except Exception as e:
        actual_status = "error"
        error = str(e)
    elapsed = round(time.time() - start, 2)

    expected_status = question_item["expected_status"]
    correct = actual_status == expected_status

    return {
        "id": question_item["id"],
        "question": question_item["question"],
        "expected_status": expected_status,
        "actual_status": actual_status,
        "correct": correct,
        "elapsed_seconds": elapsed,
        "error": error,
    }


def run_eval_for_provider(provider: str) -> dict:
    questions = load_questions()
    results = [run_single_eval(q, provider) for q in questions]

    total = len(results)
    correct_count = sum(1 for r in results if r["correct"])

    # Break down accuracy by expected status, to distinguish "missed
    # ambiguity" (false negatives) from "unnecessary clarification"
    # (false positives) — these are different failure modes worth
    # tracking separately.
    ambiguous_questions = [r for r in results if r["expected_status"] == "needs_clarification"]
    clear_questions = [r for r in results if r["expected_status"] == "ready"]

    ambiguous_correct = sum(1 for r in ambiguous_questions if r["correct"])
    clear_correct = sum(1 for r in clear_questions if r["correct"])

    return {
        "provider": provider,
        "total_questions": total,
        "overall_accuracy": round(correct_count / total, 3) if total else 0,
        "ambiguity_detection_recall": (
            round(ambiguous_correct / len(ambiguous_questions), 3)
            if ambiguous_questions else None
        ),
        "clear_question_precision": (
            round(clear_correct / len(clear_questions), 3)
            if clear_questions else None
        ),
        "avg_elapsed_seconds": round(
            sum(r["elapsed_seconds"] for r in results) / total, 2
        ) if total else 0,
        "results": results,
    }


def print_report(report: dict):
    print(f"\n{'=' * 60}")
    print(f"PROVIDER: {report['provider']}")
    print(f"{'=' * 60}")
    print(f"Overall accuracy: {report['overall_accuracy'] * 100:.1f}%")
    print(f"Ambiguity detection recall: {report['ambiguity_detection_recall']}")
    print(f"  (of questions that SHOULD trigger clarification, how many did)")
    print(f"Clear question precision: {report['clear_question_precision']}")
    print(f"  (of unambiguous questions, how many correctly skipped clarification)")
    print(f"Avg response time: {report['avg_elapsed_seconds']}s")
    print(f"\nPer-question results:")
    for r in report["results"]:
        mark = "PASS" if r["correct"] else "FAIL"
        print(f"  [{mark}] {r['id']}: expected={r['expected_status']}, got={r['actual_status']}")
        if r["error"]:
            print(f"         error: {r['error']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--provider", action="append", required=True,
        help="Provider to eval (repeat flag for multiple, e.g. --provider groq --provider gemini)",
    )
    args = parser.parse_args()

    all_reports = []
    for provider in args.provider:
        report = run_eval_for_provider(provider)
        print_report(report)
        all_reports.append(report)

    if len(all_reports) > 1:
        print(f"\n{'=' * 60}")
        print("COMPARISON SUMMARY")
        print(f"{'=' * 60}")
        for r in all_reports:
            print(
                f"{r['provider']:10s} | overall: {r['overall_accuracy']*100:5.1f}% "
                f"| ambiguity recall: {r['ambiguity_detection_recall']} "
                f"| clear precision: {r['clear_question_precision']} "
                f"| avg time: {r['avg_elapsed_seconds']}s"
            )

    # Save raw results for later reference/README material
    output_path = Path(__file__).parent / "last_run_results.json"
    with open(output_path, "w") as f:
        json.dump(all_reports, f, indent=2)
    print(f"\nFull results saved to {output_path}")


if __name__ == "__main__":
    main()