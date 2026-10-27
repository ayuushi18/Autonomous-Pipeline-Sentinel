# PipelineSentinel

A data pipeline that watches live feeds for schema and value drift, automatically repairs
safe field renames behind a validation gate, and explains every decision.

**Live demo:** https://your-service-name.onrender.com
(free hosting: the first load after idle time can take up to a minute; the hosted demo
uses saved data snapshots, see "Deployment")

![Overview](docs/overview.png)

## The problem

Pipelines that ingest third-party data break quietly. An API renames a field, changes a
type, switches units, or starts returning empty values, and downstream code keeps running
on bad data. PipelineSentinel detects those changes, repairs the ones it can verify, and
leaves a written record of what it did and why.

## What it does

1. **Detects structural drift:** renamed, added, removed or retyped fields, by exact path
   (for example `$.results[].company.display_name`).
2. **Detects value drift:** shifts in what the numbers say (a unit change, a surge of
   empty values), which a structure check cannot see.
3. **Heals safe renames:** finds the likely old-to-new name, tests the fix against saved
   history, and applies it only if every check passes.
4. **Explains each decision** in plain English and records it in a decision log.

## Architecture

```
Adzuna jobs API ----+
CDC open data ------+--> Prefect flow --> snapshot + schema fingerprint
GTFS-Realtime ------+          |
                               v
             structure drift + value drift (with noise baseline)
                               |
                  rename finder --> patch --> validator
                               |
              apply patch  /  reject  /  no action
                               |
                  decision log + plain-English explanation
```

## How detection works

- **Fingerprints:** a recursive walk of each nested record that stores, for every field
  path, the mix of value types and how often the field appears.
- **Structure drift:** compares two fingerprints and reports added, removed and retyped
  paths and changes in how often a field appears.
- **Value drift:** a two-sample KS-test on each numeric field, alarmed only when the
  KS statistic is at least 0.5, p is below 0.01, and the mean moves by at least 10%
  (a practical-significance rule), plus a check for jumps of 30 or more percentage points
  in the share of empty values. Fields with fewer than 5 values and time-like fields are
  skipped.
- **Noise baseline:** live feeds have fields that normally come and go. The baseline
  learns from the last 10 snapshots and alarms only on changes that are unusual for that
  field: a new field never seen before, a missing field that was present in at least 80%
  of recent snapshots, a type never seen for that field, or a presence rate outside the
  recent range.

## How healing works

1. **Find candidates:** match each removed field to an added field under the same parent,
   scored on name similarity (40%), type match (20%) and value overlap (40%). Only matches
   with confidence of at least 0.6 are kept, one-to-one.
2. **Build a patch** that maps new names back to the original names, so downstream code
   keeps seeing the shape it expects.
3. **Validate** before applying: the structure must be restored, the renamed fields' values
   must still look like the old values, and the patch must change nothing in saved history.
4. **Apply or refuse**, and log the decision.

Design rule: the code decides, the language model only narrates. Explanations come from
the Gemini free tier with a deterministic template as a fallback, so the pipeline never
depends on an LLM.

## Data sources

| Source | Notes |
|---|---|
| Adzuna jobs API | nested JSON, job postings |
| CDC open data (Socrata API) | flat JSON records |
| GTFS-Realtime trip updates (data.texas.gov) | protobuf converted to nested dictionaries |

Three different shapes, so the fingerprinting and drift logic is tested across
heterogeneous feeds without per-source rules.

## Results

All drift below is **synthetic**: a script damages copies of real snapshots in ways whose
correct answer is known. False-alarm figures use real consecutive snapshots with nothing
injected.

**Detection** (280 injected faults, 20 per feed and type, fixed random seeds)

| Drift type | Trials | Detected | Pinned to the exact field |
|---|---|---|---|
| rename | 60 | 100% | 100% |
| remove | 60 | 100% | 100% |
| type change | 60 | 100% | 100% |
| unit change (x100 or x1000) | 40 | 100% | 100% |
| null-out (about 60% emptied) | 60 | 100% | 98% |

**False alarms on real data** (snapshot pairs with nothing injected)

| Feed | Pairs | Alarms before the noise baseline | After |
|---|---|---|---|
| jobs | 12 | 17% | 8% |
| government data | 12 | 0% | 0% |
| transit | 14 | 43% (64% before the value-drift fix) | 14% |

**Self-healing** (injected renames)

| Scenario | Trials | Healed correctly | Rejected | Missed | Wrong fix |
|---|---|---|---|---|---|
| suffix, prefix, case, opaque renames | 120 | 100% | 0% | 0% | 0% |
| rename plus values multiplied by 1000 | 20 | 0% | 15% | 85% | 0% |

**0 unsafe patches applied across 140 injected faults.** When values also changed, the
system did not auto-apply a fix; most of those cases were never matched in the first place.

## What the benchmark changed

The benchmark exposed two problems, and I fixed them after seeing the results:

- The KS-test flagged a 0.3% shift in an almost constant field, so I added the 10%
  mean-change rule (transit false alarms fell from 64% to 43% on this change alone).
- My own injector multiplied a 0/1 direction flag by 1000, which is not a realistic unit
  change; flag-like fields are now excluded from that injection type.

Thresholds were set before benchmarking apart from these two changes.

## Limitations

- Injected drift is large (100x to 1000x unit changes, about 60% emptied). Subtle drift
  would score lower.
- False-alarm samples are small (12 to 14 snapshot pairs per feed).
- Plain-rename tests keep values identical, which is easier than real renames.
- The rename matcher is conservative: when values change along with the name, it usually
  proposes nothing.
- Null-rate shifts under 30 percentage points are not flagged; scale changes in
  mostly-zero fields can be missed.
- The remaining transit false alarms come from the mix of reporting vehicles changing and
  optional fields disappearing, which look like real drift from structure alone.
- It handles renames only. It does not repair removals, type changes or unit changes; it
  raises the alarm and names the field.

## Dashboard and deployment

A Streamlit dashboard with four tabs: Overview, Try it (pick a feed and a kind of damage;
the real detector and healer run live on a small sample), Decision log, and Benchmark.
Packaged with Docker and deployed on Render's free tier.

The hosted demo reads **saved snapshots** bundled into the image (about 10 job postings,
100 government rows, and the first 300 transit entries; job links removed). It does not
call the live feeds. The Try it damage is synthetic, and the decision log combines real
pipeline runs with entries from injected tests. The live pipeline runs locally and is not
hosted.

## Run it locally

```
pip install prefect requests python-dotenv gtfs-realtime-bindings scipy pandas streamlit
```

Create a `.env` file (never commit it):

```
ADZUNA_APP_ID=...
ADZUNA_APP_KEY=...
GEMINI_API_KEY=...        # optional; without it, template explanations are used
```

```
python ingest/flow.py                 # run the pipeline once (run twice to see drift reports)
python -m benchmark.runner            # detection and false-alarm benchmark
python -m benchmark.heal_runner       # self-healing benchmark
streamlit run dashboard/app.py        # dashboard
```

Docker:

```
docker build -t pipelinesentinel .
docker run --rm -p 8501:8501 pipelinesentinel
```

## Layout

```
ingest/       pipeline, fingerprinting, drift checks, rename finder, patcher, validator, healer
benchmark/    fault injector, benchmark runners, results
dashboard/    Streamlit app and bundled demo data
.streamlit/   theme
Dockerfile
```

## Stack

Python 3.13, Prefect, pandas, SciPy, Streamlit, Docker, Render, protobuf (GTFS-Realtime),
Gemini API (free tier).
