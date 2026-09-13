import io
import stat
import zipfile
from pathlib import Path

MAX_ZIP_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB - generous for a module, not for a payload
MAX_FILE_COUNT = 200


class ModulePackageError(Exception):
    """Anything wrong with a module ZIP - never let this reach the user
    as a raw exception, section 70 wants a friendly message instead."""


def validate_and_extract(zip_bytes: bytes, destination: Path) -> None:
    """
    Every extracted path must resolve to strictly *inside* destination -
    no "../", no absolute paths, no Windows drive letters, no symlinks
    that could point outside. This is checked technically only (section
    31/34: technical validation is not the same thing as a code security
    review - it just stops the package from writing files where it
    shouldn't, it says nothing about what the module's own code does once
    loaded).
    """
    if len(zip_bytes) > MAX_ZIP_SIZE_BYTES:
        raise ModulePackageError("package_too_large")

    buffer = io.BytesIO(zip_bytes)
    if not zipfile.is_zipfile(buffer):
        raise ModulePackageError("not_a_valid_zip")

    with zipfile.ZipFile(buffer) as zf:
        infos = zf.infolist()
        if len(infos) > MAX_FILE_COUNT:
            raise ModulePackageError("too_many_files")

        destination_resolved = destination.resolve()

        for info in infos:
            name = info.filename

            if name.startswith("/") or name.startswith("\\"):
                raise ModulePackageError(f"absolute_path_in_zip:{name}")
            if len(name) > 1 and name[1] == ":":  # Windows drive letter, e.g. "C:\\..."
                raise ModulePackageError(f"absolute_path_in_zip:{name}")
            if ".." in Path(name).parts:
                raise ModulePackageError(f"path_traversal_in_zip:{name}")

            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                raise ModulePackageError(f"symlink_in_zip:{name}")

            target = (destination_resolved / name).resolve()
            if target != destination_resolved and destination_resolved not in target.parents:
                raise ModulePackageError(f"escapes_destination:{name}")

        destination_resolved.mkdir(parents=True, exist_ok=True)
        zf.extractall(destination_resolved)
