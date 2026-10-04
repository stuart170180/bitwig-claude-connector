// TEMPORARY probe script (research only). Loaded from BitwigMCP.control.js while experimenting.
load("probe2.js");
var PX = {}, PX_ERR = {}, PX_LOG = [];
function pxMk(name, fn) { try { PX[name] = fn(); interestSafe(PX[name]); } catch (e) { PX_ERR[name] = String(e); } }
function interestSafe(o) {}
function initProbe() {
   pxMk("popup", function () { return host.createPopupBrowser(); });
   pxMk("mixer", function () { return host.createMixer(); });
   pxMk("arranger", function () { return host.createArranger(); });
   pxMk("project", function () { return host.getProject(); });
   pxMk("prefs", function () { return host.getPreferences(); });
   pxMk("docstate", function () { return host.getDocumentState(); });
   pxMk("groove", function () { return host.createGroove(); });
   pxMk("master", function () { return host.createMasterTrack(0); });
   pxMk("effects", function () { return host.createEffectTrackBank(8, 8); });
   pxMk("userctl", function () { return host.createUserControls(8); });
   pxMk("lastclicked", function () { return host.createLastClickedParameter("PXLC", "LastClicked"); });
   pxMk("detail", function () { return host.createDetailEditor(); });
   pxMk("recorder", function () { return host.createMasterRecorder(); });
   pxMk("arrCursorTrack", function () { return host.createArrangerCursorTrack(0, 0); });
   pxMk("arrClip", function () { return host.createArrangerCursorClip(16, 16); });
   pxMk("cursorLayer", function () { return cursorDevice.createCursorLayer(); });
   pxMk("drumBank", function () { return cursorDevice.createDrumPadBank(16); });
   pxMk("chainSel", function () { return cursorDevice.createChainSelector(); });
   pxMk("devBrowser", function () { return cursorDevice.createDeviceBrowser(5, 5); });
   pxMk("hw", function () { return host.createHardwareSurface(); });
   pxMk("notif", function () { return host.getNotificationSettings(); });
   pxMk("noteIn", function () { return host.getMidiInPort(0); });
   try { PX.master && PX.master.exists().markInterested(); } catch (e) {}
   try { initProbe2(); } catch (e) { PX_ERR.p2 = String(e); }
   try { PX.popup.exists().markInterested(); PX.popup.selectedContentTypeName().markInterested(); PX.popup.title().markInterested(); } catch (e) { PX_ERR.popupI = String(e); }
   try { PX.recorder.isRecording && 0; } catch (e) {}
   // mark a bunch of things
   try { var A = PX.arranger; ["hasDoubleRowTrackHeight","isClipLauncherVisible","isTimelineVisible","isIoSectionVisible","areEffectTracksVisible","isPlaybackFollowEnabled","areCueMarkersVisible"].forEach(function (n) { try { A[n]().markInterested(); } catch (e) { PX_ERR["arr." + n] = String(e); } }); } catch (e) {}
   try { var M = PX.mixer; ["isClipLauncherSectionVisible","isCrossFadeSectionVisible","isDeviceSectionVisible","isIoSectionVisible","isMeterSectionVisible","isSendSectionVisible"].forEach(function (n) { try { M[n]().markInterested(); } catch (e) { PX_ERR["mix." + n] = String(e); } }); } catch (e) {}
   try { var P = PX.project; ["hasSoloedTracks","hasMutedTracks","hasArmedTracks"].forEach(function (n) { try { P[n]().markInterested(); } catch (e) { PX_ERR["prj." + n] = String(e); } }); P.name && 0; } catch (e) {}
   try { application.projectName().markInterested(); } catch (e) { PX_ERR.projname = String(e); }
   try { application.canUndo().markInterested(); application.canRedo().markInterested(); } catch (e) { PX_ERR.undo = String(e); }
   try { application.hasActiveEngine().markInterested(); application.panelLayout().markInterested(); application.displayProfile().markInterested(); } catch (e) { PX_ERR.app = String(e); }
   try { cursorTrack.sourceSelector().hasAudioInputSelected().markInterested(); cursorTrack.sourceSelector().hasNoteInputSelected().markInterested(); } catch (e) { PX_ERR.src = String(e); }
   try { cursorTrack.monitorMode().markInterested(); cursorTrack.isGroup().markInterested(); cursorTrack.crossFadeMode().markInterested(); } catch (e) { PX_ERR.mon = String(e); }
}
function jsonify(v, depth) {
   depth = depth || 0;
   if (v === null || v === undefined) return v === undefined ? "(undefined)" : null;
   var t = typeof v;
   if (t === "number" || t === "boolean" || t === "string") return v;
   if (t === "function") return "(function)";
   try { if (v.length !== undefined && t === "object" && depth < 3) { var o = []; for (var i = 0; i < v.length && i < 400; i++) o.push(jsonify(v[i], depth + 1)); return o; } } catch (e) {}
   try { return "" + v; } catch (e) { return "(unprintable)"; }
}
function handleProbe(cmd, a) {
   switch (cmd) {
      case "px_eval": { var r = eval(String(a.code)); return jsonify(r); }
      case "px_err": return PX_ERR;
      case "px_log": { var l = PX_LOG; PX_LOG = []; return l; }
      case "px_methods": {   // list function names on a global expression
         var obj = eval(String(a.expr)), out = [];
         for (var k in obj) { try { if (typeof obj[k] === "function") out.push(k); } catch (e) {} }
         return out.sort();
      }
   }
   return undefined;
}
