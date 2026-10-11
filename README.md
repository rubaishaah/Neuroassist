# Neuroassist — a closed-loop embodied BCI prototype

I built a shared-control BCI robot arm that combines noisy EEG, eye gaze, and task context to infer user intent and uncertainty. The robot adjusts its autonomy, respects conflicting brain signals, and adapts to signal drift without labels. In simulation, it outperformed direct BCI and robot-only control while preserving user agency.

![replay](results_synthetic/replay_shared_control.gif)

*In this replay, the EEG decode is wrong for several steps and stray glances pull the agent's belief towards the phone. Once the user's decodes and fixations point consistently at the cup, the belief flips, the agent yields and then commits, and the arm reaches the cup.*

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

Conditions compared
1. Direct BCI, static decoder. The classic setup: a day-1 decoder steers the arm on day 2.
2. Direct BCI, adaptive decoder. Same, plus unsupervised re-centring.
3. Gaze + context autonomy. The agent acts alone on gaze and context, and the user has no say.
4. Shared control, fixed α = 0.5.
5. Adaptive shared control, static decoder. An ablation.
6. Adaptive shared control. The proposed system.

Every condition runs on the same scenes and goals (a paired design) as one continuous online session per subject.

## Results (real EEG: BCI Competition IV 2a, 9 users)

Calibration used each user's day-1 session. The robot was then driven by real day-2 recordings, replayed as the simulated user's motor imagery. Each condition ran 60 episodes per user.

| Condition	| Success	| Wrong object	| Time (s) |	Path efficiency |	User control |
| --- | --- | ---| --- | --- | ---|
| Direct BCI (static decoder) |	75.7%	| 23.9%	| 36.0 |	0.72 |	100% |
| Direct BCI (adaptive decoder)	| 75.0%	| 24.3% |	36.3 |	0.72 |	100% |
| Gaze + context autonomy |	99.1%	| 0.9%	| 28.1 | 0.92	| 0% |
| Shared control, fixed α = 0.5	| 93.3%	| 6.7%	| 28.5	| 0.88	| 50% |
| Adaptive shared (static decoder) | 98.1%	| 1.9% | 27.5 |	0.93 |	23% |
| Adaptive shared control |	97.6%	| 2.4% | 27.6	| 0.93	| 24% |

Values are means across 9 users. Full tables, standard deviations and Wilcoxon signed-rank tests are in results_real/results.md. Online left/right decoding accuracy averaged about 79% (range 58–99% across users). 

What the results show:

- Shared control is far more reliable than direct BCI. Success rose from 75% to 98% (+22.6 points, p = 0.016, n = 9), tasks finished about 9 s faster, and wrong-object grasps fell from 24% to 2%. The user kept about a quarter of the control.
- The gain is largest for the weakest decoders (Fig. 2). Users whose motor imagery is hard to decode benefit most, which is directly relevant to accessibility.
- Autonomy only wins when gaze is clean. Gaze-only autonomy scores 99%, but it leaves the user no control. When gaze reliability drops to 30% on-target fixations, autonomy falls to 52% while adaptive shared control holds 83% (Fig. 4). The EEG channel lets the user correct the agent.
- Negative result 1: decoder adaptation didn't help on this dataset. Unsupervised re-centring had no significant effect on real data (direct BCI 75.7% vs 75.0%; shared 98.1% vs 97.6%, p = 0.44). The day-1 decoder already transferred well to day 2 (mean online accuracy 79.5%). This contrasts with the simulator, where a deliberately larger cross-day shift made adaptation essential. Larger real-world drift (new sessions, electrode re-placement, dry electrodes) is where adaptation is expected to matter.
- Negative result 2: adaptive α was not significantly better than fixed α (+4.3 points, p = 0.16). It achieved this while giving the user less authority than the 50/50 split. How much control people want to keep is a question for user studies.

| Condition |	Success	| User control |
| --- | --- | ---|
| Direct BCI (static decoder)	| 42% |	100% |
| Direct BCI (adaptive decoder)	| 72%	| 100%| 
| Gaze + context autonomy |	99%	| 0% |
| Shared control, fixed α	| 94%	| 50% |
| Adaptive shared (static decoder) | 72% |	28% |
| Adaptive shared control	| 98%	| 24% |

## Running it

``` bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python run_all.py --data synthetic                       # ~3 min, no download
python run_all.py                                        # real BCI IV 2a data (downloads ~ 0.7 GB once via MOABB)
python run_all.py --subjects 1 3 --episodes 20 --no-sweep   # quick check
```

Outputs go to `results_<data>/: results.md`, CSV files for each episode and subject, `stats.json`, `figures/` and `replay_shared_control.gif`.

## Limitations 
- The user is simulated. EEG trials are real recordings (with real data) but are replayed, so the user's brain doesn't actually respond to the robot. A real closed loop needs live participants, and users co-adapt to the agent.
- Gaze is modelled, not recorded. The next step is a VR headset or webcam eye tracker.
- The agent's decision-making is simple. It uses a Bayesian filter and heuristic arbitration. Natural extensions are POMDP or RL arbitration policies learned against user models, and error-related potentials as an implicit reward signal.
- No workload estimate yet. Frontal theta and parietal alpha, or pupil size, could feed into α, which is a direct route to the project's "cognitive demand" theme.
- No subjective measures. A real study would add NASA-TLX, a sense-of-agency questionnaire and SUS.


## References
- Tangermann et al. (2012). Review of the BCI Competition IV. Frontiers in Neuroscience (dataset 2a).
- Barachant et al. (2013). Classification of covariance matrices using a Riemannian-based kernel for BCI applications. Neurocomputing.
- Zanini et al. (2018). Transfer learning: a Riemannian geometry framework with applications to brain–computer interfaces. IEEE TBME.
- Guo et al. (2017). On calibration of modern neural networks. ICML (temperature scaling).
- Dragan & Srinivasa (2013). A policy-blending formalism for shared control. IJRR.
- Jacob (1990). What you look at is what you get: eye movement-based interaction techniques. CHI (the "Midas touch" problem).
- Jayaram & Barachant (2018). MOABB: trustworthy algorithm benchmarking for BCIs. Journal of Neural Engineering.
