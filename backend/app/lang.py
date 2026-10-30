"""The app's languages: English, Norwegian (bokmål) and Italian.

Texts that live in the backend (e-mails, permission names, role names, templates, the
calendar feed) come in all three. `pick(lang, en, no, it)` chooses one; unknown → English.
"""
LANGS = ("en", "no", "it")
INDEX = {"en": 0, "no": 1, "it": 2}


def norm(lang: str | None) -> str:
    return lang if lang in LANGS else "en"


def pick(lang: str | None, en, no, it):
    return (en, no, it)[INDEX[norm(lang)]]


def default_group_name(lang: str | None) -> str:
    return pick(lang, "Family", "Familien", "Famiglia")
