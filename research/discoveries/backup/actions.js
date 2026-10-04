// Bitwig actions and project-level commands (group tracks, bounce, export, ...). Owned by the "actions" feature work.
// Generic: action_list / action_run (with a deny-list). Track selection + grouping helpers: act_sel_state, act_select, act_groups.
var ACT_TRACKS = 40, ACT_CHILDREN = 16;
var actArrClip = null, actLayout = "";
var actSelMixer = [], actSelEditor = [], actChildBanks = [];
var ACT_DENY = [/^document:(close|new|open|quit|exit|save_as|revert)/i, /quit|exit(?! group)|close_project|close project|new_project|new project|open_project|open project|revert|reload/i,
   /delete_all|delete everything|clear_all|empty_trash|purge|factory|reset_all|remove_all|discard|uninstall|shutdown|restart/i,
   /^navigation:select_(next|prev)_project|activate_engine|select_project\d|switch_to_project|open_recent/i];

function actDenied(act) {
   var cid = String(act.getCategory().getId());
   if (cid === "file" && String(act.getId()) !== "Save") return true;      // new/open/close/quit/save-as/templates/library
   if (cid === "edit" && String(act.getId()) === "Delete") return true;     // generic delete of whatever is selected
   var s = String(act.getCategory().getId()) + ":" + String(act.getId()) + " " + String(act.getName());
   for (var i = 0; i < ACT_DENY.length; i++) if (ACT_DENY[i].test(s)) return true;
   return false;
}

function initActions() {
   try { application.panelLayout().addValueObserver(function (v) { actLayout = String(v); }); } catch (e) {}
   try { actArrClip = host.createArrangerCursorClip(16, 16); interest(actArrClip.exists()); interest(actArrClip.getLoopLength()); interest(actArrClip.getPlayStart()); interest(actArrClip.getPlayStop()); } catch (e) { actArrClip = null; }
   try { interest(trackBank.scrollPosition()); interest(trackBank.channelCount()); } catch (e) {}
   for (var t = 0; t < ACT_TRACKS; t++) {
      (function (i) {
         var tr = trackBank.getItemAt(i);
         actSelMixer[i] = false; actSelEditor[i] = false;
         try { tr.addIsSelectedInMixerObserver(function (v) { actSelMixer[i] = !!v; }); } catch (e) {}
         try { tr.addIsSelectedInEditorObserver(function (v) { actSelEditor[i] = !!v; }); } catch (e) {}
         try { interest(tr.isGroup()); interest(tr.isGroupExpanded()); } catch (e) {}
         try {
            var cb = tr.createTrackBank(ACT_CHILDREN, 0, 0, false);
            actChildBanks[i] = cb;
            for (var c = 0; c < ACT_CHILDREN; c++) { var ch = cb.getItemAt(c); interest(ch.exists()); interest(ch.name()); interest(ch.trackType()); }
         } catch (e2) { actChildBanks[i] = null; }
      })(t);
   }
}

function actFind(id) {
   var a = application.getAction(String(id));
   if (a) return a;
   var all = application.getActions(), low = String(id).toLowerCase();
   for (var i = 0; i < all.length; i++)
      if (String(all[i].getName()).toLowerCase() === low || String(all[i].getId()).toLowerCase() === low) return all[i];
   return null;
}

function actSelState() {
   var sel = [];
   for (var i = 0; i < ACT_TRACKS; i++) {
      var tr = trackBank.getItemAt(i);
      if (!tr.exists().get()) continue;
      sel.push({ index: i, name: tr.name().get(), mixer: actSelMixer[i], editor: actSelEditor[i],
                 is_group: tr.isGroup().get() });
   }
   return sel;
}

function actGroups() {
   var out = [];
   for (var i = 0; i < ACT_TRACKS; i++) {
      var tr = trackBank.getItemAt(i);
      if (!tr.exists().get() || !tr.isGroup().get()) continue;
      var kids = [], cb = actChildBanks[i];
      if (cb) for (var c = 0; c < ACT_CHILDREN; c++) {
         var ch = cb.getItemAt(c);
         if (ch.exists().get() && String(ch.trackType().get()) !== "Master") kids.push(String(ch.name().get()));
      }
      out.push({ index: i, name: tr.name().get(), expanded: tr.isGroupExpanded().get(), children: kids });
   }
   return out;
}

function handleActions(cmd, a) {
   switch (cmd) {
      case "action_list": {
         var all = application.getActions(), filt = a.filter ? String(a.filter).toLowerCase() : null;
         var lim = Math.min(a.limit != null ? a.limit : 100, 200), out = [], total = 0;
         for (var i = 0; i < all.length; i++) {
            var ac = all[i], cat = String(ac.getCategory().getId());
            var line = cat + " " + ac.getId() + " " + ac.getName();
            if (filt && line.toLowerCase().indexOf(filt) < 0) continue;
            total++;
            if (out.length < lim) out.push({ category: cat, id: String(ac.getId()), name: String(ac.getName()), blocked: actDenied(ac) });
         }
         return { total_matches: total, shown: out.length, actions: out };
      }
      case "action_run": {
         var act = actFind(need(a, "id"));
         if (!act) throw "no such action: " + a.id + " (use action_list to find ids)";
         if (actDenied(act)) throw "action blocked by safety deny-list: " + act.getId() + " (" + act.getName() + ")";
         act.invoke();
         return { ran: String(act.getId()), name: String(act.getName()) };
      }
      case "action_blocked": {   // names of every action the deny-list blocks
         var al = application.getActions(), bl = [];
         for (var j = 0; j < al.length; j++) if (actDenied(al[j])) bl.push(String(al[j].getCategory().getId()) + ":" + al[j].getId());
         return bl;
      }
      case "act_move_tracks": {   // experimental: move/copy tracks (flat indices). via: after | child_after | chain | start_chain | before
         var idxs = need(a, "track_indices"), mv = [];
         for (var k = 0; k < idxs.length; k++) mv.push(track(idxs[k]));
         var via = a.via || "after", ip;
         if (via === "child_after") {   // after child number a.child of group a.group (group bank item, not the main bank item)
            ip = actChildBanks[need(a, "group")].getItemAt(a.child || 0).afterTrackInsertionPoint();
         } else if (via === "chain") ip = track(need(a, "after_index")).endOfDeviceChainInsertionPoint();
         else if (via === "start_chain") ip = track(need(a, "after_index")).startOfDeviceChainInsertionPoint();
         else ip = track(need(a, "after_index")).afterTrackInsertionPoint();
         if (a.copy) ip.copyTracks.apply(ip, mv); else ip.moveTracks.apply(ip, mv);
         return "ok";
      }
      case "act_select_multi": {   // experimental: try selection APIs on several tracks in one call. how: mixer | editor | select | mixer_editor | all
         var ix = need(a, "track_indices"), how = a.how || "mixer";
         for (var q = 0; q < ix.length; q++) {
            var tq = track(ix[q]);
            if (how === "mixer" || how === "all") tq.selectInMixer();
            if (how === "editor" || how === "all") tq.selectInEditor();
            if (how === "select" || how === "all") tq.select();
            if (how === "mixer_editor") { if (q % 2 === 0) tq.selectInMixer(); else tq.selectInEditor(); }
         }
         return "ok";
      }
      case "act_bank_pos": {   // main track bank scroll position (selection-cursor actions can scroll it; 0 is normal)
         if (a.set != null) trackBank.scrollPosition().set(a.set);
         return { scroll_position: trackBank.scrollPosition().get(), channel_count: trackBank.channelCount().get() };
      }
      case "act_arr_clip": {   // the arranger-selected clip, as far as the API shows it
         if (!actArrClip) return null;
         return { exists: actArrClip.exists().get(), loop_length: actArrClip.getLoopLength().get(),
                  play_start: actArrClip.getPlayStart().get(), play_stop: actArrClip.getPlayStop().get() };
      }
      case "app_panel": {   // what: mixer | inspector | devices | note_editor | automation_editor | browser ; layout: ARRANGE | MIX | EDIT
         if (a.layout) application.setPanelLayout(String(a.layout));
         var w = a.what;
         if (w === "mixer") application.toggleMixer();
         else if (w === "inspector") application.toggleInspector();
         else if (w === "devices") application.toggleDevices();
         else if (w === "note_editor") application.toggleNoteEditor();
         else if (w === "automation_editor") application.toggleAutomationEditor();
         else if (w === "browser") application.toggleBrowserVisibility();
         return { layout: actLayout };
      }
      case "act_sel_state": return actSelState();
      case "act_groups": return actGroups();
      case "act_select": {   // select one track in mixer + editor + cursor
         var tr2 = track(need(a, "track_index"));
         tr2.selectInMixer(); tr2.selectInEditor(); cursorTrack.selectChannel(tr2);
         return "ok";
      }
   }
   return undefined;
}
