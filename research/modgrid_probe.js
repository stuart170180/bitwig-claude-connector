// TEMP probe block that was pasted into the top of `switch (cmd)` in deep.js's handleDeep (then removed).
case "probe_actions": {   // lists every Bitwig action (782 in this install)
   var acts = application.getActions(), out = [];
   for (var q = 0; q < acts.length; q++) out.push(String(acts[q].getCategory().getName()) + " | " + String(acts[q].getId()) + " | " + String(acts[q].getName()));
   return out;
}
case "probe_modsrc": {    // cursorDevice.getModulationSource(i) -> throws "deprecated since API version 2" in API v17
   var res = [];
   for (var m = 0; m < 8; m++) { try { var ms = cursorDevice.getModulationSource(m); res.push({ i: m, name: ms.name().get() }); } catch (e) { res.push({ i: m, err: String(e) }); } }
   return res;
}
case "probe_insert_uuid": { // insertBitwigDevice(UUID) after the cursor device (works for devices, ignored for modulator UUIDs)
   cursorDevice.afterDeviceInsertionPoint().insertBitwigDevice(java.util.UUID.fromString(String(need(a, "uuid")))); return "ok";
}
