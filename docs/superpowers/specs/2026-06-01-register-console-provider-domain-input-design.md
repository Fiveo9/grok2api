# Register Console Provider And Domain Input Design

## Goal

Improve the register console so the mail provider is chosen from a dropdown, and Cloud Mail can be configured with multiple domains using a native multi-line input.

## Scope

In scope:
- Change the register console "邮箱服务商" field from free text to a select dropdown
- Add explicit provider options for `cloudmail`, `duckmail`, `ahem`, and `generic`
- Change the default settings "邮箱域名" field to a multi-line input when the selected provider is `cloudmail`
- Support one-domain-per-line input for Cloud Mail domains
- Save Cloud Mail domains as a JSON array in register console settings and task config
- Keep non-Cloud-Mail providers using single-domain string behavior
- Update task detail rendering so domain arrays display clearly
- Add backend and frontend tests for the new behavior

Out of scope:
- No change to mailbox provider API behavior in `email_register.py`
- No change to task execution flow outside domain value serialization
- No multi-domain UI for task-level override fields in this change
- No new provider types beyond the existing supported set

## Design

### Provider selection

The settings form should render `temp_mail_provider` as a select instead of a text input. The available values are:

- `cloudmail`
- `duckmail`
- `ahem`
- `generic`

The selected value drives how the domain field is rendered.

### Domain input behavior

When `temp_mail_provider` is `cloudmail`:
- render `temp_mail_domain` as a `textarea`
- each non-empty line is treated as one domain
- the saved value becomes a list of strings

When `temp_mail_provider` is anything else:
- render `temp_mail_domain` as a single-line input
- the saved value remains a string

When settings are loaded from saved data:
- if the provider is `cloudmail` and the saved domain value is a list, the UI should join it with newlines
- if the saved value is a string, the UI should display that string directly

## Backend Data Handling

The register console backend should accept `temp_mail_domain` as either:
- `str`
- `list[str]`

Expected behavior:
- `SystemSettings` accepts either representation
- `TaskCreate` can continue accepting a string for task-level override because this change does not expand the task creation UI
- merged defaults preserve arrays for Cloud Mail defaults
- task config building passes through the stored array unchanged when no task-level override is provided

## Rendering Rules

Task detail rendering should avoid showing raw Python or JSON list syntax when possible. If `temp_mail_domain` is an array, render it as a human-readable joined string, such as newline-separated or comma-separated text.

## Error Handling

- Empty lines in the Cloud Mail textarea should be ignored
- Whitespace around each domain should be trimmed
- If the user enters one line only, Cloud Mail should still save it as a one-item array
- Switching provider away from `cloudmail` should switch the control back to a single-line input without changing unrelated fields

## Testing

Add tests that verify:
- the settings form renders `temp_mail_provider` as a select
- the settings form uses a `textarea` for `temp_mail_domain` when provider is `cloudmail`
- Cloud Mail multi-line domain input is saved as a list
- saved list values are returned correctly from settings/default merging
- task config building preserves stored domain arrays
- task detail rendering formats array domains readably

## Implementation Notes

This change should stay localized to the register console backend models/serialization and `app/statics/js/admin-register.js`. The goal is to improve operator input correctness without redesigning the rest of the registration workflow.
