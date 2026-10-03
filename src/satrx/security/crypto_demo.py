from __future__ import annotations

import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Demonstration "clair vs protege" (F8) : AES-256-GCM (chiffrement authentifie, standard
# moderne) applique a une charge utile pour montrer concretement l'effet d'une protection
# sur un flux qui circulerait sinon en clair (ex: telemetrie ou image LRPT non protegee).
KEY_SIZE_BYTES = 32  # AES-256
NONCE_SIZE_BYTES = 12  # taille standard recommandee pour GCM


def generate_key() -> bytes:
    return os.urandom(KEY_SIZE_BYTES)


@dataclass(frozen=True)
class EncryptedPayload:
    nonce: bytes
    ciphertext: bytes

    def to_bytes(self) -> bytes:
        return self.nonce + self.ciphertext

    @staticmethod
    def from_bytes(data: bytes) -> "EncryptedPayload":
        if len(data) <= NONCE_SIZE_BYTES:
            raise ValueError(
                f"data trop court : {len(data)} octets fournis, plus de {NONCE_SIZE_BYTES} requis"
            )
        return EncryptedPayload(nonce=data[:NONCE_SIZE_BYTES], ciphertext=data[NONCE_SIZE_BYTES:])


def encrypt_payload(plaintext: bytes, key: bytes, associated_data: bytes = b"") -> EncryptedPayload:
    if len(key) != KEY_SIZE_BYTES:
        raise ValueError(f"key doit faire {KEY_SIZE_BYTES} octets (AES-256), recu {len(key)}")
    if not plaintext:
        raise ValueError("plaintext ne doit pas etre vide")

    nonce = os.urandom(NONCE_SIZE_BYTES)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data or None)
    return EncryptedPayload(nonce=nonce, ciphertext=ciphertext)


def decrypt_payload(payload: EncryptedPayload, key: bytes, associated_data: bytes = b"") -> bytes:
    if len(key) != KEY_SIZE_BYTES:
        raise ValueError(f"key doit faire {KEY_SIZE_BYTES} octets (AES-256), recu {len(key)}")

    aesgcm = AESGCM(key)
    return aesgcm.decrypt(payload.nonce, payload.ciphertext, associated_data or None)
