import gc

import pytest

from spylls.hunspell import Dictionary


COMPOUND_PATTERN_DICTIONARIES = (
    ("dict-hu", "hu_HU"),
    ("dict-nl", "nl_NL"),
)


@pytest.mark.corpus
@pytest.mark.full_corpus
@pytest.mark.parametrize("folder,name", COMPOUND_PATTERN_DICTIONARIES)
def test_real_compound_pattern_dictionary_loads_and_accepts_a_stem(
    dictionary_corpus, folder, name
):
    dictionary = Dictionary.from_files(str(dictionary_corpus / folder / name))

    assert dictionary.aff.CHECKCOMPOUNDPATTERN
    assert all(
        pattern.replacement is None
        for pattern in dictionary.aff.CHECKCOMPOUNDPATTERN
    )
    assert any(
        not word.stem.startswith("#") and dictionary.lookup(word.stem)
        for word in dictionary.dic.words[:500]
    )

    del dictionary
    gc.collect()
