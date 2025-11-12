import importlib


def test_lib_and_textutils_importable():
    # Ensure the package and the text_utils module are importable
    lib = importlib.import_module('lib')
    text_utils = importlib.import_module('lib.text_utils')
    assert hasattr(lib, 'text_utils')
    assert hasattr(text_utils, 'clean_csv_input')


def test_clean_csv_input_and_profanity():
    from lib.text_utils import clean_csv_input, normalize_profanity

    # Artist cleaning: should trim and collapse spaces but preserve words
    assert clean_csv_input('  Son  Lux  ', is_artist=True) == 'Son Lux'

    # Profanity normalization should return canonical lowercase replacement
    assert normalize_profanity('F*ck') == 'fuck'
    assert normalize_profanity('Sh*t') == 'shit'

    # Album cleaning: should remove suffixes like "- EP" and normalize profanity
    cleaned = clean_csv_input('F*ck Love  - EP')
    assert 'EP' not in cleaned
    assert 'fuck' in cleaned.lower()
