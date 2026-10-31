# NeuroAssist — a closed-loop embodied BCI prototype

A compact research prototype in which a **brain–computer interface and an embodied AI agent share control** of a simulated assistive robot arm. The user wants one of several objects on a table. The agent never receives a command saying which one. It has to infer the goal from noisy motor-imagery EEG, gaze and task context, then decide moment by moment how much of the movement to take on itself.

![replay](results_real/replay_shared_control.gif)

*Replay of one real-data episode: the agent's belief over objects, its share of control (α) and each step's EEG decode (green = correct, red = wrong).*


## Architecture

```
 user (hidden goal)
   │ motor imagery ──► EEG trial (real BCI IV-2a recording) ──► decoder ──► p(right), uncertainty
   │ gaze ───────────► fixation (noisy, sometimes off-target) ─────────────────┐
   │                                                                            ▼
   │                 task context prior ─────────────────────────► IntentEstimator ─► belief over objects
   │                                                                            │
   │                       user command  u_user  ◄── p(right)                   ▼
   │                       agent command u_agent ◄── most likely object  ─► arbitration α
   │                                                                            │
   └──────────── observes the arm ◄── robot moves:  u = α·u_agent + (1−α)·u_user
```

## Conditions compared

1. **Direct BCI, static decoder.** The classic setup: a day-1 decoder steers the arm on day 2.
2. **Direct BCI, adaptive decoder.** Same, plus unsupervised re-centring.
3. **Gaze + context autonomy.** The agent acts alone on gaze and context, and the user has no say.
4. **Shared control, fixed α = 0.5.**
5. **Adaptive shared control, static decoder.** An ablation.
6. **Adaptive shared control.** The proposed system.

Every condition runs on the same scenes and goals (a paired design) as one continuous online session per subject.

## Results (real EEG: BCI Competition IV 2a, 9 users)

Calibration used each user's day-1 session. The robot was then driven by real day-2 recordings, replayed as the simulated user's motor imagery. Each condition ran 60 episodes per user.

| Condition | Success | Wrong object | Time (s) | Path efficiency | User control |
|---|---|---|---|---|---|
| Direct BCI (static decoder) | 75.7% | 23.9% | 36.0 | 0.72 | 100% |
| Direct BCI (adaptive decoder) | 75.0% | 24.3% | 36.3 | 0.72 | 100% |
| Gaze + context autonomy | 99.1% | 0.9% | 28.1 | 0.92 | 0% |
| Shared control, fixed α = 0.5 | 93.3% | 6.7% | 28.5 | 0.88 | 50% |
| Adaptive shared (static decoder) | 98.1% | 1.9% | 27.5 | 0.93 | 23% |
| **Adaptive shared control** | **97.6%** | **2.4%** | **27.6** | **0.93** | **24%** |

Values are means across 9 users. Full tables, standard deviations and Wilcoxon signed-rank tests are in `results_real/results.md`. Online left/right decoding accuracy averaged about 79% (range 58–99% across users).

What the results show:

- **Shared control is far more reliable than direct BCI.** Success rose from 75% to 98% (+22.6 points, p = 0.016, n = 9), tasks finished about 9 s faster, and wrong-object grasps fell from 24% to 2%. The user kept about a quarter of the control.
- **The gain is largest for the weakest decoders** (Fig. 2). Users whose motor imagery is hard to decode benefit most, which is directly relevant to accessibility.
- **Autonomy only wins when gaze is clean.** Gaze-only autonomy scores 99%, but it leaves the user no control. When gaze reliability drops to 30% on-target fixations, autonomy falls to 52% while adaptive shared control holds 83% (Fig. 4). The EEG channel lets the user correct the agent.
- **Negative result 1: decoder adaptation didn't help on this dataset.** Unsupervised re-centring had no significant effect on real data (direct BCI 75.7% vs 75.0%; shared 98.1% vs 97.6%, p = 0.44). The day-1 decoder already transferred well to day 2 (mean online accuracy 79.5%). This contrasts with the simulator, where a deliberately larger cross-day shift made adaptation essential. Larger real-world drift (new sessions, electrode re-placement, dry electrodes) is where adaptation is expected to matter.
- **Negative result 2: adaptive α was not significantly better than fixed α** (+4.3 points, p = 0.16). It achieved this while giving the user less authority than the 50/50 split. How much control people *want* to keep is a question for user studies.

| | |
|---|---|
| ![](results_real/figures/1_main_results.png) | |
| ![](results_real/figures/2_who_benefits.png) | ![](results_real/figures/4_gaze_robustness.png) |
| ![](results_real/figures/3_decoder_adaptation.png) | ![](results_real/figures/5_episode_shared_adapt.png) |

<details><summary>Synthetic-EEG results (simulator with a larger cross-day shift)</summary>

| Condition | Success | User control |
|---|---|---|
| Direct BCI (static decoder) | 42% | 100% |
| Direct BCI (adaptive decoder) | 72% | 100% |
| Gaze + context autonomy | 99% | 0% |
| Shared control, fixed α | 94% | 50% |
| Adaptive shared (static decoder) | 72% | 28% |
| Adaptive shared control | 98% | 24% |

With strong simulated drift, unsupervised adaptation added about 26–30 points. Run with `python run_all.py --data synthetic`.
</details>

## Interactive demo and pilot user study

`docs/index.html` is a self-contained web demo of the shared-control system. You play the user: press ← / → to "imagine" a hand, a calibrated simulated decoder misreads some presses, and the robot fuses your intent with your gaze and the task context.

**Gaze sources:** simulated eye tracker, your mouse pointer, or **your real eyes via the webcam** ([WebGazer.js](https://webgazer.cs.brown.edu/), 9-point calibration plus an accuracy check). Video is processed only in the browser; only gaze coordinates are kept.

**Study mode** ("Take part in the study") runs a complete within-subject pilot:

1. Information and consent screen, anonymous participant code.
2. Webcam calibration (or pointer fallback).
3. 3 practice runs.
4. 3 blocks of 6 runs: Direct BCI, Gaze autonomy and Adaptive shared control, labelled neutrally as System A/B/C and counterbalanced across participants (6 orders).
5. After each block: raw NASA-TLX (6 items) plus "I felt in control" and "I trusted the robot" (1–7).
6. Results are saved automatically to your Google Sheet (see below), with a **Copy results** button as a backup.

Per run it logs success, wrong-object grasps, decisions and wall-clock time, the user's share of control, decoder misreads, the share of gaze samples on the goal, and every decision step.

**Hosting it publicly (GitHub Pages):** push this repo to GitHub, then go to *Settings → Pages → Build and deployment*, set *Source* to "Deploy from a branch", choose `main` and the `/docs` folder, and save. After a minute the demo is live at `https://<your-username>.github.io/<repo-name>/`. Webcam eye tracking needs this kind of normal hosting (HTTPS); it is blocked inside embedded viewers.

### Saving results automatically (Google Sheets)

Study results can go straight into a private Google Sheet, so participants don't have to send you anything.

1. Create a new Google Sheet (for example "NeuroAssist study results").
2. In the sheet, open **Extensions → Apps Script**. Delete the starter code, paste in everything from `study_backend/Code.gs`, and click **Save**.
3. Click **Deploy → New deployment**. Click the gear next to "Select type" and choose **Web app**. Set **Execute as: Me** and **Who has access: Anyone**, then click **Deploy**.
4. Google asks you to authorise the script: choose your account, then **Advanced → Go to (project name) → Allow**. It only gets access to this one spreadsheet.
5. Copy the **Web app URL** (it ends in `/exec`). Open it in a browser tab once: you should see `{"ok":true,...}`.
6. In `docs/index.html`, find `const RESULTS_URL = "";` near the top of the script and paste the URL between the quotes. Commit and push.

Now every participant's results are saved after each block (so partial sessions are kept) and again when they finish. The sheet gets two tabs: **Participants** (one row per person with per-condition success, time, workload, control and trust, plus the full data in the `json_` columns) and **Trials** (one row per run). The end screen tells the participant whether saving worked, and the Copy button stays as a backup.

To analyse: open the **Participants** tab, choose **File → Download → Comma-separated values**, and run

```bash
python analyse_study.py participants.csv
```

Notes: if you edit `Code.gs` later, use **Deploy → Manage deployments → Edit → New version** so the URL stays the same. The `STUDY_KEY` in both files only filters out random traffic; it is not a password. Only you can open the spreadsheet. The Claude-hosted copy of the demo cannot reach Google, so automatic saving works on the GitHub Pages site only.

**Analysing the study:** save each participant's file in one folder, then run

```bash
python analyse_study.py study_data/
```

This writes `results_study/` with per-participant tables, a Friedman test across conditions, Wilcoxon signed-rank tests (adaptive vs each alternative, Holm-corrected), a six-panel figure and `study_results.md`.

**What is real and what is simulated:** the participants, their gaze, behaviour and ratings are real; the EEG decoder is simulated at 79% accuracy (the mean measured offline on real EEG). Report it as *a pilot usability study with real gaze and simulated EEG*. It is an informal pilot: get verbal consent, keep data anonymous, and note that a formal study would need ethics approval.

## Running it

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python run_all.py --data synthetic                       # ~3 min, no download
python run_all.py                                        # real BCI IV 2a data (downloads ~ 0.7 GB once via MOABB)
python run_all.py --subjects 1 3 --episodes 20 --no-sweep   # quick check
```

Outputs go to `results_<data>/`: `results.md`, CSV files for each episode and subject, `stats.json`, `figures/` and `replay_shared_control.gif`.

## Project layout

```
neuroassist/
  data.py        real (MOABB) and synthetic EEG with the same interface
  decoder.py     Riemannian decoder, temperature scaling, online re-centring, ECE
  env.py         tabletop scene, simulated user (motor imagery + gaze), constants
  agent.py       Bayesian intent fusion, user and agent commands, adaptive arbitration
  experiment.py  closed-loop episode runner and the 6 conditions
  viz.py         figures and replay animation
run_all.py       full evaluation, statistics and report
analyse_study.py pilot study analysis (sheet CSV or JSON files -> stats + figures)
export_web_eeg.py exports real EEG trials + decoder outputs for the web demo
study_backend/   Google Apps Script that saves study results to a Google Sheet
docs/index.html  interactive demo + study mode (GitHub Pages)
```

## Limitations 

- **The user is simulated.** EEG trials are real recordings (with real data) but are replayed, so the user's brain doesn't actually respond to the robot. A real closed loop needs live participants, and users co-adapt to the agent.
- **Gaze is modelled, not recorded.** The next step is a VR headset or webcam eye tracker.
- **The agent's decision-making is simple.** It uses a Bayesian filter and heuristic arbitration. Natural extensions are POMDP or RL arbitration policies learned against user models, and error-related potentials as an implicit reward signal.
- **No workload estimate yet.** Frontal theta and parietal alpha, or pupil size, could feed into α, which is a direct route to the project's "cognitive demand" theme.
- **No subjective measures.** A real study would add NASA-TLX, a sense-of-agency questionnaire and SUS.

## References

- Tangermann et al. (2012). Review of the BCI Competition IV. *Frontiers in Neuroscience* (dataset 2a).
- Barachant et al. (2013). Classification of covariance matrices using a Riemannian-based kernel for BCI applications. *Neurocomputing*.
- Zanini et al. (2018). Transfer learning: a Riemannian geometry framework with applications to brain–computer interfaces. *IEEE TBME*.
- Guo et al. (2017). On calibration of modern neural networks. *ICML* (temperature scaling).
- Dragan & Srinivasa (2013). A policy-blending formalism for shared control. *IJRR*.
- Jacob (1990). What you look at is what you get: eye movement-based interaction techniques. *CHI* (the "Midas touch" problem).
- Jayaram & Barachant (2018). MOABB: trustworthy algorithm benchmarking for BCIs. *Journal of Neural Engineering*.
