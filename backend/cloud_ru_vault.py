"""Per-user Cloud.ru credentials encrypted with Windows DPAPI CurrentUser."""
import ctypes
import json
import os
import re
import sys
from ctypes import wintypes
from pathlib import Path

DEFAULT_MODEL = "ai-sage/GigaChat3-10B-A1.8B"
MODEL_PATTERN = re.compile(r"^[a-zA-Z0-9_./:-]{1,150}$")


def credential_path():
    root = os.environ.get("LOCALAPPDATA")
    if sys.platform != "win32" or not root:
        raise RuntimeError("Cloud.ru credential vault requires Windows and LOCALAPPDATA")
    return Path(root) / "Yorika" / "secrets" / "cloud-ru.dpapi"


def _crypt(data: bytes, *, decrypt: bool) -> bytes:
    if sys.platform != "win32":
        raise RuntimeError("DPAPI is available only on Windows")
    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]
    source = ctypes.create_string_buffer(data)
    source_blob = Blob(len(data), ctypes.cast(source, ctypes.POINTER(ctypes.c_byte)))
    target = Blob()
    library = ctypes.WinDLL("crypt32", use_last_error=True)
    fn = library.CryptUnprotectData if decrypt else library.CryptProtectData
    fn.restype = wintypes.BOOL
    if decrypt:
        fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob),
                       ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
                       ctypes.POINTER(Blob)]
        args = (ctypes.byref(source_blob), None, None, None, None, 0, ctypes.byref(target))
    else:
        fn.argtypes = [ctypes.POINTER(Blob), wintypes.LPCWSTR, ctypes.POINTER(Blob),
                       ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
                       ctypes.POINTER(Blob)]
        args = (ctypes.byref(source_blob), "Yorika Cloud.ru API credential", None,
                None, None, 0x01, ctypes.byref(target))
    if not fn(*args):
        raise OSError(ctypes.get_last_error(), "Windows DPAPI operation failed")
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        kernel.LocalFree(ctypes.cast(target.pbData, ctypes.c_void_p))


def read_credentials():
    path = credential_path()
    if path.is_symlink():
        raise RuntimeError("Refusing linked credential file")
    if not path.is_file():
        return None
    value = json.loads(_crypt(path.read_bytes(), decrypt=True).decode("utf-8"))
    if (not isinstance(value, dict) or not isinstance(value.get("key"), str)
            or not 1 <= len(value["key"]) <= 8192
            or any(ord(char) in (10, 13) for char in value["key"])
            or not isinstance(value.get("model"), str)
            or not MODEL_PATTERN.fullmatch(value["model"])):
        raise RuntimeError("Corrupt Cloud.ru credential vault")
    return value


def save_credentials(key: str, model: str):
    if not isinstance(key, str) or not 1 <= len(key) <= 8192 or any(c in key for c in "\r\n"):
        raise ValueError("Invalid Cloud.ru key")
    if not isinstance(model, str) or not MODEL_PATTERN.fullmatch(model):
        raise ValueError("Invalid Cloud.ru model")
    path = credential_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.parent.is_symlink():
        raise RuntimeError("Refusing unsafe Cloud.ru credential path")
    content = json.dumps({"key": key, "model": model}, ensure_ascii=False).encode("utf-8")
    encrypted = _crypt(content, decrypt=False)
    # Exclusive creation of temporary file prevents races and symlink replacement.
    import tempfile
    fd, temp = tempfile.mkstemp(prefix=".cloud-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(encrypted)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def delete_credentials():
    path = credential_path()
    if path.is_symlink():
        raise RuntimeError("Refusing linked credential file")
    if path.exists():
        path.unlink()
    return True


def public_status():
    value = read_credentials()
    return {"configured": value is not None, "model": value["model"] if value else DEFAULT_MODEL,
            "storage": "windows-dpapi-current-user"}
