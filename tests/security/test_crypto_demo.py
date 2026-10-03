import pytest
from cryptography.exceptions import InvalidTag

from satrx.security.crypto_demo import (
    EncryptedPayload,
    decrypt_payload,
    encrypt_payload,
    generate_key,
)
from satrx.security.entropy import classify_payload


class TestEncryptDecryptRoundtrip:

    def test_nominal_case(self):
        key = generate_key()
        plaintext = b"METEOR-M2 3 TELEMETRY TEMP=20C STATUS=NOMINAL"

        payload = encrypt_payload(plaintext, key)
        decrypted = decrypt_payload(payload, key)

        assert decrypted == plaintext

    def test_edge_case_wrong_key_fails_authentication(self):
        key = generate_key()
        wrong_key = generate_key()
        payload = encrypt_payload(b"donnee sensible", key)

        with pytest.raises(InvalidTag):
            decrypt_payload(payload, wrong_key)

    def test_edge_case_invalid_key_size(self):
        with pytest.raises(ValueError):
            encrypt_payload(b"data", key=b"trop court")

    def test_edge_case_empty_plaintext(self):
        with pytest.raises(ValueError):
            encrypt_payload(b"", generate_key())


class TestEncryptedPayloadSerialization:

    def test_interop_to_bytes_from_bytes_roundtrip(self):
        key = generate_key()
        payload = encrypt_payload(b"donnee de telemetrie", key)

        serialized = payload.to_bytes()
        recovered = EncryptedPayload.from_bytes(serialized)
        decrypted = decrypt_payload(recovered, key)

        assert decrypted == b"donnee de telemetrie"

    def test_edge_case_too_short_to_deserialize(self):
        with pytest.raises(ValueError):
            EncryptedPayload.from_bytes(b"trop court")


class TestClearVsProtectedDemo:

    def test_interop_encryption_raises_entropy_of_structured_payload(self):
        # demonstration F8 : un payload structure/repetitif (clair) a une entropie basse,
        # le meme payload une fois chiffre devient quasi indiscernable d'un flux aleatoire.
        plaintext = b"APID=65 TEMP=20.5C PRESSURE=1013HPA " * 30
        key = generate_key()

        clear_classification = classify_payload(plaintext)
        payload = encrypt_payload(plaintext, key)
        encrypted_classification = classify_payload(payload.ciphertext)

        assert clear_classification == "probablement clair / structure"
        assert encrypted_classification == "probablement chiffre ou compresse"
