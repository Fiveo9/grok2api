import unittest
from unittest.mock import patch


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


class AhemProviderTests(unittest.TestCase):
    def tearDown(self):
        import email_register

        email_register._ahem_domains_cache.clear()

    def test_detects_ahem_provider_from_config_value(self):
        import email_register

        with patch.object(email_register, "TEMP_MAIL_PROVIDER", "ahem"):
            self.assertEqual(email_register._detect_mail_provider("https://mail.example"), "ahem")
            self.assertEqual(email_register._provider_label(), "AHEM")

    def test_create_ahem_email_uses_properties_domains(self):
        import email_register

        response = FakeResponse(200, {"allowedDomains": ["ahem.test"]})
        session = FakeSession([response])

        with (
            patch.object(email_register, "TEMP_MAIL_PROVIDER", "ahem"),
            patch.object(email_register, "TEMP_MAIL_API_BASE", "https://ahem.example"),
            patch.object(email_register, "_ahem_domains_cache", {}),
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
            patch.object(email_register, "_ahem_domains_cache", {}),
            patch.object(email_register, "_create_session", return_value=(session, False)),
        ):
            with self.assertRaisesRegex(Exception, "AHEM"):
                email_register.create_temp_email()

    def test_create_ahem_email_does_not_reuse_cached_domains_across_api_bases(self):
        import email_register

        session_one = FakeSession([FakeResponse(200, {"allowedDomains": ["one.test"]})])
        session_two = FakeSession([FakeResponse(200, {"allowedDomains": ["two.test"]})])

        with (
            patch.object(email_register, "TEMP_MAIL_PROVIDER", "ahem"),
            patch.object(email_register, "_ahem_domains_cache", {}),
            patch.object(email_register, "_generate_local_part", return_value="abc123"),
        ):
            with (
                patch.object(email_register, "TEMP_MAIL_API_BASE", "https://ahem-one.example"),
                patch.object(email_register, "_create_session", return_value=(session_one, False)),
            ):
                first_email, _first_password, first_token = email_register.create_temp_email()

            with (
                patch.object(email_register, "TEMP_MAIL_API_BASE", "https://ahem-two.example"),
                patch.object(email_register, "_create_session", return_value=(session_two, False)),
            ):
                second_email, _second_password, second_token = email_register.create_temp_email()

        self.assertEqual(first_email, "abc123@one.test")
        self.assertEqual(first_token, "abc123")
        self.assertEqual(second_email, "abc123@two.test")
        self.assertEqual(second_token, "abc123")
        self.assertEqual(session_one.calls[0][1], "https://ahem-one.example/properties")
        self.assertEqual(session_two.calls[0][1], "https://ahem-two.example/properties")

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

        session = FakeSession([FakeResponse(200, {"textAsHtml": "<p>Your code is <strong>ABC-123</strong></p>"})])

        with (
            patch.object(email_register, "TEMP_MAIL_PROVIDER", "ahem"),
            patch.object(email_register, "TEMP_MAIL_API_BASE", "https://ahem.example"),
            patch.object(email_register, "_create_session", return_value=(session, False)),
        ):
            detail = email_register.fetch_email_detail("abc123", "msg-1")

        self.assertEqual(detail["textAsHtml"], "<p>Your code is <strong>ABC-123</strong></p>")
        self.assertNotIn("html", detail)
        self.assertEqual(session.calls[0][1], "https://ahem.example/mailbox/abc123/email/msg-1")

    def test_wait_for_verification_code_reads_ahem_html_detail_payload(self):
        import email_register

        list_response = FakeResponse(200, [{"emailId": "msg-1"}])
        detail_response = FakeResponse(200, {"textAsHtml": "<p>Your verification code is <strong>ABC&#45;123</strong></p>"})
        session = FakeSession([list_response, detail_response])

        with (
            patch.object(email_register, "TEMP_MAIL_PROVIDER", "ahem"),
            patch.object(email_register, "TEMP_MAIL_API_BASE", "https://ahem.example"),
            patch.object(email_register, "_create_session", return_value=(session, False)),
        ):
            code = email_register.wait_for_verification_code("abc123", timeout=1)

        self.assertEqual(code, "ABC-123")


if __name__ == "__main__":
    unittest.main()
