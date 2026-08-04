# Notch — report generation demo

A small, self-contained demo of how a Notch report gets generated end to end:
from raw voice-journal entries in a database, through one LLM call, through
deterministic chart rendering, to a finished PDF with the charts already
embedded.

This is **not production code**. It's a working thing to run in front of people.
No frontend, no app — just a CLI.

---

## The point of the demo

There's one architectural claim this is built to demonstrate:

> **The LLM reads and writes. Python counts. Matplotlib draws.**

Concretely:

- The LLM is **never** asked to compute a number. Tag counts, percentages,
  entries-per-week, sub-pattern tallies — all of it is plain arithmetic over rows
  we already have, so `db.py` does it in Python. It's free, instant, and exact.
- The LLM is **never** asked to draw a chart. It doesn't emit SVG, HTML, or chart
  markup. It returns structured numbers and labels; `charts.py` renders them with
  matplotlib. That's what makes the charts *guaranteed* accurate rather than
  approximately right.
- Both steps happen inside **one backend pipeline**. By the time
  `generate_report.py` prints "done", the PDF is complete with charts baked in.
  Nothing about charting is deferred to a hypothetical frontend.

The one place the model does real classification work is **semantic
sub-clustering** — splitting the `collaboration` entries into "unblocking
teammates" vs "cross-team work" vs "catching issues before they shipped". That's
a judgment about meaning, not arithmetic, so it's the right job for a model. Even
there the split is clean: **the LLM labels each entry, and Python counts the
labels.** The grouping is the model's call; the percentages on the chart are
exact.

Model is **Claude Haiku 4.5** (`claude-haiku-4-5-20251001`), deliberately — in
the real product this runs on a schedule for every user every week, so it needs
to be the cheap/fast tier. Each report is one call at roughly 500–1,700 input
tokens.

---

## Setup

Needs **Python 3.11+**.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Set your API key — either in a `.env` file (loaded automatically) or as an
environment variable:

```bash
cp .env.example .env      # then edit it
# ...or:
export ANTHROPIC_API_KEY=sk-ant-...
```

Then build the fake database:

```bash
python seed_db.py
```

It prints a summary so you can sanity-check the data before demoing:

```
  Seeded notch.db
  ----------------------------------------------------
  User            Jordan Kim (Software Engineer)
  Entries         52
  Date range      2026-05-06 to 2026-08-03
  Project         Front-End Refactor (2026-06-08 to 2026-07-17, 15 entries)
  Acknowledged    18 entries (34%)

  Tag counts
    wins            22  ######################
    collaboration   21  #####################
    ...
```

`seed_db.py` is safe to re-run — it drops and rebuilds the tables. Dates are
generated relative to the day you run it, so "Last 7 Days" always has content.

---

## Running the three reports

```bash
python generate_report.py --type last7days
python generate_report.py --type project --project "Front-End Refactor"
python generate_report.py --type tag --tag collaboration
```

PDFs land in `output/`, chart PNGs in `output/charts/`.

Each run narrates itself as it goes, which is the part worth watching:

```
  Notch · report generation
  ──────────────────────────────────────────────────────────
  1/5  Fetching entries from SQLite…
     21 entries tagged "collaboration" out of 52 total
  2/5  Computing counts and percentages in Python…
     collaboration is 40.4% of all entries in the period
  3/5  Calling Claude (claude-haiku-4-5-20251001) for narrative + sub-clustering…
     structured response received in 6.2s (1823 in / 1502 out)
     Claude grouped them into 3 sub-patterns; Python counted:
       · Unblocking teammates: 8 entries (38.1%)
       · Cross-team work: 7 entries (33.3%)
       · Catching issues before they shipped: 6 entries (28.6%)
  4/5  Rendering charts with matplotlib (deterministic — no LLM)…
  5/5  Assembling PDF with charts embedded…

  ✓  Report ready — output/tag_collaboration.pdf (60 KB)
```

---

## How this maps to the pipeline

```
  ┌─────────────────────────────────────────────────────────────────┐
  │  generate_report.py  — CLI, orchestrates the five steps         │
  └─────────────────────────────────────────────────────────────────┘
            │
   STEP 1   ▼   db.py                                    [ no LLM ]
   FETCH        Plain SQL. One query per report type:
                last 7 days / by project / by tag.
            │
   STEP 2   ▼   db.py                                    [ no LLM ]
   COUNT        Plain Python arithmetic — tag counts, percentages,
                entries-per-week, recognition filter.
                Free, instant, 100% accurate.
            │
   STEP 3   ▼   llm.py                             [ ONE Claude call ]
   NARRATE      Claude Haiku 4.5, tool-use with a forced JSON schema.
   + CLUSTER    Returns: the narrative sections, which entries are
                "uncounted work", the estimate-vs-actual pulled out of
                prose, and a sub-pattern LABEL for each entry.
                Never returns a count. Never returns chart markup.
            │
            │   ...and the sub-pattern labels go straight back to
            │      db.count_subpatterns() — Python does the tallying.
            │
   STEP 4   ▼   charts.py                                [ no LLM ]
   RENDER       matplotlib takes the numbers from step 2 and draws
                bar charts. Saves PNGs. This step is what guarantees
                the charts match the data.
            │
   STEP 5   ▼   report_builder.py                        [ no LLM ]
   ASSEMBLE     reportlab lays out the 8 sections and embeds the PNGs.
                Output: a finished PDF. Nothing left for a frontend.
```

### Files

| File                 | Its one job                                        |
| -------------------- | -------------------------------------------------- |
| `seed_db.py`         | Build the fake SQLite database                     |
| `db.py`              | SQL queries + all the Python-side arithmetic       |
| `llm.py`             | The single Anthropic call + the forced tool schema |
| `charts.py`          | matplotlib functions: numbers in, PNG path out     |
| `report_builder.py`  | reportlab PDF assembly                             |
| `generate_report.py` | CLI entry point and progress output                |

---

## Report structure

All three types use the same eight sections in the same order:

1. **Opening Snapshot** — a short paragraph plus a stat line
2. **Highlights** — grouped by theme, not chronology
3. **Work That Doesn't Usually Get Counted** — the LLM identifies these
4. **Strengths & Growth** — leads with what's working; growth is framed as
   *building on* a strength, never as a weakness. This is enforced twice: once
   in the system prompt, and once structurally — the tool schema has `strengths`
   and `building_on` fields and no field a "weaknesses" list could go in.
5. **Reflection Questions** — 2, specific to the actual entries
6. **Recognition Received** — every entry with an `acknowledged_by`, pulled
   straight from the database (no LLM — it's a filter, not a judgment)
7. **Data Visualization** — chart images, embedded
8. **Forward Frame** — a closing paragraph pointing at something concrete

Dates always carry the year: `(Jul 29, 2026)` for single dates,
`June 15 – July 30, 2026` for ranges.

### Charts per report type

| Report        | Charts                                                                                  |
| ------------- | --------------------------------------------------------------------------------------- |
| **Last 7 Days** | This week's tag mix (%) vs last week's, grouped bars — the week-over-week comparison    |
| **Project**   | Tag mix across the project · entries per week · estimated vs actual days (if the entries contain it) |
| **Tag**       | The tag as a share of all entries · the within-tag sub-pattern breakdown                |

---

## Notes on the seed data

The fake data is shaped deliberately, because the reports depend on that shape:

- The **last two weeks have opposite tag mixes** — a collaboration-heavy week
  (80% of entries) following a solo-build week (0%). That's what makes the
  week-over-week chart show a real shift rather than noise.
- **"Front-End Refactor"** spans ~6 weeks with 15 entries covering every tag,
  including two that state an estimate and an actual ("thought it'd be a one-day
  job, took three").
- **21 entries are tagged `collaboration`**, falling into three genuinely
  distinguishable sub-patterns — so there's something real for the LLM to find.
- `raw_text` is written the way a person actually talks, not as resume bullets.
  That's the premise of the product: the user rambles, the system does the
  translation.

---

## Failure cases

Handled with a clear message rather than a traceback, so a live demo doesn't die:

- No `ANTHROPIC_API_KEY` → tells you to set it
- No `notch.db` → tells you to run `seed_db.py`
- Unknown project name → lists the projects that do exist
- Unknown tag → lists the tags in use
- No entries in the window → says so
