from __future__ import annotations

import hashlib
import io
from pathlib import Path
import tarfile
from unittest.mock import patch

import pytest

from pyqt6_linguistic_tools import (
    DictionaryCatalogEntry,
    DictionaryDownloadCancelled,
    DictionaryDownloadError,
    ManagedDictionaryProvider,
    download_dictionary,
    install_dictionary_archive,
)


def _entry(
    archive: Path, *, code: str = "fr", **overrides: object
) -> DictionaryCatalogEntry:
    payload = archive.read_bytes()
    fields = {
        "code": code,
        "name": "French",
        "url": f"https://example.test/dict-{code}.tar.gz",
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "spelling": True,
        "thesaurus": False,
    }
    fields.update(overrides)
    return DictionaryCatalogEntry(**fields)  # type: ignore[arg-type]


def _bundle_archive(tmp_path: Path, *, code: str = "fr", extra: bool = True) -> Path:
    bundle = tmp_path / "source" / f"dict-{code}"
    bundle.mkdir(parents=True)
    (bundle / f"{code}_FR.aff").write_text("SET UTF-8\n", encoding="utf-8")
    (bundle / f"{code}_FR.dic").write_text("1\nword\n", encoding="utf-8")
    if extra:
        (bundle / f"hyph_{code}_FR.dic").write_text("1\nhy-phen\n", encoding="utf-8")
        (bundle / "README.txt").write_text("not a dictionary\n", encoding="utf-8")
    archive = tmp_path / f"dict-{code}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(bundle, arcname=bundle.name)
    return archive


def _manual_archive(tmp_path: Path, members: list[tuple[str, bytes]]) -> Path:
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        for name, payload in members:
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
    return archive


def test_installs_verified_archive_and_skips_metadata(tmp_path: Path):
    archive = _bundle_archive(tmp_path)
    provider = ManagedDictionaryProvider(tmp_path / "managed")

    result = install_dictionary_archive(archive, _entry(archive), provider)

    assert result.destination == provider.root / "dict-fr"
    assert (result.destination / "fr_FR.aff").is_file()
    assert (result.destination / "fr_FR.dic").is_file()
    assert not (result.destination / "README.txt").exists()
    assert not (result.destination / "hyph_fr_FR.dic").exists()
    discovered = provider.discover()
    assert any(candidate.locale == "fr_FR" for candidate in discovered)


def test_skips_a_malformed_regional_variant_but_keeps_valid_ones(tmp_path: Path):
    bundle = tmp_path / "source" / "dict-fr"
    bundle.mkdir(parents=True)
    (bundle / "fr_FR.aff").write_text("SET UTF-8\n", encoding="utf-8")
    (bundle / "fr_FR.dic").write_text("1\nword\n", encoding="utf-8")
    (bundle / "fr_XX.aff").write_text("SET NOT-A-CODEC\n", encoding="utf-8")
    (bundle / "fr_XX.dic").write_text("1\nword\n", encoding="utf-8")
    archive = tmp_path / "dict-fr.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(bundle, arcname=bundle.name)
    provider = ManagedDictionaryProvider(tmp_path / "managed")

    result = install_dictionary_archive(archive, _entry(archive), provider)

    assert result.destination == provider.root / "dict-fr"
    assert (result.destination / "fr_FR.aff").is_file()
    assert not (result.destination / "fr_XX.aff").exists()


def test_rejects_a_missing_checksum(tmp_path: Path):
    archive = _bundle_archive(tmp_path)
    entry = _entry(archive, sha256=None)

    with pytest.raises(DictionaryDownloadError, match="no SHA-256"):
        install_dictionary_archive(
            archive, entry, ManagedDictionaryProvider(tmp_path / "managed")
        )


def test_rejects_a_size_mismatch(tmp_path: Path):
    archive = _bundle_archive(tmp_path)
    entry = _entry(archive, size=archive.stat().st_size + 1)

    with pytest.raises(DictionaryDownloadError, match="size mismatch"):
        install_dictionary_archive(
            archive, entry, ManagedDictionaryProvider(tmp_path / "managed")
        )


def test_rejects_a_checksum_mismatch(tmp_path: Path):
    archive = _bundle_archive(tmp_path)
    entry = _entry(archive, sha256="a" * 64)

    with pytest.raises(DictionaryDownloadError, match="SHA-256 mismatch"):
        install_dictionary_archive(
            archive, entry, ManagedDictionaryProvider(tmp_path / "managed")
        )


def test_rejects_path_traversal_and_leaves_no_bundle(tmp_path: Path):
    archive = _manual_archive(
        tmp_path,
        [("dict-fr/../evil.aff", b"SET UTF-8\n")],
    )
    provider = ManagedDictionaryProvider(tmp_path / "managed")

    with pytest.raises(DictionaryDownloadError, match="unsafe path"):
        install_dictionary_archive(archive, _entry(archive), provider)

    assert not (provider.root / "dict-fr").exists()
    assert not (tmp_path / "evil.aff").exists()


def test_rejects_symlinks(tmp_path: Path):
    archive = tmp_path / "symlink.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        info = tarfile.TarInfo("dict-fr/link.aff")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        tar.addfile(info)

    with pytest.raises(DictionaryDownloadError, match="unsupported entry"):
        install_dictionary_archive(
            archive,
            _entry(archive),
            ManagedDictionaryProvider(tmp_path / "managed"),
        )


class _FakeResponse:
    def __init__(
        self, payload: bytes, *, url: str = "https://example.test/dict-fr.tar.gz"
    ):
        self._payload = payload
        self._offset = 0
        self._url = url
        self.headers = {"Content-Length": str(len(payload))}

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._payload) - self._offset
        chunk = self._payload[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk

    def geturl(self) -> str:
        return self._url

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_download_streams_verifies_and_reports_progress(tmp_path: Path):
    archive = _bundle_archive(tmp_path)
    entry = _entry(archive)
    provider = ManagedDictionaryProvider(tmp_path / "managed")
    progress: list[tuple[int, int]] = []
    response = _FakeResponse(archive.read_bytes())

    with patch("pyqt6_linguistic_tools.download.urlopen", return_value=response):
        result = download_dictionary(
            entry,
            provider,
            progress=lambda done, total: progress.append((done, total)),
        )

    assert result.destination == provider.root / "dict-fr"
    assert progress
    assert progress[-1] == (entry.size, entry.size)


def test_cancellation_raises_and_does_not_publish(tmp_path: Path):
    archive = _bundle_archive(tmp_path)
    provider = ManagedDictionaryProvider(tmp_path / "managed")
    calls = 0

    def should_cancel() -> bool:
        nonlocal calls
        calls += 1
        return calls > 1

    with patch(
        "pyqt6_linguistic_tools.download.urlopen",
        return_value=_FakeResponse(archive.read_bytes()),
    ):
        with pytest.raises(DictionaryDownloadCancelled):
            download_dictionary(
                _entry(archive),
                provider,
                should_cancel=should_cancel,
            )

    assert not (provider.root / "dict-fr").exists()


def test_rejects_a_non_https_download(tmp_path: Path):
    archive = _bundle_archive(tmp_path)
    entry = _entry(archive, url="http://example.test/dict-fr.tar.gz")

    with pytest.raises(DictionaryDownloadError, match="HTTPS"):
        download_dictionary(entry, ManagedDictionaryProvider(tmp_path / "managed"))


def test_rejects_a_redirect_to_http(tmp_path: Path):
    archive = _bundle_archive(tmp_path)
    response = _FakeResponse(
        archive.read_bytes(),
        url="http://example.test/dict-fr.tar.gz",
    )

    with patch("pyqt6_linguistic_tools.download.urlopen", return_value=response):
        with pytest.raises(DictionaryDownloadError, match="non-HTTPS"):
            download_dictionary(
                _entry(archive),
                ManagedDictionaryProvider(tmp_path / "managed"),
            )
