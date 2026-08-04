"""
charts.py — STEP 3 of the pipeline: turn numbers into pictures. NO LLM HERE.

ONE JOB: take plain Python numbers and save a PNG.

This is the file that makes the "chart accuracy" claim true. Every function below
takes numbers that were already computed in db.py — arithmetic over real rows — and
draws exactly those numbers. There is no model in this step, so there is nothing
that can round wrong, transpose a figure, or invent a bar.

The alternative approach — asking the LLM to output SVG or chart HTML directly — is
what we're specifically NOT doing. A model drawing a chart is a model estimating
where to put the rectangles. This way the model never touches the geometry.

Every function returns the path it wrote to, so the PDF builder can just embed it.
"""

import os

import matplotlib

# "Agg" is the non-interactive backend — we're writing files, not opening windows.
# This has to be set before pyplot is imported.
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "charts")

# A small, deliberately boring palette. Blue and orange are the first two slots of
# a colorblind-safe categorical order — they stay distinguishable under protanopia,
# deuteranopia and tritanopia, and both clear 3:1 contrast on this surface.
SURFACE = "#fcfcfb"
INK = "#0b0b0b"          # primary text
INK_MUTED = "#898781"    # axis labels, tick marks
AXIS = "#c3c2b7"         # baseline and gridlines
SERIES_1 = "#2a78d6"     # blue  — "this week", "estimated", the tag in focus
SERIES_2 = "#eb6834"     # orange — "last week", "actual"
NEUTRAL = "#c3c2b7"      # for the "everything else" share

DPI = 150


def _ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _style_axes(ax, ylabel=None):
    """
    Shared chart furniture: recessive grid, no box around the plot.

    The data should be the loudest thing on the chart. Gridlines and axes are
    support structure, so they're thin and light.
    """
    ax.set_facecolor(SURFACE)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=INK_MUTED, labelsize=9, length=0)
    ax.yaxis.grid(True, color=AXIS, linewidth=0.6, alpha=0.6)
    ax.set_axisbelow(True)  # gridlines behind the bars, not on top of them
    if ylabel:
        ax.set_ylabel(ylabel, color=INK_MUTED, fontsize=9)


def _label_bars(ax, bars, suffix="", fmt="{:.0f}"):
    """
    Write each bar's value just above it.

    Labels use text ink, not the bar's colour — the coloured bar right beside the
    number already carries the identity, so tinting the text too just makes it
    harder to read.
    """
    for bar in bars:
        height = bar.get_height()
        ax.annotate(
            fmt.format(height) + suffix,
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
            color=INK,
        )


def _finish(fig, filename):
    """Save and close. Closing matters — matplotlib figures leak if you don't."""
    _ensure_output_dir()
    path = os.path.join(OUTPUT_DIR, filename)
    fig.patch.set_facecolor(SURFACE)
    fig.tight_layout()
    fig.savefig(path, dpi=DPI, facecolor=SURFACE)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# LAST 7 DAYS — week-over-week tag mix
# ---------------------------------------------------------------------------

def week_over_week_tag_mix(this_week, last_week, filename="week_over_week.png"):
    """
    Grouped bars: this week's tag mix (%) beside last week's, one group per tag.

    `this_week` and `last_week` are {tag: percent} dicts straight out of
    db.tag_mix_percent(). This is the report's "compare to something that happened
    in the past" chart — it's the difference between "you collaborated a lot" and
    "you collaborated a lot more than you did last week".
    """
    tags = list(this_week.keys())
    positions = range(len(tags))
    width = 0.38
    gap = 0.02  # a hair of surface between the paired bars so they read as two marks

    fig, ax = plt.subplots(figsize=(7.2, 3.4))

    bars_now = ax.bar(
        [p - width / 2 - gap / 2 for p in positions],
        [this_week[t] for t in tags],
        width, label="This week", color=SERIES_1,
    )
    bars_prev = ax.bar(
        [p + width / 2 + gap / 2 for p in positions],
        [last_week[t] for t in tags],
        width, label="Last week", color=SERIES_2,
    )

    _style_axes(ax, ylabel="% of entries")
    ax.set_xticks(list(positions))
    ax.set_xticklabels([t.capitalize() for t in tags])
    _label_bars(ax, bars_now, suffix="%")
    _label_bars(ax, bars_prev, suffix="%")

    # Two series, so a legend is required — colour alone must never be the only
    # way to tell which bar is which.
    legend = ax.legend(frameon=False, fontsize=9, loc="upper right")
    for text in legend.get_texts():
        text.set_color(INK)

    ax.set_ylim(0, max([*this_week.values(), *last_week.values(), 10]) * 1.25)
    return _finish(fig, filename)


# ---------------------------------------------------------------------------
# PROJECT — tag mix, effort over time, estimate vs actual
# ---------------------------------------------------------------------------

def tag_mix(mix, title, filename="tag_mix.png"):
    """
    Single-series bars: the tag mix (%) across a whole project.

    One series, so no legend — the title says what the bars are.
    """
    tags = list(mix.keys())
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    bars = ax.bar([t.capitalize() for t in tags], [mix[t] for t in tags],
                  width=0.6, color=SERIES_1)
    _style_axes(ax, ylabel="% of entries")
    ax.set_title(title, color=INK, fontsize=10, pad=12, loc="left")
    _label_bars(ax, bars, suffix="%")
    ax.set_ylim(0, max([*mix.values(), 10]) * 1.25)
    return _finish(fig, filename)


def entries_per_week(labels, counts, title, filename="entries_per_week.png"):
    """
    Single-series bars: how many entries landed in each week of the project.

    Shows where the effort actually clustered — which weeks were heavy and which
    were quiet. Counts are whole numbers, so the y-axis uses integer ticks only.
    """
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    bars = ax.bar(labels, counts, width=0.55, color=SERIES_1)
    _style_axes(ax, ylabel="entries")
    ax.set_title(title, color=INK, fontsize=10, pad=12, loc="left")
    _label_bars(ax, bars)
    ax.set_ylim(0, max(counts + [1]) * 1.3)
    ax.set_yticks(range(0, max(counts + [1]) + 1))
    return _finish(fig, filename)


def estimate_vs_actual(task, estimated_days, actual_days, filename="estimate_vs_actual.png"):
    """
    Two labelled bars: what the work was estimated at, versus what it took.

    The numbers come from the LLM, because pulling "thought it'd take a day, took
    three" out of conversational prose is a reading task. But once extracted they're
    just two numbers, and this function draws them literally — the model doesn't get
    to decide how tall the bars are.
    """
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    bars = ax.bar(["Estimated", "Actual"], [estimated_days, actual_days],
                  width=0.45, color=[SERIES_1, SERIES_2])
    _style_axes(ax, ylabel="days")
    ax.set_title(task, color=INK, fontsize=10, pad=12, loc="left")
    _label_bars(ax, bars, suffix="d", fmt="{:g}")
    ax.set_ylim(0, max(estimated_days, actual_days, 1) * 1.3)
    return _finish(fig, filename)


# ---------------------------------------------------------------------------
# TAG — share of the period, and the within-tag breakdown
# ---------------------------------------------------------------------------

def tag_share(tag, tag_percent, other_percent, filename="tag_share.png"):
    """
    Two bars: this tag as a share of every entry in the period.

    The tag in focus gets the accent colour; "everything else" gets a neutral, so
    the eye lands on the number that matters.
    """
    fig, ax = plt.subplots(figsize=(4.6, 3.0))
    bars = ax.bar([tag.capitalize(), "Everything else"], [tag_percent, other_percent],
                  width=0.45, color=[SERIES_1, NEUTRAL])
    _style_axes(ax, ylabel="% of all entries")
    _label_bars(ax, bars, suffix="%", fmt="{:g}")
    ax.set_ylim(0, 100)
    return _finish(fig, filename)


def subpattern_breakdown(subpatterns, title, filename="subpatterns.png"):
    """
    Horizontal bars: the sub-patterns the LLM found inside a single tag.

    Horizontal because sub-pattern names are phrases ("Catching issues before they
    shipped") and phrases don't fit under a vertical bar without rotating them.

    Worth being precise about where these numbers came from: the LLM decided which
    sub-pattern each entry belongs to (a judgment about meaning), and then Python
    counted the labels (arithmetic). So the grouping is a model's call, but the
    percentages on this chart are exact.

    `subpatterns` is [{"name": ..., "count": ..., "percent": ...}].
    """
    names = [s["name"] for s in subpatterns][::-1]      # reversed: biggest at top
    percents = [s["percent"] for s in subpatterns][::-1]
    counts = [s["count"] for s in subpatterns][::-1]

    fig, ax = plt.subplots(figsize=(7.2, 0.55 * len(names) + 1.6))
    bars = ax.barh(names, percents, height=0.55, color=SERIES_1)

    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.tick_params(colors=INK_MUTED, labelsize=9, length=0)
    ax.xaxis.grid(True, color=AXIS, linewidth=0.6, alpha=0.6)
    ax.set_axisbelow(True)
    ax.set_xlabel("% of entries with this tag", color=INK_MUTED, fontsize=9)
    ax.set_title(title, color=INK, fontsize=10, pad=12, loc="left")

    # Direct-label each bar with both the share and the raw count, so the reader
    # never has to do "31% of what?" in their head.
    for bar, pct, count in zip(bars, percents, counts):
        ax.annotate(
            f"{pct:g}%  ({count})",
            xy=(bar.get_width(), bar.get_y() + bar.get_height() / 2),
            xytext=(5, 0), textcoords="offset points",
            ha="left", va="center", fontsize=8, color=INK,
        )

    ax.set_xlim(0, max(percents + [10]) * 1.28)
    return _finish(fig, filename)
