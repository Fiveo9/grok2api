# Register Console Stability And UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden register console task state transitions and improve operator-facing task status/error hints.

**Architecture:** Keep the existing single-module backend and static JS frontend. Add a `STATUS_STARTING` constant, narrow queue claiming to the current supervisor pass, make refresh/startup recovery defensive, and add static/frontend tests for status labels and button rules.

**Tech Stack:** Python `unittest`, FastAPI helper functions, SQLite task table, browser-side JavaScript in `app/statics/js/admin-register.js`.

---

### Task 1: State Constants And Queue Claiming

**Files:**
- Modify: `app/products/web/admin/register.py`
- Test: `tests/test_register_console.py`

- [ ] **Step 1: Write failing tests**

Add tests asserting `STATUS_STARTING` exists and `_launch_queued()` starts only tasks claimed in the current pass, not old `starting` rows.

- [ ] **Step 2: Run targeted tests**

Run: `python -m unittest tests.test_register_console.RegisterConsoleHelperTests.test_register_defines_starting_status_constant tests.test_register_console.RegisterConsoleHelperTests.test_launch_queued_only_starts_newly_claimed_tasks -v`

Expected: FAIL before implementation.

- [ ] **Step 3: Implement minimal backend change**

Add `STATUS_STARTING = "starting"`, replace raw `"starting"`, and make `_launch_queued()` select queued ids, update only those ids, then fetch only those rows.

- [ ] **Step 4: Verify targeted tests pass**

Run the same command from Step 2. Expected: PASS.

---

### Task 2: Startup And Refresh Recovery

**Files:**
- Modify: `app/products/web/admin/register.py`
- Test: `tests/test_register_console.py`

- [ ] **Step 1: Write failing tests**

Add tests for `_cleanup_orphaned_tasks()` marking `starting/running/stopping` as failed, `_refresh_running()` removing a managed process whose DB row was deleted, and `_tail_read()` skipping a partial first tail line.

- [ ] **Step 2: Run targeted tests**

Run: `python -m unittest tests.test_register_console.RegisterConsoleHelperTests.test_cleanup_orphaned_tasks_marks_starting_running_and_stopping_failed tests.test_register_console.RegisterConsoleHelperTests.test_refresh_running_removes_missing_task_row_without_crashing tests.test_tail_read_skips_partial_first_line_for_large_files -v`

Expected: FAIL before implementation where behavior is missing.

- [ ] **Step 3: Implement minimal recovery hardening**

Update orphan cleanup to include `STATUS_STARTING`; wrap missing rows and log parsing failures inside `_refresh_running()`; keep `_tail_read()` tail-only behavior and skip partial first lines.

- [ ] **Step 4: Verify targeted tests pass**

Run the same command from Step 2. Expected: PASS.

---

### Task 3: Frontend Status And Error UX

**Files:**
- Modify: `app/statics/js/admin-register.js`
- Test: `tests/test_register_console.py`

- [ ] **Step 1: Write failing static tests**

Add tests asserting the JS includes `starting: '启动中'`, stop allows `starting`, delete does not treat `queued` or `starting` as terminal, pending rows display `等待调度` / `准备启动`, and action failures include task id/action context.

- [ ] **Step 2: Run targeted tests**

Run: `python -m unittest tests.test_register_console.RegisterConsoleHelperTests.test_register_admin_js_handles_starting_status_and_actions tests.test_register_console.RegisterConsoleHelperTests.test_register_admin_js_has_clearer_action_error_context -v`

Expected: FAIL before implementation.

- [ ] **Step 3: Implement minimal JS changes**

Add the `starting` label, adjust terminal/stop status sets, add pending phase fallback text, and include task/action context in operation errors.

- [ ] **Step 4: Verify targeted tests pass**

Run the same command from Step 2. Expected: PASS.

---

### Task 4: Full Verification And Commit

**Files:**
- Modify: `app/products/web/admin/register.py`
- Modify: `app/statics/js/admin-register.js`
- Modify: `tests/test_register_console.py`

- [ ] **Step 1: Run full register console tests**

Run: `python -m unittest tests.test_register_console -v`

Expected: PASS.

- [ ] **Step 2: Inspect diff**

Run: `git diff --name-only`

Expected: only plan/design docs and the three implementation files for this work.

- [ ] **Step 3: Commit implementation**

Run:

```bash
git add -- app/products/web/admin/register.py app/statics/js/admin-register.js tests/test_register_console.py docs/superpowers/plans/2026-06-02-register-console-stability-ux.md
git commit -m "fix: harden register console task stability"
```

Expected: commit succeeds.

---

## Self-Review

- Spec coverage: status constants, queue claim isolation, orphan cleanup, refresh hardening, log tail boundary, frontend status/action UX are all covered.
- Placeholder scan: no placeholders remain.
- Type consistency: uses existing `TaskSupervisor`, `ManagedProcess`, `STATUS_*`, and `unittest` patterns.
