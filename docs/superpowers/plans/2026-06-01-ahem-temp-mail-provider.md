# AHEM Temp Mail Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `temp_mail_provider=ahem` so the existing registration flow can use AHEM disposable mailboxes.

**Architecture:** Keep AHEM inside the existing `email_register.py` adapter. Provider detection selects an AHEM branch for create/list/detail while the existing `wait_for_verification_code()` and `extract_verification_code()` flow remains shared.

**Tech Stack:** Python 3, `unittest`, `unittest.mock`, existing `requests`/`curl_cffi` session abstraction.

---

## File Structure

- Modify `email_register.py`: add AHEM provider detection, email creation, mailbox listing, and message detail retrieval.
- Create `tests/test_email_register_ahem.py`: focused unit tests for AHEM behavior using mocked request sessions.
- Modify `docs/temp-mail-api.md`: document `temp_mail_provider=ahem` and its AHEM API contract.

## Task 1: Provider Detection

**Files:**
- Create: `tests/test_email_register_ahem.py`
- Modify: `email_register.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_email_register_ahem.py` with:

```python
import unittest
from unittest.mock import patch


class AhemProviderTests(unittest.TestCase):
    def test_detects_ahem_provider_from_config_value(self):
        import email_register

        with patch.object(email_register, "TEMP_MAIL_PROVIDER", "ahem"):
            self.assertEqual(email_register._detect_mail_provider("https://mail.example"), "ahem")
            self.assertEqual(email_register._provider_label(), "AHEM")

    def test_detects_ahem_provider_from_hostname(self):
        import email_register

        with patch.object(email_register, "TEMP_MAIL_PROVIDER", ""):
            self.assertEqual(email_register._detect_mail_provider("https://ahem.example.com"), "ahem")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_email_register_ahem -v`

Expected: FAIL because `_detect_mail_provider()` returns `generic` or `_provider_label()` returns `Temp Mail`.

- [ ] **Step 3: Implement provider detection**

In `email_register.py`, update `_detect_mail_provider()` and `_provider_label()`:

```python
def _detect_mail_provider(api_base: str) -> str:
    provider = TEMP_MAIL_PROVIDER.replace("-", "_")
    if provider in {"duckmail", "duck_mail"}:
        return "duckmail"
    if provider in {"cloudmail", "cloud_mail", "skymail"}:
        return "cloudmail"
    if provider == "ahem":
        return "ahem"
    if provider in {"temp_mail", "generic"}:
        return "generic"

    hostname = (urlparse(api_base).hostname or "").lower()
    if "duckmail" in hostname:
        return "duckmail"
    if any(marker in hostname for marker in ("cloudmail", "cloud-mail", "skymail")):
        return "cloudmail"
    if "ahem" in hostname:
        return "ahem"
    return "generic"


def _provider_label() -> str:
    provider = _detect_mail_provider(TEMP_MAIL_API_BASE)
    if provider == "duckmail":
        return "DuckMail"
    if provider == "cloudmail":
        return "Cloud Mail"
    if provider == "ahem":
        return "AHEM"
    return "Temp Mail"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_email_register_ahem -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add email_register.py tests/test_email_register_ahem.py
git commit -m "feat: detect AHEM temp mail provider"
```

## Task 2: AHEM Email Creation

**Files:**
- Modify: `tests/test_email_register_ahem.py`
- Modify: `email_register.py`

- [ ] **Step 1: Add failing creation tests**

Append to `AhemProviderTests`:

```python
    def test_create_ahem_email_uses_properties_domains(self):
        import email_register

        response = FakeResponse(200, {"allowedDomains": ["ahem.test"]})
        session = FakeSession([response])

        with (
            patch.object(email_register, "TEMP_MAIL_PROVIDER", "ahem"),
            patch.object(email_register, "TEMP_MAIL_API_BASE", "https://ahem.example"),
            patch.object(email_register, "_ahem_domains_cache", []),
            patch.object(email_register, "_create_session", return_value=(session, False)),
            patch.object(email_register, "_generate_local_part", return_value="abc123"),
        ):
            email, password, token = email_register.create_temp_email()

        self.assertEqual(email, "abc123@ahem.test")
        self.assertEqual(password, "")
        self.assertEqual(token, "abc123")
        self.assertEqual(session.calls[0][0], "get")
        self.assertEqual(session.calls[0][1], "https://ahem.example/properties")

    def test_create_ahem_email_fails_when_domains_are_empty(self):
        import email_register

        session = FakeSession([FakeResponse(200, {"allowedDomains": []})])

        with (
            patch.object(email_register, "TEMP_MAIL_PROVIDER", "ahem"),
            patch.object(email_register, "TEMP_MAIL_API_BASE", "https://ahem.example"),
            patch.object(email_register, "_ahem_domains_cache", []),
            patch.object(email_register, "_create_session", return_value=(session, False)),
        ):
            with self.assertRaisesRegex(Exception, "AHEM"):
                email_register.create_temp_email()
```

Add these helper classes near the top of the file:

```python
class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("get", url, kwargs))
        return self._responses.pop(0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_email_register_ahem -v`

Expected: FAIL because AHEM creation is not implemented and generic creation requires admin password/domain.

- [ ] **Step 3: Implement AHEM creation**

In `email_register.py`, add a cache near the other provider globals:

```python
_ahem_domains_cache: List[str] = []
```

Add functions before `create_temp_email()`:

```python
def _get_ahem_domains(session, use_cffi, api_base: str) -> List[str]:
    global _ahem_domains_cache
    if _ahem_domains_cache:
        return _ahem_domains_cache

    res = _do_request(
        session,
        use_cffi,
        "get",
        f"{api_base.rstrip('/')}/properties",
        headers=_build_headers(),
        timeout=20,
    )
    if res.status_code != 200:
        raise Exception(f"获取 AHEM 域名失败: {res.status_code} - {res.text[:200]}")

    data = res.json()
    if not isinstance(data, dict):
        raise Exception("AHEM properties 接口返回格式异常")

    domains = data.get("allowedDomains") or []
    if not isinstance(domains, list):
        raise Exception("AHEM allowedDomains 返回格式异常")

    _ahem_domains_cache = [str(domain).strip() for domain in domains if str(domain).strip()]
    if not _ahem_domains_cache:
        raise Exception("AHEM 域名列表为空，无法创建邮箱")
    return _ahem_domains_cache


def _create_ahem_email() -> Tuple[str, str, str]:
    if not TEMP_MAIL_API_BASE:
        raise Exception("temp_mail_api_base 未设置，无法创建 AHEM 邮箱")

    session, use_cffi = _create_session()
    domains = _get_ahem_domains(session, use_cffi, TEMP_MAIL_API_BASE)
    email_local = _generate_local_part(random.randint(8, 12))
    email = f"{email_local}@{random.choice(domains)}"
    print(f"[*] AHEM 临时邮箱创建成功: {email}")
    return email, "", email_local
```

Update `create_temp_email()` after the Cloud Mail branch:

```python
    if provider == "ahem":
        try:
            return _create_ahem_email()
        except Exception as e:
            raise Exception(f"AHEM 临时邮箱创建失败: {e}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_email_register_ahem -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add email_register.py tests/test_email_register_ahem.py
git commit -m "feat: create AHEM temp mailboxes"
```

## Task 3: AHEM Mailbox Listing And Detail

**Files:**
- Modify: `tests/test_email_register_ahem.py`
- Modify: `email_register.py`

- [ ] **Step 1: Add failing mailbox tests**

Append to `AhemProviderTests`:

```python
    def test_fetch_ahem_emails_normalizes_email_id(self):
        import email_register

        session = FakeSession([FakeResponse(200, [{"emailId": "msg-1", "subject": "code"}])])

        with (
            patch.object(email_register, "TEMP_MAIL_PROVIDER", "ahem"),
            patch.object(email_register, "TEMP_MAIL_API_BASE", "https://ahem.example"),
            patch.object(email_register, "_create_session", return_value=(session, False)),
        ):
            messages = email_register.fetch_emails("abc123")

        self.assertEqual(messages[0]["id"], "msg-1")
        self.assertEqual(session.calls[0][1], "https://ahem.example/mailbox/abc123/email")

    def test_fetch_ahem_email_detail_uses_mailbox_detail_url(self):
        import email_register

        session = FakeSession([FakeResponse(200, {"textAsHtml": "Your code is ABC-123"})])

        with (
            patch.object(email_register, "TEMP_MAIL_PROVIDER", "ahem"),
            patch.object(email_register, "TEMP_MAIL_API_BASE", "https://ahem.example"),
            patch.object(email_register, "_create_session", return_value=(session, False)),
        ):
            detail = email_register.fetch_email_detail("abc123", "msg-1")

        self.assertEqual(detail["html"], "Your code is ABC-123")
        self.assertEqual(session.calls[0][1], "https://ahem.example/mailbox/abc123/email/msg-1")

    def test_wait_for_verification_code_reads_ahem_detail_payload(self):
        import email_register

        list_response = FakeResponse(200, [{"emailId": "msg-1"}])
        detail_response = FakeResponse(200, {"textAsHtml": "Your verification code is ABC-123"})
        session = FakeSession([list_response, detail_response])

        with (
            patch.object(email_register, "TEMP_MAIL_PROVIDER", "ahem"),
            patch.object(email_register, "TEMP_MAIL_API_BASE", "https://ahem.example"),
            patch.object(email_register, "_create_session", return_value=(session, False)),
        ):
            code = email_register.wait_for_verification_code("abc123", timeout=1)

        self.assertEqual(code, "ABC-123")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_email_register_ahem -v`

Expected: FAIL because `fetch_emails()` and `fetch_email_detail()` do not route to AHEM.

- [ ] **Step 3: Implement AHEM mailbox fetchers**

In `email_register.py`, add before `fetch_emails()`:

```python
def _normalize_ahem_message(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    msg_id = item.get("emailId") or item.get("id")
    if msg_id is None:
        return None
    normalized = dict(item)
    normalized["id"] = str(msg_id)
    return normalized


def _fetch_ahem_emails(mail_token: str) -> List[Dict[str, Any]]:
    api_base = TEMP_MAIL_API_BASE.rstrip("/")
    session, use_cffi = _create_session()
    res = _do_request(
        session,
        use_cffi,
        "get",
        f"{api_base}/mailbox/{mail_token}/email",
        headers=_build_headers(),
        timeout=20,
    )
    if res.status_code == 404:
        return []
    if res.status_code != 200:
        return []
    data = res.json()
    if not isinstance(data, list):
        return []
    messages: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        normalized = _normalize_ahem_message(item)
        if normalized:
            messages.append(normalized)
    return messages


def _fetch_ahem_email_detail(mail_token: str, msg_id: str) -> Optional[Dict[str, Any]]:
    api_base = TEMP_MAIL_API_BASE.rstrip("/")
    normalized_id = _normalize_message_id(msg_id)
    session, use_cffi = _create_session()
    res = _do_request(
        session,
        use_cffi,
        "get",
        f"{api_base}/mailbox/{mail_token}/email/{normalized_id}",
        headers=_build_headers(),
        timeout=20,
    )
    if res.status_code != 200:
        return None
    data = res.json()
    if not isinstance(data, dict):
        return None
    if data.get("textAsHtml") and not data.get("html"):
        data["html"] = data.get("textAsHtml")
    return data
```

Update `fetch_emails()` after the Cloud Mail branch:

```python
    if provider == "ahem":
        try:
            return _fetch_ahem_emails(mail_token)
        except Exception:
            return []
```

Update `fetch_email_detail()` after the Cloud Mail branch:

```python
    if provider == "ahem":
        try:
            return _fetch_ahem_email_detail(mail_token, msg_id)
        except Exception:
            return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_email_register_ahem -v`

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add email_register.py tests/test_email_register_ahem.py
git commit -m "feat: read AHEM inbox messages"
```

## Task 4: Documentation

**Files:**
- Modify: `docs/temp-mail-api.md`

- [ ] **Step 1: Add documentation**

In `docs/temp-mail-api.md`, add an AHEM section near the existing DuckMail and Cloud Mail notes:

```markdown
如果你用的是 AHEM：

- 把 `temp_mail_provider` 填成 `ahem`
- 把 `temp_mail_api_base` 填 AHEM API 根地址
- 不需要填写 `temp_mail_admin_email` / `temp_mail_admin_password`
- `temp_mail_domain` 可留空，执行器会从 AHEM `/properties` 的 `allowedDomains` 中随机选择域名
- 执行器会用邮箱前缀轮询 `/mailbox/<prefix>/email` 和 `/mailbox/<prefix>/email/<id>` 获取验证码
```

Also update the provider list around the configuration section to include:

```markdown
- `ahem`：使用 AHEM 邮箱接口
```

- [ ] **Step 2: Verify docs mention AHEM**

Run: `rg -n "AHEM|ahem|/properties|/mailbox" docs/temp-mail-api.md`

Expected: output includes the new AHEM provider section and API paths.

- [ ] **Step 3: Commit**

Run:

```bash
git add docs/temp-mail-api.md
git commit -m "docs: document AHEM temp mail provider"
```

## Task 5: Final Verification

**Files:**
- Verify only

- [ ] **Step 1: Run focused AHEM tests**

Run: `python -m unittest tests.test_email_register_ahem -v`

Expected: all AHEM tests pass.

- [ ] **Step 2: Run register console tests**

Run: `python -m unittest tests.test_register_console -v`

Expected: all register console tests pass.

- [ ] **Step 3: Compile changed Python files**

Run: `python -m compileall email_register.py tests/test_email_register_ahem.py`

Expected: compile succeeds with no syntax errors.

- [ ] **Step 4: Run linter on changed Python files**

Run: `python -m ruff check email_register.py tests/test_email_register_ahem.py`

Expected: no lint errors.

- [ ] **Step 5: Review final status**

Run: `git status --short --branch`

Expected: clean working tree on `feature/register-console-integration`.
