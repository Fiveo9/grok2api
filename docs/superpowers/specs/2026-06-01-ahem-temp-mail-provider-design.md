# AHEM Temp Mail Provider Design

## Goal

Add an `ahem` temp mail provider to `email_register.py` so the existing registration flow can use the AHEM mailbox API as a first-class source of disposable email addresses.

## Scope

In scope:
- Add `temp_mail_provider=ahem`
- Support AHEM domain discovery from `/properties`
- Support AHEM mailbox listing and message detail lookup
- Reuse the existing verification-code extraction logic
- Document the new provider in `docs/temp-mail-api.md`
- Add tests for the AHEM provider path

Out of scope:
- No new external service process
- No changes to DuckMail behavior
- No changes to Cloud Mail behavior
- No changes to the generic Temp Mail contract
- No changes to registration task orchestration beyond provider selection

## API Contract

AHEM provider behavior is:

- `GET {temp_mail_api_base}/properties`
  - returns `allowedDomains`
- `GET {temp_mail_api_base}/mailbox/{prefix}/email`
  - returns a list of mail summaries
- `GET {temp_mail_api_base}/mailbox/{prefix}/email/{msg_id}`
  - returns a mail detail object

The provider should treat `prefix` as the mailbox token for subsequent mailbox requests.

## Design

### Provider detection

Extend `_detect_mail_provider()` so the value `ahem` maps to the new provider branch. Existing provider detection remains unchanged.

### Email creation

Add a dedicated AHEM creation path that:
- fetches allowed domains from `/properties`
- chooses one domain at random
- generates a random local prefix
- returns `(email, password, mail_token)`

For AHEM, `password` may be empty if the API does not provide one.

### Mail polling

Add AHEM-specific list and detail fetchers that:
- list messages from `/mailbox/{prefix}/email`
- fetch message details from `/mailbox/{prefix}/email/{msg_id}`
- normalize message IDs consistently with existing mailbox logic

### Verification extraction

Reuse the existing content extraction and verification-code parser. The AHEM detail payload only needs to expose enough text through `subject`, `text`, `html`, or `textAsHtml` for the current regex-based extraction to succeed.

## Configuration

New or clarified behavior:
- `temp_mail_provider = ahem`
- `temp_mail_api_base` is required
- `temp_mail_domain` is optional for AHEM because domains are discovered dynamically
- `temp_mail_admin_email` is not used by AHEM
- `temp_mail_admin_password` is not used by AHEM
- `temp_mail_site_password` remains optional and, if set, continues to be sent as `x-custom-auth`

## Error Handling

- If `/properties` does not return domains, fail mailbox creation with a clear AHEM-specific error.
- If mailbox listing or detail retrieval fails, return no messages rather than crashing the registration loop.
- Keep existing timeout and retry behavior consistent with the current temp mail adapter style.

## Testing

Add tests that verify:
- `temp_mail_provider=ahem` is recognized
- AHEM domain discovery is used for creation
- AHEM mailbox listing is called with the expected URL shape
- AHEM message detail lookup is called with the expected URL shape
- The verification-code extraction path still works with AHEM-style payloads

## Implementation Notes

The change should stay localized to the temp-mail adapter and its documentation. The goal is to make AHEM a drop-in provider, not to introduce a second registration architecture.
