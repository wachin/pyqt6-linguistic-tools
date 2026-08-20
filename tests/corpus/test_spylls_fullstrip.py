import gc

import pytest

from spylls.hunspell import Dictionary


FULLSTRIP_DICTIONARIES = (
    ("dict-ca", "ca"),
    ("dict-ca", "ca-valencia"),
    ("dict-fr", "fr"),
    ("dict-hr", "hr_HR"),
    ("dict-is", "is"),
    ("dict-lv", "lv_LV"),
    ("dict-mn", "mn_MN"),
    ("dict-sv", "sv_FI"),
    ("dict-sv", "sv_SE"),
)


@pytest.mark.corpus
@pytest.mark.full_corpus
@pytest.mark.parametrize("folder,name", FULLSTRIP_DICTIONARIES)
def test_real_fullstrip_dictionary_loads_and_accepts_a_stem(
    dictionary_corpus, folder, name
):
    dictionary = Dictionary.from_files(str(dictionary_corpus / folder / name))

    assert dictionary.aff.FULLSTRIP
    assert any(
        not word.stem.startswith("#") and dictionary.lookup(word.stem)
        for word in dictionary.dic.words[:500]
    )

    del dictionary
    gc.collect()
