#!/usr/bin/env python3
"""
Utility helpers to tidy the Todoist Bridge cache (data.json).

The script can remove task entries that are known to be inconsistent with
Todoist or Obsidian, optionally using a database-check report for guidance.
It keeps file metadata in sync and can verify whether referenced notes
contain the expected todoist markers.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set


DEFAULT_VAULT = Path(r"C:/Users/rodri/Obsidian/Rodrigo's Vault")
MARKER_TEMPLATE = r"todoist_id::\s*{task_id}"


class CleanupError(RuntimeError):
    """Raised when the cleanup process cannot continue."""


def load_data_json(path: Path) -> Dict:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise CleanupError(f"Could not find data.json at {path}") from exc
    except json.JSONDecodeError as exc:
        raise CleanupError(f"Failed to parse JSON data at {path}: {exc}") from exc


def backup_file(source: Path, destination: Optional[Path]) -> Path:
    if destination is None:
        destination = source.with_suffix(source.suffix + ".bak")
    shutil.copy2(source, destination)
    return destination


def extract_ids_from_report(report_path: Optional[Path]) -> Set[str]:
    if not report_path:
        return set()
    if not report_path.exists():
        raise CleanupError(f"Report file not found: {report_path}")
    pattern = re.compile(r"todoist_id:\s*(\d+)")
    ids: Set[str] = set()
    with report_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            match = pattern.search(line)
            if match:
                ids.add(match.group(1))
    return ids


def resolve_vault_root(path: Optional[str]) -> Optional[Path]:
    if path is None:
        return DEFAULT_VAULT if DEFAULT_VAULT.exists() else None
    candidate = Path(path).expanduser()
    return candidate if candidate.exists() else None


def ids_from_args(values: Optional[Sequence[str]]) -> Set[str]:
    return {value.strip() for value in values or [] if value.strip()}


def marker_missing(note_path: Path, task_id: str) -> bool:
    if not note_path.exists():
        return True
    try:
        text = note_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = note_path.read_text(encoding="utf-8", errors="ignore")
    pattern = re.compile(MARKER_TEMPLATE.format(task_id=re.escape(task_id)))
    return pattern.search(text) is None


def gather_auto_removals(tasks: Iterable[Dict], vault_root: Optional[Path], *, drop_missing_path: bool, drop_missing_marker: bool, verbose: bool) -> Dict[str, List[str]]:
    reasons: Dict[str, List[str]] = defaultdict(list)
    if not (drop_missing_path or drop_missing_marker):
        return reasons
    if vault_root is None:
        raise CleanupError("Vault root not available; provide --vault-root to enable automatic checks.")

    for task in tasks:
        task_id = str(task.get("id"))
        note_rel_path = task.get("path") or ""
        note_path = vault_root / note_rel_path if note_rel_path else None

        if drop_missing_path:
            if not note_rel_path:
                reasons[task_id].append("missing note path")
            elif not note_path.exists():
                reasons[task_id].append("note file not found")

        if drop_missing_marker and note_path and note_path.exists():
            if marker_missing(note_path, task_id):
                reasons[task_id].append("todoist marker missing in note")
        elif drop_missing_marker and (not note_path or not note_path.exists()):
            reasons[task_id].append("todoist marker unavailable (missing note)")

    if verbose and reasons:
        for task_id, why in reasons.items():
            print(f"Auto-removal candidate {task_id}: {', '.join(why)}")

    return reasons


def remove_tasks(data: Dict, task_ids: Set[str]) -> Dict[str, Dict[str, int]]:
    removed_summary: Dict[str, Dict[str, int]] = {"tasks": {"before": 0, "after": 0}, "metadata": {"updated_entries": 0, "pruned_entries": 0}}
    tasks = data.get("todoistTasksData", {}).get("tasks", [])
    removed_summary["tasks"]["before"] = len(tasks)
    task_ids = set(task_ids)
    data.get("todoistTasksData", {})["tasks"] = [task for task in tasks if str(task.get("id")) not in task_ids]
    removed_summary["tasks"]["after"] = len(data.get("todoistTasksData", {}).get("tasks", []))

    # Clean file metadata
    metadata = data.get("fileMetadata", {})
    for note_path, meta in list(metadata.items()):
        ids = meta.get("todoistTasks", []) or []
        new_ids = [task_id for task_id in ids if task_id not in task_ids]
        if len(new_ids) != len(ids):
            meta["todoistTasks"] = new_ids
            meta["todoistCount"] = len(new_ids)
            removed_summary["metadata"]["updated_entries"] += 1
            if not new_ids:
                removed_summary["metadata"]["pruned_entries"] += 1
    return removed_summary


def prune_empty_metadata(data: Dict) -> int:
    metadata = data.get("fileMetadata", {})
    to_remove = [note for note, meta in metadata.items() if (meta.get("todoistTasks") in ([], None))]
    for note in to_remove:
        metadata.pop(note, None)
    return len(to_remove)


def dump_json(path: Path, data: Dict) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    temp_path.replace(path)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean inconsistent Todoist cache entries.")
    parser.add_argument("--data-json", dest="data_json", default="data.json", help="Path to data.json (default: %(default)s)")
    parser.add_argument("--vault-root", dest="vault_root", default=None, help="Path to the Obsidian vault root.")
    parser.add_argument("--report", dest="report", default=None, help="Path to a Todoist Bridge database-check report to auto-select task IDs.")
    parser.add_argument("--remove-ids", nargs="*", dest="remove_ids", default=None, help="Explicit task IDs to remove.")
    parser.add_argument("--drop-missing-path", action="store_true", help="Remove tasks whose note file path is missing.")
    parser.add_argument("--drop-missing-marker", action="store_true", help="Remove tasks whose note is missing the todoist marker.")
    parser.add_argument("--prune-empty-metadata", action="store_true", help="Remove file metadata entries that end up empty after cleanup.")
    parser.add_argument("--no-backup", action="store_true", help="Skip automatic creation of a .bak backup file.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed without saving changes.")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    data_path = Path(args.data_json).expanduser()
    data = load_data_json(data_path)

    report_ids = extract_ids_from_report(Path(args.report)) if args.report else set()
    manual_ids = ids_from_args(args.remove_ids)

    vault_root = resolve_vault_root(args.vault_root)
    auto_reasons = gather_auto_removals(
        data.get("todoistTasksData", {}).get("tasks", []),
        vault_root,
        drop_missing_path=args.drop_missing_path,
        drop_missing_marker=args.drop_missing_marker,
        verbose=args.verbose,
    )

    auto_ids = set(auto_reasons.keys())

    task_ids = report_ids | manual_ids | auto_ids
    task_ids.discard("")

    if not task_ids:
        print("No task IDs selected for removal. Nothing to do.")
        return 0

    if args.verbose:
        print(f"Tasks selected for removal ({len(task_ids)}): {', '.join(sorted(task_ids))}")

    if args.dry_run:
        print("Dry-run mode: the following tasks would be removed:")
        for tid in sorted(task_ids):
            reasons = []
            if tid in report_ids:
                reasons.append("listed in report")
            if tid in manual_ids:
                reasons.append("explicit request")
            if tid in auto_reasons:
                reasons.extend(auto_reasons[tid])
            reason_str = ", ".join(reasons) if reasons else "(no reason recorded)"
            print(f"  - {tid}: {reason_str}")
        return 0

    if not args.no_backup:
        backup_path = backup_file(data_path, None)
        if args.verbose:
            print(f"Backup created at {backup_path}")

    summary = remove_tasks(data, task_ids)

    pruned_count = 0
    if args.prune_empty_metadata:
        pruned_count = prune_empty_metadata(data)

    dump_json(data_path, data)

    removed = summary["tasks"]["before"] - summary["tasks"]["after"]
    print(f"Removed {removed} task(s) from data.json.")
    print(f"Updated {summary['metadata']['updated_entries']} file metadata entrie(s).")
    if pruned_count:
        print(f"Pruned {pruned_count} empty metadata entrie(s).")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CleanupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
