import hashlib
import json
import mimetypes
import os
import shutil
import zipfile
from typing import Any, List, Optional, Tuple

from adsk.flow.local.storage_manager.exceptions import StorageError

HASH_ALGORITHM = "sha256"


def cleanpath(path: str, *extra: str) -> str:
    """Return the same path, normalized and using only forward slashes.

    Args:
        path: String absolute or relative path.
        *extra: Zero or more string arguments representing extra bits to
                add to input path in given order.

    Returns:
        str: Path that is the product of all input parameters joined.

    Examples:
        >>> cleanpath('c:\\dev\\my_root', 'my_dir', 'my_file.ma')
        'c:/dev/my_root/my_dir/my_file.ma'
        >>> cleanpath('/Users//smith/folder1/file1.txt')
        '/Users/smith/folder1/file1.txt'
        >>> cleanpath('C:/temp/some_dir/', '/some_folder/')
        'C:/temp/some_dir/some_folder'
        >>> cleanpath('/Applications', '/\\some_app')
        '/Applications/some_app'
        >>> cleanpath('D:', 'MIM_Files')
        'D:/MIM_Files'
        >>> cleanpath('D:\\\\', 'MIM_Files')
        'D:/MIM_Files'
        >>> cleanpath('')
        ''
        >>> cleanpath('', 'blah', 'blah')
        'blah/blah'
        >>> cleanpath('/path/to/dir/')
        '/path/to/dir'
        >>> cleanpath('/path/./to/../file.txt')
        '/path/file.txt'
    """
    if path.endswith(":"):
        path += "/"
    extras = [ext.lstrip("/\\") for ext in extra]
    result = os.path.join(path, *extras)
    if not result:
        return ""
    return os.path.normpath(result).replace("\\", "/")


def get_mimetype_from_ext(ext: str) -> str:
    """Return the mimetype of the given file extension.

    Args:
        ext: A file extension which may or may not be preceded by a '.'.
             A file path is also accepted.

    Returns:
        String mimetype, or blank string if extension is not recognized.

    Examples:
        >>> get_mimetype_from_ext('jpg')
        'image/jpeg'
        >>> get_mimetype_from_ext('.jpeg')
        'image/jpeg'
        >>> get_mimetype_from_ext('c:/temp/my_image.jpg')
        'image/jpeg'
        >>> get_mimetype_from_ext('.not_a_recognized_file_type')
        ''
    """
    if "." in ext and not ext.startswith("."):
        ext = os.path.splitext(ext)[1]
    else:
        ext = "." + ext.strip(".")
    try:
        return mimetypes.types_map[ext]
    except KeyError:
        return ""


def is_zip_path(path: str) -> bool:
    """True if *path*'s extension marks it as a packed archive to expand on download.

    BinaryComponentSpec auto-zips multi-file components and ImageSequenceComponentSpec
    always zips frames — both round-trip correctly. Limitation: a user-supplied
    standalone .zip will also be treated as expandable. A disambiguating marker in
    component data isn't viable because MEDM's schema validation strips arbitrary
    fields. Avoid publishing .zip files directly if archive preservation is required.
    """
    return os.path.splitext(path)[1].lower() == ".zip"


def ensure_dir(path: str) -> None:
    """Create *path* and all missing parents, raising StorageError on failure."""
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as exc:
        raise StorageError(f"Cannot create directory {path}: {exc}") from exc


def copy_file(src: str, dst: str) -> None:
    """Copy file from *src* to *dst*, raising StorageError on failure."""
    try:
        shutil.copy2(src, dst)
    except OSError as exc:
        raise StorageError(f"Cannot copy file from {src} to {dst}: {exc}") from exc


def new_hasher(algorithm: str = HASH_ALGORITHM) -> "hashlib._Hash":
    """Return a new hashlib hash object for *algorithm*."""
    return hashlib.new(algorithm)


def copy_file_with_hash(
    src: str, dst: str, *, algorithm: str = HASH_ALGORITHM, chunk_size: int = 1024 * 1024
) -> Tuple[str, int]:
    """Copy *src* to *dst* atomically (temp file + os.replace), hashing in the same read pass.

    Args:
        src: Path to *src* file to copy.
        dst: Path to *dst* file to copy.
        algorithm: Hashlib hash algorithm.
        chunk_size: Number of bytes to read at a time.

    Returns:
        Tuple[str, int]: A tuple containing the hexadecimal digest of the hash and the size of the copied file.

    Raises:
        StorageError: If the copy operation fails.
    """
    tmp = dst + ".tmp"
    hasher = new_hasher(algorithm)
    size = 0
    try:
        with open(src, "rb") as src_file, open(tmp, "wb") as dst_file:
            while True:
                chunk = src_file.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
                dst_file.write(chunk)
                size += len(chunk)
        os.replace(tmp, dst)
    except OSError as exc:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise StorageError(f"Cannot copy file from {src} to {dst}: {exc}") from exc
    return hasher.hexdigest(), size


def hash_file(path: str, algorithm: str = HASH_ALGORITHM, chunk_size: int = 1024 * 1024) -> str:
    """Return the hex digest of path's contents, streamed so large files never load fully into memory.

    Raises:
        StorageError: If the file cannot be read.
    """
    hasher = new_hasher(algorithm)
    try:
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
    except OSError as exc:
        raise StorageError(f"Cannot hash file {path}: {exc}") from exc
    return hasher.hexdigest()


def atomic_write_json(path: str, data: Any, *, indent: Optional[int] = None) -> None:
    """Write *data* as JSON to *path* atomically (write a .tmp, then os.replace).

    Raises the underlying OSError so callers can map it to a domain error (or
    swallow it for advisory writes); does not catch it here.
    """
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=indent)
    os.replace(tmp, path)


def is_non_empty_dir(path: str) -> bool:
    """Return True if *path* is a directory that contains at least one file or subdir."""
    return os.path.isdir(path) and bool(os.listdir(path))


def path_is_within(file_path: str, dir_path: str) -> bool:
    """True if *file_path* lies inside *dir_path* (or equals it).

    Deliberately not a bare `file_path.startswith(dir_path)`: that would
    incorrectly match `v1` against a sibling directory like ``v10/blob``.
    """
    return file_path == dir_path or file_path.startswith(dir_path.rstrip("/") + "/")


def unzip_into(zip_path: str, dest_dir: str) -> List[str]:
    """Extract *zip_path* into *dest_dir*, returning the extracted file paths.

    Guards against zip-slip: entries that escape *dest_dir* abort with a
    StorageError.
    """
    ensure_dir(dest_dir)
    dest_root = os.path.abspath(dest_dir)
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_file:
            for name in zip_file.namelist():
                target = os.path.abspath(os.path.join(dest_dir, name))
                if target != dest_root and not target.startswith(dest_root + os.sep):
                    raise StorageError(f"Unsafe path in zip {zip_path}: {name}")
            zip_file.extractall(dest_dir)
            return [
                os.path.join(dest_dir, entry_name) for entry_name in zip_file.namelist() if not entry_name.endswith("/")
            ]
    except zipfile.BadZipFile as exc:
        raise StorageError(f"Corrupt zip {zip_path}: {exc}") from exc
    except OSError as exc:
        raise StorageError(f"Cannot extract zip {zip_path}: {exc}") from exc


def zip_entry_paths(zip_path: str, dest_dir: str) -> List[str]:
    """Return the paths unzip_into(zip_path, dest_dir) would produce, without extracting.

    Used when a zip's expansion is already known-current (per the version
    manifest) so re-extraction can be skipped. Applies the same zip-slip guard
    as unzip_into: entries that would escape *dest_dir* abort with a
    StorageError, since callers (copy_file, etc.) trust these paths to stay
    within *dest_dir*.

    Args:
        zip_path: Path to the zip file.
        dest_dir: Path to the destination directory.

    Returns:
        List[str]: A list of paths that would be created by extracting the zip file into the destination directory.

    Raises:
        StorageError: If the copy operation fails or the zip file is corrupt.
    """
    dest_root = os.path.abspath(dest_dir)
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_file:
            for name in zip_file.namelist():
                target = os.path.abspath(os.path.join(dest_dir, name))
                if target != dest_root and not target.startswith(dest_root + os.sep):
                    raise StorageError(f"Unsafe path in zip {zip_path}: {name}")
            return [
                os.path.join(dest_dir, entry_name) for entry_name in zip_file.namelist() if not entry_name.endswith("/")
            ]
    except zipfile.BadZipFile as exc:
        raise StorageError(f"Corrupt zip {zip_path}: {exc}") from exc
    except OSError as exc:
        raise StorageError(f"Cannot read zip {zip_path}: {exc}") from exc
