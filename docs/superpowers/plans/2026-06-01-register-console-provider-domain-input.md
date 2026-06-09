# Register Console Provider And Domain Input Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change the register console provider field to a dropdown and add native one-domain-per-line Cloud Mail multi-domain input.

**Architecture:** Keep the change localized to the existing register console backend models/serialization and `app/statics/js/admin-register.js`. The backend will accept `temp_mail_domain` as either string or string list, while the frontend will render a provider-driven control that switches between single-line and multi-line domain input.

**Tech Stack:** Python 3, FastAPI, Pydantic, vanilla JavaScript, `unittest`.

---

## File Structure

- Modify `app/products/web/admin/register.py`: widen settings typing for `temp_mail_domain`, preserve array values, and format domain arrays for task detail display.
- Modify `app/statics/js/admin-register.js`: render provider dropdown, switch Cloud Mail domain input to `textarea`, and serialize one-domain-per-line input into arrays.
- Modify `tests/test_register_console.py`: add backend and static asset regression tests for provider select and Cloud Mail domain arrays.

## Task 1: Backend Domain Array Support

**Files:**
- Modify: `tests/test_register_console.py`
- Modify: `app/products/web/admin/register.py`

- [ ] **Step 1: Write the failing backend tests**

Add these tests to `tests/test_register_console.py`:

```python
    def test_write_and_read_settings_preserves_cloudmail_domain_arrays(self):
        import app.products.web.admin.register as register

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "register"
            with patch.object(register, "REGISTER_ROOT", root), patch.object(register, "TASKS_DIR", root / "tasks"), patch.object(register, "DB_PATH", root / "console.db"):
                register.init_db()
                saved = register.write_settings(
                    register.SystemSettings(
                        temp_mail_provider="cloudmail",
                        temp_mail_api_base="https://mail.example.com",
                        temp_mail_domain=["one.example.com", "two.example.com"],
                    )
                )
                loaded = register.read_settings()

        self.assertEqual(saved["temp_mail_domain"], ["one.example.com", "two.example.com"])
        self.assertEqual(loaded["temp_mail_domain"], ["one.example.com", "two.example.com"])

    def test_build_task_config_preserves_default_domain_array_when_no_override(self):
        from app.products.web.admin.register import TaskCreate, build_task_config_from_defaults

        defaults = {
            "run": {"count": 50},
            "proxy": "",
            "browser_proxy": "",
            "temp_mail_provider": "cloudmail",
            "temp_mail_api_base": "https://mail.example.com",
            "temp_mail_admin_email": "admin@example.com",
            "temp_mail_admin_password": "secret",
            "temp_mail_domain": ["one.example.com", "two.example.com"],
            "temp_mail_site_password": "",
            "api": {"endpoint": "", "token": "", "append": True},
        }
        payload = TaskCreate(name="batch-1", count=3, temp_mail_domain=None)

        result = build_task_config_from_defaults(defaults, payload)

        self.assertEqual(result["temp_mail_domain"], ["one.example.com", "two.example.com"])

    def test_serialize_task_detail_formats_domain_array_readably(self):
        import app.products.web.admin.register as register

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            CREATE TABLE tasks (
                id INTEGER, name TEXT, status TEXT, target_count INTEGER,
                completed_count INTEGER, failed_count INTEGER, current_round INTEGER,
                current_phase TEXT, last_email TEXT, last_error TEXT, last_log_at TEXT,
                notes TEXT, config_json TEXT, task_dir TEXT, console_path TEXT,
                pid INTEGER, created_at TEXT, started_at TEXT, finished_at TEXT,
                exit_code INTEGER
            )
            """
        )
        conn.execute(
            "INSERT INTO tasks VALUES (1, 'batch', 'queued', 2, 0, 0, 0, '', '', '', '', '', ?, '/tmp/task', '/tmp/log', NULL, 'now', NULL, NULL, NULL)",
            (json.dumps({"temp_mail_domain": ["one.example.com", "two.example.com"]}),),
        )
        row = conn.execute("SELECT * FROM tasks").fetchone()

        result = register.serialize_task(row)
        conn.close()

        self.assertEqual(result["config"]["temp_mail_domain"], ["one.example.com", "two.example.com"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_register_console.RegisterConsoleHelperTests.test_write_and_read_settings_preserves_cloudmail_domain_arrays tests.test_register_console.RegisterConsoleHelperTests.test_build_task_config_preserves_default_domain_array_when_no_override tests.test_register_console.RegisterConsoleHelperTests.test_serialize_task_detail_formats_domain_array_readably -v`

Expected: FAIL because `SystemSettings.temp_mail_domain` currently only accepts `str` and array handling is incomplete.

- [ ] **Step 3: Write minimal backend implementation**

In `app/products/web/admin/register.py`, update the models and helpers:

```python
class TaskCreate(BaseModel):
    ...
    temp_mail_domain: str | None = None
    ...


class SystemSettings(BaseModel):
    ...
    temp_mail_domain: str | list[str] = ""
    ...


def _clean_domain_list(values: list[Any]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]
```

Use `_clean_domain_list()` in `write_settings()` input preparation or right before persistence so arrays are trimmed and empty lines are removed.

Keep these behaviors in `merged_defaults()` / `build_task_config_from_defaults()`:

```python
    if "temp_mail_domain" in saved:
        saved_domain = saved.get("temp_mail_domain")
        if isinstance(saved_domain, str) and saved_domain.strip():
            base["temp_mail_domain"] = saved_domain.strip()
        elif isinstance(saved_domain, list):
            base["temp_mail_domain"] = _clean_domain_list(saved_domain)
```

Do not change task-level override type in `TaskCreate`; keep it as string-only for now.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_register_console.RegisterConsoleHelperTests.test_write_and_read_settings_preserves_cloudmail_domain_arrays tests.test_register_console.RegisterConsoleHelperTests.test_build_task_config_preserves_default_domain_array_when_no_override tests.test_register_console.RegisterConsoleHelperTests.test_serialize_task_detail_formats_domain_array_readably -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add app/products/web/admin/register.py tests/test_register_console.py
git commit -m "feat: support Cloud Mail domain arrays in register settings"
```

## Task 2: Provider Dropdown And Domain Field Switching

**Files:**
- Modify: `tests/test_register_console.py`
- Modify: `app/statics/js/admin-register.js`

- [ ] **Step 1: Write the failing frontend/static tests**

Add these tests to `tests/test_register_console.py`:

```python
    def test_register_admin_js_renders_provider_select_and_cloudmail_domain_textarea(self):
        js = (Path(__file__).parents[1] / "app" / "statics" / "js" / "admin-register.js").read_text(encoding="utf-8")

        self.assertIn("selectField('temp_mail_provider'", js)
        self.assertIn("textareaField('temp_mail_domain'", js)
        self.assertIn("isCloudMailProvider", js)

    def test_register_admin_js_serializes_cloudmail_domain_lines(self):
        js = (Path(__file__).parents[1] / "app" / "statics" / "js" / "admin-register.js").read_text(encoding="utf-8")

        self.assertIn("split(/\\r?\\n/)", js)
        self.assertIn("payload.temp_mail_domain = domains", js)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_register_console.RegisterConsoleHelperTests.test_register_admin_js_renders_provider_select_and_cloudmail_domain_textarea tests.test_register_console.RegisterConsoleHelperTests.test_register_admin_js_serializes_cloudmail_domain_lines -v`

Expected: FAIL because the current JS renders text inputs only and does not parse multi-line domains.

- [ ] **Step 3: Write minimal frontend implementation**

In `app/statics/js/admin-register.js`, add helpers like:

```javascript
  const isCloudMailProvider = (value) => String(value || '').trim().toLowerCase() === 'cloudmail';

  const domainFieldValue = (value) => Array.isArray(value) ? value.join('\n') : String(value ?? '');
```

Also add concrete `selectField()` and `textareaField()` helpers that follow the existing `inputField()` markup pattern:
- `selectField()` must render a `<select>` with `<option>` entries for `cloudmail`, `duckmail`, `ahem`, and `generic`
- `textareaField()` must render a `<textarea>` with the same label/container structure as other form controls

Update `renderSettingsForm()` so:
- `temp_mail_provider` uses `selectField()`
- `temp_mail_domain` uses `textareaField()` when provider is `cloudmail`
- `temp_mail_domain` uses `inputField()` otherwise

Update `formPayload()` so when handling the settings form:

```javascript
    const provider = String(payload.temp_mail_provider || '').trim().toLowerCase();
    if (provider === 'cloudmail' && Object.prototype.hasOwnProperty.call(payload, 'temp_mail_domain')) {
      const domains = String(payload.temp_mail_domain || '')
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean);
      payload.temp_mail_domain = domains;
    }
```

Leave task creation form domain override as a single-line input.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_register_console.RegisterConsoleHelperTests.test_register_admin_js_renders_provider_select_and_cloudmail_domain_textarea tests.test_register_console.RegisterConsoleHelperTests.test_register_admin_js_serializes_cloudmail_domain_lines -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add app/statics/js/admin-register.js tests/test_register_console.py
git commit -m "feat: add provider select and Cloud Mail domain textarea"
```

## Task 3: Domain Array Display In Task Details

**Files:**
- Modify: `tests/test_register_console.py`
- Modify: `app/statics/js/admin-register.js`

- [ ] **Step 1: Write the failing display test**

Add this test to `tests/test_register_console.py`:

```python
    def test_register_admin_js_formats_domain_arrays_for_detail_view(self):
        js = (Path(__file__).parents[1] / "app" / "statics" / "js" / "admin-register.js").read_text(encoding="utf-8")

        self.assertIn("Array.isArray(value)", js)
        self.assertIn("value.join('\\n')", js)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_register_console.RegisterConsoleHelperTests.test_register_admin_js_formats_domain_arrays_for_detail_view -v`

Expected: FAIL because detail rendering currently stringifies arrays through `text()`.

- [ ] **Step 3: Write minimal display implementation**

In `app/statics/js/admin-register.js`, update the value formatting helper so arrays render readably:

```javascript
  const text = (value, fallback = '-') => {
    if (Array.isArray(value)) {
      const joined = value.map((item) => String(item ?? '').trim()).filter(Boolean).join('\n');
      return joined || fallback;
    }
    const stringValue = String(value ?? '').trim();
    return stringValue || fallback;
  };
```

This allows the existing task detail rendering to display domain arrays without further structural changes.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_register_console.RegisterConsoleHelperTests.test_register_admin_js_formats_domain_arrays_for_detail_view -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add app/statics/js/admin-register.js tests/test_register_console.py
git commit -m "feat: format register domain arrays in detail view"
```

## Task 4: Final Verification

**Files:**
- Verify only

- [ ] **Step 1: Run register console tests**

Run: `python -m unittest tests.test_register_console -v`

Expected: all register console tests pass.

- [ ] **Step 2: Run compile check**

Run: `python -m compileall app/products/web/admin/register.py`

Expected: compile succeeds with no syntax errors.

- [ ] **Step 3: Run linter on changed Python file**

Run: `python -m ruff check app/products/web/admin/register.py`

Expected: no lint errors.

- [ ] **Step 4: Run JavaScript syntax check**

Run: `node --check app/statics/js/admin-register.js`

Expected: no syntax errors.

- [ ] **Step 5: Review final status**

Run: `git status --short --branch`

Expected: clean working tree on the implementation branch.
