"""Message templates: English and Hindi defaults, per-practice overrides, safe rendering.

Safety model for practice-edited templates (they are untrusted input):
1. Parsed first; an allow-list walk rejects calls, macros, imports, arithmetic and
   anything beyond text, variables, if/for, comparisons and a short filter list.
   `for` nesting is capped at 2 (variables are small lists).
2. Rendered in Jinja2's ImmutableSandboxedEnvironment with StrictUndefined, globals
   removed, filters restricted, and attribute access to callables denied.
3. Length caps on source and output.
The advisory line and the stop instruction are not part of the editable text: they are
appended by `render_message`, so no template can drop them.
"""

from __future__ import annotations

from dataclasses import dataclass

from jinja2 import StrictUndefined, TemplateSyntaxError, nodes
from jinja2.exceptions import SecurityError
from jinja2.sandbox import ImmutableSandboxedEnvironment

MAX_SOURCE = 3000
MAX_OUTPUT = 5000
MAX_FOR_DEPTH = 2
ALLOWED_FILTERS = ("e", "escape", "default", "d", "length", "count", "first", "last", "join",
                   "lower", "upper", "title", "capitalize", "trim", "int", "string")

ALLOWED_VARIABLES = {
    "name": "Client first name",
    "practice": "Practice name",
    "plan_title": "Remedy plan title",
    "day": "Day number in the cycle",
    "total": "Cycle length in days",
    "days_left": "Days remaining in the cycle",
    "items": "List of remedy item titles",
    "link": "One-tap check-in link (remedy reminders)",
    "policy_note": "Sentence describing what the missed-day policy did",
    "followup_date": "Follow-up date",
    "missed_date": "The missed date",
}

SAMPLE_CONTEXT = {
    "name": "Asha", "practice": "Sample Practice", "plan_title": "43 day Saturn remedy",
    "day": 12, "total": 43, "days_left": 3, "items": ["Light a mustard oil lamp",
                                                     "Feed a crow"],
    "link": "https://example.test/v1/public/checkin/SAMPLE", "policy_note": "",
    "followup_date": "14 Nov 2026", "missed_date": "13 Nov 2026",
}

_DENY = tuple(getattr(nodes, n) for n in (
    "Call", "Macro", "CallBlock", "Import", "FromImport", "Include", "Extends", "Block",
    "Scope", "FilterBlock", "Mul", "Pow", "Mod", "Div", "FloorDiv", "Assign", "AssignBlock",
    "With", "Getattr", "ExprStmt") if hasattr(nodes, n))


class TemplateError(ValueError):
    """A template is invalid or unsafe. The message is safe to show the author."""


class _Env(ImmutableSandboxedEnvironment):
    def is_safe_attribute(self, obj, attr, value):  # no method calls via attribute access
        return not callable(value) and super().is_safe_attribute(obj, attr, value)


def _env() -> _Env:
    env = _Env(autoescape=False, undefined=StrictUndefined, trim_blocks=True,
               lstrip_blocks=True, keep_trailing_newline=False)
    env.globals = {}
    env.filters = {k: v for k, v in env.filters.items() if k in ALLOWED_FILTERS}
    env.tests = {}
    return env


_ENV = _env()


def _check_tree(tree: nodes.Template) -> None:
    def walk(node: nodes.Node, depth: int) -> None:
        if isinstance(node, _DENY):
            raise TemplateError(f"'{type(node).__name__}' is not allowed in templates")
        if isinstance(node, nodes.Name) and node.name.startswith("_"):
            raise TemplateError("names starting with an underscore are not allowed")
        if isinstance(node, nodes.For):
            depth += 1
            if depth > MAX_FOR_DEPTH:
                raise TemplateError(f"loops may nest at most {MAX_FOR_DEPTH} deep")
        for child in node.iter_child_nodes():
            walk(child, depth)

    walk(tree, 0)


def compile_check(source: str) -> None:
    """Raise TemplateError unless `source` is a safe, valid template."""
    if len(source) > MAX_SOURCE:
        raise TemplateError(f"template is longer than {MAX_SOURCE} characters")
    try:
        _check_tree(_ENV.parse(source))
    except TemplateSyntaxError as exc:
        raise TemplateError(f"syntax error on line {exc.lineno}: {exc.message}") from None


def render_text(source: str, context: dict) -> str:
    compile_check(source)
    try:
        out = _ENV.from_string(source).render(**context)
    except TemplateError:
        raise
    except SecurityError as exc:
        raise TemplateError(f"not allowed: {exc}") from None
    except Exception as exc:
        raise TemplateError(f"could not render: {type(exc).__name__}: {exc}") from None
    if len(out) > MAX_OUTPUT:
        raise TemplateError("rendered message is too long")
    return out


def validate_template(subject: str | None, body: str) -> None:
    """Dry-run with the sample context; raises TemplateError."""
    if subject is not None:
        if "\n" in subject or "\r" in subject:
            raise TemplateError("subject must be one line")
        render_text(subject, SAMPLE_CONTEXT)
    if not body.strip():
        raise TemplateError("body is empty")
    render_text(body, SAMPLE_CONTEXT)


# ------------------------------------------------------------------ defaults
_FOOTER = {
    "en": ("This is traditional guidance, not medical, legal or financial advice. For those "
           "matters please consult a qualified professional.\n"
           "To stop these reminders, open {stop_url} (or reply STOP)."),
    "hi": ("यह पारंपरिक मार्गदर्शन है, चिकित्सा, कानूनी या वित्तीय सलाह नहीं। ऐसे विषयों के "
           "लिए कृपया किसी योग्य विशेषज्ञ से परामर्श करें।\n"
           "ये संदेश बंद करने के लिए {stop_url} खोलें (या STOP लिखकर उत्तर दें)।"),
}

_ITEMS = "{% for i in items %}- {{ i }}\n{% endfor %}"

DEFAULTS: dict[tuple[str, str], tuple[str, str]] = {
    ("remedy_due", "en"): (
        "Today's remedy: day {{ day }} of {{ total }}",
        "Namaste {{ name }},\n\nA gentle reminder for day {{ day }} of {{ total }} of "
        "{{ plan_title }}:\n" + _ITEMS + "\nWhen you have finished, tap here to mark today as "
        "done:\n{{ link }}\n\nWith care,\n{{ practice }}"),
    ("remedy_due", "hi"): (
        "आज का उपाय: {{ total }} में से दिन {{ day }}",
        "नमस्ते {{ name }},\n\n{{ plan_title }} के {{ total }} में से दिन {{ day }} की "
        "विनम्र याद:\n" + _ITEMS + "\nपूरा करने के बाद आज का दिन चिह्नित करने के लिए यहाँ "
        "दबाएँ:\n{{ link }}\n\nसादर,\n{{ practice }}"),
    ("remedy_missed", "en"): (
        "We missed you yesterday",
        "Namaste {{ name }},\n\nYesterday ({{ missed_date }}) was not marked for "
        "{{ plan_title }}. {{ policy_note }}\n\nIf you did it, or when you do today's, tap "
        "here:\n{{ link }}\n\nWith care,\n{{ practice }}"),
    ("remedy_missed", "hi"): (
        "कल का दिन छूट गया",
        "नमस्ते {{ name }},\n\n{{ plan_title }} में कल ({{ missed_date }}) का दिन चिह्नित नहीं "
        "हुआ। {{ policy_note }}\n\nयदि आपने किया था, या आज का कर लें, तो यहाँ दबाएँ:\n"
        "{{ link }}\n\nसादर,\n{{ practice }}"),
    ("ending_soon", "en"): (
        "{{ days_left }} days left in your remedy",
        "Namaste {{ name }},\n\nYou are on day {{ day }} of {{ total }} of {{ plan_title }}, "
        "close to the end. Keep going, {{ days_left }} days remain.\n\nWith care,\n"
        "{{ practice }}"),
    ("ending_soon", "hi"): (
        "आपके उपाय के {{ days_left }} दिन शेष",
        "नमस्ते {{ name }},\n\nआप {{ plan_title }} के {{ total }} में से दिन {{ day }} पर हैं, "
        "समाप्ति पास है। बस {{ days_left }} दिन बाकी हैं।\n\nसादर,\n{{ practice }}"),
    ("plan_complete", "en"): (
        "You have completed {{ plan_title }}",
        "Namaste {{ name }},\n\nThe {{ total }} day cycle of {{ plan_title }} has come to its "
        "end. Thank you for your steadiness. {{ practice }} will be in touch about what "
        "comes next.\n\nWith care,\n{{ practice }}"),
    ("plan_complete", "hi"): (
        "आपने {{ plan_title }} पूरा किया",
        "नमस्ते {{ name }},\n\n{{ plan_title }} के {{ total }} दिनों का चक्र पूरा हुआ। आपकी "
        "निरंतरता के लिए धन्यवाद। आगे की बात के लिए {{ practice }} आपसे संपर्क करेगा।\n\n"
        "सादर,\n{{ practice }}"),
    ("followup_due", "en"): (
        "Your follow-up on {{ followup_date }}",
        "Namaste {{ name }},\n\nA reminder that your follow-up with {{ practice }} is on "
        "{{ followup_date }}. If the time does not suit you, please tell the practice "
        "directly.\n\nWith care,\n{{ practice }}"),
    ("followup_due", "hi"): (
        "{{ followup_date }} को आपका फ़ॉलो-अप",
        "नमस्ते {{ name }},\n\n{{ practice }} के साथ आपका फ़ॉलो-अप {{ followup_date }} को है। "
        "समय अनुकूल न हो तो कृपया सीधे प्रैक्टिस को बताएँ।\n\nसादर,\n{{ practice }}"),
}

POLICY_NOTES = {
    "restart": {
        "en": "As agreed, the cycle begins again from today, day 1 of {total}.",
        "hi": "तय व्यवस्था के अनुसार चक्र आज से फिर शुरू होता है, {total} में से दिन 1।"},
    "extend": {
        "en": "As agreed, your cycle is extended by one day and now runs {total} days.",
        "hi": "तय व्यवस्था के अनुसार आपका चक्र एक दिन बढ़ा दिया गया है, अब कुल {total} दिन।"},
    "warn": {
        "en": "Please try to keep each day in sequence.",
        "hi": "कृपया हर दिन क्रम से करने का प्रयास करें।"},
}


def policy_note(action: str, language: str, total: int) -> str:
    return POLICY_NOTES.get(action, POLICY_NOTES["warn"])[language].format(total=total)


@dataclass(frozen=True)
class Rendered:
    subject: str | None
    body: str
    source: str  # "default" or "practice"


def default_template(kind: str, language: str) -> tuple[str, str]:
    return DEFAULTS.get((kind, language)) or DEFAULTS[(kind, "en")]


def render_message(kind: str, channel: str, language: str, context: dict, stop_url: str,
                   overrides: dict[tuple[str, str, str], tuple[str | None, str]] | None = None
                   ) -> Rendered:
    """Pick the practice override (kind, channel, lang) then (kind, '*', lang) then the
    default, render it, and append the advisory and stop footer."""
    overrides = overrides or {}
    chosen = overrides.get((kind, channel, language)) or overrides.get((kind, "*", language))
    source = "practice"
    if chosen is None:
        chosen, source = default_template(kind, language), "default"
    subject_src, body_src = chosen
    ctx = {**context, "stop_url": stop_url}
    body = render_text(body_src, ctx).rstrip()
    footer = _FOOTER.get(language, _FOOTER["en"]).format(stop_url=stop_url)
    subject = render_text(subject_src, ctx).strip() if subject_src and channel == "email" else None
    return Rendered(subject, f"{body}\n\n{footer}", source)
