"""Small shared presentation catalog. Source content and canonical objects stay exact.

Turkish-mode invariant: no English structural/chrome text in supported public
renders, except exact source content, identifiers, proper names and technical
diagnostics. Call text on owned templates BEFORE inserting source values.
"""
from functools import lru_cache
from functools import wraps
from contextvars import ContextVar
import builtins
import sys
from pathlib import Path
import json
import re

_LANGUAGE = ContextVar("presentation_language", default="en")


def current():
    return _LANGUAGE.get()


def presentation(function):
    """Optional language argument is presentation-only, inherited by nested renders."""
    @wraps(function)
    def render(*args, output_language=None, **kwargs):
        language = output_language or current()
        if language not in {"en", "tr"}:
            raise ValueError("invalid_output_language")
        token = _LANGUAGE.set(language)
        try:
            return function(*args, **kwargs)
        finally:
            _LANGUAGE.reset(token)
    return render


def run_presentation(function):
    """Carry an existing run option across async presentation work, without routing changes."""
    @wraps(function)
    async def render(orch, *args, **kwargs):
        import run_options
        token = _LANGUAGE.set(run_options.for_context(orch.run_context).output_language)
        try:
            return await function(orch, *args, **kwargs)
        finally:
            _LANGUAGE.reset(token)
    return render


def saved_presentation(function):
    @wraps(function)
    def render(deliv_dir, *args, **kwargs):
        import run_options
        language = kwargs.pop("output_language", None) or run_options.saved(Path(deliv_dir).parent).output_language
        return presentation(function)(deliv_dir, *args, output_language=language, **kwargs)
    return render


def cli_presentation(function):
    """Select display language before parsing; the real parser still validates argv."""
    @wraps(function)
    def render(argv=None):
        values = list(sys.argv[1:] if argv is None else argv)
        language = "en"
        for i, value in enumerate(values):
            if value.startswith("--output-language="):
                language = value.split("=", 1)[1]
            elif value == "--output-language" and i + 1 < len(values):
                language = values[i + 1]
        token = _LANGUAGE.set("tr" if language == "tr" else "en")
        try:
            return function(argv)
        finally:
            _LANGUAGE.reset(token)
    return render


def operator_print(*args, **kwargs):
    # Only known human-facing templates are projected. Structured progress,
    # machine logs and third-party diagnostics remain exact.
    return builtins.print(*(message(a) if isinstance(a, str) else a for a in args), **kwargs)


def operator_input(prompt=""):
    return builtins.input(message(prompt))


def localize_parser(parser):
    """Localize argparse's display copy, never its options, defaults or choices."""
    if current() != "tr":
        return parser
    parser.description = text(parser.description)
    for group in parser._action_groups:
        group.title = text(group.title)
    for action in parser._actions:
        if action.help:
            action.help = text(action.help)
    output = parser._print_message
    def localized_output(value, file=None):
        if value:
            value = value.replace("usage: ", text("usage: "), 1).replace(": error: ", ": hata: ", 1)
        return output(value, file)
    parser._print_message = localized_output
    error = parser.error
    parser.error = lambda value: error(message(value))
    return parser


@lru_cache(maxsize=1)
def catalog():
    source = (Path(__file__).parent / "ui/localization_catalog.js").read_text(encoding="utf-8")
    return json.loads(source.split("var SHIMMER_TR = ", 1)[1].rstrip().removesuffix(";"))


def text(original, language=None, **values):
    language = language or current()
    template = catalog().get(original, original) if language == "tr" else original
    return template.format(**values) if values else template


def label(value, language=None):
    language = language or current()
    return catalog().get("_values", {}).get(value, value) if language == "tr" else value


def message(original, language=None):
    language = language or current()
    if language != "tr" or not isinstance(original, str):
        return original
    if original in catalog():
        return catalog()[original]
    for row in catalog().get("_messages", []):
        match = re.fullmatch(row["pattern"], original, re.DOTALL)
        if match:
            return re.sub(r"\{(\d+)\}", lambda m: match[int(m[1]) + 1], row["translation"])
    return original


def console_document(path):
    """Inline local assets for /console; no additional API routes or requests."""
    path = Path(path)
    result = path.read_text(encoding="utf-8")
    for name in ("localization_catalog.js", "localization.js"):
        result = result.replace(f'<script src="{name}"></script>',
                                "<script>" + (path.parent / name).read_text(encoding="utf-8") + "</script>")
    return result
