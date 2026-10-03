// Bitwig MCP bridge: OSC over UDP. Request /mcp "<json {id, cmd, args}>" on 8765; reply /reply "<json {id, ok, result|error}>" to 8766.
// The Python MCP server (Documents/Bitwig/bitwig_mcp/server.py) builds musical content; this script only executes primitives.
loadAPI(17);
load("pro.js");
load("expert.js");
load("arranger.js");
load("deep.js");

host.defineController("Claude", "Bitwig MCP", "3.0", "6b1f3a52-9d1e-4c8e-a7a1-5c3f2b8e9d10", "Claude");
host.defineMidiPorts(0, 0);

var VERSION = "6.0";
var PORT = 8765, REPLY_PORTS = [8766, 8767, 8768, 8769, 8770, 8771];  // one per concurrent client
var NUM_TRACKS = 64, NUM_SCENES = 32, NUM_SENDS = 8, NUM_DEVICES = 32;
var deviceBank, transport, application, trackBank, cursorTrack, cursorDevice, remotePage, cursorClip, sceneBank;
var recValue;
var missingApis = [];

// Call an API getter that may not exist in this Bitwig version; returns null if missing.
function opt(obj, names) {
   for (var i = 0; i < names.length; i++) {
      try { var v = obj[names[i]](); if (v) return v; } catch (e) {}
   }
   missingApis.push(names[0]);
   return null;
}

// Move the playhead. getPosition().set() is silently ignored in some Bitwig versions, so try setPosition.
function seekTo(beats) {
   try { transport.setPosition(beats); } catch (e) { transport.getPosition().set(beats); }
}

function interest(v) { try { v.markInterested(); } catch (e) {} }

function init() {
   transport = host.createTransport();
   application = host.createApplication();
   trackBank = host.createMainTrackBank(NUM_TRACKS, NUM_SENDS, NUM_SCENES);
   sceneBank = trackBank.sceneBank();
   cursorTrack = host.createCursorTrack("MCP_CURSOR", "MCP", NUM_SENDS, NUM_SCENES, true);
   cursorDevice = cursorTrack.createCursorDevice();
   deviceBank = cursorTrack.createDeviceBank(NUM_DEVICES);
   remotePage = cursorDevice.createCursorRemoteControlsPage(8);
   cursorClip = cursorTrack.createLauncherCursorClip(8192, 128);

   interest(transport.isPlaying());
   recValue = opt(transport, ["isArrangerRecordEnabled", "isArrangementRecordEnabled"]);
   if (recValue) interest(recValue);
   interest(transport.tempo().value());
   interest(transport.getPosition());
   interest(transport.isMetronomeEnabled());
   interest(cursorTrack.name());
   interest(cursorTrack.position());
   interest(cursorDevice.name());
   interest(cursorDevice.exists());
   interest(cursorDevice.isEnabled());
   interest(cursorDevice.position());
   interest(remotePage.getName());
   interest(remotePage.pageNames());
   interest(remotePage.selectedPageIndex());
   interest(cursorClip.exists());
   interest(cursorClip.getLoopLength());
   for (var p = 0; p < 8; p++) {
      var prm = remotePage.getParameter(p);
      interest(prm.name()); interest(prm.value()); interest(prm.displayedValue()); interest(prm.exists());
   }
   for (var d = 0; d < NUM_DEVICES; d++) {
      var dv = deviceBank.getItemAt(d);
      interest(dv.exists()); interest(dv.name()); interest(dv.isEnabled()); interest(dv.presetName()); interest(dv.isPlugin());
   }
   for (var s = 0; s < NUM_SCENES; s++) {
      var sc = sceneBank.getScene(s);
      interest(sc.name()); interest(sc.exists());
   }
   for (var t = 0; t < NUM_TRACKS; t++) {
      var tr = trackBank.getItemAt(t);
      interest(tr.exists()); interest(tr.name()); interest(tr.trackType()); interest(tr.color());
      interest(tr.mute()); interest(tr.solo()); interest(tr.arm());
      interest(tr.volume().value()); interest(tr.volume().displayedValue());
      interest(tr.pan().value()); interest(tr.pan().displayedValue());
      var sends = tr.sendBank();
      for (var se = 0; se < NUM_SENDS; se++) {
         var snd = sends.getItemAt(se);
         interest(snd.exists()); interest(snd.name()); interest(snd.value()); interest(snd.displayedValue());
      }
      var slots = tr.clipLauncherSlotBank();
      for (var c = 0; c < NUM_SCENES; c++) {
         var sl = slots.getItemAt(c);
         interest(sl.hasContent()); interest(sl.name());
         interest(sl.isPlaying()); interest(sl.isRecording());
      }
   }

   initPro();
   initExpert();
   initDeep();

   var osc = host.getOscModule();
   var space = osc.createAddressSpace();
   // OSC connections can only be made during init, so open one per allowed client reply port.
   var replyConns = {};
   for (var rp = 0; rp < REPLY_PORTS.length; rp++)
      replyConns[REPLY_PORTS[rp]] = osc.connectToUdpServer("127.0.0.1", REPLY_PORTS[rp], null);
   space.registerMethod("/mcp", ",s", "MCP request", function (source, message) {
      var reply, req = null;
      try {
         req = JSON.parse(message.getString(0));
         reply = { id: req.id, ok: true, result: dispatch(req.cmd, req.args || {}) };
      } catch (e) {
         reply = { id: req ? req.id : null, ok: false, error: String(e) };
      }
      try {
         var conn = replyConns[(req && req.reply_port) || REPLY_PORTS[0]] || replyConns[REPLY_PORTS[0]];
         conn.sendMessage("/reply", JSON.stringify(reply));
      } catch (e2) {
         host.errorln("Bitwig MCP send failed: " + e2);
      }
   });
   osc.createUdpServer(PORT, space);
   host.println("Bitwig MCP " + VERSION + " listening on UDP " + PORT);
}

// "batch" runs several commands in one round trip; each reports its own success/error.
function dispatch(cmd, a) {
   if (cmd !== "batch") return handle(cmd, a);
   var out = [];
   var cmds = a.commands || [];
   for (var i = 0; i < cmds.length; i++) {
      try { out.push({ ok: true, result: handle(cmds[i].cmd, cmds[i].args || {}) }); }
      catch (e) { out.push({ ok: false, error: String(e) }); }
   }
   return out;
}

function need(a, key) {
   if (a[key] === undefined || a[key] === null) throw "missing argument: " + key;
   return a[key];
}

function clamp01(v) {
   if (typeof v !== "number" || isNaN(v)) throw "value must be a number between 0 and 1";
   return Math.max(0, Math.min(1, v));
}

function track(i) {
   if (typeof i !== "number" || i < 0 || i >= NUM_TRACKS) throw "track_index must be 0-" + (NUM_TRACKS - 1);
   var tr = trackBank.getItemAt(i);
   if (!tr.exists().get()) throw "no track at index " + i + " (use get_session to list tracks)";
   return tr;
}

function slotOf(tr, s) {
   if (typeof s !== "number" || s < 0 || s >= NUM_SCENES) throw "slot must be 0-" + (NUM_SCENES - 1);
   return tr.clipLauncherSlotBank().getItemAt(s);
}

function hex(c) {
   function h(x) { var s = Math.round(x * 255).toString(16); return s.length < 2 ? "0" + s : s; }
   return "#" + h(c.red()) + h(c.green()) + h(c.blue());
}

function trackInfo(i, tr, withClips) {
   var o = {
      index: i, name: tr.name().get(), type: tr.trackType().get(), color: hex(tr.color()),
      mute: tr.mute().get(), solo: tr.solo().get(), arm: tr.arm().get(),
      volume: tr.volume().value().get(), volume_display: tr.volume().displayedValue().get(),
      pan: tr.pan().value().get(), pan_display: tr.pan().displayedValue().get(), sends: []
   };
   var sends = tr.sendBank();
   for (var se = 0; se < NUM_SENDS; se++) {
      var snd = sends.getItemAt(se);
      if (snd.exists().get())
         o.sends.push({ index: se, name: snd.name().get(), value: snd.value().get(), display: snd.displayedValue().get() });
   }
   if (withClips) {
      o.clips = [];
      var slots = tr.clipLauncherSlotBank();
      for (var c = 0; c < NUM_SCENES; c++) {
         var sl = slots.getItemAt(c);
         if (sl.hasContent().get())
            o.clips.push({ slot: c, name: sl.name().get(), playing: sl.isPlaying().get(), recording: sl.isRecording().get() });
      }
   }
   return o;
}

// Writes notes into the clip in (track, slot), creating it if needed. Runs asynchronously because
// Bitwig needs a moment for selection changes to reach the cursor clip.
function writeClip(a) {
   var tr = track(need(a, "track_index"));
   var slot = slotOf(tr, need(a, "slot"));
   var length = a.length_beats || 4;
   var step = NOTE_STEP;
   var notes = a.notes || [];
   focusedClip = a.track_index + "/" + a.slot; clipNotes = {};
   if (!slot.hasContent().get()) slot.createEmptyClip(length);
   cursorTrack.selectChannel(tr);
   host.scheduleTask(function () {
      slot.select();
      host.scheduleTask(function () {
         if (a.replace !== false) cursorClip.clearSteps();
         // Let the grid change and clear land before writing, otherwise it can wipe the first notes.
         host.scheduleTask(function () {
            for (var n = 0; n < notes.length; n++) {
               var nt = notes[n];
               if (nt.pitch < 0 || nt.pitch > 127) continue;
               cursorClip.setStep(Math.round(nt.start / step), nt.pitch,
                  Math.max(1, Math.min(127, nt.velocity == null ? 100 : nt.velocity)), nt.duration || step);
            }
            cursorClip.getLoopLength().set(length);
            if (a.name) { try { cursorClip.setName(String(a.name)); } catch (e) {} }
         }, 250);
      }, 200);
   }, 150);
   return { scheduled: notes.length + " notes", track: a.track_index, slot: a.slot };
}

function handle(cmd, a) {
   switch (cmd) {
      case "ping": return "pong";
      case "capabilities": return {
         version: VERSION, max_tracks: NUM_TRACKS, max_scenes: NUM_SCENES, max_sends: NUM_SENDS,
         missing_apis: missingApis
      };
      case "get_session": {
         var tracks = [];
         for (var t = 0; t < NUM_TRACKS; t++) {
            var tr = trackBank.getItemAt(t);
            if (tr.exists().get()) tracks.push(trackInfo(t, tr, !!a.with_clips));
         }
         var scenes = [];
         for (var s = 0; s < NUM_SCENES; s++) {
            var sc = sceneBank.getScene(s);
            if (sc.exists().get()) scenes.push({ index: s, name: sc.name().get() });
         }
         return {
            tempo: transport.tempo().value().getRaw(), playing: transport.isPlaying().get(),
            recording: recValue ? recValue.get() : null, position_beats: transport.getPosition().get(),
            metronome: transport.isMetronomeEnabled().get(),
            selected_track: { index: cursorTrack.position().get(), name: cursorTrack.name().get() },
            tracks: tracks, scenes: scenes
         };
      }
      case "get_track": return trackInfo(a.track_index, track(a.track_index), true);

      // Transport
      case "play": transport.play(); return "ok";
      case "stop": transport.stop(); return "ok";
      case "record": transport.record(); return "ok";
      case "set_tempo": {
         var bpm = need(a, "bpm");
         if (bpm < 20 || bpm > 666) throw "bpm must be between 20 and 666";
         transport.tempo().value().setRaw(bpm); return "ok";
      }
      case "set_position": seekTo(need(a, "beats")); return "ok";
      case "set_metronome": transport.isMetronomeEnabled().set(!!a.enabled); return "ok";
      case "undo": application.undo(); return "ok";
      case "redo": application.redo(); return "ok";

      // Tracks
      case "create_instrument_track": application.createInstrumentTrack(a.position == null ? -1 : a.position); return "ok";
      case "create_audio_track": application.createAudioTrack(a.position == null ? -1 : a.position); return "ok";
      case "create_effect_track": application.createEffectTrack(a.position == null ? -1 : a.position); return "ok";
      case "delete_track": track(a.track_index).deleteObject(); return "ok";
      case "set_track_name": track(a.track_index).name().set(String(need(a, "name"))); return "ok";
      case "set_track_volume": track(a.track_index).volume().setImmediately(clamp01(a.value)); return "ok";
      case "set_track_pan": track(a.track_index).pan().setImmediately(clamp01(a.value)); return "ok";
      case "set_track_mute": track(a.track_index).mute().set(!!a.value); return "ok";
      case "set_track_solo": track(a.track_index).solo().set(!!a.value); return "ok";
      case "set_track_arm": track(a.track_index).arm().set(!!a.value); return "ok";
      case "set_track_color": track(a.track_index).color().set(clamp01(a.r), clamp01(a.g), clamp01(a.b)); return "ok";
      case "set_send": {
         var snd = track(a.track_index).sendBank().getItemAt(need(a, "send_index"));
         if (!snd.exists().get()) throw "no send " + a.send_index + " (create an FX track first)";
         snd.setImmediately(clamp01(a.value)); return "ok";
      }
      case "select_track": {
         var trs = track(a.track_index);
         trs.selectInEditor(); cursorTrack.selectChannel(trs); return "ok";
      }

      // Clip launcher
      case "launch_clip": slotOf(track(a.track_index), a.slot).launch(); return "ok";
      case "stop_track_clips": track(a.track_index).stop(); return "ok";
      case "launch_scene": sceneBank.getScene(need(a, "scene")).launch(); return "ok";
      case "stop_all_clips": trackBank.getClipLauncherScenes().stop(); return "ok";
      case "set_scene_name": {
         var scn = sceneBank.getScene(need(a, "scene")), nm = String(need(a, "name"));
         try { scn.name().set(nm); } catch (e) { scn.setName(nm); }  // newer API: name() is settable
         return "ok";
      }
      case "create_clip": {
         var trc = track(a.track_index);
         var slot = slotOf(trc, a.slot);
         if (slot.hasContent().get()) throw "slot " + a.slot + " already has a clip";
         slot.createEmptyClip(a.length_beats || 4);
         cursorTrack.selectChannel(trc);
         host.scheduleTask(function () { slot.select(); }, 150);
         return "ok";
      }
      case "write_clip": return writeClip(a);
      case "delete_clip": slotOf(track(a.track_index), a.slot).deleteObject(); return "ok";
      case "select_clip": {
         var tr2 = track(a.track_index);
         cursorTrack.selectChannel(tr2);
         slotOf(tr2, a.slot).select();
         return "ok";
      }
      case "add_notes": {
         if (!cursorClip.exists().get()) throw "no clip selected (use select_clip or write_clip)";
         var step = NOTE_STEP;
         var notes = a.notes || [];
         for (var n = 0; n < notes.length; n++) {
            var nt = notes[n];
            cursorClip.setStep(Math.round(nt.start / step), nt.pitch, nt.velocity == null ? 100 : nt.velocity, nt.duration || step);
         }
         return "added " + notes.length;
      }
      case "clear_notes": cursorClip.clearSteps(); return "ok";
      case "set_clip_loop_length": cursorClip.getLoopLength().set(need(a, "length_beats")); return "ok";
      case "transpose_clip": cursorClip.transpose(need(a, "semitones")); return "ok";

      // Devices / remote controls on the selected track
      case "insert_file": {
         var ip = a.before_device != null ? deviceBank.getItemAt(a.before_device).beforeDeviceInsertionPoint()
            : a.where === "start" ? cursorTrack.startOfDeviceChainInsertionPoint() : cursorTrack.endOfDeviceChainInsertionPoint();
         ip.insertFile(String(need(a, "path")));
         return "ok";
      }
      case "insert_file_to_slot": {
         var sl2 = slotOf(track(a.track_index), need(a, "slot"));
         sl2.replaceInsertionPoint().insertFile(String(need(a, "path")));
         return "ok";
      }
      case "insert_device_browser": cursorTrack.endOfDeviceChainInsertionPoint().browse(); return "browser opened in Bitwig";
      case "list_devices": {
         var devs = [];
         for (var d = 0; d < NUM_DEVICES; d++) {
            var dv = deviceBank.getItemAt(d);
            if (dv.exists().get()) devs.push({ index: d, name: dv.name().get(), preset: dv.presetName().get(), plugin: dv.isPlugin().get(), enabled: dv.isEnabled().get() });
         }
         return { track: cursorTrack.name().get(), devices: devs };
      }
      case "get_device": {
         var params = [];
         for (var p = 0; p < 8; p++) {
            var prm = remotePage.getParameter(p);
            if (prm.exists().get())
               params.push({ index: p, name: prm.name().get(), value: prm.value().get(), display: prm.displayedValue().get() });
         }
         var names = remotePage.pageNames().get(), pages = [];
         for (var q = 0; q < names.length; q++) pages.push(String(names[q]));
         return {
            track: cursorTrack.name().get(),
            device: cursorDevice.exists().get() ? cursorDevice.name().get() : null,
            device_index: cursorDevice.exists().get() ? cursorDevice.position().get() : null,
            enabled: cursorDevice.exists().get() ? cursorDevice.isEnabled().get() : null,
            page: remotePage.getName().get(), page_index: remotePage.selectedPageIndex().get(),
            pages: pages, params: params
         };
      }
      case "select_device": {
         var dsel = deviceBank.getItemAt(need(a, "device_index"));
         if (!dsel.exists().get()) throw "no device at index " + a.device_index + " (use list_devices)";
         cursorDevice.selectDevice(dsel); return "ok";
      }
      case "delete_device": {
         var ddel = deviceBank.getItemAt(need(a, "device_index"));
         if (!ddel.exists().get()) throw "no device at index " + a.device_index;
         ddel.deleteObject(); return "ok";
      }
      case "next_device": cursorDevice.selectNext(); return "ok";
      case "prev_device": cursorDevice.selectPrevious(); return "ok";
      case "select_remote_page": remotePage.selectedPageIndex().set(need(a, "page")); return "ok";
      case "set_remote_param": {
         var rp = remotePage.getParameter(need(a, "index"));
         if (!rp.exists().get()) throw "no remote control at index " + a.index;
         rp.setImmediately(clamp01(a.value)); return "ok";
      }
      case "set_device_enabled": cursorDevice.isEnabled().set(!!a.enabled); return "ok";
      case "toggle_device": cursorDevice.isEnabled().toggle(); return "ok";
   }
   var r = handlePro(cmd, a);
   if (r !== undefined) return r;
   r = handleExpert(cmd, a);
   if (r !== undefined) return r;
   r = handleArranger(cmd, a);
   if (r !== undefined) return r;
   r = handleDeep(cmd, a);
   if (r !== undefined) return r;
   throw "unknown command: " + cmd;
}

function exit() {}
