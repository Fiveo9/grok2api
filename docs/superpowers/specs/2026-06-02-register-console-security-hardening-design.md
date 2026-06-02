# Register Console Security Hardening Design

## Goal

Reduce the chance of leaking local registration credentials, API tokens, and proxy secrets through accidental commits or admin API responses.

## Scope

In scope:
- Ignore the local root-level `config.json` file used by registration runs.
- Keep `config.example.json` as the committed non-secret template.
- Document that real passwords and tokens must stay in local config or environment variables.
- Ensure register console API responses mask sensitive settings and task config fields.
- Add regression tests for preserving stored sensitive values and masking returned sensitive values.

Out of scope:
- No secret backend migration.
- No encryption-at-rest for the SQLite settings database.
- No change to the registration runner's runtime config format.
- No automated credential rotation.

## Design

### Git hygiene

Add root-level `config.json` to `.gitignore`. This prevents the local registration config from appearing as an untracked file when it contains real Cloud Mail credentials, proxy settings, or token sink keys.

The committed `config.example.json` remains the template operators copy from. It should not contain real secrets.

### Admin API masking

The register console should never return full values for these fields in settings/default responses:
- `temp_mail_admin_password`
- `temp_mail_site_password`
- `api_token`
- proxy URLs that may contain credentials

Task serialization should also mask sensitive values inside task config, including nested `api.token`.

Masking should preserve enough information to tell that a value exists, without exposing the original secret. Empty values stay empty.

### Saving settings

The frontend sends empty strings for password/token fields when the user leaves them unchanged. The backend should preserve the existing stored sensitive value in that case. If no existing value is present, an empty string remains empty.

This keeps the UI from needing to receive or echo real secrets back to the browser.

### Documentation

Update quickstart guidance to state:
- Copy `config.example.json` to `config.json` for local runs.
- Do not commit `config.json`.
- Rotate passwords/tokens if they were ever committed, pasted into logs, or shared.

## Error Handling

- Invalid or missing local config files should fall back to safe defaults or the example template without exposing file contents in responses.
- Masking helpers should tolerate malformed proxy URLs and non-string values.

## Testing

Add tests that verify:
- `write_settings()` preserves existing sensitive values when incoming payload fields are empty.
- `get_settings()` or the settings masking helper does not return raw sensitive values.
- `serialize_task()` masks task config secrets, including nested `api.token`.
- `.gitignore` contains a root-level `config.json` rule.

## Implementation Notes

Keep the change small and localized to `.gitignore`, `docs/quickstart.md`, `app/products/web/admin/register.py`, and `tests/test_register_console.py`. Avoid introducing a larger secret management system until there is a concrete deployment requirement.
