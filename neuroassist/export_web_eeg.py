"""Export real EEG trials + real decoder outputs for the web demo.

For every subject this script:
  1. trains the project's Riemannian decoder on the day-1 (calibration) session,
  2. decodes every day-2 (online) trial with it, giving a genuine p(right),
  3. stores the C3 and C4 traces of each day-2 trial (8-30 Hz, 2 s window),
     downsampled to 125 Hz and quantised to 8 bits, plus the relative band
     power at C3 and C4 (trial power / that subject's mean power).

The result, ``docs/eeg_trials.json``, lets the web demo replay a real recorded
trial of the imagined class on every key press and feed its real decoder output
to the robot.

    python export_web_eeg.py                    # real BCI IV 2a data, 9 subjects
    python export_web_eeg.py --data synthetic   # for testing only
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

import numpy as np

from neuroassist.data import CH_NAMES, load_subject
from neuroassist.decoder import MIDecoder


def b64_int8(x: np.ndarray, scale: float) -> str:
    q = np.clip(np.round(x / scale), -127, 127).astype(np.int8)
    return base64.b64encode(q.tobytes()).decode("ascii")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", choices=["real", "synthetic"], default="real")
    ap.add_argument("--subjects", type=int, nargs="+", default=list(range(1, 10)))
    ap.add_argument("--out", type=Path, default=Path("docs/eeg_trials.json"))
    args = ap.parse_args()

    c3, c4 = CH_NAMES.index("C3"), CH_NAMES.index("C4")
    subjects = []
    for s in args.subjects:
        d = load_subject(s, args.data)
        dec = MIDecoder().fit(d.X_cal, d.y_cal)
        p = dec.proba_from_cov(dec.covariances(d.X_online), dec.ref_cal)  # static day-1 decoder on day-2 trials
        X = d.X_online[:, [c3, c4], ::2]                                   # 250 Hz -> 125 Hz (signal is band-limited to 30 Hz)
        power = X.var(axis=2)
        rel = power / power.mean(axis=0, keepdims=True)
        trials = []
        for i in range(len(d.y_online)):
            scale = float(np.abs(X[i]).max() / 127) or 1.0
            trials.append(dict(y=int(d.y_online[i]), p=round(float(p[i]), 4), s=scale,
                               c3=b64_int8(X[i, 0], scale), c4=b64_int8(X[i, 1], scale),
                               rp=[round(float(rel[i, 0]), 3), round(float(rel[i, 1]), 3)]))
        acc = float(((p > 0.5).astype(int) == d.y_online).mean())
        subjects.append(dict(id=s, acc=round(acc, 4), n=len(trials), trials=trials))
        print(f"subject {s}: {len(trials)} day-2 trials, real decoder accuracy {acc:.1%}")

    out = dict(schema="neuroassist-web-eeg/1", source=("BNCI2014_001 / BCI Competition IV 2a" if args.data == "real"
                                                        else "SYNTHETIC test data (not real EEG)"),
               real=args.data == "real", fs=125, seconds=2.0, band="8-30 Hz", channels=["C3", "C4"],
               classes={"0": "left hand", "1": "right hand"},
               decoder="Riemannian tangent space + logistic regression, trained on day 1, applied to day 2",
               subjects=subjects)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"\nWrote {args.out} ({args.out.stat().st_size/1e6:.2f} MB)")


if __name__ == "__main__":
    main()
