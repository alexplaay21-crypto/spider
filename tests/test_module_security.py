import io
import zipfile

import pytest

from module_manager.security import MAX_ZIP_SIZE_BYTES, ModulePackageError, validate_and_extract


def _make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def test_valid_module_extracts(tmp_path):
    zip_bytes = _make_zip({"main.py": b"async def setup(client):\n    pass\n"})
    dest = tmp_path / "autoreply"
    validate_and_extract(zip_bytes, dest)
    assert (dest / "main.py").exists()


def test_rejects_path_traversal(tmp_path):
    zip_bytes = _make_zip({"../../etc/passwd": b"pwned"})
    with pytest.raises(ModulePackageError, match="path_traversal"):
        validate_and_extract(zip_bytes, tmp_path / "mod")


def test_rejects_absolute_path(tmp_path):
    zip_bytes = _make_zip({"/etc/passwd": b"pwned"})
    with pytest.raises(ModulePackageError, match="absolute_path"):
        validate_and_extract(zip_bytes, tmp_path / "mod")


def test_rejects_oversized_package(tmp_path):
    huge = b"x" * (MAX_ZIP_SIZE_BYTES + 1)
    with pytest.raises(ModulePackageError, match="package_too_large"):
        validate_and_extract(huge, tmp_path / "mod")


def test_rejects_too_many_files(tmp_path):
    files = {f"file_{i}.txt": b"x" for i in range(300)}
    zip_bytes = _make_zip(files)
    with pytest.raises(ModulePackageError, match="too_many_files"):
        validate_and_extract(zip_bytes, tmp_path / "mod")


def test_rejects_non_zip_data(tmp_path):
    with pytest.raises(ModulePackageError, match="not_a_valid_zip"):
        validate_and_extract(b"not a zip file", tmp_path / "mod")
