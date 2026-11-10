"""Verified dictionary download and installation from the bundled catalog.

Network access and archive extraction live here, outside the Qt layer. The
workflow is deliberately fail-closed: HTTPS only, exact size and SHA-256
verification, a single expected top-level directory, regular files only, and
final deep validation before atomic publication into a managed provider.
"""

from __future__ import annotations

from collections.abc import Callable
import hashlib
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pyqt6_linguistic_tools.catalog import DictionaryCatalogEntry
from pyqt6_linguistic_tools.errors import (
    DictionaryDownloadCancelled,
    DictionaryDownloadError,
    DictionaryImportError,
)
from pyqt6_linguistic_tools.models import DictionaryImportResult
from pyqt6_linguistic_tools.providers import ManagedDictionaryProvider


ProgressCallback = Callable[[int, int], None]
CancelCheck = Callable[[], bool]

_ALLOWED_SUFFIXES = {".aff", ".dic", ".dat", ".idx"}
_MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
_MAX_EXTRACTED_BYTES = 512 * 1024 * 1024
_CHUNK_SIZE = 64 * 1024
_USER_AGENT = "pyqt6-linguistic-tools/1.0"


def download_dictionary(
    entry: DictionaryCatalogEntry,
    provider: ManagedDictionaryProvider,
    *,
    progress: ProgressCallback | None = None,
    should_cancel: CancelCheck | None = None,
    timeout: float = 30.0,
) -> DictionaryImportResult:
    """Download, verify, validate and install one catalog entry.

    ``progress`` receives ``(downloaded_bytes, total_bytes)`` while the archive
    is streamed. ``should_cancel`` is polled between chunks; a true result
    raises :class:`DictionaryDownloadCancelled` and leaves no partial bundle.
    """
    if not isinstance(entry, DictionaryCatalogEntry):
        raise TypeError("entry must be a DictionaryCatalogEntry")
    if not isinstance(provider, ManagedDictionaryProvider):
        raise TypeError("provider must be a ManagedDictionaryProvider")
    if entry.sha256 is None:
        raise DictionaryDownloadError(
            f"catalog entry {entry.code} has no SHA-256 checksum"
        )
    parsed = urlparse(entry.url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise DictionaryDownloadError(
            f"catalog entry {entry.code} must use an HTTPS URL"
        )
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool):
        raise TypeError("timeout must be a number")
    if timeout <= 0:
        raise ValueError("timeout must be positive")

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="pyqt6-dictionary-",
            suffix=".tar.gz",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        _download_to_path(
            entry,
            temporary_path,
            progress=progress,
            should_cancel=should_cancel,
            timeout=float(timeout),
        )
        return install_dictionary_archive(
            temporary_path,
            entry,
            provider,
        )
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def install_dictionary_archive(
    archive_path: str | Path,
    entry: DictionaryCatalogEntry,
    provider: ManagedDictionaryProvider,
) -> DictionaryImportResult:
    """Verify and install an already downloaded catalog archive."""
    if not isinstance(entry, DictionaryCatalogEntry):
        raise TypeError("entry must be a DictionaryCatalogEntry")
    if not isinstance(provider, ManagedDictionaryProvider):
        raise TypeError("provider must be a ManagedDictionaryProvider")
    if entry.sha256 is None:
        raise DictionaryDownloadError(
            f"catalog entry {entry.code} has no SHA-256 checksum"
        )
    source = Path(archive_path).expanduser().resolve()
    if not source.is_file():
        raise DictionaryDownloadError(f"dictionary archive does not exist: {source}")
    if entry.size:
        actual_size = source.stat().st_size
        if actual_size != entry.size:
            raise DictionaryDownloadError(
                f"dictionary archive size mismatch: expected {entry.size}, "
                f"got {actual_size}"
            )
    digest = _sha256(source)
    if digest != entry.sha256.lower():
        raise DictionaryDownloadError(
            f"dictionary archive SHA-256 mismatch for {entry.code}"
        )

    with tempfile.TemporaryDirectory(prefix="pyqt6-dictionary-extract-") as temporary:
        extracted = _extract_bundle(source, entry, Path(temporary))
        if not extracted:
            raise DictionaryDownloadError(
                f"dictionary archive for {entry.code} contains no usable files"
            )
        # Curated release bundles can contain one malformed regional variant
        # (for example es_UY at the time of writing). Keep the valid variants
        # instead of rejecting the entire language pack.
        usable = _usable_bundle_files(Path(temporary))
        if not usable:
            raise DictionaryDownloadError(
                f"dictionary archive for {entry.code} contains no usable components"
            )
        try:
            return provider.import_validated_files(
                usable,
                bundle_name=f"dict-{entry.code}",
            )
        except (DictionaryImportError, FileExistsError) as error:
            raise DictionaryDownloadError(
                f"dictionary installation failed for {entry.code}: {error}"
            ) from error


def _download_to_path(
    entry: DictionaryCatalogEntry,
    destination: Path,
    *,
    progress: ProgressCallback | None,
    should_cancel: CancelCheck | None,
    timeout: float,
) -> None:
    request = Request(entry.url, headers={"User-Agent": _USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            final_url = urlparse(response.geturl())
            if final_url.scheme != "https" or not final_url.netloc:
                raise DictionaryDownloadError(
                    "dictionary download redirected to a non-HTTPS URL"
                )
            content_length = response.headers.get("Content-Length")
            try:
                declared = int(content_length) if content_length else 0
            except ValueError:
                declared = 0
            if entry.size and declared and declared != entry.size:
                raise DictionaryDownloadError(
                    f"dictionary server size mismatch: expected {entry.size}, "
                    f"got {declared}"
                )
            total = entry.size or declared
            downloaded = 0
            with destination.open("wb") as output:
                while True:
                    if should_cancel is not None and should_cancel():
                        raise DictionaryDownloadCancelled(
                            f"dictionary download cancelled for {entry.code}"
                        )
                    chunk = response.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > _MAX_ARCHIVE_BYTES:
                        raise DictionaryDownloadError(
                            "dictionary archive exceeds the maximum download size"
                        )
                    if entry.size and downloaded > entry.size:
                        raise DictionaryDownloadError(
                            f"dictionary download exceeded catalog size for {entry.code}"
                        )
                    output.write(chunk)
                    if progress is not None:
                        progress(downloaded, total)
    except DictionaryDownloadCancelled:
        raise
    except DictionaryDownloadError:
        raise
    except Exception as error:
        raise DictionaryDownloadError(
            f"failed to download dictionary {entry.code}: {error}"
        ) from error

    actual = destination.stat().st_size
    if entry.size and actual != entry.size:
        raise DictionaryDownloadError(
            f"dictionary download size mismatch: expected {entry.size}, "
            f"got {actual}"
        )
    if actual > _MAX_ARCHIVE_BYTES:
        raise DictionaryDownloadError(
            "dictionary archive exceeds the maximum download size"
        )


def _usable_bundle_files(root: Path) -> tuple[Path, ...]:
    """Return files belonging to components that pass deep validation."""
    from pyqt6_linguistic_tools.providers import DirectoryDictionaryProvider
    from pyqt6_linguistic_tools.validation import DictionaryValidator

    candidates = DirectoryDictionaryProvider(
        root,
        source="managed",
        priority=0,
        recursive=False,
    ).discover()
    validator = DictionaryValidator()
    keep: set[Path] = set()
    for candidate in candidates:
        report = validator.validate_candidates((candidate,))
        if not report.usable:
            continue
        for path in (
            candidate.aff_path,
            candidate.dic_path,
            candidate.thesaurus_dat,
            candidate.thesaurus_idx,
        ):
            if path is not None:
                keep.add(path)
    return tuple(sorted(keep))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _extract_bundle(
    archive_path: Path,
    entry: DictionaryCatalogEntry,
    destination: Path,
) -> tuple[Path, ...]:
    prefixes = {
        f"dict-{entry.code}",
        f"dict-{entry.code.replace('_', '-')}",
    }
    extracted: list[Path] = []
    extracted_bytes = 0
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive:
                if member.isdir():
                    continue
                if (
                    not member.isfile()
                    or member.issym()
                    or member.islnk()
                    or member.isdev()
                ):
                    raise DictionaryDownloadError(
                        "dictionary archive contains an unsupported entry"
                    )
                if "\\" in member.name or "\x00" in member.name:
                    raise DictionaryDownloadError(
                        "dictionary archive contains an unsafe path"
                    )
                parts = [
                    part
                    for part in PurePosixPath(member.name).parts
                    if part not in ("", ".")
                ]
                if (
                    not parts
                    or ".." in parts
                    or any(":" in part for part in parts)
                    or member.name.startswith("/")
                ):
                    raise DictionaryDownloadError(
                        "dictionary archive contains an unsafe path"
                    )
                if parts[0] not in prefixes:
                    raise DictionaryDownloadError(
                        "dictionary archive has an unexpected top-level directory"
                    )
                relative = parts[1:]
                if not relative:
                    raise DictionaryDownloadError(
                        "dictionary archive contains an empty bundle path"
                    )
                suffix = Path(relative[-1]).suffix.lower()
                if suffix not in _ALLOWED_SUFFIXES:
                    continue
                stem = Path(relative[-1]).stem.lower()
                if suffix in {".aff", ".dic"} and stem.startswith("hyph_"):
                    continue
                if suffix in {".dat", ".idx"} and not stem.startswith("th_"):
                    continue
                target = destination.joinpath(*relative)
                if not target.resolve().is_relative_to(destination.resolve()):
                    raise DictionaryDownloadError(
                        "dictionary archive escapes the extraction directory"
                    )
                if target.exists():
                    raise DictionaryDownloadError(
                        "dictionary archive contains duplicate paths"
                    )
                if (
                    member.size < 0
                    or extracted_bytes + member.size > _MAX_EXTRACTED_BYTES
                ):
                    raise DictionaryDownloadError(
                        "dictionary archive expands beyond the maximum size"
                    )
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise DictionaryDownloadError(
                        "dictionary archive entry cannot be read"
                    )
                with source, target.open("wb") as output:
                    shutil.copyfileobj(source, output, length=_CHUNK_SIZE)
                actual_size = target.stat().st_size
                if actual_size != member.size:
                    raise DictionaryDownloadError(
                        "dictionary archive entry has an inconsistent size"
                    )
                extracted_bytes += actual_size
                extracted.append(target)
    except DictionaryDownloadError:
        raise
    except (OSError, tarfile.TarError) as error:
        raise DictionaryDownloadError(
            f"dictionary archive could not be opened safely: {error}"
        ) from error
    return tuple(extracted)


__all__ = [
    "CancelCheck",
    "ProgressCallback",
    "download_dictionary",
    "install_dictionary_archive",
]
