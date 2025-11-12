"""
DEPRECATED: the top-level `text_utils` shim was removed in favor of
`lib.text_utils`. Import from `lib.text_utils` instead.

This module now raises an ImportError to avoid silently masking import
errors and to encourage dependents to update their imports.
"""

raise ImportError(
    "The top-level `text_utils` shim was removed. Use `from lib.text_utils import ...` "
    "or importlib.import_module('lib.text_utils') instead."
)
