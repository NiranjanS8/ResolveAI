"""Console analytics report.

Prints exactly the numbers the API serves, because both read the same snapshot
function in ``app.core.metrics``. There is no second implementation to drift.

Usage:
    python analytics_dashboard.py
    python analytics_dashboard.py --range 24h
"""

from __future__ import annotations

import argparse

from app.core.metrics import DEFAULT_RANGE, RANGE_DELTAS, analytics_snapshot


def _percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value}%"


def _usd(value: float | None) -> str:
    return "n/a" if value is None else f"${value:.6f}"


def _seconds(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}s"


def _millis(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0f}ms"


def report(snapshot: dict, range_id: str) -> None:
    volume = snapshot["volume"]
    reply = snapshot["time_to_reply"]
    cost = snapshot["cost"]
    health = snapshot["provider_health"]
    review = snapshot["draft_review"]
    escalation = snapshot["escalation_reasons"]
    guardrails = snapshot["guardrails"]

    print("=" * 68)
    print(f"ResolveAI analytics — {range_id}")
    print("=" * 68)
    print()
    print(snapshot["summary"])
    print()

    print("Deflection")
    print(f"  tickets:        {volume['total']}")
    print(f"  deflected:      {volume['deflected']} ({_percent(volume['deflection_rate'])})")
    print(f"  auto-resolved:  {volume['auto_resolved']}")
    print(f"  agent-resolved: {volume['resolved']}")
    print(f"  needs review:   {volume['draft_for_review']}")
    print(f"  escalated:      {volume['escalated']}")
    print()

    print("Time to first reply")
    if reply["sample_size"]:
        print(f"  sample:         {reply['sample_size']} tickets")
        print(f"  average:        {_seconds(reply['average_seconds'])}")
        print(f"  median:         {_seconds(reply['median_seconds'])}")
        print(f"  p95:            {_seconds(reply['p95_seconds'])}")
    else:
        print("  no replies recorded in this window")
    print()

    print("Cost (USD, from real token usage)")
    print(f"  total:          {_usd(cost['total_cost'])}")
    print(f"  per ticket:     {_usd(cost['cost_per_ticket'])}")
    print(f"  priced calls:   {cost['priced_calls']}")
    if cost["unpriced_calls"]:
        print(f"  unpriced calls: {cost['unpriced_calls']} (no price on file, excluded)")
    print()

    print("Provider health")
    print(f"  calls:          {health['calls']}")
    print(f"  failures:       {health['failures']} ({_percent(health['error_rate'])} error rate)")
    print(f"  latency median: {_millis(health['median_latency_ms'])}")
    print(f"  latency p95:    {_millis(health['p95_latency_ms'])}")
    for task in health["by_task"]:
        print(
            f"    {task['task']:<12} {task['calls']:>4} calls, "
            f"{task['failures']} fail, avg {_millis(task['average_latency_ms'])}, {_usd(task['cost'])}"
        )
    print()

    print("Draft review")
    if review["total_reviewed"]:
        print(f"  reviewed:       {review['total_reviewed']}")
        print(f"  approved as-is: {review['approved_unchanged']} ({_percent(review['acceptance_rate'])})")
        print(f"  edited:         {review['edited']}")
        print(f"  rejected:       {review['rejected']}")
    else:
        print("  no drafts reviewed in this window")
    print()

    print("Escalation reasons")
    if escalation["reasons"]:
        for reason, count in sorted(escalation["reasons"].items(), key=lambda item: -item[1]):
            print(f"  {reason:<28} {count}")
    else:
        print("  no escalations in this window")
    print()

    print("Guardrails")
    print(f"  refund cap interceptions: {guardrails['refund_cap_interceptions']}")
    print(f"  allow-listed dispatches:  {guardrails['allow_listed_dispatches']}")
    print(f"  format deviations:        {guardrails['format_deviations']}")
    print("=" * 68)


def main() -> None:
    parser = argparse.ArgumentParser(description="Print the ResolveAI analytics snapshot.")
    parser.add_argument("--range", default=DEFAULT_RANGE, choices=sorted(RANGE_DELTAS), dest="range_id")
    args = parser.parse_args()
    report(analytics_snapshot(args.range_id), args.range_id)


if __name__ == "__main__":
    main()
