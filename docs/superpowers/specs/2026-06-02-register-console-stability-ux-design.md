# Register Console Stability And UX Design

## Goal

Improve register console reliability around task state transitions, concurrent start/stop behavior, startup recovery, and log parsing boundaries while making task status and operator errors clearer in the admin UI.

## Scope

In scope:
- Add a first-class `starting` task status constant.
- Make queued task claiming process only the tasks claimed in the current supervisor pass.
- Treat `starting`, `running`, and `stopping` tasks as orphaned after server restart.
- Harden supervisor refresh against missing task rows and log parsing failures.
- Add tests for task claim isolation, startup orphan cleanup, missing rows, and tail log boundaries.
- Show `starting` clearly in the task list.
- Align stop/delete button availability with backend status rules.
- Improve form placeholder text and visible operator error messages.

Out of scope:
- No multi-file backend refactor.
- No new persistent task event table.
- No frontend redesign or layout overhaul.
- No change to the registration runner protocol or log line format.

## Backend Design

### Status model

Introduce `STATUS_STARTING = "starting"` next to the existing task status constants. Replace backend and tests' raw `"starting"` comparisons with the constant.

The state flow remains:
- `queued` when a task is created.
- `starting` when the supervisor claims the task but before the process is successfully spawned.
- `running` after `subprocess.Popen()` succeeds.
- terminal states: `completed`, `partial`, `failed`, `stopped`.

### Queue claiming

`_launch_queued()` should claim up to the available slot count by changing selected `queued` rows to `starting`. It should then query only those claimed ids for this supervisor pass.

This avoids accidentally starting unrelated old `starting` rows that were left behind by an earlier crash or another supervisor loop.

### Stop behavior

`stop_task()` should allow stopping `queued`, `starting`, and `running` tasks. For a not-yet-managed task, it should mark it `stopped`, set `finished_at`, clear `pid`, set `current_phase` to `stopped`, and write a status-appropriate message.

Tasks already in terminal states should return a clear 409 message such as `Task is not stoppable in status '<status>'`.

### Startup recovery

On startup, `_cleanup_orphaned_tasks()` should mark `starting`, `running`, and `stopping` rows as `failed`. The error should explain that the server restarted before the task could finish.

### Supervisor refresh hardening

`_refresh_running()` should handle task rows disappearing while a process is still tracked. If `task_row()` raises 404, the supervisor should terminate and close that managed process and remove it from `_processes` without crashing the loop.

If parsing a log file fails unexpectedly, the task should remain tracked and the refresh loop should record a recoverable error rather than ending the supervisor loop.

### Log tail boundaries

`_tail_read()` should continue reading only the tail of large files. When the read starts in the middle of a line, it should skip the partial first line so parsed status comes from complete log lines.

## Frontend Design

### Status display

Add `starting: "启动中"` to `statusLabel()`. Task list fallback text should make pending states more useful:
- `queued`: `等待调度`
- `starting`: `准备启动`
- no phase: empty fallback remains `-`

### Button availability

Stop should be enabled for `queued`, `starting`, and `running`. Delete should be enabled only for terminal states: `completed`, `failed`, `stopped`, and `partial`.

### Error visibility

Task action failures should be visible near the task/detail area, not only by replacing logs. The implementation can reuse the existing log panel for now, but error text should include the task id and action name when available.

### Form hints

Keep the current form layout. Improve placeholder text only:
- task-level override fields should say they inherit system defaults when blank
- password/token settings should continue saying existing values remain unchanged when blank
- count should indicate a practical example value

## Testing

Add or update tests that verify:
- `STATUS_STARTING` exists and frontend static text includes `starting` / `启动中`.
- `_launch_queued()` only starts tasks claimed in the current pass.
- `_cleanup_orphaned_tasks()` marks `starting`, `running`, and `stopping` as failed.
- `_refresh_running()` handles a deleted task row without crashing and removes the managed process.
- `_tail_read()` skips partial first lines when reading a large file tail.
- frontend stop/delete button logic includes `starting` for stop and excludes it from delete.
- frontend error strings include clearer operation failure wording.

## Implementation Notes

Keep this change localized to `app/products/web/admin/register.py`, `app/statics/js/admin-register.js`, and `tests/test_register_console.py`. Prefer narrow helper functions or constants over broad refactoring.
