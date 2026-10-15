# PipelineSentinel benchmark results

All drift in these tests is synthetic: a script breaks copies of real snapshots in ways whose correct answer is known. False-alarm numbers use real consecutive snapshots with nothing injected.

## 1. Drift detection (injected drift)

| Drift type | Trials | Detected | Localized to the exact field |
|---|---|---|---|
| rename | 60 | 100% (94-100%) | 100% (94-100%) |
| remove | 60 | 100% (94-100%) | 100% (94-100%) |
| type_change | 60 | 100% (94-100%) | 100% (94-100%) |
| unit_scale | 40 | 100% (91-100%) | 100% (91-100%) |
| null_out | 60 | 100% (94-100%) | 98% (91-100%) |

Values in brackets are 95% Wilson confidence intervals. Trials reuse the same base snapshots, so the intervals are optimistic.

No eligible field in govdata for: unit_scale.

## 2. False alarms on real consecutive snapshots

| Source | Snapshot pairs | Raw alarms | With noise filter |
|---|---|---|---|
| jobs | 12 | 2 (17%) | 1 (8%) |
| govdata | 12 | 0 (0%) | 0 (0%) |
| transit | 14 | 6 (43%) | 2 (14%) |

Small samples. Treat these as indicative, not precise.

## 3. Self-healing (injected renames)

| Scenario | Trials | Healed correctly | Rejected | Missed | Wrong fix |
|---|---|---|---|---|---|
| suffix | 30 | 100% | 0% | 0% | 0% |
| prefix | 30 | 100% | 0% | 0% | 0% |
| case | 30 | 100% | 0% | 0% | 0% |
| opaque | 30 | 100% | 0% | 0% | 0% |
| rename+scale | 20 | 0% | 15% | 85% | 0% |

- Plain renames healed correctly: **120 of 120**
- Unsafe patches applied (all scenarios): **0 of 140**
- In the rename+scale scenario most cases were never matched at all, so no patch was proposed. Only a few reached the validator.

## Method notes and limitations

- Thresholds were fixed before benchmarking: KS statistic >= 0.5 with p < 0.01, null-rate jump >= 30 percentage points, baseline window of 10 snapshots, a field must appear in >= 80% of recent snapshots to count as stable.
- Two changes were made after seeing benchmark results: the value check now also requires the mean to move by at least 10%, and the injector skips flag-like fields (5 or fewer distinct values). Each fixed a specific weakness found in diagnosis.
- Injected drift is large (100x or 1000x unit changes, about 60% null-out). Subtle drift would score lower.
- Null-rate shifts under 30 percentage points are not flagged by default, which explains the null_out cases that were detected but not localized.
- Scale changes in fields that are mostly zeros can be missed, because the KS statistic is capped by the share of non-zero values.
- Remaining transit false alarms come from the mix of reporting vehicles changing and optional fields disappearing, which look the same as real drift from structure alone.
- The rename matcher is conservative: when values change along with the name, it usually proposes nothing.
- Plain-rename tests keep values identical, which is easier than real life.
