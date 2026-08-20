import warnings

import pytest

from pythes import PyThes, PyThesIndexWarning


THESAURUS_MATRIX = (
    ("dict-en", "th_en_US_v2.dat"),
    ("dict-es", "th_es_v2.dat"),
    ("dict-sl", "th_sl_SI_v2.dat"),
    ("dict-ru", "th_ru_RU_M_aot_and_v2.dat"),
    ("dict-pl", "th_pl_PL_v2.dat"),
)


def _assert_first_entry_can_be_read(path):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", PyThesIndexWarning)
        thesaurus = PyThes(path)
    first_word = next(iter(thesaurus.index))
    assert thesaurus.lookup(first_word) is not None
    return caught


@pytest.mark.corpus
@pytest.mark.parametrize("folder,filename", THESAURUS_MATRIX)
def test_real_thesaurus_encoding_and_offset(dictionary_corpus, folder, filename):
    _assert_first_entry_can_be_read(dictionary_corpus / folder / filename)


@pytest.mark.corpus
@pytest.mark.full_corpus
def test_every_real_thesaurus_can_read_an_indexed_entry(dictionary_corpus):
    files = sorted(dictionary_corpus.rglob("th_*.dat"))
    assert files, "the configured corpus contains no thesaurus data files"

    failures = []
    for path in files:
        try:
            _assert_first_entry_can_be_read(path)
        except Exception as error:  # report the entire corpus in one execution
            failures.append(f"{path}: {type(error).__name__}: {error}")

    assert not failures, "\n".join(failures)


@pytest.mark.corpus
@pytest.mark.full_corpus
def test_every_real_thesaurus_can_regenerate_a_valid_index(
    dictionary_corpus, tmp_path
):
    files = sorted(dictionary_corpus.rglob("th_*.dat"))
    assert files, "the configured corpus contains no thesaurus data files"

    failures = []
    for path in files:
        destination = tmp_path / f"{path.parent.name}-{path.stem}.idx"
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", PyThesIndexWarning)
                thesaurus = PyThes(path)
                generated_path = thesaurus.regenerate_index(destination)
            assert generated_path == destination
            assert generated_path.is_file()
            assert thesaurus.lookup(next(iter(thesaurus.index))) is not None
        except Exception as error:  # report the entire corpus in one execution
            failures.append(f"{path}: {type(error).__name__}: {error}")

    assert not failures, "\n".join(failures)
