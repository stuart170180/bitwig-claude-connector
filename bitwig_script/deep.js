// Deep device access: walk into a device's layers / slots (e.g. the Mid and Side chains of Mid-Side Split),
// read and set EVERY parameter of the selected device (not just the 8 remote controls), insert and delete devices
// anywhere in the tree. Works on Bitwig's cursor device: navigate with deep_nav, then deep_info / deep_set.
var dpIds = [], dpName = {}, dpValue = {}, dpDisplay = {};
var deepLayers, deepSlot, eqSpec, eqTypeParams = [], eqErr = null;
var DEEP_LAYERS = 16;
var dispSpecs = {};
var DISP_DEVICES = { "42b32cd2-6275-4ff1-970f-4fac71d15ad9": ["ATTACK", "RELEASE", "RATIO", "THRESHOLD", "RELAX", "SMOOTH", "EXPAND_MID", "LINK_AMOUNT", "LINK_MODE",
   "INTENSITY_LOW", "INTENSITY_LMID", "INTENSITY_MID", "INTENSITY_HIGH", "TIMING_LOW", "TIMING_LMID", "TIMING_MID", "TIMING_HIGH", "VCA_MODE", "MIX", "INPUT",
   "ENVELOPE_MODE", "AUTO_TIMING", "GR_MODE", "RATIO_EXTENDED", "MAKEUP", "LATCH",
   "GR", "GAIN_REDUCTION", "REDUCTION", "GR_METER", "METER", "GAIN_REDUCTION_L", "GAIN_REDUCTION_R", "DETECTOR", "OUTPUT_LEVEL", "INPUT_LEVEL"] };

// DISP_EXTRA: more stock devices for real-unit display text (ids from deep_params; generated from the exploration run)
DISP_DEVICES["f2baa2a8-36c5-4a79-b1d9-a4e461c45ee9"] = ["MIX", "FEEDBACK", "HICUT", "LOCUT", "OFFSET", "MODEL", "PATTERN", "FOREVER", "STEPS", "TIME", "UNIT", "LEVEL_CONTROL", "THRESHOLD", "UPDATE_RATE", "WIDTH", "BLUR", "DUCKING", "DETUNE", "STEREO_DETUNE", "PAN", "CROSSFEED", "WIDTH_AFFECTS_FEEDBACK", "BLUR_TYPE"];  // Delay+
DISP_DEVICES["5a1cb339-1c4a-4cc7-9cae-bd7a2058153d"] = ["ROOM_SIZE", "DIFFUSION", "REVERB_TIME", "MIX", "BUILDUP", "WIDTH", "PRE-DELAY", "SHAPE", "LOFREQ", "HIFREQ", "LOX", "HIX", "EARLY_LATE"];  // Reverb
DISP_DEVICES["8da7251e-2578-4bcc-b3c4-8f4ec2e115d0"] = ["CEILING", "GAIN", "RELEASE", "RELEASE_BIAS"];  // Peak Limiter
DISP_DEVICES["e67b9c56-838d-4fba-8e3e-ae4e02cccbcb"] = ["AMPLITUDE", "WIDTH", "INVERT_LEFT", "INVERT_RIGHT", "PAN", "PAN_SWAP", "VOLUME"];  // Tool
DISP_DEVICES["8750db61-e9d3-4d0e-a610-e734006a64dc"] = ["FREQ", "AMOUNT", "MONITOR", "FILTER_TYPE"];  // De-Esser
DISP_DEVICES["556300ac-3a6e-4423-966a-5d5dde459a1b"] = ["THRESHOLD_LEVEL", "ATTACK", "RELEASE", "DEPTH"];  // Gate
DISP_DEVICES["93d11348-86ae-4ead-9fe7-84ac03b9369c"] = ["LOW_THRESHOLD", "LOW_RATIO", "LOW_KNEE", "HIGH_THRESHOLD", "HIGH_RATIO", "HIGH_KNEE", "DRIVE", "SKEW_THRESHOLD", "RATIO_SKEW", "KNEE_SKEW", "NORMALIZE", "CUTOFF", "POLES", "OUTPUT"];  // Saturator

DISP_DEVICES["384fe469-6023-4f69-9560-e0c2eec2da49"] = ["PITCH", "MIX", "GRAIN_RATE"];  // Pitch Shifter
DISP_DEVICES["4ac40334-99cc-43a3-b693-f3dc63211f0c"] = ["NOTE1", "NOTE2", "NOTE3", "NOTE4", "NOTE8", "NOTE7", "NOTE6", "NOTE5", "NOTE11", "NOTE10", "NOTE8VA", "NOTE9", "ROOT_KEY", "TUNE", "AMOUNT", "EDO_DIVISIONS", "MODE"];  // Micro-pitch
DISP_DEVICES["7ec87fdf-0bf8-42e7-b54b-5d8b68e330b1"] = ["MIX", "RANGE", "SHIFT", "LR_SPLIT"];  // Freq Shifter
DISP_DEVICES["e0ec7fdd-8b04-468b-8ebe-d320495957dc"] = ["REFERENCE_FREQUENCY", "SMOOTHING_FREQUENCY", "SILENCE_THRESHOLD", "HIGH_CUT_FREQUENCY"];  // Tuner

function initDeep() {
   interest(cursorDevice.hasLayers()); interest(cursorDevice.hasSlots()); interest(cursorDevice.isNested());
   interest(cursorDevice.slotNames());
   deepLayers = cursorDevice.createLayerBank(DEEP_LAYERS);
   deepSlot = cursorDevice.getCursorSlot();
   for (var i = 0; i < DEEP_LAYERS; i++) {
      var l = deepLayers.getItemAt(i);
      interest(l.exists()); interest(l.name());
   }
   // EQ+ exposes display text (band type names) only through its device-specific parameter objects.
   try {
      eqSpec = cursorDevice.createSpecificBitwigDevice(java.util.UUID.fromString("e4815188-ba6f-4d14-bcfc-2dcb8f778ccb"));
      for (var b = 1; b <= 8; b++) {
         var tp = eqSpec.createParameter("TYPE" + b);
         interest(tp.value()); interest(tp.displayedValue()); eqTypeParams.push(tp);
      }
   } catch (e) { eqErr = String(e); }
   // Direct-parameter display text never arrives, so real units come from device-specific parameter objects (init-time only).
   for (var uu in DISP_DEVICES) {
      try {
         var dev = cursorDevice.createSpecificBitwigDevice(java.util.UUID.fromString(uu)), ps = {};
         DISP_DEVICES[uu].forEach(function (id) { try { var q = dev.createParameter(id); interest(q.value()); interest(q.displayedValue()); ps[id] = q; } catch (e) {} });
         dispSpecs[uu] = { dev: dev, params: ps };
      } catch (e) { eqErr = (eqErr || "") + " disp " + uu + ": " + e; }
   }
   cursorDevice.addDirectParameterIdObserver(function (ids) {
      dpIds = []; dpName = {}; dpValue = {}; dpDisplay = {};
      for (var i = 0; i < ids.length; i++) dpIds.push(String(ids[i]));
   });
   cursorDevice.addDirectParameterNameObserver(60, function (id, name) { dpName[String(id)] = String(name); });
   cursorDevice.addDirectParameterNormalizedValueObserver(function (id, v) { dpValue[String(id)] = v; });
   cursorDevice.addDirectParameterValueDisplayObserver(32, function (id, t) { dpDisplay[String(id)] = String(t); });
}

function layerList() {
   var out = [];
   for (var i = 0; i < DEEP_LAYERS; i++) {
      var l = deepLayers.getItemAt(i);
      if (l.exists().get()) out.push({ index: i, name: l.name().get() });
   }
   return out;
}

function deepInfo(a) {
   var off = a.offset || 0, lim = a.limit != null ? a.limit : 80, filt = a.filter ? String(a.filter).toLowerCase() : null;
   var ids = dpIds;
   if (filt) ids = ids.filter(function (id) { return (String(dpName[id] || "") + " " + id).toLowerCase().indexOf(filt) >= 0; });
   var params = [];
   for (var i = off; i < ids.length && params.length < lim; i++) {
      var id = ids[i];
      params.push({ id: id, name: dpName[id] || "", value: dpValue[id], display: dpDisplay[id] || "" });
   }
   var slots = [], sn = cursorDevice.slotNames().get();
   for (var s = 0; s < sn.length; s++) slots.push(String(sn[s]));
   return {
      track: cursorTrack.name().get(),
      device: cursorDevice.exists().get() ? cursorDevice.name().get() : null,
      position: cursorDevice.exists().get() ? cursorDevice.position().get() : null,
      nested: cursorDevice.isNested().get(),
      enabled: cursorDevice.exists().get() ? cursorDevice.isEnabled().get() : null,
      has_layers: cursorDevice.hasLayers().get(), layers: layerList(),
      has_slots: cursorDevice.hasSlots().get(), slots: slots,
      param_count: ids.length, offset: off, params: params
   };
}

function handleDeep(cmd, a) {
   switch (cmd) {
      case "deep_info": return deepInfo(a);
      case "deep_display": {   // real display text (e.g. "-18.0 dB") for a device's parameters, via device-specific parameter objects
         var uuid = String(need(a, "uuid")), spec = dispSpecs[uuid];
         if (!spec) throw "no display support for device " + uuid + " (supported: " + Object.keys(dispSpecs).join(", ") + ")";
         var res = {}, want = a.ids || Object.keys(spec.params);
         for (var i = 0; i < want.length; i++) {
            var pid = String(want[i]), short = pid.indexOf("/") >= 0 ? pid.substring(pid.indexOf("/") + 1) : pid, pp = spec.params[short];
            if (pp) res["CONTENTS/" + short] = { display: String(pp.displayedValue().get()), value: pp.value().get() };
         }
         return res;
      }
      case "deep_eq_types": {
         if (eqErr) throw "EQ+ specific device unavailable: " + eqErr;
         var tl = [];
         for (var i = 0; i < eqTypeParams.length; i++) tl.push({ band: i + 1, value: eqTypeParams[i].value().get(), display: eqTypeParams[i].displayedValue().get() });
         return tl;
      }
      case "deep_nav": {
         var act = String(need(a, "action"));
         if (act === "parent") cursorDevice.selectParent();
         else if (act === "first_in_layer") { if (typeof a.layer === "string") cursorDevice.selectFirstInLayer(a.layer); else cursorDevice.selectFirstInLayer(need(a, "layer")); }
         else if (act === "last_in_layer") { if (typeof a.layer === "string") cursorDevice.selectLastInLayer(a.layer); else cursorDevice.selectLastInLayer(need(a, "layer")); }
         else if (act === "first_in_slot") cursorDevice.selectFirstInSlot(String(need(a, "slot")));
         else if (act === "last_in_slot") cursorDevice.selectLastInSlot(String(need(a, "slot")));
         else if (act === "select_slot") deepSlot.selectSlot(String(need(a, "slot")));
         else if (act === "next") cursorDevice.selectNext();
         else if (act === "prev") cursorDevice.selectPrevious();
         else if (act === "first") cursorDevice.selectFirst();
         else if (act === "last") cursorDevice.selectLast();
         else throw "action must be parent, first_in_layer, last_in_layer, first_in_slot, last_in_slot, next, prev, first or last";
         return "ok";
      }
      case "deep_set": {
         var id = String(need(a, "id"));
         if (dpIds.indexOf(id) < 0) throw "no parameter with id " + id + " on the selected device (use deep_info)";
         cursorDevice.setDirectParameterValueNormalized(id, clamp01(need(a, "value")) * 16384, 16384);  // value is in 0..resolution
         return "ok";
      }
      case "deep_insert_uuid": {
         // Insert any Bitwig device by UUID (no file needed): top level end/start/before/after, or the end of a slot.
         var uid = java.util.UUID.fromString(String(need(a, "uuid"))), wh = a.where || "end";
         if (wh === "slot_end") {
            if (a.slot) deepSlot.selectSlot(String(a.slot));
            deepSlot.endOfDeviceChainInsertionPoint().insertBitwigDevice(uid);
         } else if (wh === "after") cursorDevice.afterDeviceInsertionPoint().insertBitwigDevice(uid);
         else if (wh === "before") cursorDevice.beforeDeviceInsertionPoint().insertBitwigDevice(uid);
         else if (wh === "start") cursorTrack.startOfDeviceChainInsertionPoint().insertBitwigDevice(uid);
         else cursorTrack.endOfDeviceChainInsertionPoint().insertBitwigDevice(uid);
         return "ok";
      }
      case "deep_delete": cursorDevice.deleteObject(); return "ok";
      case "deep_insert_file": {
         var path = String(need(a, "path"));
         var where = a.where || "after";
         if (where === "slot_end") {
            if (a.slot) deepSlot.selectSlot(String(a.slot));  // pass no slot to use the one chosen with deep_nav select_slot
            deepSlot.endOfDeviceChainInsertionPoint().insertFile(path);
         } else if (where === "layer_end") {
            var l = deepLayers.getItemAt(need(a, "layer"));
            if (!l.exists().get()) throw "no layer " + a.layer;
            l.endOfDeviceChainInsertionPoint().insertFile(path);
         } else if (where === "before") cursorDevice.beforeDeviceInsertionPoint().insertFile(path);
         else if (where === "replace") cursorDevice.replaceDeviceInsertionPoint().insertFile(path);
         else cursorDevice.afterDeviceInsertionPoint().insertFile(path);
         return "ok";
      }
   }
   return undefined;
}
