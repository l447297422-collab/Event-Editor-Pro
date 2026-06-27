import json
import os
import typing

_translations: typing.Dict[str, typing.Any] = {}
_current_language = 'en_US'
_language_changed_callbacks: typing.List[typing.Callable[[str], None]] = []

def get_language() -> str:
    return _current_language

def language_changed_signal():
    """Returns a callback handler that can be used to register language change listeners."""
    return _LanguageChangeHandler()

class _LanguageChangeHandler:
    def connect(self, callback: typing.Callable[[str], None]) -> None:
        _language_changed_callbacks.append(callback)

    def disconnect(self, callback: typing.Callable[[str], None]) -> None:
        if callback in _language_changed_callbacks:
            _language_changed_callbacks.remove(callback)

def tr(key: str, default: str = '') -> str:
    """Translate a nested key like 'menu.file' to its value."""
    keys = key.split('.')
    value = _translations
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return default if default else key
    return str(value)

def _load_language_file(lang_code: str) -> bool:
    global _translations
    lang_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'Language')
    file_path = os.path.join(lang_dir, f'{lang_code}.json')

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            _translations = json.load(f)
        return True
    except Exception:
        _translations = {}
        return False

def set_language(lang_code: str) -> bool:
    global _current_language
    if _load_language_file(lang_code):
        _current_language = lang_code
        for callback in _language_changed_callbacks:
            try:
                callback(lang_code)
            except Exception:
                pass
        return True
    return False

def load_from_settings() -> str:
    try:
        import PyQt5.QtCore as qc # type: ignore
        settings = qc.QSettings()
        lang_code = settings.value('language', 'en_US', type=str)
    except:
        lang_code = 'en_US'

    if not set_language(lang_code):
        set_language('en_US')
    return _current_language

def save_to_settings() -> None:
    try:
        import PyQt5.QtCore as qc # type: ignore
        settings = qc.QSettings()
        settings.setValue('language', _current_language)
    except:
        pass