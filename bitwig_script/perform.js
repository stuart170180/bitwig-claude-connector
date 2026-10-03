// Scripted parameter movement while recording (automation by performance). Owned by the "perform" feature work.
// A plan is a list of moves {target, from, to, start_beat, length_beats, curve}. Moves are driven by the transport
// position (sampled every PF_TICK_MS), so they stay locked to the timeline; with automation write on, Bitwig
// records the touched parameter's movement as real automation.
//
// target: {kind:"volume"|"pan", track}            track volume / pan
//         {kind:"send", track, send}              send level
//         {kind:"master_volume"}
//         {kind:"remote", index}                  remote control (0-7) of the CURSOR device (page via plan.remote_page)
//         {kind:"direct", id}                     direct parameter id of the CURSOR device (see deep_info)
// Device targets use the cursor device; give plan.select = {track, device} and the script selects it first.
// All values are normalised 0..1.

var PF_TICK_MS = 30;
var pfOverride = null;
var pf = { running: false, phase: "idle", moves: [], error: null, pos: 0, applied: 0, ticks: 0, log: [] };

function initPerform() {
   for (var t = 0; t < NUM_TRACKS; t++) {
      var tr = trackBank.getItemAt(t);
      try { interest(tr.volume().hasAutomation()); interest(tr.pan().hasAutomation()); } catch (e) {}
      for (var s = 0; s < NUM_SENDS; s++) { try { interest(tr.sendBank().getItemAt(s).hasAutomation()); } catch (e) {} }
   }
   for (var p = 0; p < 8; p++) { try { interest(remotePage.getParameter(p).hasAutomation()); } catch (e) {} }
   try { interest(masterTrack.volume().hasAutomation()); } catch (e) {}
   try { interest(transport.isArrangerAutomationWriteEnabled()); } catch (e) {}
   try { pfOverride = transport.isAutomationOverrideActive(); interest(pfOverride); } catch (e) {}
}

function pfCurve(name, t) {
   if (t <= 0) return 0;
   if (t >= 1) return 1;
   switch (name) {
      case "exp": case "ease_in": return (Math.exp(4 * t) - 1) / (Math.exp(4) - 1);   // slow start, fast end
      case "log": case "ease_out": return 1 - (Math.exp(4 * (1 - t)) - 1) / (Math.exp(4) - 1);  // fast start, slow end
      case "ease": case "smooth": return t * t * (3 - 2 * t);                          // smoothstep
      case "hold": return 0;
      default: return t;                                                                // linear
   }
}

function pfResolve(t) {
   var kind = String(need(t, "kind"));
   var p;
   switch (kind) {
      case "volume": p = track(need(t, "track")).volume(); break;
      case "pan": p = track(need(t, "track")).pan(); break;
      case "send": {
         p = track(need(t, "track")).sendBank().getItemAt(need(t, "send"));
         if (!p.exists().get()) throw "no send " + t.send;
         break;
      }
      case "master_volume": p = masterTrack.volume(); break;
      case "remote": p = remotePage.getParameter(need(t, "index")); if (!p.exists().get()) throw "no remote control " + t.index; break;
      case "direct": {
         var id = String(need(t, "id"));
         if (dpIds.indexOf(id) < 0) throw "no direct parameter " + id + " on the cursor device";
         return { key: "d:" + id, set: function (v) { cursorDevice.setDirectParameterValueNormalized(id, v * 16384, 16384); },
                  touch: function () {}, get: function () { return dpValue[id]; } };
      }
      default: throw "unknown target kind " + kind;
   }
   var key = kind + ":" + (t.track != null ? t.track : "") + ":" + (t.send != null ? t.send : t.index != null ? t.index : "");
   return { key: key, set: function (v) { if (pf.setMode === "set") p.set(v, 16384); else p.setImmediately(v); }, touch: function (b) { p.touch(b); },
            get: function () { return p.get(); }, p: p };
}

function pfNow() { return java.lang.System.nanoTime() / 1e6; }

function pfRestore() {
   var s = pf.saved || {};
   try { if (autoWrite && s.write != null) autoWrite.set(s.write); } catch (e) {}
   try { if (autoMode && s.mode != null) autoMode.set(s.mode); } catch (e) {}
   try { if (arrRec && s.rec != null && !pf.keepRecord) arrRec.set(s.rec); } catch (e) {}
}

function pfFinish(reason) {
   for (var i = 0; i < pf.moves.length; i++) {
      var m = pf.moves[i];
      if (m.touched) { try { m.h.touch(false); } catch (e) {} m.touched = false; }
   }
   if (pf.stopAtEnd && pf.ownTransport) { try { transport.stop(); } catch (e) {} }
   pfRestore();
   pf.running = false; pf.phase = reason;
}

function pfApply(m, v) {
   if (pf.touch && !m.touched) { m.h.touch(true); m.touched = true; }
   m.h.set(v);
   m.last = v; pf.applied++;
}

function pfTick() {
   if (!pf.running) return;
   try {
      var pos = transport.getPosition().get();
      var t = pfNow();
      // Interpolate between position updates (the observer only changes once per audio block).
      if (pos !== pf.lastPos) { pf.lastPos = pos; pf.lastT = t; }
      var tempo = transport.tempo().value().getRaw();
      var est = (transport.isPlaying().get() && pf.lastT != null) ? pos + Math.min(0.1, (t - pf.lastT) / 60000 * tempo) : pos;
      pf.pos = est; pf.ticks++;
      if (pf.phase === "positioning") {   // wait until the playhead really reads from_beat, then enable write and start
         if (Math.abs(pos - pf.fromBeat) > 0.05) {
            if (++pf.tries > 80) { pf.error = "couldn't move the playhead to " + pf.fromBeat; pfFinish("error"); return; }
            seekTo(pf.tries % 2 ? pf.fromBeat + 1 : pf.fromBeat);
         } else {
            if (pf.startMode === "record") arrRec.set(true);
            pf.enable();
            transport.play();
            pf.phase = "waiting"; pf.t0 = pfNow(); pf.lastPos = null;
         }
         host.scheduleTask(pfTick, PF_TICK_MS); return;
      }
      if (pf.phase === "waiting") {
         // wait for the playhead to reach the plan (record mode: the arranger state machine starts the transport)
         if (pf.viaArranger) {
            if (!rec.running && rec.phase !== "recording") { pf.error = rec.error || "arranger recording did not start"; pfFinish("error"); return; }
            if (rec.phase !== "recording" && rec.phase !== "starting") { host.scheduleTask(pfTick, PF_TICK_MS); return; }
            if (pos <= 0.05 && rec.phase !== "recording") { host.scheduleTask(pfTick, PF_TICK_MS); return; }
         } else if (!transport.isPlaying().get() || Math.abs(pos - pf.fromBeat) > 2) {
            if (pfNow() - pf.t0 > 5000) { pf.error = "transport never started"; pfFinish("error"); return; }
            host.scheduleTask(pfTick, PF_TICK_MS); return;
         }
         pf.phase = "running";
         if (pf.reassert) pf.reassert();
      }
      var allDone = true;
      for (var i = 0; i < pf.moves.length; i++) {
         var m = pf.moves[i];
         if (m.done) continue;
         allDone = false;
         if (est < m.start) continue;
         var u = m.len > 0 ? (est - m.start) / m.len : 1;
         if (u >= 1) { pfApply(m, m.to); if (m.touched) { m.h.touch(false); m.touched = false; } m.done = true; continue; }
         pfApply(m, m.from + (m.to - m.from) * pfCurve(m.curve, u));
      }
      if (pf.viaArranger && !rec.running) { pfFinish(allDone ? "done" : "arranger_stopped"); return; }
      if (allDone && pf.autoStop) { pf.phase = "finishing"; pf.finishAt = pf.finishAt || (est + pf.tail); }
      if (pf.finishAt != null && est >= pf.finishAt) { pfFinish("done"); return; }
      if (pf.endBeat != null && est >= pf.endBeat && !pf.viaArranger) { pfFinish("done"); return; }
      if (!pf.viaArranger && !transport.isPlaying().get() && pf.phase !== "waiting" && pfNow() - pf.t0 > 1000) { pfFinish("transport_stopped"); return; }
   } catch (e) { pf.error = String(e); pfFinish("error"); return; }
   host.scheduleTask(pfTick, PF_TICK_MS);
}

function pfBuild(a) {
   var moves = need(a, "moves"), out = [];
   for (var i = 0; i < moves.length; i++) {
      var mv = moves[i];
      out.push({ h: pfResolve(need(mv, "target")), from: clamp01(need(mv, "from")), to: clamp01(need(mv, "to")),
                 start: need(mv, "start_beat"), len: need(mv, "length_beats"), curve: String(mv.curve || "linear"),
                 touched: false, done: false, last: null });
   }
   return out;
}

function pfNeedsDevice(moves) {
   for (var i = 0; i < moves.length; i++) { var k = moves[i].target && moves[i].target.kind; if (k === "remote" || k === "direct") return true; }
   return false;
}

// Start after (optional) cursor-device selection; device targets resolve only after Bitwig has followed the selection.
function pfLaunch(a, record) {
   if (pf.running) throw "a performance is already running (perform_abort to cancel)";
   var raw = need(a, "moves");
   var needDev = pfNeedsDevice(raw);
   if (needDev && a.select) {
      cursorTrack.selectChannel(track(need(a.select, "track")));
      host.scheduleTask(function () {
         var d = deviceBank.getItemAt(need(a.select, "device"));
         if (d.exists().get()) cursorDevice.selectDevice(d);
         if (a.remote_page != null) remotePage.selectedPageIndex().set(a.remote_page);
         host.scheduleTask(function () { try { pfLaunch2(a, record); } catch (e) { pf.error = String(e); pf.running = false; pf.phase = "error"; } }, 700);
      }, 500);
      pf.running = true; pf.phase = "selecting"; pf.error = null;   // reserve
      return "started (selecting device first)";
   }
   pfLaunch2(a, record);
   return "started";
}

function pfLaunch2(a, record) {
   pf.running = false;
   var moves = pfBuild(a);
   var saved = { write: autoWrite ? autoWrite.get() : null, mode: autoMode ? autoMode.get() : null, rec: arrRec ? arrRec.get() : null };
   pf = { running: true, phase: "waiting", moves: moves, error: null, pos: 0, applied: 0, ticks: 0, saved: saved,
          touch: a.touch !== false, stopAtEnd: !!a.stop_at_end, ownTransport: false, viaArranger: false,
          autoStop: a.auto_stop !== false, tail: a.tail_beats != null ? a.tail_beats : 0.25,
          endBeat: a.end_beat != null ? a.end_beat : null, t0: pfNow(), lastPos: null, lastT: null, finishAt: null,
          keepRecord: !!a.keep_record, setMode: a.set_mode || "immediate" };
   // NOTE: transport.stop() switches arranger record AND automation write off, and arranger record on switches
   // automation write on. So stop/seek first, then enable, then play.
   function enable() {
      if (a.mode && autoMode) autoMode.set(String(a.mode));
      if (a.write !== false && autoWrite) autoWrite.set(true);
   }
   pf.enable = enable;
   if (record) {
      if (!arrRec) throw "arranger record not exposed";
      if (!a.scenes || !a.scenes.length) {
         // No clips: plain arranger record from from_beat (default 0). Positioned in pfTick before play.
         transport.stop();
         pf.fromBeat = a.from_beat != null ? a.from_beat : 0; pf.tries = 0; pf.startMode = "record";
         seekTo(pf.fromBeat); pf.phase = "positioning"; pf.ownTransport = true; pf.stopAtEnd = true;
      } else {
         pf.viaArranger = true;
         enable();   // arranger_start stops the transport first; pfTick re-asserts write once the recording runs
         handleArranger("arranger_start", { plan: a.scenes, total_beats: need(a, "total_beats") });
         pf.reassert = enable;
      }
   } else if (a.play) {
      transport.stop();
      pf.fromBeat = a.from_beat != null ? a.from_beat : 0; pf.tries = 0; pf.startMode = "play";
      seekTo(pf.fromBeat); pf.phase = "positioning"; pf.ownTransport = true;
   } else enable();
   host.scheduleTask(pfTick, PF_TICK_MS);
}

function pfStatus() {
   var ms = [];
   for (var i = 0; i < pf.moves.length; i++) { var m = pf.moves[i]; ms.push({ key: m.h.key, done: m.done, last: m.last }); }
   return { running: pf.running, phase: pf.phase, position: Math.round(pf.pos * 1000) / 1000, applied: pf.applied, ticks: pf.ticks,
            moves: ms, error: pf.error, via_arranger: !!pf.viaArranger };
}

function handlePerform(cmd, a) {
   switch (cmd) {
      case "perform_plan": return pfLaunch(a, false);
      case "perform_record": return pfLaunch(a, true);
      case "perform_ramp": {   // single move convenience
         var b = { moves: [{ target: need(a, "target"), from: need(a, "from"), to: need(a, "to"), start_beat: a.start_beat || 0,
                             length_beats: need(a, "length_beats"), curve: a.curve }] };
         for (var k in a) if (k !== "target" && k !== "from" && k !== "to" && k !== "start_beat" && k !== "length_beats" && k !== "curve") b[k] = a[k];
         return pfLaunch(b, !!a.record);
      }
      case "perform_status": return pfStatus();
      case "perform_abort": if (pf.running) pfFinish("aborted"); if (rec.running) recFinish("aborted"); return "ok";
      case "perform_override": {   // global automation-override state (orange button); reset=true restores automation control
         if (a.reset) transport.resetAutomationOverrides();
         return { override_active: pfOverride ? pfOverride.get() : null };
      }
      // --- research primitives ---
      case "perform_touch_set": {   // touch (optional), set, un-touch (optional) one target; for probing automation write rules
         var h = pfResolve(need(a, "target"));
         if (a.touch) h.touch(true);
         if (a.immediate === false && h.p) h.p.set(clamp01(a.value)); else h.set(clamp01(a.value));
         if (a.touch && a.untouch !== false) host.scheduleTask(function () { h.touch(false); }, a.hold_ms || 50);
         return "ok";
      }
      case "perform_has_automation": {
         var hp = pfResolve(need(a, "target"));
         return hp.p ? { has_automation: !!hp.p.hasAutomation().get() } : "n/a";
      }
      case "perform_clear_automation": { var hc = pfResolve(need(a, "target")); if (!hc.p) throw "n/a"; hc.p.deleteAllAutomation(); return "ok"; }
      case "perform_restore_control": { var hr = pfResolve(need(a, "target")); if (!hr.p) throw "n/a"; hr.p.restoreAutomationControl(); return "ok"; }
      case "perform_read": {   // current value (normalised) of a target
         var hg = pfResolve(need(a, "target")); return hg.get();
      }
   }
   return undefined;
}
