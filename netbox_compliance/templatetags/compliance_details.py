import json

from django import template
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe

register = template.Library()

# Signals a `details` blob was posted by something using our Evidence shape (expected/found/
# missing/unexpected/error) -- config-compliance-engine always emits both keys (as possibly-
# empty lists, via its pydantic Evidence model's defaults), but a details blob from a different
# source/script is very unlikely to coincidentally use this exact pair of list-valued keys, so
# this is a reliable enough signal without hard-coding a dependency on that engine.
_EVIDENCE_LIST_KEYS = ('missing', 'unexpected')

_FAIL_LIKE_STATUSES = ('fail', 'error')


def _describe_entry(entry):
    """One evidence list entry -> a short, human-readable safe HTML fragment. Check primitives
    disagree on which keys they populate (a config `line` plus optional `line_number`, a bare
    `regex` pattern for a required-but-absent line, a `value` for exact_set-style checks, or the
    whole-block `exact_lines_expected`/`exact_lines_found` pair for banner-style comparisons) --
    this normalizes all of them into one consistent look."""
    if not isinstance(entry, dict):
        return str(entry)
    if 'line' in entry:
        if entry.get('line_number') is not None:
            return format_html(
                '<code>{}</code> <span class="text-muted small">(line {})</span>',
                entry['line'], entry['line_number'],
            )
        return format_html('<code>{}</code>', entry['line'])
    if 'exact_lines_expected' in entry:
        return format_html(
            'block content differs — expected <code>{}</code>, found <code>{}</code>',
            ' / '.join(entry.get('exact_lines_expected') or []),
            ' / '.join(entry.get('exact_lines_found') or []),
        )
    if 'value' in entry:
        return format_html('<code>{}</code>', entry['value'])
    if 'regex' in entry:
        return format_html('pattern <code>{}</code> not found', entry['regex'])
    return str(entry)


def _entry_list(entries, css_class, label):
    if not entries:
        return ''
    items = format_html_join('', '<li>{}</li>', ((_describe_entry(e),) for e in entries))
    return format_html(
        '<div class="mb-2"><strong class="{}">{}:</strong><ul class="mb-0 ps-3">{}</ul></div>',
        css_class, label, items,
    )


def _raw_details_block(details):
    return format_html(
        '<details class="mt-2"><summary class="text-muted small" style="cursor:pointer">'
        'Raw details</summary><pre class="mb-0 mt-1">{}</pre></details>',
        json.dumps(details, indent=2),
    )


@register.filter
def render_details(details, status=None):
    """Renders a ComplianceResult.details JSON blob for the in-app result page. `details` is
    genuinely arbitrary -- posted by whatever script/system produced the result, per this
    plugin's own design (see ComplianceResult.source) -- so this only special-cases the shape
    config-compliance-engine (and anything else using the same Evidence convention) posts:
    `evidence.missing`/`evidence.unexpected` broken out as their own labelled lists, plus
    `remediation` called out prominently for a failing/erroring result, instead of making a
    reviewer parse raw JSON to see which lines need adding vs. removing. Anything that doesn't
    match falls back to the plain pretty-printed JSON this page always showed."""
    if not details:
        return mark_safe('<span class="text-muted">&mdash;</span>')
    if not isinstance(details, dict):
        return str(details)

    evidence = details.get('evidence')
    if not isinstance(evidence, dict) or not any(k in evidence for k in _EVIDENCE_LIST_KEYS):
        return _raw_details_block(details)

    parts = []
    remediation = details.get('remediation')
    if remediation and status in _FAIL_LIKE_STATUSES:
        parts.append(format_html(
            '<div class="alert alert-info py-2 px-3 mb-2"><strong>Remediation</strong><br>{}</div>',
            remediation,
        ))
    if evidence.get('error'):
        parts.append(format_html('<div class="text-danger fw-bold mb-2">{}</div>', evidence['error']))
    parts.append(_entry_list(evidence.get('missing'), 'text-danger', 'Missing'))
    parts.append(_entry_list(evidence.get('unexpected'), 'text-warning', 'Unexpected'))
    parts.append(_raw_details_block(details))
    return mark_safe(''.join(parts))
