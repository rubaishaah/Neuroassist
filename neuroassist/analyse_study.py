"""Analyse the NeuroAssist pilot usability study.

Results arrive automatically in your Google Sheet (see README). Download its
"Participants" tab as CSV and run:

    python analyse_study.py participants.csv

or, for results participants copied and sent you, put the .json files in one folder:

    python analyse_study.py study_data/

Outputs go to ``results_study/``: per-participant and per-condition tables,
statistics, figures and a ``study_results.md`` summary.

Statistics: with the three within-subject conditions, a Friedman test checks for
any difference, then the proposed adaptive shared control is compared with each
alternative using Wilcoxon signed-rank tests with Holm correction. With a small
pilot (n < 10) treat p-values as indicative only, and report effect sizes and
individual data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import friedmanchisquare, wilcoxon

CONDS = ["direct", "autonomy", "adaptive"]
LABELS = {"direct": "Direct BCI", "autonomy": "Gaze autonomy", "adaptive": "Adaptive shared\n(proposed)"}
METRICS = [  # column, title, scale, unit, higher_is_better
    ("success", "Task success", 100, "%", True),
    ("time_s", "Time per run (s)", 1, "", False),
    ("user_share", "User's share of control", 100, "%", None),
    ("tlx_raw", "Workload (raw NASA-TLX, 0-100)", 1, "", False),
    ("control", "Felt in control (1-7)", 1, "", True),
    ("trust", "Trusted the robot (1-7)", 1, "", True),
]
INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e0", "#fcfcfb"
BLUE, BASELINE = "#2a78d6", "#b9b8b2"


def _records(src: Path):
    """Yield (name, result dict) from a folder of .json files or a CSV export of the
    Google Sheet's Participants tab (File -> Download -> Comma-separated values)."""
    if src.is_file() and src.suffix.lower() == ".csv":
        sheet = pd.read_csv(src, dtype=str).fillna("")
        cols = sorted([c for c in sheet.columns if c.startswith("json_")], key=lambda c: int(c.split("_")[1]))
        if not cols:
            raise SystemExit(f"{src} has no json_ columns. Export the 'Participants' tab of the results sheet.")
        for i, row in sheet.iterrows():
            text = "".join(row[c] for c in cols)
            if text:
                yield f"{src.name} row {i + 2}", json.loads(text)
        return
    files = sorted(src.glob("*.json"))
    if not files:
        raise SystemExit(f"No .json files found in {src}")
    for f in files:
        yield f.name, json.loads(f.read_text(encoding="utf-8"))


def load(src: Path) -> list[dict]:
    out, seen = [], set()
    for name, d in _records(src):
        f = type("F", (), {"name": name})
        if d.get("schema") != "neuroassist-study/1":
            print(f"  skipping {f.name}: not a NeuroAssist study file")
            continue
        if d["participant"] in seen:
            print(f"  skipping {f.name}: duplicate participant {d['participant']}")
            continue
        if not d.get("finished"):
            print(f"  note: {d['participant']} did not finish; partial blocks are included")
        seen.add(d["participant"])
        out.append(d)
    return out


def tidy(parts: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    trials, quest = [], []
    for d in parts:
        s = d["settings"]
        for t in d["trials"]:
            if t["condition"] == "practice":
                continue
            trials.append(dict(participant=d["participant"], gaze_source=s["gaze_source"],
                               calib_error_px=s.get("calib_error_px"), condition=t["condition"],
                               block=t["block"], trial=t["trial"], success=float(t["success"]),
                               wrong_object=float(not t["success"] and t["outcome"] != "timeout"),
                               decisions=t["decisions"], time_s=2 * t["decisions"], wall_s=t["wall_ms"] / 1000,
                               user_share=t["user_share"], misreads=t["misreads"],
                               misread_rate=t["misreads"] / max(t["decisions"], 1),
                               gaze_on_goal=t["gaze_on_goal"]))
        for q in d["questionnaires"]:
            quest.append(dict(participant=d["participant"], condition=q["condition"], block=q["block"],
                              tlx_raw=q["tlx_raw"], control=q["control"], trust=q["trust"],
                              **{f"tlx_{k}": v for k, v in q["tlx"].items()}))
    return pd.DataFrame(trials), pd.DataFrame(quest)


def per_participant(tr: pd.DataFrame, qu: pd.DataFrame) -> pd.DataFrame:
    agg = tr.groupby(["participant", "condition"]).agg(
        success=("success", "mean"), wrong_object=("wrong_object", "mean"), time_s=("time_s", "mean"),
        wall_s=("wall_s", "mean"), user_share=("user_share", "mean"), misread_rate=("misread_rate", "mean"),
        gaze_on_goal=("gaze_on_goal", "mean"), runs=("success", "size")).reset_index()
    return agg.merge(qu, on=["participant", "condition"], how="left")


def holm(ps: list[float]) -> list[float]:
    order = np.argsort(ps)
    adj, running = [np.nan] * len(ps), 0.0
    for rank, i in enumerate(order):
        if np.isnan(ps[i]):
            continue
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = running
    return adj


def stats(pp: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col, title, *_ in METRICS:
        wide = pp.pivot(index="participant", columns="condition", values=col).reindex(columns=CONDS).dropna()
        n = len(wide)
        fr = friedmanchisquare(*[wide[c] for c in CONDS]).pvalue if n >= 3 and wide.nunique().max() > 1 else np.nan
        comps, ps = [], []
        for other in ("direct", "autonomy"):
            diff = wide["adaptive"] - wide[other]
            p = wilcoxon(wide["adaptive"], wide[other]).pvalue if n >= 5 and (diff != 0).any() else np.nan
            comps.append((other, diff.mean(), diff.median())); ps.append(p)
        for (other, mean_d, med_d), p, p_adj in zip(comps, ps, holm(ps)):
            rows.append(dict(metric=title, n=n, friedman_p=fr, comparison=f"adaptive vs {other}",
                             mean_diff=mean_d, median_diff=med_d, wilcoxon_p=p, holm_p=p_adj))
    return pd.DataFrame(rows)


def figure(pp: pd.DataFrame, path: Path):
    plt.rcParams.update({"figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
                         "axes.edgecolor": MUTED, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                         "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
                         "axes.axisbelow": True, "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
                         "axes.titlelocation": "left"})
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    x = np.arange(len(CONDS))
    for ax, (col, title, scale, unit, _) in zip(axes.flat, METRICS):
        wide = pp.pivot(index="participant", columns="condition", values=col).reindex(columns=CONDS) * scale
        means = wide.mean()
        ax.bar(x, means, width=0.6, color=[BLUE if c == "adaptive" else BASELINE for c in CONDS],
               edgecolor=SURFACE, linewidth=2)
        for _, row in wide.iterrows():  # one line per participant: within-subject view
            ax.plot(x, row.values, color=INK2, alpha=0.35, lw=1, marker="o", ms=3.5, zorder=3)
        for i, c in enumerate(CONDS):
            if not np.isnan(means[c]):
                ax.text(i, 0, f" {means[c]:.0f}{unit}" if scale == 100 else f" {means[c]:.1f}", ha="center",
                        va="bottom", fontsize=9, color="white" if c == "adaptive" else INK, fontweight="bold")
        ax.set_xticks(x, [LABELS[c] for c in CONDS], fontsize=8.5)
        ax.set_title(title)
        ax.grid(axis="x", visible=False)
        if col in ("control", "trust"):
            ax.set_ylim(0, 7.5)
        elif scale == 100:
            ax.set_ylim(0, 108)
    n = pp["participant"].nunique()
    fig.text(0.01, 0.005, f"Bars: mean across {n} participants. Lines: individual participants. "
             "Blue: proposed adaptive shared control.", color=MUTED, fontsize=8.5)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", type=Path, help="folder of participant .json files, or the CSV export of the results sheet")
    ap.add_argument("--out", type=Path, default=Path("results_study"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    parts = load(args.folder)
    tr, qu = tidy(parts)
    pp = per_participant(tr, qu)
    tr.to_csv(args.out / "trials.csv", index=False)
    pp.to_csv(args.out / "per_participant.csv", index=False)
    st = stats(pp)
    st.to_csv(args.out / "stats.csv", index=False)
    figure(pp, args.out / "study_results.png")

    summ = pp.groupby("condition")[[m[0] for m in METRICS] + ["wrong_object", "misread_rate", "gaze_on_goal"]] \
             .agg(["mean", "std"]).reindex(CONDS)
    n = pp["participant"].nunique()
    gs = pd.Series([d["settings"]["gaze_source"] for d in parts]).value_counts().to_dict()
    cal = [d["settings"].get("calib_error_px") for d in parts if d["settings"].get("calib_error_px") is not None]
    L = ["# NeuroAssist pilot study results", "",
         f"Participants: {n} · gaze source: {gs}" + (f" · median webcam calibration error {np.median(cal):.0f} px" if cal else ""),
         f"Runs per condition per participant: {int(pp['runs'].median())} (practice runs excluded)", "",
         "| Condition | Success | Wrong object | Time (s) | User control | Workload (TLX) | Felt in control | Trust |",
         "|---|---|---|---|---|---|---|---|"]
    for c in CONDS:
        m = summ.loc[c]
        f = lambda k, s=1, d=0: f"{m[(k,'mean')]*s:.{d}f} ± {m[(k,'std')]*s:.{d}f}" if not np.isnan(m[(k,'mean')]) else "–"
        L.append(f"| {LABELS[c].replace(chr(10), ' ')} | {f('success',100)}% | {f('wrong_object',100)}% | {f('time_s',1,1)} "
                 f"| {f('user_share',100)}% | {f('tlx_raw',1,1)} | {f('control',1,1)} | {f('trust',1,1)} |")
    L += ["", "Mean ± SD across participants (each participant averaged over their runs first).", "",
          "## Statistics", "", "Friedman test across the three conditions; Wilcoxon signed-rank tests for the proposed "
          "condition against each alternative, Holm-corrected. Wilcoxon needs at least 5 participants.", ""]
    show = st.copy()
    for c in ("friedman_p", "wilcoxon_p", "holm_p"):
        show[c] = show[c].map(lambda v: "–" if np.isnan(v) else f"{v:.3g}")
    show["mean_diff"] = show["mean_diff"].map(lambda v: f"{v:+.3g}")
    show["median_diff"] = show["median_diff"].map(lambda v: f"{v:+.3g}")
    L += [show.to_markdown(index=False), "",
          "Note: this is a small pilot with simulated EEG and real gaze/behaviour. Treat p-values as indicative only."]
    (args.out / "study_results.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    print(f"\nWrote results to {args.out.resolve()}")


if __name__ == "__main__":
    main()
