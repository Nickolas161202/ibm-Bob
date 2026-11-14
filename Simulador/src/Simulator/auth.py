"""
auth.py
-------
Utilitários de autenticação de perfil.

Usa PBKDF2-HMAC-SHA256 (stdlib hashlib) para derivar e verificar senhas.
O hash é armazenado como string hexadecimal no formato:
    "pbkdf2:sha256:<iterações>$<salt_hex>$<hash_hex>"
"""

from __future__ import annotations

import hashlib
import os


_ITERATIONS = 260_000   # OWASP 2023 recomendation for PBKDF2-SHA256


def hash_password(password: str) -> str:
    """
    Deriva um hash seguro de *password*.
    Retorna uma string armazenável no formato:
        "pbkdf2:sha256:<iter>$<salt_hex>$<dk_hex>"
    """
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"pbkdf2:sha256:{_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verifica se *password* corresponde ao *stored_hash*.
    Retorna True se a senha estiver correta, False caso contrário.
    Retorna True (sem verificação) se *stored_hash* for vazio — perfil sem senha.
    """
    if not stored_hash:
        return True  # Perfil sem senha: qualquer entrada (inclusive vazia) é aceita

    try:
        prefix, algo, rest = stored_hash.split(":", 2)
        if prefix != "pbkdf2" or algo != "sha256":
            return False
        iterations_str, salt_hex, dk_hex = rest.split("$")
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected_dk = bytes.fromhex(dk_hex)
    except (ValueError, AttributeError):
        return False

    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return candidate == expected_dk
