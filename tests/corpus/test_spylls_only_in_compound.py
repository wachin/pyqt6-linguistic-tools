import gc
import re

import pytest

from spylls.hunspell import Dictionary


ONLY_IN_COMPOUND_DIRECTIVE = re.compile(rb"(?m)^\s*ONLYINCOMPOUND\b")


@pytest.mark.corpus
@pytest.mark.full_corpus
def test_every_only_in_compound_dictionary_loads_and_accepts_a_stem(
    dictionary_corpus,
):
    affix_files = sorted(
        path
        for path in dictionary_corpus.rglob("*.aff")
        if ONLY_IN_COMPOUND_DIRECTIVE.search(path.read_bytes())
    )
    assert len(affix_files) == 20

    failures = []
    for affix_path in affix_files:
        dictionary = Dictionary.from_files(str(affix_path.with_suffix("")))
        accepted = any(
            not word.stem.startswith("#") and dictionary.lookup(word.stem)
            for word in dictionary.dic.words[:500]
        )
        if not dictionary.aff.ONLYINCOMPOUND or not accepted:
            failures.append(str(affix_path.relative_to(dictionary_corpus)))
        del dictionary
        gc.collect()

    assert not failures, f"ONLYINCOMPOUND dictionaries failed validation: {failures}"
