"""Criptografia do pacote de backup (SEC-10): AES-256-GCM em fluxo (STREAM), sem binário externo.

Formato: `FTTHBK01` | prefixo aleatório (8 bytes) | blocos [tamanho (4 bytes) | texto cifrado + tag].
Cada bloco de 1 MiB é autenticado separadamente com nonce = prefixo + contador (4 bytes) e AAD que
inclui o cabeçalho, o contador e a marca de "último bloco" — reordenar, remover ou truncar blocos
falha na autenticação. A chave (`BACKUP_ENCRYPTION_KEY`, 32 bytes em hex ou base64) é distinta da
chave de assinatura do manifesto e deve ser guardada FORA do servidor de backup.
"""

from __future__ import annotations

import base64
import binascii
import os
import struct
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"FTTHBK01"
CHUNK_SIZE = 1024 * 1024
_HEADER_LEN = len(MAGIC) + 8


class BackupCryptoError(Exception):
    """Falha de criptografia (chave inválida, dado adulterado ou truncado)."""


def parse_key(material: str) -> bytes:
    """Aceita 64 caracteres hex ou base64 (padrão/urlsafe) de exatamente 32 bytes."""
    value = material.strip()
    for decoder in (bytes.fromhex, base64.b64decode, base64.urlsafe_b64decode):
        try:
            key = decoder(value)
        except (ValueError, binascii.Error):
            continue
        if len(key) == 32:
            return bytes(key)
    raise BackupCryptoError(
        "BACKUP_ENCRYPTION_KEY inválida: use 32 bytes em hex (openssl rand -hex 32) ou base64."
    )


def is_encrypted_file(path: Path) -> bool:
    with open(path, "rb") as f:
        return f.read(len(MAGIC)) == MAGIC


def _nonce(prefix: bytes, counter: int) -> bytes:
    return prefix + struct.pack(">I", counter)


def _aad(header: bytes, counter: int, final: bool) -> bytes:
    return header + struct.pack(">I", counter) + (b"\x01" if final else b"\x00")


def encrypt_file(source: Path, destination: Path, key_material: str) -> None:
    aead = AESGCM(parse_key(key_material))
    prefix = os.urandom(8)
    header = MAGIC + prefix
    with open(source, "rb") as src, open(destination, "wb") as dst:
        dst.write(header)
        counter = 0
        chunk = src.read(CHUNK_SIZE)
        while True:
            nxt = src.read(CHUNK_SIZE)
            final = not nxt
            sealed = aead.encrypt(_nonce(prefix, counter), chunk, _aad(header, counter, final))
            dst.write(struct.pack(">I", len(sealed)) + sealed)
            if final:
                break
            chunk, counter = nxt, counter + 1


def decrypt_file(source: Path, destination: Path, key_material: str) -> None:
    aead = AESGCM(parse_key(key_material))
    try:
        with open(source, "rb") as src, open(destination, "wb") as dst:
            header = src.read(_HEADER_LEN)
            if len(header) != _HEADER_LEN or header[: len(MAGIC)] != MAGIC:
                raise BackupCryptoError("Arquivo não é um backup criptografado do FTTH Manager.")
            prefix = header[len(MAGIC) :]
            counter = 0
            length_raw = src.read(4)
            if not length_raw:
                raise BackupCryptoError("Pacote criptografado vazio ou truncado.")
            while True:
                if len(length_raw) != 4:
                    raise BackupCryptoError("Pacote criptografado truncado.")
                (length,) = struct.unpack(">I", length_raw)
                if length < 16 or length > CHUNK_SIZE + 16:
                    raise BackupCryptoError("Bloco criptografado com tamanho inválido.")
                sealed = src.read(length)
                if len(sealed) != length:
                    raise BackupCryptoError("Pacote criptografado truncado.")
                next_length = src.read(4)
                final = not next_length
                try:
                    plain = aead.decrypt(
                        _nonce(prefix, counter), sealed, _aad(header, counter, final)
                    )
                except InvalidTag:
                    raise BackupCryptoError(
                        "Falha de autenticação: chave incorreta ou pacote adulterado/truncado."
                    ) from None
                dst.write(plain)
                if final:
                    return
                length_raw, counter = next_length, counter + 1
    except BackupCryptoError:
        destination.unlink(missing_ok=True)
        raise
