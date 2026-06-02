import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch


class RegisterConsoleHelperTests(unittest.TestCase):
    def test_gitignore_excludes_root_config_json(self):
        gitignore = (Path(__file__).resolve().parents[1] / ".gitignore").read_text(encoding="utf-8")
        rules = {line.strip() for line in gitignore.splitlines() if line.strip() and not line.startswith("#")}

        self.assertIn("/config.json", rules)

    def test_init_db_creates_settings_and_tasks_tables(self):
        import app.products.web.admin.register as register

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "register"
            with patch.object(register, "REGISTER_ROOT", root), patch.object(register, "TASKS_DIR", root / "tasks"), patch.object(register, "DB_PATH", root / "console.db"):
                register.init_db()

                with closing(sqlite3.connect(root / "console.db")) as conn:
                    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
                    task_columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}

        self.assertIn("settings", tables)
        self.assertIn("tasks", tables)
        self.assertIn("config_json", task_columns)
        self.assertIn("console_path", task_columns)

    def test_write_and_read_settings_round_trip(self):
        import app.products.web.admin.register as register

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "register"
            with patch.object(register, "REGISTER_ROOT", root), patch.object(register, "TASKS_DIR", root / "tasks"), patch.object(register, "DB_PATH", root / "console.db"):
                register.init_db()
                saved = register.write_settings(
                    register.SystemSettings(
                        proxy="http://proxy.example:8080",
                        browser_proxy="http://browser.example:8080",
                        temp_mail_provider="cloudmail",
                        temp_mail_api_base="https://mail.example.com",
                        temp_mail_admin_email="admin@example.com",
                        temp_mail_admin_password="secret",
                        temp_mail_domain="example.com",
                        temp_mail_site_password="site-secret",
                        api_endpoint="http://api.example/admin/api/tokens",
                        api_token="admin-key",
                        api_append=False,
                    )
                )
                loaded = register.read_settings()

        self.assertEqual(loaded, saved)
        self.assertFalse(loaded["api_append"])

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
                        temp_mail_domain=[" one.example.com ", "", "two.example.com", "   "],
                    )
                )
                loaded = register.read_settings()

        self.assertEqual(saved["temp_mail_domain"], ["one.example.com", "two.example.com"])
        self.assertEqual(loaded["temp_mail_domain"], ["one.example.com", "two.example.com"])

    def test_write_settings_ignores_non_string_domain_array_items(self):
        import app.products.web.admin.register as register

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "register"
            with patch.object(register, "REGISTER_ROOT", root), patch.object(register, "TASKS_DIR", root / "tasks"), patch.object(register, "DB_PATH", root / "console.db"):
                register.init_db()
                saved = register.write_settings(
                    register.SystemSettings.model_construct(
                        temp_mail_provider="cloudmail",
                        temp_mail_api_base="https://mail.example.com",
                        temp_mail_domain=[" one.example.com ", None, 7, "", " two.example.com "],
                    )
                )
                loaded = register.read_settings()

        self.assertEqual(saved["temp_mail_domain"], ["one.example.com", "two.example.com"])
        self.assertEqual(loaded["temp_mail_domain"], ["one.example.com", "two.example.com"])

    def test_delete_task_files_rejects_paths_outside_tasks_dir_and_tasks_dir_itself(self):
        import app.products.web.admin.register as register

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "register"
            tasks_dir = root / "tasks"
            outside = Path(tmp) / "outside"
            tasks_dir.mkdir(parents=True)
            outside.mkdir()
            with patch.object(register, "TASKS_DIR", tasks_dir):
                with self.assertRaises(register.HTTPException):
                    register.delete_task_files({"task_dir": str(outside)})
                with self.assertRaises(register.HTTPException):
                    register.delete_task_files({"task_dir": str(tasks_dir)})
                self.assertTrue(outside.exists())
                self.assertTrue(tasks_dir.exists())

    def test_create_task_cleans_up_db_row_when_task_dir_creation_fails(self):
        import app.products.web.admin.register as register

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "register"
            source = Path(tmp) / "source"
            python_path = source / ".venv" / "bin" / "python"
            source.mkdir()
            python_path.parent.mkdir(parents=True)
            python_path.write_text("", encoding="utf-8")
            with (
                patch.object(register, "REGISTER_ROOT", root),
                patch.object(register, "TASKS_DIR", root / "tasks"),
                patch.object(register, "DB_PATH", root / "console.db"),
                patch.object(register, "SOURCE_PROJECT", source),
                patch.object(register, "SOURCE_VENV_PYTHON", python_path),
            ):
                register.init_db()
                with patch.object(register.Path, "mkdir", side_effect=OSError("disk full")):
                    with self.assertRaises(OSError):
                        register.create_task(register.TaskCreate(name="batch", count=1))
                rows = register.fetch_all("SELECT * FROM tasks")

        self.assertEqual(rows, [])

    def test_build_task_config_uses_overrides_and_defaults(self):
        from app.products.web.admin.register import TaskCreate, build_task_config_from_defaults

        defaults = {
            "run": {"count": 50},
            "proxy": "http://default-proxy:8080",
            "browser_proxy": "http://default-browser:8080",
            "temp_mail_provider": "cloudmail",
            "temp_mail_api_base": "https://mail.example.com",
            "temp_mail_admin_email": "admin@example.com",
            "temp_mail_admin_password": "secret",
            "temp_mail_domain": "example.com",
            "temp_mail_site_password": "site-secret",
            "api": {
                "endpoint": "http://grok2api:8000/admin/api/tokens",
                "token": "admin-key",
                "append": True,
            },
        }
        payload = TaskCreate(
            name="batch-1",
            count=3,
            proxy=None,
            browser_proxy="http://override-browser:8080",
            temp_mail_provider=None,
            temp_mail_api_base=None,
            temp_mail_admin_email=None,
            temp_mail_admin_password=None,
            temp_mail_domain=" override.example.com ",
            temp_mail_site_password=None,
            api_endpoint=None,
            api_token="override-key",
            api_append=False,
        )

        result = build_task_config_from_defaults(defaults, payload)

        self.assertEqual(result["run"], {"count": 3})
        self.assertEqual(result["proxy"], "http://default-proxy:8080")
        self.assertEqual(result["browser_proxy"], "http://override-browser:8080")
        self.assertEqual(result["temp_mail_domain"], "override.example.com")
        self.assertEqual(result["api"]["endpoint"], "http://grok2api:8000/admin/api/tokens")
        self.assertEqual(result["api"]["token"], "override-key")
        self.assertFalse(result["api"]["append"])

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

    def test_merged_defaults_preserves_trimmed_saved_domain_arrays(self):
        import app.products.web.admin.register as register

        source_defaults = {
            "run": {"count": 50},
            "proxy": "",
            "browser_proxy": "",
            "temp_mail_provider": "cloudmail",
            "temp_mail_api_base": "https://mail.example.com",
            "temp_mail_admin_email": "admin@example.com",
            "temp_mail_admin_password": "secret",
            "temp_mail_domain": "fallback.example.com",
            "temp_mail_site_password": "",
            "api": {"endpoint": "", "token": "", "append": True},
        }
        saved_settings = {
            "temp_mail_domain": [" one.example.com ", "", "two.example.com", "   "],
        }

        with patch.object(register, "load_source_defaults", return_value=source_defaults), patch.object(register, "read_settings", return_value=saved_settings):
            result = register.merged_defaults()

        self.assertEqual(result["temp_mail_domain"], ["one.example.com", "two.example.com"])

    def test_parse_console_state_extracts_progress(self):
        from app.products.web.admin.register import parse_console_state

        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "console.log"
            log_path.write_text(
                "\n".join(
                    [
                        "2026-05-31 10:00:00 | [*] 开始第 1 轮注册",
                        "2026-05-31 10:00:01 | 临时邮箱创建成功: user@example.com",
                        "2026-05-31 10:00:02 | 提取到验证码 ABC123",
                        "2026-05-31 10:00:03 | 注册成功 | email=user@example.com | password=x",
                        "2026-05-31 10:00:04 | SSO token 已推送到 API（共 1 个）",
                        "2026-05-31 10:00:05 | [Error] 第 2 轮失败: blocked",
                    ]
                ),
                encoding="utf-8",
            )

            state = parse_console_state(log_path)

        self.assertEqual(state["current_round"], 1)
        self.assertEqual(state["completed_count"], 1)
        self.assertEqual(state["failed_count"], 1)
        self.assertEqual(state["last_email"], "user@example.com")
        self.assertEqual(state["last_error"], "blocked")
        self.assertEqual(state["current_phase"], "pushed_to_api")

    def test_serialize_task_decodes_config_json(self):
        from app.products.web.admin.register import serialize_task

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
            (json.dumps({"run": {"count": 2}}),),
        )
        row = conn.execute("SELECT * FROM tasks").fetchone()

        result = serialize_task(row)
        conn.close()

        self.assertEqual(result["id"], 1)
        self.assertEqual(result["name"], "batch")
        self.assertEqual(result["config"], {"run": {"count": 2}})

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

    def test_register_router_is_mounted_on_main_app(self):
        from app.main import app

        self.assertTrue(any(route.path == "/admin/api/register/tasks" for route in app.routes))

    def test_register_admin_page_route_is_mounted_on_main_app(self):
        from app.main import app

        self.assertTrue(any(route.path == "/admin/register" for route in app.routes))
        self.assertTrue((Path(__file__).parents[1] / "app" / "statics" / "admin" / "register.html").exists())

    def test_register_admin_page_loads_shared_admin_scripts_in_header_order(self):
        html = (Path(__file__).parents[1] / "app" / "statics" / "admin" / "register.html").read_text(encoding="utf-8")

        script_order = [
            '/static/js/i18n.js?v={{APP_VERSION}}',
            '/static/js/auth.js?v={{APP_VERSION}}',
            '/static/js/admin-header.js?v={{APP_VERSION}}',
            '/static/js/footer.js?v={{APP_VERSION}}',
            '/static/js/admin-register.js?v={{APP_VERSION}}',
        ]
        positions = [html.index(script) for script in script_order]

        self.assertEqual(positions, sorted(positions))
        self.assertIn('await renderSiteFooter?.();', html)

    def test_register_admin_js_confirms_delete_and_uses_non_overlapping_polling(self):
        js = (Path(__file__).parents[1] / "app" / "statics" / "js" / "admin-register.js").read_text(encoding="utf-8")

        self.assertIn("confirm(", js)
        self.assertNotIn("setInterval(", js)
        self.assertIn("pollTasks", js)
        self.assertIn("isPollingTasks", js)

    def test_register_admin_js_renders_provider_select_and_cloudmail_domain_textarea(self):
        js = (Path(__file__).parents[1] / "app" / "statics" / "js" / "admin-register.js").read_text(encoding="utf-8")

        self.assertIn("temp_mail_provider", js)
        self.assertIn("temp_mail_domain", js)
        self.assertIn("<select", js)
        self.assertIn("<textarea", js)
        self.assertIn("cloudmail", js)
        self.assertIn("duckmail", js)
        self.assertIn("ahem", js)
        self.assertIn("generic", js)

    def test_register_admin_js_preserves_unknown_selected_provider_option(self):
        js = (Path(__file__).parents[1] / "app" / "statics" / "js" / "admin-register.js").read_text(encoding="utf-8")

        self.assertIn("const stringValue = String(value ?? '');", js)
        self.assertIn("options.some(([optionValue]) => String(optionValue) === stringValue)", js)
        self.assertIn("[[stringValue, stringValue], ...options]", js)
        self.assertIn("String(optionValue) === stringValue ? 'selected' : ''", js)

    def test_register_admin_js_serializes_cloudmail_domain_lines(self):
        js = (Path(__file__).parents[1] / "app" / "statics" / "js" / "admin-register.js").read_text(encoding="utf-8")

        self.assertIn("provider === 'cloudmail'", js)
        self.assertIn("split(/\\r?\\n/)", js)
        self.assertIn("payload.temp_mail_domain = domains", js)

    def test_register_admin_js_formats_domain_arrays_for_detail_view(self):
        js = (Path(__file__).parents[1] / "app" / "statics" / "js" / "admin-register.js").read_text(encoding="utf-8")

        self.assertIn("config.temp_mail_domain],", js)
        self.assertIn("<div class=\"detail-value\">${renderDetailValue(value)}</div>", js)
        self.assertIn(": esc(text(value));", js)
        self.assertIn(".join('<br>')", js)
        self.assertNotIn("if (Array.isArray(value)) {", js)

    def test_task_supervisor_start_stop_are_idempotent(self):
        import app.products.web.admin.register as register

        supervisor = register.TaskSupervisor()

        try:
            supervisor.start()
            first_thread = supervisor._thread
            supervisor.start()

            self.assertIs(supervisor._thread, first_thread)
            self.assertTrue(first_thread.is_alive())
        finally:
            supervisor.stop()
            supervisor.stop()

        self.assertTrue(supervisor._stop.is_set())

    def test_task_supervisor_stop_marks_running_tasks_stopped(self):
        import app.products.web.admin.register as register

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "register"
            task_dir = root / "tasks" / "task_1"
            console_path = task_dir / "console.log"
            task_dir.mkdir(parents=True)
            log_handle = console_path.open("a", encoding="utf-8")
            process = Mock(pid=4321)
            process.poll.return_value = None
            process.wait.return_value = 0

            with (
                patch.object(register, "REGISTER_ROOT", root),
                patch.object(register, "TASKS_DIR", root / "tasks"),
                patch.object(register, "DB_PATH", root / "console.db"),
            ):
                register.init_db()
                task_id = register.execute(
                    """
                    INSERT INTO tasks (
                        name, status, target_count, config_json, task_dir, console_path,
                        pid, created_at, started_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "batch",
                        register.STATUS_RUNNING,
                        1,
                        json.dumps({"run": {"count": 1}}),
                        str(task_dir),
                        str(console_path),
                        4321,
                        register.now_iso(),
                        register.now_iso(),
                    ),
                )
                supervisor = register.TaskSupervisor()
                supervisor._processes[task_id] = register.ManagedProcess(task_id, process, log_handle)

                supervisor.stop()

                row = register.task_row(task_id)

        self.assertEqual(row["status"], register.STATUS_STOPPED)
        self.assertIsNone(row["pid"])
        self.assertIsNotNone(row["finished_at"])
        self.assertEqual(row["last_error"], "Task stopped during application shutdown.")
        self.assertTrue(log_handle.closed)
        process.terminate.assert_called_once()

    def test_start_task_marks_failed_when_popen_fails(self):
        import app.products.web.admin.register as register

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "register"
            task_dir = root / "tasks" / "task_1"
            console_path = task_dir / "console.log"
            task_dir.mkdir(parents=True)

            with (
                patch.object(register, "REGISTER_ROOT", root),
                patch.object(register, "TASKS_DIR", root / "tasks"),
                patch.object(register, "DB_PATH", root / "console.db"),
                patch.object(register, "copy_source_to_task_dir"),
                patch.object(register.subprocess, "Popen", side_effect=OSError("launch failed")),
            ):
                register.init_db()
                task_id = register.execute(
                    """
                    INSERT INTO tasks (
                        name, status, target_count, config_json, task_dir, console_path, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "batch",
                        "starting",
                        1,
                        json.dumps({"run": {"count": 1}}),
                        str(task_dir),
                        str(console_path),
                        register.now_iso(),
                    ),
                )
                row = register.task_row(task_id)

                with self.assertRaises(OSError):
                    register.TaskSupervisor()._start_task(row)

                row = register.task_row(task_id)

        self.assertEqual(row["status"], register.STATUS_FAILED)
        self.assertIsNotNone(row["finished_at"])
        self.assertEqual(row["last_error"], "launch failed")

    def test_start_task_marks_failed_when_source_copy_fails(self):
        import app.products.web.admin.register as register

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "register"
            task_dir = root / "tasks" / "task_1"
            console_path = task_dir / "console.log"

            with (
                patch.object(register, "REGISTER_ROOT", root),
                patch.object(register, "TASKS_DIR", root / "tasks"),
                patch.object(register, "DB_PATH", root / "console.db"),
                patch.object(register, "copy_source_to_task_dir", side_effect=OSError("copy failed")),
                patch.object(register.subprocess, "Popen") as popen,
            ):
                register.init_db()
                task_id = register.execute(
                    """
                    INSERT INTO tasks (
                        name, status, target_count, config_json, task_dir, console_path, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "batch",
                        "starting",
                        1,
                        json.dumps({"run": {"count": 1}}),
                        str(task_dir),
                        str(console_path),
                        register.now_iso(),
                    ),
                )
                row = register.task_row(task_id)

                with self.assertRaises(OSError):
                    register.TaskSupervisor()._start_task(row)

                row = register.task_row(task_id)

        self.assertEqual(row["status"], register.STATUS_FAILED)
        self.assertEqual(row["current_phase"], "start_failed")
        self.assertIsNotNone(row["finished_at"])
        self.assertIsNone(row["pid"])
        self.assertEqual(row["last_error"], "copy failed")
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
