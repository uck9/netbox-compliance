# Compliance Plugin — Naming Convention Standards

**Scope:** Naming rules for Packages, Measures, and related identifiers in the NetBox compliance plugin.
**Audience:** Network engineers creating or modifying compliance objects, and script authors ingesting results.
**Status:** Standard — deviations require review.

---

## 1. General Principles

1. **Every object has two names.** A *slug* (machine identity) and a *display name* (human label). Slugs are permanent; display names may be edited freely at any time.
2. **Slugs are immutable once in use.** Ingestion scripts, API consumers, and historical results reference slugs. Renaming a slug is a breaking change and requires a coordinated migration — treat it like renaming a production interface.
3. **Names describe the thing, not the state.** The measure names *what is checked*; the result carries pass/fail and detail. Never encode a threshold, target, or outcome in a name.
4. **Reuse NetBox vocabulary.** Where a package or measure maps to a NetBox concept (device role, site group, platform), use the same words NetBox uses, so the mapping is obvious to anyone reading either system.

---

## 2. Slug Format (applies to all slugs)

| Rule | Value |
|---|---|
| Character set | Lowercase `a–z`, digits `0–9`, hyphen separator |
| Pattern | `^[a-z0-9]+(-[a-z0-9]+)*$` |
| Length | 3–50 characters |
| Prohibited | Underscores, capitals, spaces, leading/trailing hyphens, consecutive hyphens |
| Abbreviations | Only well-known networking abbreviations (`ntp`, `aaa`, `snmp`, `acl`, `bgp`, `mgmt`). Do not invent new ones. |

This pattern is enforced by a model validator; the API and UI will reject non-conforming slugs.

---

## 3. Measures

A measure is a single check whose result is ingested per device. Name the **noun and attribute being checked** — no verbs, no outcomes.

**Pattern:** `<subject>[-<attribute>]`

### Rules

- No `check-`, `verify-`, `is-`, or `has-` prefixes. Every measure is a check; the prefix adds nothing.
- No pass conditions in the name. `software-version`, not `software-version-current` — targets change, the measure persists.
- No thresholds in the name. `config-backup-age`, not `config-backup-30d` — put the threshold in the description and the measure's evaluation logic, so tightening it later doesn't force a rename.
- Add a domain prefix **only** to resolve a genuine collision between platform variants (e.g. `ap-firmware` vs `software-version`). Do not pre-emptively namespace — the plugin context is already devices.
- Measure slugs are **globally unique** (not per-package), because a measure can belong to multiple packages and scripts reference it standalone.

### Standard measure names

| Slug | Display name | What it checks |
|---|---|---|
| `software-version` | Software Version | Running OS version vs platform target |
| `config-backup-age` | Config Backup Age | Time since last successful config backup |
| `config-drift` | Configuration Drift | Running config vs intended/golden config |
| `ntp-servers` | NTP Configuration | Configured NTP servers vs standard |
| `aaa-tacacs` | AAA / TACACS+ | TACACS+ server and method-list configuration |
| `snmp-community` | SNMP Configuration | SNMP settings vs standard (no default communities) |
| `mgmt-acl` | Management ACL | ACLs applied to management plane access |
| `syslog-servers` | Syslog Configuration | Configured syslog destinations vs standard |
| `dns-servers` | DNS Configuration | Configured name servers vs standard |
| `banner-login` | Login Banner | Presence and content of the corporate login banner |
| `ap-firmware` | AP Firmware Version | Wireless AP firmware vs controller target |

Add new measures to this table as they are created.

### Display names for measures

Title Case, human-first, short. State *what* is checked, not how: "Config Backup Age", not "Checks the age of the last backup". Thresholds and targets belong in the **description** field, e.g. *"Fails when the last successful backup is older than 30 days."*

---

## 3a. Measure Result Types

Every measure has a `result_type`: `boolean`, `percentage`, or `enum`. This governs which other fields apply and how a result's **credit** (0–100) is derived — credit, not a pass/fail flag, is what packages actually score on.

| result_type | `pass_threshold` | `value_map` | Credit derivation |
|---|---|---|---|
| `boolean` | must be unset | must be empty | `pass` → 100, `fail` → 0 |
| `percentage` | required | must be empty | credit = the posted percentage, clamped 0–100 |
| `enum` | must be unset | required, non-empty | credit = the matched entry's `credit` |

These are mutually exclusive and enforced by `ComplianceMeasure.clean()` and the API serializer — setting `value_map` on a `percentage` measure (or vice versa) is rejected.

For `percentage` measures, a posted result is `pass` only if the value is `>= pass_threshold`; the credit itself is the raw percentage regardless of pass/fail, so a package's score reflects partial credit rather than a binary cutoff.

---

## 4. Packages

A package groups measures into a standard applied to a set of devices. Name the **audience or standard the package serves**, not its contents — contents drift as measures are added.

**Pattern:** `<standard-or-audience>[-<qualifier>]`

### Rules

- Answer the question *"why does this set of measures exist?"* — `baseline-security`, not `software-and-backup-checks`.
- Mirror NetBox device roles, platforms, or site tiers where the package maps to one: a package applied to the `branch-router` role should be `branch-router-standard`.
- **No version numbers in slugs.** Packages evolve in place; score snapshots preserve historical composition. Only create a parallel package when two standards genuinely coexist (e.g. during a platform transition), and name it for the standard, not a version: `ios-xe-17x-baseline`, not `baseline-v2`.

### Standard package names

| Slug | Display name | Applies to |
|---|---|---|
| `baseline-security` | Baseline Security | All managed devices |
| `baseline-operational` | Baseline Operational | All managed devices (backups, logging, NTP) |
| `branch-router-standard` | Branch Router Standard | Devices with role `branch-router` |
| `datacentre-core-standard` | Datacentre Core Standard | DC core/aggregation devices |
| `wireless-standard` | Wireless Standard | WLCs and APs |
| `pci-scope` | PCI Scope | Devices in PCI-scoped sites/VLANs |

### Display names for packages

Title Case. May include the word "Standard", "Baseline", or the framework name (PCI, Essential Eight) where it aids recognition. Descriptions should state the intended device population and the owning team.

### Package scoring fields

Beyond naming, every package carries three fields that control how it resolves to a traffic light on the device panel and reports:

| Field | Purpose |
|---|---|
| `status` | `draft` / `active` / `retired`. Only `active` packages are applied to devices; use `draft` while building out a new standard. |
| `amber_threshold` | Score (default `80.00`) at/above which a non-green package shows amber rather than red. |
| `red_on_critical_fail` | If set (default), any failing `critical`/`high`-severity measure forces the package red regardless of score. |

These aren't naming decisions, but set them deliberately when creating a package — a `pci-scope` package, for example, should likely keep `red_on_critical_fail` on rather than let a high score mask a critical failure.

---

## 5. Result Detail Keys

Detail keys carried in ingested results (and enforced via `required_detail_keys`) use **lowercase snake_case**, since they are JSON payload keys rather than URL-facing slugs.

| Convention | Example |
|---|---|
| Observed value | `running` (e.g. running software version) |
| Expected value | `target` |
| Timestamps | `last_backup_at`, ISO 8601 UTC |
| Free-text context | `note` |

Use `running` / `target` consistently across measures so display templates and the insights consumer can rely on them.

---

## 6. Enum Value Structure (`value_map`)

Enum-typed measures store their values in **`value_map`** — a JSON *object* keyed by the enum value itself, not an array. There is no separate `key` property; the dict key **is** the key.

### Key format (the `value_map` dict keys)

| Rule | Value |
|---|---|
| Character set | Lowercase snake_case: `a–z`, `0–9`, underscore |
| Pattern | `^[a-z][a-z0-9_]*$` |
| Length | ≤ 30 characters |
| Style | Name the *state*, not the action — `upgrade_required`, not `needs_upgrading` |

Keys are stored in results and referenced by scripts and the API — like slugs, they are immutable once in use.

### Entry shape

Each `value_map[key]` is an object with exactly three properties:

| Property | Type | Values | Notes |
|---|---|---|---|
| `label` | string | non-empty | Title Case display label |
| `color` | string | `green`, `orange`, `red`, `grey` | Traffic-light color shown in the UI |
| `credit` | number | `0`–`100` | Scoring weight this value contributes; **not** a pass/fail flag |

There is **no `status` property.** Pass/fail is only derived at ingestion time, and only as a simplification: `credit == 100` → `pass`, anything else → `fail`. Scoring itself always uses the raw `credit`, so two `fail`-deriving entries (e.g. credit `90` vs credit `10`) are not scored identically — don't assume otherwise when choosing values.

**Standard: `software-version`**

| Key | Label | Color | Credit |
|---|---|---|---|
| `on_target` | On Target | green | 100 |
| `accepted` | Accepted | green | 100 |
| `upgrade_required` | Upgrade Required | orange | 0 |
| `unsupported` | Unsupported | red | 0 |
| `unknown_version` | Unknown Version | red | 0 |

Required detail keys for this measure: `running`, `target` (see §5).

**Standard: `config-backup-age`** *(illustrative — if implemented as `enum`; a percentage-based freshness measure would instead use `percentage` per §3a and carry no `value_map`)*

| Key | Label | Color | Credit |
|---|---|---|---|
| `current` | Current | green | 100 |
| `aging` | Aging | orange | 100 |
| `overdue` | Overdue | red | 0 |
| `never_backed_up` | Never Backed Up | red | 0 |

### Rules for defining new entries

- Keys describe the device's state relative to the standard, not the operator's task.
- `color` may be more cautious than the derived pass/fail (an orange `upgrade_required` that derives to `fail`, or a green `accepted` at credit 100 that derives to `pass`) but should not contradict a value's own credit — don't pair `credit: 100` with `color: red` or vice versa.
- Prefer entries whose `credit` is either `100` or `0`; intermediate credit values are legal but should be a deliberate scoring decision, documented in the measure's description, not a default.
- Scripts must send only defined keys — unknown enum values are rejected at ingestion. Add the key to `value_map` (and this document) *before* deploying the script change.
- Prefer 3–5 values per measure. If you need more, the measure is probably doing two jobs — split it.
- To edit later: `label` and `color` may be changed in place; **never delete or rename a key** that has ingested results — mark it obsolete by appending `(deprecated)` to its label and stop scripts sending it, then remove the entry only after no results reference it within the retention window.

### JSON layouts

**Enum definition on the measure** (stored in the measure's `value_map` field; this is the single source of truth ingestion validates against):

```json
{
  "target":        { "label": "Target Active",        "color": "green",  "credit": 100 },
  "accepted":          { "label": "Accepted",          "color": "green",  "credit": 100 },
  "upgrade_required":  { "label": "Upgrade Required",  "color": "orange", "credit": 0 },
  "unsupported":       { "label": "Unsupported",       "color": "red",    "credit": 0 },
  "unknown_version":   { "label": "Unknown Version",   "color": "red",    "credit": 0 }
}
```

**Bulk result ingestion payload** (`POST /api/plugins/compliance/results/bulk/`; accepts one object or a list, each with a `device` and a `results` array; `source`/`timestamp` may be set per batch or overridden per item):

```json
{
  "device": "bran-rtr-01",
  "source": "software_version",
  "timestamp": "2026-07-19T02:15:00Z",
  "results": [
    {
      "measure": "software-version",
      "value": "upgrade_required",
      "details": {
        "running": "17.9.4a",
        "target": "17.12.3"
      }
    }
  ]
}
```

A script sends `value` and `details`; `status` is derived server-side from the measure's `result_type` and is normally omitted. The **only** exception: a script may post `status` explicitly as `error` or `not_applicable` (the check itself broke, or doesn't apply to this device) — any other explicit `status` is rejected. `value` is optional only in that explicit-status case.

For `boolean`/`percentage` measures, `value_map` doesn't apply — see §3a.

### Core result status (`ComplianceResult.status`, as stored)

| Key | Label | Meaning |
|---|---|---|
| `pass` | Pass | Check succeeded (or percentage ≥ threshold, or enum credit 100) |
| `fail` | Fail | Check failed |
| `error` | Error | The check itself broke and couldn't produce a result |
| `not_applicable` | Not Applicable | Script determined the check doesn't apply to this device |

These four are the only values ever written to `ComplianceResult.status`. `pending`, `stale`, and `exempt` are **not** stored statuses — they're display-only states computed at read time for a device that has no result yet, a result older than `max_result_age_days`, or a measure removed from the effective set by a compliance exemption. An exempted measure doesn't produce a result with `status: exempt` — it's dropped from the device's effective measure set entirely and won't appear at all except in an audit trail.

### Rules for defining new typed values

See "Rules for defining new entries" above — kept as one section to avoid drift between duplicate rule lists.

### UI entry format

When creating or editing a measure in the NetBox UI (**Plugins → Compliance → Measures → Add**), enter fields exactly as follows:

| Form field | Format to enter | Example |
|---|---|---|
| Slug | Lowercase kebab-case per §2. Type it manually — do **not** rely on auto-slugging from the name, and verify it before saving (immutable after first result) | `software-version` |
| Name | Title Case display name | `Software Version` |
| Description | One sentence stating what is checked, including any threshold/target logic | `Compares the running OS version against the platform target and accepted list.` |
| Result Type | `boolean`, `percentage`, or `enum` per §3a | `enum` |
| Pass threshold | `percentage` measures only — leave blank otherwise | `95` |
| Required detail keys | Comma-separated snake_case keys, no spaces, no quotes | `running,target` |
| Value map | Single JSON **object** in the textarea, keyed by enum value, in the order values should appear in dropdowns/reports (best → worst). `enum` measures only — leave blank otherwise. Paste-validate before saving | see below |
| Display template | Django-template snippet referencing `{value, label, details}` | `{{ details.running }} (target {{ details.target }})` |
| Show on device panel | Checkbox — tick only for measures pinned to the device page | — |

**Value map textarea — exact entry format:**

```json
{
  "on_target":       { "label": "On Target",       "color": "green",  "credit": 100 },
  "accepted":        { "label": "Accepted",         "color": "green",  "credit": 100 },
  "upgrade_required":{ "label": "Upgrade Required", "color": "orange", "credit": 0 },
  "unsupported":     { "label": "Unsupported",      "color": "red",    "credit": 0 },
  "unknown_version": { "label": "Unknown Version",  "color": "red",    "credit": 0 }
}
```

Entry rules for the textarea:

- All three properties are required on every entry: `label`, `color`, `credit`. The form/API validator rejects entries missing any of them.
- `color` must be exactly `green`, `orange`, `red`, or `grey` — all lowercase, no other values.
- `credit` must be a number 0–100 (not a boolean, not a string).
- Order the object best-state-first; the UI renders choices in that order.
- Leave the field **empty** for `boolean` measures — do not enter `{}` or a pass/fail pair, as the core statuses are implicit. For `percentage` measures, use `pass_threshold` instead.
- To edit later: `label` and `color` may be changed in place; **never delete or rename a key** that has ingested results — mark it obsolete by appending `(deprecated)` to its label and stop scripts sending it, then remove the entry only after no results reference it within the retention window.

For a **package** (**Plugins → Compliance → Packages → Add**): Slug and Name per §4, `status`/`amber_threshold`/`red_on_critical_fail` per §4's Package scoring fields, then add measures on the package's measure tab with Weight (integer, default `1`), Required (checkbox), and Display order in gaps of 100 (`100`, `200`, `300`…) so later measures can be inserted without renumbering.

## 7. Ingestion Script Naming

Scripts that produce results should be named after the measure(s) they feed, using the measure slug with underscores for the filename: `software_version.py` feeds `software-version`. A script feeding a family of measures takes the family name: `baseline_config_audit.py`. The script's reported `source` identifier in results should match the filename without extension.

---

## 8. Do / Don't Quick Reference

| Don't | Do | Why |
|---|---|---|
| `check-ntp` | `ntp-servers` | No verb prefixes |
| `software-version-current` | `software-version` | No outcomes in names |
| `config-backup-30d` | `config-backup-age` | No thresholds in names |
| `network-device-snmp-config` | `snmp-community` | No redundant namespacing |
| `baseline-security-v2` | `baseline-security` (evolve in place) | No versions in slugs |
| `Software_Version` | `software-version` | Lowercase kebab-case only |
| Renaming a slug in use | New measure + deprecate old | Slugs are immutable |
| Encoding pass/fail as a per-value `status` | Encoding it as `credit` (0 or 100) | The data model has no per-value status — see §6 |

---

## 9. Change Management

- **New measure/package:** propose slug + display name + description via the standard change process; confirm the slug against this document and the tables above before creation.
- **Renaming:** display names may be changed at will. Slug changes are prohibited; if a slug is genuinely wrong, create a new object, migrate assignments, mark the old one retired, and remove it once no results reference it within the retention window.
- **This document:** update the measure and package tables whenever objects are added, in the same change that creates them.
