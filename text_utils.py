"""
Compatibility shim: top-level `text_utils` module that re-exports symbols
from `lib.text_utils`.

This preserves older `from text_utils import ...` imports while the
real implementation lives in `lib/text_utils.py` (packaged as `lib`).
"""

from importlib import import_module

_real = import_module("lib.text_utils")

# Re-export common functions and names
__all__ = [
    "normalize_artist_name",
    "normalize_profanity",
    "strip_album_suffixes",
    "get_album_title_variations",
    "get_edition_variants",
    "normalize_album_title_for_matching",
    "clean_csv_input",
]

for _name in __all__:
    globals()[_name] = getattr(_real, _name)

# Also export the module for callers that expect a module object
__real_module__ = _real
