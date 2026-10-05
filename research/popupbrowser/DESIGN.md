# PopupBrowser design (draft)

## API facts (Bitwig 6.1 javadoc, `Program Files\Bitwig Studio\resources\doc\control-surface\api`)
- `host.createPopupBrowser()` (API 2). Members: `exists()` (true only while a session is open), `title()`, `contentTypeNames()`, `selectedContentTypeIndex()` (settable), `selectedContentTypeName()`, columns `locationColumn/fileTypeColumn/categoryColumn/tagColumn/creatorColumn/deviceTypeColumn/deviceColumn/smartCollectionColumn`, `resultsColumn()`, `shouldAudition()`, `canAudition()`, `selectNext/Previous/First/LastFile`, `commit()`, `cancel()`.
- Column: `name()`, `entryCount()`, `getWildcardItem()`, `createCursorItem()`, `createItemBank(n)`. Cursor item `createSiblingsBank(n)` gives a Scrollable bank (`scrollPosition()`, `scrollBy`). Items: `name()`, `isSelected()` (settable), filter items also `hitCount()`.
- Opening: `InsertionPoint.browse()` from `track.endOfDeviceChainInsertionPoint()` / `startOf...`, `device.afterDeviceInsertionPoint()` / `before...` / `replaceDeviceInsertionPoint()`. The `browseTo*` methods and `Browser`/`createDeviceBrowser` are deprecated. Our script already uses `endOfDeviceChainInsertionPoint().browse()` (`insert_device_browser`).
- The old `Browser` API is deprecated: "Use PopupBrowser instead".

## Mirroring DrivenByMoss (`BrowserImpl.java`, `BrowserColumnImpl.java`, git-moss/DrivenByMoss master)
Create the popup once in init; mark exists/name/entryCount/hitCount interested; results via `cursor.createSiblingsBank(n)`; open with `scheduleTask(insertionPoint::browse, 100)` after `cancel()`; commit/cancel via `browser.commit()/cancel()`. It skips `smartCollectionColumn` and hardcodes the content-type name ("TODO API extension required ... Bitwig 5"), so expect those to be unreliable. Preset content type is index 1 in its code.

## Commands
`browse_open{where,track_index,device_index}`, `browse_content_type`, `browse_status`, `browse_columns{column,start}`, `browse_filter{column,value}`, `browse_results{limit,start}`, `browse_select{slot}`, `browse_audition`, `browse_commit`, `browse_cancel`. Python: `browse_open/columns/filter/results/select/commit/cancel` plus one-shot `browse_load`. Everything is asynchronous (values update next flush), so Python sleeps and polls.

## Risks / unknowns (NOT verified; no Bitwig was touched)
- Whether `isSelected().set(true)` on a filter/result item really selects (settable per javadoc; DBM uses cursor movement instead). Fallback: `cursorIndex().set`, `selectNext()`.
- Whether the popup works with the panel closed/hidden (browser opens in-app, so the Bitwig window must be foreground).
- Whether third-party plug-in presets appear in the Preset/Device tabs without the plug-in being instantiated: unknown. Per-plug-in presets are shown by Bitwig only for VST3/CLAP presets it has indexed.
- 7 columns x 24 + 32 results = ~200 more observed proxies at init; modest.
- Only one session at a time; a stale open session blocks UI (always cancel in `finally`).
- Crash potential: low in theory (no Signal, no engine calls). Committing a plug-in preset loads a plug-in: heavy plug-ins can stall or die ("Plugin host died" note in CLAUDE.md). Avoid committing while audio plays.
- Wrong `device_index`/selected track would replace the wrong device: use `where=replace` only after verifying `list_devices()['track']`.

## Safe test (empty scratch project, a new one, NOT a song tab)
1. `get_session` shows 0 tracks and a scratch name. Create one instrument track.
2. Install JS (copy to live folder only after review), wait for reload, `browse_status` -> `open:false`, columns exist false/true.
3. `browse_open(where=end)`; `browse_status`; `browse_columns("category")`; `browse_cancel` (repeat 3x to check no stuck session).
4. `browse_filter("creator","Bitwig")`, `browse_results`, `browse_select`, compare `result_cursor`, then `browse_commit(expect=...)`; `list_devices`; `undo_redo` to clean up.
5. Then a third-party VST3 preset, then replace-mode.
6. Keep the Bitwig window focused; restore arm/selection after.
