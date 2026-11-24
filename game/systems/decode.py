"""Encoding helpers for puzzles, encoded command lines, and the terminal `decode` command."""

from __future__ import annotations

import base64
import binascii
import codecs


class DecodeError(ValueError):
    pass


def parse_key(key: str | int | None) -> bytes:
    if key is None or key == "":
        raise DecodeError("XOR needs a key, e.g. decode xor 6c6b 0x2a")
    if isinstance(key, int):
        return bytes([key & 0xFF])
    k = str(key).strip()
    if k.lower().startswith("0x"):
        try:
            value = bytes.fromhex(k[2:].rjust(len(k[2:]) + len(k[2:]) % 2, "0"))
        except ValueError as exc:
            raise DecodeError(f"'{k}' is not a valid hex key") from exc
        return value or b"\x00"
    if k.lower().startswith("key:"):
        k = k[4:]
    return k.encode()


def xor_bytes(data: bytes, key: bytes) -> bytes:
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def _bytes_to_text(raw: bytes) -> str:
    if len(raw) >= 4 and len(raw) % 2 == 0 and raw[1::2].count(0) >= len(raw) // 2 - 1:
        return raw.decode("utf-16-le", errors="replace")
    return raw.decode("utf-8", errors="replace")


def encode(kind: str, text: str, key=None) -> str:
    kind = kind.lower()
    if kind == "base64":
        return base64.b64encode(text.encode()).decode()
    if kind == "base64u16":
        return base64.b64encode(text.encode("utf-16-le")).decode()
    if kind == "hex":
        return text.encode().hex()
    if kind == "xor":
        return xor_bytes(text.encode(), parse_key(key)).hex()
    if kind == "rot13":
        return codecs.encode(text, "rot13")
    raise DecodeError(f"unknown encoding '{kind}'")


def decode(kind: str, data: str, key=None) -> str:
    kind = kind.lower()
    data = data.strip()
    try:
        if kind in ("base64", "b64"):
            padded = data + "=" * (-len(data) % 4)
            return _bytes_to_text(base64.b64decode(padded, validate=False))
        if kind == "hex":
            clean = data.replace(" ", "").replace("0x", "")
            return _bytes_to_text(bytes.fromhex(clean))
        if kind == "xor":
            clean = data.replace(" ", "")
            return _bytes_to_text(xor_bytes(bytes.fromhex(clean), parse_key(key)))
        if kind == "rot13":
            return codecs.decode(data, "rot13")
    except (binascii.Error, ValueError) as exc:
        if isinstance(exc, DecodeError):
            raise
        raise DecodeError(f"that doesn't look like valid {kind} data") from exc
    raise DecodeError("decode supports: base64, hex, xor, rot13")
