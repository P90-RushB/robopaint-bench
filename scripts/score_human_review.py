#!/usr/bin/env python3
"""Validate and aggregate optional blinded human preference reviews offline."""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

from prepare_human_review import (CHOICES, KEY_SCHEMA, PRIMARY_ATTEMPT, ROOT, SCHEMA,
                                 ReviewError, load_dataset, local_output, rater_identity, read_json)


def validate_key(key: dict, manifest: dict) -> None:
    if key.get("schema") != KEY_SCHEMA or key.get("selection") != manifest["selection"]:
        raise ReviewError("Administrator key does not match the current canvas selection")
    for field in ("dataset_sha256", "selection_sha256"):
        if key.get(field) != manifest[field]:
            raise ReviewError("Dataset identity mismatch")
    if key.get("primary_attempt") != PRIMARY_ATTEMPT or key.get("reference_sha256") != manifest["selection"]["reference"]["sha256"]:
        raise ReviewError("Reference target or primary attempt mismatch")
    mapping = key.get("attempt_mapping", {})
    selected = manifest["selection"]["canvases"]
    if len(mapping) != 11 or sorted(mapping.values(), key=lambda item: item["model_id"]) != selected:
        raise ReviewError("Invalid anonymous attempt mapping")
    expected = {frozenset(pair) for pair in itertools.combinations(mapping, 2)}
    pairs = key.get("pairs", [])
    actual = [frozenset([pair.get("a"), pair.get("b")]) for pair in pairs]
    if len(pairs) != 55 or len({pair.get("pair_id") for pair in pairs}) != 55 or set(actual) != expected:
        raise ReviewError("Administrator key must contain every unordered pair exactly once")


def validate_review(review: dict, key: dict) -> list[tuple[str, str, str]]:
    if review.get("schema") != SCHEMA:
        raise ReviewError("Unknown review schema")
    for field in ("package_id", "rater_id", "dataset_sha256", "selection_sha256", "reference_sha256", "primary_attempt"):
        if review.get(field) != key.get(field):
            raise ReviewError(f"Review {field} does not match its administrator key")
    rater_identity(review["rater_id"])
    if review.get("independence_attestation") is not True:
        raise ReviewError("Review lacks a self-declared independence attestation")
    answers = review.get("answers", [])
    expected = {pair["pair_id"]: pair for pair in key["pairs"]}
    if not isinstance(answers, list) or len(answers) != 55 or len({a.get("pair_id") for a in answers}) != 55:
        raise ReviewError("A complete review must answer all 55 pairs exactly once")
    result = []
    for answer in answers:
        pair = expected.get(answer.get("pair_id"))
        if pair is None or any(answer.get(side) != pair[side] for side in ("a", "b")):
            raise ReviewError("Unknown pair or altered A/B presentation")
        choice = answer.get("choice")
        if choice not in CHOICES:
            raise ReviewError("Invalid review choice")
        result.append((key["attempt_mapping"][pair["a"]]["model_id"],
                       key["attempt_mapping"][pair["b"]]["model_id"], choice))
    return result


def score(dataset: Path, site_root: Path, key_paths: list[Path], review_paths: list[Path]) -> dict:
    if not review_paths:
        raise ReviewError("At least one completed review is required")
    manifest, _ = load_dataset(dataset, site_root)
    keys = {}
    for path in key_paths:
        key = read_json(path)
        validate_key(key, manifest)
        package = key.get("package_id")
        if not isinstance(package, str) or not package or package in keys:
            raise ReviewError("Missing or duplicated administrator package ID")
        keys[package] = key
    totals = {item["model_id"]: {"wins": 0, "losses": 0, "ties": 0, "cannot_judge": 0}
              for item in manifest["selection"]["canvases"]}
    pair_totals = {pair: {"left_wins": 0, "right_wins": 0, "ties": 0, "cannot_judge": 0}
                   for pair in itertools.combinations(sorted(totals), 2)}
    raters, package_ids = set(), set()
    for path in review_paths:
        review = read_json(path)
        key = keys.get(review.get("package_id"))
        if key is None:
            raise ReviewError("A review has no matching administrator key")
        answers = validate_review(review, key)
        rater = rater_identity(review["rater_id"])
        if rater in raters or review["package_id"] in package_ids:
            raise ReviewError("Duplicate rater ID or review package; each rater may contribute once")
        raters.add(rater)
        package_ids.add(review["package_id"])
        for a, b, choice in answers:
            ordered = tuple(sorted([a, b]))
            pair_counts = pair_totals[ordered]
            if choice in ("tie", "cannot_judge"):
                category = "ties" if choice == "tie" else "cannot_judge"
                totals[a][category] += 1
                totals[b][category] += 1
                pair_counts[category] += 1
            else:
                winner, loser = (a, b) if choice == "A" else (b, a)
                totals[winner]["wins"] += 1
                totals[loser]["losses"] += 1
                pair_counts["left_wins" if winner == ordered[0] else "right_wins"] += 1
    rows = []
    for model, count in totals.items():
        denominator = count["wins"] + count["losses"] + count["ties"]
        opponents = []
        for pair, pair_counts in pair_totals.items():
            if model not in pair:
                continue
            votes = pair_counts["left_wins"] + pair_counts["right_wins"] + pair_counts["ties"]
            wins = pair_counts["left_wins" if model == pair[0] else "right_wins"]
            opponents.append({"opponent": pair[1] if model == pair[0] else pair[0],
                              "judged_comparisons": votes, "cannot_judge": pair_counts["cannot_judge"],
                              "tie_adjusted_win_rate": (wins + .5 * pair_counts["ties"]) / votes if votes else None})
        rates = [opponent["tie_adjusted_win_rate"] for opponent in opponents]
        mean_rate = sum(rates) / 10 if all(rate is not None for rate in rates) else None
        rows.append({"model_id": model, **count, "judged_comparisons": denominator,
                     "presented_comparisons": denominator + count["cannot_judge"],
                     "tie_adjusted_win_rate": mean_rate,
                     "preference_score_100": 100 * mean_rate if mean_rate is not None else None,
                     "opponents": opponents})
    enough_raters = len(raters) >= 3
    pending_pairs = [{"models": list(pair), "valid_votes": count["left_wins"] + count["right_wins"] + count["ties"],
                      "cannot_judge": count["cannot_judge"]}
                     for pair, count in pair_totals.items()
                     if count["left_wins"] + count["right_wins"] + count["ties"] < 3]
    for row in rows:
        row["descriptive_preference_score_100"] = row["preference_score_100"]
        row["score_status"] = "complete_primary" if enough_raters and not pending_pairs else "provisional_incomplete_coverage"
        if row["score_status"] != "complete_primary":
            row["preference_score_100"] = None
    # Rates describe this fixed 11-model, attempt-3 cohort. They are not a success
    # rate, significance test or generalization estimate to other robot tasks.
    ranking = None
    if enough_raters and not pending_pairs:
        ranking, last_rate, rank = [], None, 0
        for index, row in enumerate(sorted(rows, key=lambda r: (-r["tie_adjusted_win_rate"], r["model_id"])), 1):
            if row["tie_adjusted_win_rate"] != last_rate:
                rank = index
                last_rate = row["tie_adjusted_win_rate"]
            ranking.append({"rank": rank, "model_id": row["model_id"], "tie_adjusted_win_rate": row["tie_adjusted_win_rate"],
                            "preference_score_100": row["preference_score_100"]})
    return {"schema": "robopaint.human-review-scores.v1", "case_id": "golden_gate",
            "dataset_sha256": manifest["dataset_sha256"], "selection_sha256": manifest["selection_sha256"],
            "reference_sha256": manifest["selection"]["reference"]["sha256"], "primary_attempt": PRIMARY_ATTEMPT,
            "complete_raters": len(raters), "required_complete_raters_for_ranking": 3,
            "minimum_valid_votes_per_pair": 3, "pending_pairs": pending_pairs,
            "ranking_status": "eligible_descriptive" if ranking is not None else "withheld",
            "withheld_reason": None if ranking is not None else ("At least three complete distinct self-declared independent raters are required." if not enough_raters else "Every unordered pair requires at least three valid votes; cannot_judge does not count as a valid vote."),
            "method": "For each opponent: (wins + 0.5 * ties) / (wins + losses + ties). Average the ten opponent rates equally; multiply by 100 for preference_score_100. cannot_judge is excluded from denominators and reported separately.",
            "identity_limit": "Rater identity and independence are self-declared, not externally verified.",
            "scope": "Optional human-rated descriptive comparison of one fixed final attempt per model; no statistical significance or general capability claim. This does not gate an attributed owner recommendation.",
            "scores": rows, "ranking": ranking}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "benchmarks/results/golden_gate.json")
    parser.add_argument("--site-root", type=Path, default=ROOT / "site")
    parser.add_argument("--keys", nargs="+", required=True, type=Path)
    parser.add_argument("--reviews", nargs="+", required=True, type=Path)
    parser.add_argument("--output", type=Path, required=True, help="New JSON file under local_save/")
    args = parser.parse_args()
    try:
        output = local_output(args.output)
        if output.exists():
            raise ReviewError("Refusing to overwrite an existing score file")
        result = score(args.dataset, args.site_root, args.keys, args.reviews)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(result, indent=2) + "\n")
    except (ReviewError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        parser.exit(2, f"Review scoring failed: {error}\n")
    print(f"Validated {result['complete_raters']} complete rater(s). Ranking: {result['ranking_status']}. Output: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
