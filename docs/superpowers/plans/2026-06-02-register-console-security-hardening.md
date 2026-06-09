# Register Console Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent local registration secrets from being committed and verify register console responses do not expose stored credentials.

**Architecture:** Keep the change localized to Git hygiene, quickstart guidance, and register console regression tests. Existing masking and sensitive-value preservation helpers in `app/products/web/admin/register.py` should be verified rather than expanded unless a test exposes a gap.

**Tech Stack:** Python `unittest`, FastAPI route helpers, SQLite-backed register console settings, JavaScript admin UI, Git ignore rules.

---

### Task 1: Ignore Local Runtime Config

**Files:**
- Modify: `.gitignore`
- Test: `tests/test_register_console.py`

- [ ] **Step 1: Write the failing test**

Add this test to `tests/test_register_console.py` inside `RegisterConsoleHelperTests`:

```python
    def test_gitignore_excludes_root_config_json(self):
        gitignore = (Path(__file__).resolve().parents[1] / ".gitignore").read_text(encoding="utf-8")
        rules = {line.strip() for line in gitignore.splitlines() if line.strip() and not line.startswith("#")}

        self.assertIn("/config.json", rules)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest tests.test_register_console.RegisterConsoleHelperTests.test_gitignore_excludes_root_config_json -v`

Expected: FAIL because `/config.json` is not yet ignored.

- [ ] **Step 3: Implement the minimal ignore rule**

Add this rule to `.gitignore` under the existing environment/config section:

```gitignore
/config.json
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m unittest tests.test_register_console.RegisterConsoleHelperTests.test_gitignore_excludes_root_config_json -v`

Expected: PASS.

---

### Task 2: Add Sensitive Response Regression Tests

**Files:**
- Modify: `tests/test_register_console.py`
- Modify only if needed: `app/products/web/admin/register.py`

- [ ] **Step 1: Write tests for stored secret preservation and masking**

Add these tests to `tests/test_register_console.py` inside `RegisterConsoleHelperTests`:

```python
    def test_write_settings_preserves_existing_sensitive_values_when_blank(self):
        import app.products.web.admin.register as register

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "register"
            with patch.object(register, "REGISTER_ROOT", root), patch.object(register, "TASKS_DIR", root / "tasks"), patch.object(register, "DB_PATH", root / "console.db"):
                register.init_db()
                register.write_settings(
                    register.SystemSettings(
                        temp_mail_admin_password="mail-secret",
                        temp_mail_site_password="site-secret",
                        api_token="api-secret",
                    )
                )

                saved = register.write_settings(register.SystemSettings())

        self.assertEqual(saved["temp_mail_admin_password"], "mail-secret")
        self.assertEqual(saved["temp_mail_site_password"], "site-secret")
        self.assertEqual(saved["api_token"], "api-secret")

    def test_mask_settings_hides_sensitive_values_and_proxy_credentials(self):
        import app.products.web.admin.register as register

        masked = register._mask_settings(
            {
                "temp_mail_admin_password": "mail-secret",
                "temp_mail_site_password": "site-secret",
                "api_token": "api-secret",
                "proxy": "http://user:pass@example.com:8080",
                "browser_proxy": "socks5://user:pass@browser.example.com:1080",
            }
        )

        self.assertEqual(masked["temp_mail_admin_password"], "ma***")
        self.assertEqual(masked["temp_mail_site_password"], "si***")
        self.assertEqual(masked["api_token"], "ap***")
        self.assertEqual(masked["proxy"], "http://example.com:8080")
        self.assertEqual(masked["browser_proxy"], "socks5://browser.example.com:1080")

    def test_serialize_task_masks_sensitive_config_values(self):
        import app.products.web.admin.register as register

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "register"
            task_dir = root / "tasks" / "task_1"
            console_path = task_dir / "console.log"
            with patch.object(register, "REGISTER_ROOT", root), patch.object(register, "TASKS_DIR", root / "tasks"), patch.object(register, "DB_PATH", root / "console.db"):
                register.init_db()
                task_id = register.execute(
                    """
                    INSERT INTO tasks (
                        name, status, target_count, config_json, task_dir, console_path, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "batch",
                        register.STATUS_QUEUED,
                        1,
                        json.dumps(
                            {
                                "temp_mail_admin_password": "mail-secret",
                                "temp_mail_site_password": "site-secret",
                                "api_token": "api-secret",
                                "api": {"token": "nested-secret", "endpoint": "http://example.com"},
                                "proxy": "http://user:pass@example.com:8080",
                            }
                        ),
                        str(task_dir),
                        str(console_path),
                        register.now_iso(),
                    ),
                )
                serialized = register.serialize_task(register.task_row(task_id))

        config = serialized["config"]
        self.assertEqual(config["temp_mail_admin_password"], "ma***")
        self.assertEqual(config["temp_mail_site_password"], "si***")
        self.assertEqual(config["api_token"], "ap***")
        self.assertEqual(config["api"]["token"], "ne***")
        self.assertEqual(config["proxy"], "http://example.com:8080")
```

- [ ] **Step 2: Run tests to verify current behavior**

Run: `python -m unittest tests.test_register_console.RegisterConsoleHelperTests.test_write_settings_preserves_existing_sensitive_values_when_blank tests.test_register_console.RegisterConsoleHelperTests.test_mask_settings_hides_sensitive_values_and_proxy_credentials tests.test_register_console.RegisterConsoleHelperTests.test_serialize_task_masks_sensitive_config_values -v`

Expected: PASS if existing implementation already satisfies the design; FAIL only if a masking or preservation gap exists.

- [ ] **Step 3: Implement minimal production changes if any test fails**

If preservation fails, update `write_settings()` in `app/products/web/admin/register.py` so it keeps existing `temp_mail_admin_password`, `temp_mail_site_password`, and `api_token` when incoming values are empty.

If masking fails, update `_mask_settings()` and `_mask_sensitive_config()` in `app/products/web/admin/register.py` so they mask the same sensitive keys and strip proxy credentials via `_mask_proxy()`.

- [ ] **Step 4: Re-run the targeted tests**

Run: `python -m unittest tests.test_register_console.RegisterConsoleHelperTests.test_write_settings_preserves_existing_sensitive_values_when_blank tests.test_register_console.RegisterConsoleHelperTests.test_mask_settings_hides_sensitive_values_and_proxy_credentials tests.test_register_console.RegisterConsoleHelperTests.test_serialize_task_masks_sensitive_config_values -v`

Expected: PASS.

---

### Task 3: Document Local Secret Handling

**Files:**
- Modify: `docs/quickstart.md`

- [ ] **Step 1: Add quickstart guidance**

In `docs/quickstart.md`, after the `cp config.example.json config.json` command, add:

```markdown
`config.json` 是本地运行配置，可能包含邮箱密码、Token Sink Key 和代理凭据。它已经被 Git 忽略，不要提交。如果真实密码或 token 曾经被提交、粘贴到日志或分享给他人，请立即轮换。
```

- [ ] **Step 2: Review the changed paragraph**

Run: `git diff -- docs/quickstart.md`

Expected: The new note appears directly under the local config copy command and does not change unrelated quickstart content.

---

### Task 4: Verify And Commit Implementation

**Files:**
- Modify: `.gitignore`
- Modify: `docs/quickstart.md`
- Modify: `tests/test_register_console.py`
- Modify only if needed: `app/products/web/admin/register.py`

- [ ] **Step 1: Run full register console tests**

Run: `python -m unittest tests.test_register_console -v`

Expected: PASS.

- [ ] **Step 2: Check staged safety**

Run: `git diff --name-only`

Expected: Only implementation files from this plan appear. `config.json` must not appear.

- [ ] **Step 3: Commit**

Run:

```bash
git add -- .gitignore docs/quickstart.md tests/test_register_console.py app/products/web/admin/register.py
git commit -m "chore: harden register console secret handling"
```

Expected: Commit succeeds without staging local runtime config or secrets.

---

## Self-Review

- Spec coverage: Git ignore, response masking tests, stored secret preservation tests, and quickstart guidance are covered.
- Placeholder scan: No placeholders or deferred steps remain.
- Type consistency: Tests use existing `SystemSettings`, `write_settings()`, `_mask_settings()`, `serialize_task()`, and `task_row()` APIs.
