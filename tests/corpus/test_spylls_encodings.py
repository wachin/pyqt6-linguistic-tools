import gc

import pytest

from spylls.hunspell import Dictionary


SPELLING_MATRIX = (
    ("UTF-8", "dict-es", "es_EC"),
    ("ISO8859-1", "dict-an", "an_ES"),
    ("ISO8859-2", "dict-sl", "sl_SI"),
    ("ISO8859-7", "dict-el", "el_GR"),
    ("ISO8859-13", "dict-lt", "lt"),
    ("ISO8859-15", "dict-et", "et_EE"),
)


@pytest.mark.corpus
@pytest.mark.parametrize("declared_encoding,folder,name", SPELLING_MATRIX)
def test_real_dictionary_encoding_and_lookup(
    dictionary_corpus, declared_encoding, folder, name
):
    dictionary_root = dictionary_corpus / folder / name
    dictionary = Dictionary.from_files(str(dictionary_root))

    assert dictionary.aff.SET.upper() == declared_encoding
    assert any(dictionary.lookup(word.stem) for word in dictionary.dic.words[:200])

    del dictionary
    gc.collect()
