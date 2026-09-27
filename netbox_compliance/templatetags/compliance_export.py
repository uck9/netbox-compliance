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

# NetBox ChoiceSet color-name -> hex. The device compliance export document is a
# standalone file (viewable inline, or downloaded and opened offline/emailed), so it
# can't rely on NetBox's own compiled CSS (the `text-bg-<color>` classes the in-app
# {% badge %} tag emits only resolve when NetBox's stylesheet is loaded) -- every
# color needs to be a real inline value instead.
_COLOR_HEX = {
    'green': '#2f9e44',
    'red': '#e03131',
    'dark-red': '#862e2e',
    'orange': '#e8590c',
    'amber': '#f08c00',
    'yellow': '#f2c94c',
    'grey': '#868e96',
    'gray': '#868e96',
    'blue': '#1971c2',
    'cyan': '#0c8599',
    'purple': '#7048e8',
}
_DEFAULT_HEX = '#868e96'


@register.filter
def color_hex(color_name):
    return _COLOR_HEX.get(color_name, _DEFAULT_HEX)


def _describe_evidence_entry(entry):
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
                '<code>{}</code> <span style="color:{};font-size:0.85em;">(line {})</span>',
                entry['line'], _DEFAULT_HEX, entry['line_number'],
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


def _evidence_entry_list(entries, color, label):
    if not entries:
        return ''
    items = format_html_join('', '<li>{}</li>', ((_describe_evidence_entry(e),) for e in entries))
    return format_html(
        '<div style="margin-bottom:0.35rem;"><strong style="color:{};">{}:</strong>'
        '<ul style="margin:0.15rem 0 0 1.1rem;padding:0;">{}</ul></div>',
        color, label, items,
    )


def _raw_details_block(details):
    """Same collapsible fallback as the in-app result page's `render_details` filter
    (compliance_details.py) -- inline-styled instead of Bootstrap classes, same constraint as
    the rest of this document, but otherwise identical: nothing from `details` is ever lost
    just because it was rendered as a friendly summary above."""
    return format_html(
        '<details style="margin-top:0.3rem;"><summary style="cursor:pointer;color:{};'
        'font-size:0.85em;">Raw details</summary>'
        '<pre style="margin:0.25rem 0 0;white-space:pre-wrap;font-size:0.85em;">{}</pre></details>',
        _DEFAULT_HEX, json.dumps(details, indent=2),
    )


def _format_evidence_details(details, evidence, status):
    """The evidence-shaped rendering: missing/unexpected called out as their own labelled
    lists (red for what should be there and isn't, amber for what's there and shouldn't be),
    remediation for a failing/erroring result, and the full raw JSON collapsed behind a
    <details> toggle (same as the in-app result page) so nothing is lost -- all inline-styled,
    no CSS classes, so it still renders correctly once downloaded/emailed/opened offline, same
    constraint as the rest of this document."""
    parts = []
    remediation = details.get('remediation')
    if remediation and status in _FAIL_LIKE_STATUSES:
        parts.append(format_html(
            '<div style="background:#e7f3ff;border-left:3px solid {blue};padding:0.3rem 0.5rem;'
            'margin-bottom:0.35rem;"><strong style="color:{blue};">Remediation:</strong> {rem}</div>',
            blue=_COLOR_HEX['blue'], rem=remediation,
        ))
    if evidence.get('error'):
        parts.append(format_html(
            '<div style="color:{};font-weight:600;margin-bottom:0.35rem;">{}</div>',
            _COLOR_HEX['red'], evidence['error'],
        ))
    parts.append(_evidence_entry_list(evidence.get('missing'), _COLOR_HEX['red'], 'Missing'))
    parts.append(_evidence_entry_list(evidence.get('unexpected'), _COLOR_HEX['amber'], 'Unexpected'))
    parts.append(_raw_details_block(details))
    return mark_safe(''.join(parts))


@register.filter
def format_details(details, status=None):
    """Render a ComplianceResult.details JSON blob. If it's shaped like
    config-compliance-engine's Evidence (missing/unexpected lists, a remediation string),
    those are broken out as labelled callouts instead of an opaque blob -- `details` is
    otherwise genuinely arbitrary (posted by whatever script/system produced the result, per
    this plugin's own design), so anything not matching that shape falls back to the plain
    key: value list this filter always rendered, still passed through format_html's normal
    escaping so arbitrary externally-posted string content can't break out of the document."""
    if not details:
        return ''
    if not isinstance(details, dict):
        return str(details)
    evidence = details.get('evidence')
    if isinstance(evidence, dict) and any(k in evidence for k in _EVIDENCE_LIST_KEYS):
        return _format_evidence_details(details, evidence, status)
    return format_html_join(
        mark_safe('<br>'),
        '<strong>{}:</strong> {}',
        ((key, value) for key, value in details.items()),
    )
