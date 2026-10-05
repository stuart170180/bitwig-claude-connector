// DRAFT - NOT INSTALLED. PopupBrowser commands for the Bitwig MCP controller script (loadAPI 25).
// Wire-in (after review): save as bitwig_script/browser.js, add load("browser.js"); to BitwigMCP.control.js,
// call initBrowser() at the end of init() (BEFORE the osc block), and add to handle():
//    r = handleBrowser(cmd, a); if (r !== undefined) return r;
// Rules respected: every proxy object is created and markInterested() in init only; no Signal.fire(); no new reply ports.
// Sources: Bitwig 6.1 Controller API javadoc (PopupBrowser, BrowserFilterColumn, BrowserItemBank, InsertionPoint, Scrollable);
// structure mirrors DrivenByMoss BrowserImpl.java / BrowserColumnImpl.java.

var BR_COLS = ["location", "file_type", "category", "tag", "creator", "device_type", "device"];   // smartCollectionColumn skipped (DrivenByMoss: broken since Bitwig 5)
var BR_FILTER_WINDOW = 24, BR_RESULT_WINDOW = 32;
var brPopup = null, brCols = {}, brResultBank = null, brResultCursor = null, brErr = null;

function initBrowser() {
   try {
      brPopup = host.createPopupBrowser();
      interest(brPopup.exists()); interest(brPopup.title());
      interest(brPopup.contentTypeNames()); interest(brPopup.selectedContentTypeIndex()); interest(brPopup.selectedContentTypeName());
      interest(brPopup.shouldAudition()); interest(brPopup.canAudition());
      var cols = { location: brPopup.locationColumn(), file_type: brPopup.fileTypeColumn(), category: brPopup.categoryColumn(),
                   tag: brPopup.tagColumn(), creator: brPopup.creatorColumn(), device_type: brPopup.deviceTypeColumn(), device: brPopup.deviceColumn() };
      for (var i = 0; i < BR_COLS.length; i++) {
         var k = BR_COLS[i], c = cols[k];
         interest(c.exists()); interest(c.name()); interest(c.entryCount());
         var wild = c.getWildcardItem(); interest(wild.name()); interest(wild.exists());
         var cur = c.createCursorItem(); interest(cur.exists()); interest(cur.name());
         var bank = cur.createSiblingsBank(BR_FILTER_WINDOW);   // follows the cursor; scrollPosition() is settable
         interest(bank.itemCount()); interest(bank.scrollPosition());
         for (var j = 0; j < BR_FILTER_WINDOW; j++) {
            var it = bank.getItemAt(j);
            interest(it.exists()); interest(it.name()); interest(it.isSelected()); interest(it.hitCount());
         }
         brCols[k] = { col: c, wild: wild, bank: bank };
      }
      var rc = brPopup.resultsColumn(); interest(rc.exists()); interest(rc.entryCount());
      brResultCursor = rc.createCursorItem(); interest(brResultCursor.exists()); interest(brResultCursor.name());
      brResultBank = brResultCursor.createSiblingsBank(BR_RESULT_WINDOW);
      interest(brResultBank.itemCount()); interest(brResultBank.scrollPosition());
      for (var r = 0; r < BR_RESULT_WINDOW; r++) {
         var ri = brResultBank.getItemAt(r); interest(ri.exists()); interest(ri.name()); interest(ri.isSelected());
      }
   } catch (e) { brErr = String(e); brPopup = null; }
}

function brNeed() {
   if (!brPopup) throw "popup browser unavailable: " + brErr;
   if (!brPopup.exists().get()) throw "no browser session is open (call browse_open first)";
}

function brState() {
   var o = { open: brPopup.exists().get(), title: brPopup.title().get(), content_types: brPopup.contentTypeNames().get(),
             content_type: brPopup.selectedContentTypeName().get(), content_type_index: brPopup.selectedContentTypeIndex().get(), columns: {} };
   for (var i = 0; i < BR_COLS.length; i++) {
      var k = BR_COLS[i], b = brCols[k], sel = [];
      for (var j = 0; j < BR_FILTER_WINDOW; j++) { var it = b.bank.getItemAt(j); if (it.exists().get() && it.isSelected().get()) sel.push(it.name().get()); }
      o.columns[k] = { exists: b.col.exists().get(), name: b.col.name().get(), entries: b.col.entryCount().get(), selected: sel };
   }
   o.result_count = brPopup.resultsColumn().entryCount().get();
   o.result_cursor = brResultCursor.exists().get() ? brResultCursor.name().get() : null;
   return o;
}

function handleBrowser(cmd, a) {
   switch (cmd) {
      case "browse_status": return brPopup ? brState() : { available: false, error: brErr };

      // Open the browser. where: end | start (of the track's chain), after | before | replace (relative to a device of the SELECTED track
      // at device_index in deviceBank). track_index uses trackBank (no selection needed for end/start). Browser opens ~100 ms later.
      case "browse_open": {
         if (!brPopup) throw "popup browser unavailable: " + brErr;
         var where = a.where || "end", ip;
         if (brPopup.exists().get()) { brPopup.cancel(); }   // close any previous session first, then wait (DrivenByMoss waits 100 ms)
         if (where === "end" || where === "start") {
            var tr = a.track_index === undefined || a.track_index === null ? cursorTrack : track(a.track_index);
            ip = where === "end" ? tr.endOfDeviceChainInsertionPoint() : tr.startOfDeviceChainInsertionPoint();
         } else {
            var dv = deviceBank.getItemAt(need(a, "device_index"));
            if (!dv.exists().get()) throw "no device at index " + a.device_index + " on the selected track";
            ip = where === "after" ? dv.afterDeviceInsertionPoint() : where === "before" ? dv.beforeDeviceInsertionPoint() : dv.replaceDeviceInsertionPoint();
         }
         host.scheduleTask(function () { ip.browse(); }, 150);
         return { scheduled: where };   // poll browse_status until open === true
      }

      case "browse_content_type": {   // by index or name (tabs: e.g. Device, Preset, Sample ...)
         brNeed();
         if (a.index != null) brPopup.selectedContentTypeIndex().set(+a.index);
         else if (a.name != null) {
            var names = brPopup.contentTypeNames().get(), n = -1;
            for (var i = 0; i < names.length; i++) if (String(names[i]).toLowerCase() === String(a.name).toLowerCase()) n = i;
            if (n < 0) throw "no content type " + a.name + "; have " + names.join(", ");
            brPopup.selectedContentTypeIndex().set(n);
         }
         return "ok";   // columns and results refill asynchronously; re-read with browse_status
      }

      // List a filter column's entries from window offset `start` (0 = top). Large columns (Device, Creator) need paging.
      case "browse_columns": {
         brNeed();
         var kk = String(need(a, "column")), cb = brCols[kk];
         if (!cb) throw "column must be one of " + BR_COLS.join(", ");
         if (a.start != null) cb.bank.scrollPosition().set(+a.start);
         var items = [];
         for (var j = 0; j < BR_FILTER_WINDOW; j++) {
            var it = cb.bank.getItemAt(j);
            if (it.exists().get()) items.push({ name: it.name().get(), hits: it.hitCount().get(), selected: it.isSelected().get() });
         }
         return { column: kk, entries: cb.col.entryCount().get(), window_start: cb.bank.scrollPosition().get(), items: items };
      }

      // Select a filter entry by exact (case-insensitive) name in the current window; value "*" or null selects the wildcard (clears the filter).
      case "browse_filter": {
         brNeed();
         var cn = String(need(a, "column")), cf = brCols[cn];
         if (!cf) throw "column must be one of " + BR_COLS.join(", ");
         if (a.value == null || a.value === "*") { cf.wild.isSelected().set(true); return "wildcard selected"; }
         var want = String(a.value).toLowerCase();
         for (var q = 0; q < BR_FILTER_WINDOW; q++) {
            var f = cf.bank.getItemAt(q);
            if (f.exists().get() && f.name().get().toLowerCase() === want) { f.isSelected().set(true); return "selected " + f.name().get(); }
         }
         throw "'" + a.value + "' not in the visible window (start " + cf.bank.scrollPosition().get() + " of " + cf.col.entryCount().get() + "); page with browse_columns start=N";
      }

      case "browse_results": {
         brNeed();
         if (a.start != null) brResultBank.scrollPosition().set(+a.start);
         var lim = Math.min(a.limit || 20, BR_RESULT_WINDOW), res = [];
         for (var r = 0; r < BR_RESULT_WINDOW && res.length < lim; r++) {
            var ri = brResultBank.getItemAt(r);
            if (ri.exists().get()) res.push({ slot: r, name: ri.name().get(), selected: ri.isSelected().get() });
         }
         return { total: brPopup.resultsColumn().entryCount().get(), window_start: brResultBank.scrollPosition().get(), results: res };
      }

      // Select a result by window slot (from browse_results) - selecting loads nothing until browse_commit.
      case "browse_select": {
         brNeed();
         var s = brResultBank.getItemAt(need(a, "slot"));
         if (!s.exists().get()) throw "no result in slot " + a.slot;
         s.isSelected().set(true);
         return { selected: s.name().get() };   // name read is pre-change; confirm with browse_status.result_cursor
      }

      case "browse_audition": brNeed(); brPopup.shouldAudition().set(!!a.on); return "ok";   // plays the selected sample/preset in place
      case "browse_commit": brNeed(); brPopup.commit(); return "committed";                  // loads into the insertion point
      case "browse_cancel": if (brPopup && brPopup.exists().get()) brPopup.cancel(); return "cancelled";
   }
   return undefined;
}
