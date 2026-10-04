// TEMPORARY probe part 2 (init-time markInterested for lots of objects; settings creation)
function mi(o) { try { o.markInterested(); } catch (e) { PX_ERR["mi" + (PX_LOG.length)] = String(e); PX_LOG.push(String(e)); } }
function each(obj, names, tag) {
   names.forEach(function (n) { try { var v = obj[n](); if (v && v.markInterested) mi(v); } catch (e) { PX_ERR[tag + "." + n] = String(e); } });
}
function initProbe2() {
   try { mi(PX.recorder.isActive()); mi(PX.recorder.duration()); } catch (e) { PX_ERR.rec2 = String(e); }
   try { var lp = PX.lastclicked.parameter(); mi(PX.lastclicked.exists()); mi(PX.lastclicked.isLocked()); mi(lp.name()); mi(lp.value()); mi(lp.displayedValue()); mi(lp.exists()); } catch (e) { PX_ERR.lc2 = String(e); }
   each(transport, ["isArrangerLoopEnabled", "isPunchInEnabled", "isPunchOutEnabled", "isArrangerOverdubEnabled", "isClipLauncherOverdubEnabled", "isArrangerAutomationWriteEnabled", "isClipLauncherAutomationWriteEnabled", "isFillModeActive", "isMetronomeTickPlaybackEnabled", "preRoll", "clipLauncherPostRecordingAction", "automationWriteMode", "defaultLaunchQuantization", "isMetronomeAudibleDuringPreRoll", "arrangerLoopStart", "arrangerLoopDuration", "playStartPosition", "playPositionInSeconds", "playStartPositionInSeconds", "getInPosition", "getOutPosition", "clipLauncherPostRecordingTimeOffset", "timeSignature", "crossfade", "metronomeVolume"], "tr");
   each(PX.groove, ["getEnabled", "getAccentAmount", "getAccentPhase", "getAccentRate", "getShuffleAmount", "getShuffleRate"], "gr");
   for (var i = 0; i < 8; i++) each(trackBank.getItemAt(i), ["monitorMode", "crossFadeMode", "isGroup", "isStopped", "isQueuedForStop", "canHoldAudioData", "canHoldNoteData", "isActivated", "position", "isPreFader", "autoMonitor", "monitor"], "tb");
   try { for (var i2 = 0; i2 < 8; i2++) { var s = trackBank.getItemAt(i2).sourceSelector(); mi(s.hasAudioInputSelected()); mi(s.hasNoteInputSelected()); } } catch (e) { PX_ERR.ssel = String(e); }
   each(cursorTrack, ["crossFadeMode", "monitorMode", "autoMonitor", "monitor", "isGroup", "isPreFader"], "ct");
   each(cursorDevice, ["isPlugin", "isWindowOpen", "isExpanded", "isMacroSectionVisible", "isParameterPageSectionVisible", "isRemoteControlsSectionVisible", "presetName", "presetCategory", "presetCreator", "sampleName", "hasDrumPads", "hasLayers", "hasSlots", "deviceType"], "dev");
   try { PX.macros = []; for (var m = 0; m < 8; m++) { var mc = cursorDevice.getMacro(m); mi(mc.getAmount().value()); mi(mc.getAmount().name()); mi(mc.getAmount().displayedValue()); mi(mc.isMapped()); mi(mc.getLabel()); PX.macros.push(mc); } } catch (e) { PX_ERR.macro = String(e); }
   try { PX.modSrc = []; for (var k = 0; k < 8; k++) { var ms = cursorDevice.getModulationSource(k); mi(ms.name()); mi(ms.exists()); mi(ms.isMapping()); PX.modSrc.push(ms); } } catch (e) { PX_ERR.modsrc = String(e); }
   each(cursorClip, ["getShuffle", "getAccent", "getPlayStart", "getPlayStop", "isLoopEnabled", "getLoopStart", "getLoopLength", "exists"], "clip");
   each(PX.arrClip, ["exists", "getShuffle", "getAccent", "getLoopLength", "getLoopStart", "isLoopEnabled", "getPlayStart", "getPlayStop"], "arrclip");
   each(PX.arrCursorTrack, ["name", "exists"], "act");
   each(PX.popup, ["exists", "title", "selectedContentTypeName", "selectedContentTypeIndex", "contentTypeNames", "canAudition", "shouldAudition"], "pb");
   try { PX.pbCols = pbCols(); } catch (e) { PX_ERR.pbcols = String(e); }
   each(PX.master, ["exists", "name", "color", "mute"], "mt");
   try { mi(PX.master.volume().value()); mi(PX.master.volume().displayedValue()); mi(PX.master.pan().value()); } catch (e) { PX_ERR.mt2 = String(e); }
   try { PX.fx = []; for (var f = 0; f < 8; f++) { var ft = PX.effects.getItemAt(f); mi(ft.exists()); mi(ft.name()); mi(ft.position()); PX.fx.push(ft); } } catch (e) { PX_ERR.fx = String(e); }
   each(application, ["projectName", "canUndo", "canRedo", "hasActiveEngine", "displayProfile", "recordQuantizationGrid", "recordQuantizeNoteLength"], "app2");
   each(PX.project, ["cueVolume", "cueMix"], "prj2");
   try { PX.uc = []; for (var u = 0; u < 8; u++) { var c = PX.userctl.getControl(u); mi(c.value()); mi(c.name()); mi(c.displayedValue()); PX.uc.push(c); } } catch (e) { PX_ERR.uc = String(e); }
   PX.sets = {};
   try {
      var P = PX.prefs;
      PX.sets.pstr = P.getStringSetting("PX String", "Probe", 30, "default"); mi(PX.sets.pstr);
      PX.sets.pnum = P.getNumberSetting("PX Number", "Probe", 0, 100, 1, "units", 42); mi(PX.sets.pnum);
      PX.sets.penum = P.getEnumSetting("PX Enum", "Probe", ["a", "b", "c"], "b"); mi(PX.sets.penum);
      PX.sets.pbool = P.getBooleanSetting("PX Bool", "Probe", true); mi(PX.sets.pbool);
   } catch (e) { PX_ERR.sets1 = String(e); }
   try {
      var D = PX.docstate;
      PX.sets.dstr = D.getStringSetting("PX DocString", "Probe", 60, "hello"); mi(PX.sets.dstr);
      PX.sets.dnum = D.getNumberSetting("PX DocNum", "Probe", 0, 10, 1, "x", 3); mi(PX.sets.dnum);
      PX.sigfired = 0;
      PX.sets.dsig = D.getSignalSetting("PX Signal", "Probe", "Fire"); PX.sets.dsig.addSignalObserver(function () { PX.sigfired++; });
      PX.sets.dtxt = D.getStringSetting("PX Notes", "Probe", 500, ""); mi(PX.sets.dtxt);
   } catch (e) { PX_ERR.sets2 = String(e); }
}
function pbCols() {
   var pb = PX.popup, o = {};
   ["smartCollectionColumn", "locationColumn", "deviceColumn", "categoryColumn", "tagColumn", "creatorColumn", "deviceTypeColumn", "fileTypeColumn"].forEach(function (n) {
      try {
         var col = pb[n](); mi(col.exists()); mi(col.entryCount());
         var bank = col.createItemBank(16);
         for (var i = 0; i < 16; i++) { var it = bank.getItemAt(i); mi(it.exists()); mi(it.name()); mi(it.isSelected()); mi(it.hitCount()); }
         o[n] = { col: col, bank: bank };
      } catch (e) { PX_ERR["col." + n] = String(e); }
   });
   try {
      var rc = pb.resultsColumn(); mi(rc.exists()); mi(rc.entryCount());
      var rb = rc.createItemBank(32);
      for (var j = 0; j < 32; j++) { var r = rb.getItemAt(j); mi(r.exists()); mi(r.name()); mi(r.isSelected()); }
      o.results = { col: rc, bank: rb };
   } catch (e) { PX_ERR.col_results = String(e); }
   return o;
}
