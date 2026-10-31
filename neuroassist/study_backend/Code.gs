/**
 * NeuroAssist study backend: receives results from the study page and stores
 * them in this Google Sheet.
 *
 * Setup (once): see README "Saving results automatically". In short:
 *   Extensions -> Apps Script -> paste this file -> Deploy -> New deployment ->
 *   type "Web app", Execute as "Me", Who has access "Anyone" -> copy the URL
 *   into RESULTS_URL in docs/index.html.
 *
 * Sheets created automatically:
 *   Participants  one row per participant (updated after every block, so a
 *                 participant who stops early still leaves their completed blocks)
 *   Trials        one row per scored run, for a quick look in the spreadsheet
 *
 * The full result file is stored in the json_1, json_2, ... columns of
 * Participants (Google limits a cell to 50,000 characters, so it is split).
 * analyse_study.py joins them back together.
 */

// Must match STUDY_KEY in docs/index.html. It only stops random spam; it is not a password.
const STUDY_KEY = "neuroassist-pilot";
const CHUNK = 45000;
const P_HEAD = ["received_at", "participant", "started", "finished", "status", "gaze_source", "calib_error_px",
  "order", "scored_runs",
  "success_direct", "success_autonomy", "success_adaptive",
  "time_direct_s", "time_autonomy_s", "time_adaptive_s",
  "tlx_direct", "tlx_autonomy", "tlx_adaptive",
  "control_direct", "control_autonomy", "control_adaptive",
  "trust_direct", "trust_autonomy", "trust_adaptive",
  "app_version"];
const T_HEAD = ["participant", "block", "condition", "trial", "goal", "outcome", "success", "decisions",
  "wall_s", "user_share", "misreads", "gaze_on_goal"];

function doGet() {
  return out_({ ok: true, service: "neuroassist-study", time: new Date().toISOString() });
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(20000);
    const body = JSON.parse((e && e.postData && e.postData.contents) || "{}");
    if (body.key !== STUDY_KEY) return out_({ ok: false, error: "bad key" });
    const d = body.data;
    if (!d || d.schema !== "neuroassist-study/1" || !d.participant || !d.started) return out_({ ok: false, error: "bad payload" });
    const json = JSON.stringify(d);
    if (json.length > 2000000) return out_({ ok: false, error: "too large" });
    saveParticipant_(d, json);
    saveTrials_(d);
    return out_({ ok: true, participant: d.participant, runs: d.trials.length });
  } catch (err) {
    return out_({ ok: false, error: String(err) });
  } finally {
    try { lock.releaseLock(); } catch (_) {}
  }
}

function sheet_(name, head) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sh = ss.getSheetByName(name);
  if (!sh) { sh = ss.insertSheet(name); sh.appendRow(head); sh.setFrozenRows(1); }
  return sh;
}

function summary_(d) {
  const s = {};
  ["direct", "autonomy", "adaptive"].forEach(function (c) {
    const tr = d.trials.filter(function (t) { return t.condition === c; });
    const q = (d.questionnaires || []).filter(function (x) { return x.condition === c; })[0];
    s[c] = {
      success: tr.length ? tr.filter(function (t) { return t.success; }).length / tr.length : "",
      time: tr.length ? tr.reduce(function (a, t) { return a + 2 * t.decisions; }, 0) / tr.length : "",
      tlx: q ? q.tlx_raw : "", control: q ? q.control : "", trust: q ? q.trust : ""
    };
  });
  return s;
}

function saveParticipant_(d, json) {
  const sh = sheet_("Participants", P_HEAD);
  const s = summary_(d), set = d.settings || {};
  const chunks = [];
  for (let i = 0; i < json.length; i += CHUNK) chunks.push(json.slice(i, i + CHUNK));
  const row = [new Date(), d.participant, d.started, d.finished || "", d.finished ? "complete" : "in progress",
    set.gaze_source || "", set.calib_error_px == null ? "" : set.calib_error_px, (set.order || []).join(" > "),
    d.trials.filter(function (t) { return t.condition !== "practice"; }).length,
    s.direct.success, s.autonomy.success, s.adaptive.success,
    s.direct.time, s.autonomy.time, s.adaptive.time,
    s.direct.tlx, s.autonomy.tlx, s.adaptive.tlx,
    s.direct.control, s.autonomy.control, s.adaptive.control,
    s.direct.trust, s.autonomy.trust, s.adaptive.trust,
    d.app_version || ""].concat(chunks);
  // make sure there are enough json_N header cells
  const need = P_HEAD.length + chunks.length, head = sh.getRange(1, 1, 1, Math.max(sh.getLastColumn(), 1)).getValues()[0];
  for (let c = head.length; c < need; c++) sh.getRange(1, c + 1).setValue("json_" + (c - P_HEAD.length + 1));
  // update the participant's existing row if this is a later save of the same session
  const last = sh.getLastRow();
  let target = last + 1;
  if (last > 1) {
    const keys = sh.getRange(2, 2, last - 1, 2).getValues();
    for (let r = 0; r < keys.length; r++) if (keys[r][0] === d.participant && String(keys[r][1]) === d.started) { target = r + 2; break; }
  }
  if (target <= last) sh.getRange(target, 1, 1, sh.getLastColumn()).clearContent();
  sh.getRange(target, 1, 1, row.length).setValues([row]);
}

function saveTrials_(d) {
  const sh = sheet_("Trials", T_HEAD);
  const last = sh.getLastRow();
  if (last > 1) { // remove earlier rows from this participant, then rewrite them all
    const ids = sh.getRange(2, 1, last - 1, 1).getValues();
    for (let r = ids.length - 1; r >= 0; r--) if (ids[r][0] === d.participant) sh.deleteRow(r + 2);
  }
  const rows = d.trials.filter(function (t) { return t.condition !== "practice"; }).map(function (t) {
    return [d.participant, t.block, t.condition, t.trial, t.goal, t.outcome, t.success, t.decisions,
      t.wall_ms / 1000, t.user_share, t.misreads, t.gaze_on_goal == null ? "" : t.gaze_on_goal];
  });
  if (rows.length) sh.getRange(sh.getLastRow() + 1, 1, rows.length, T_HEAD.length).setValues(rows);
}

function out_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
