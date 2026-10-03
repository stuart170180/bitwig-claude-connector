// Deep device access: walk into a device's layers / slots (e.g. the Mid and Side chains of Mid-Side Split),
// read and set EVERY parameter of the selected device (not just the 8 remote controls), insert and delete devices
// anywhere in the tree. Works on Bitwig's cursor device: navigate with deep_nav, then deep_info / deep_set.
var dpIds = [], dpName = {}, dpValue = {}, dpDisplay = {};
var deepLayers, deepSlot, eqSpec, eqTypeParams = [], eqErr = null;
var DEEP_LAYERS = 16;

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
