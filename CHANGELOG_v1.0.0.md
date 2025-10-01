# v1.0.0 — Todoist Bridge Sync & Audit Overhaul

**Release date:** 2025-10-01 (America/São_Paulo)

## Highlights

* Clear **Task Sync Rules** (Todoist ↔ Obsidian) with predictable behavior.
* One-click **Check Database** report with precise diagnostics.
* Faster sync: only scans files referenced in `data.json`.
* Housekeeping: simplified config & code paths.
* All user-facing strings **translated to English**.

## Added

* **Check Database** command

  * Generates `todoist_bridgedatabase_check_{YYYY-MM-DD_HH-mm-ss}.md` at vault root.
  * Reports:

    1. **Orphaned Bridge Marks** (unchecked tasks in Obsidian that are missing in Todoist).
    2. **Local-Only Tasks** (`#obsidian` tag, not synced).
    3. **data.json Inconsistencies** (presence/status/text/due/project mismatches).
  * Console logs:

    * Start → `Check Database: started …`
    * Finish → `Check Database: N issues | Orphaned: a | Local-only: b | data.json: c`
    * Report path on success.
* **Manual Sync notifications** (manual only):

  * Start line
  * Finish summary: `X tasks completed`, `X tasks deleted`, `X tasks on cache`.

## Changed

* **Sync rules**

  * If **deleted in Todoist** → remove bridge mark in Obsidian and remove record from `data.json`.
  * If **deleted in Obsidian** → **no action** taken in Todoist.
* **Timestamps**: use local `America/Sao_Paulo` time and format `YYYY-MM-DD_HH-mm-ss`.
* **Text comparison**: whitespace normalized before diffing.
* **“Unchecked” definition** unified: `- [ ]` (Obsidian) and `completed: false` (Todoist).

## Performance

* **Scoped scanning**: only search files that contain tasks listed in `data.json` (big speedup on large vaults).
* External **helper script** recommended to prune `data.json` to **incomplete tasks only** (keeps cache lean and fast).

## Removed

* Default project per-file (and associated command palette entry)
* Full-vault sync
* “Remove completed tag on reopen”
* “Clean up missing tasks on sync”
* “Remove markers for deleted Todoist tasks”
* Creation-only mode

## UI / Config

* **Kept / Exposed controls**:

  * Toggle: **Automatic Sync**
  * Button: **Manual Sync**
  * Button: **Check Database**
  * Toggle: **Debug Mode**
  * Button: **Backup Todoist Data**

## Internationalization

* **All Chinese strings translated to English** (UI, logs, and docs).

## Edge Cases & Validation

* Bridge mark with malformed/empty `todoist_id` → flagged under **data.json inconsistencies** (`reason: invalid_todoist_id`).
* Status, text, due date, and project/section mismatches explicitly listed per `todoist_id`.

## Migration Notes

* Run the external **data.json cleanup** once after upgrading to ensure the cache contains **only incomplete tasks**.
* If you previously relied on any **removed** options, migrate to manual workflows:

  * Use **Manual Sync** and **Check Database** for reconciliation.
  * Remove per-file default project settings from your config.