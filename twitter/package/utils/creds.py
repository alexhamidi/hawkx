"""
Chrome cookie decryptor for macOS.

Reads cookies directly from Chrome's SQLite database and decrypts v10-encrypted values.

Encryption format (Chrome on macOS):
  - Prefix:     3 bytes  ("v10")
  - IV:        16 bytes  (AES-128-CBC initialization vector, embedded in the blob)
  - Ciphertext: rest
  After decryption, strip the 16-byte metadata prefix to get the actual value.

Key derivation:
  PBKDF2-HMAC-SHA1, password from macOS Keychain ("Chrome Safe Storage"),
  salt="saltysalt", iterations=1003, keylen=16.
"""

import os
import shutil
import sqlite3
import subprocess
import tempfile

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

CHROME_COOKIES_PATH = os.path.expanduser(
    "~/Library/Application Support/Google/Chrome/Profile 1/Cookies"
)

_key_cache = None


def _chrome_key() -> bytes:
    global _key_cache
    if _key_cache is not None:
        return _key_cache

    result = subprocess.run(
        ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage"],
        capture_output=True,
        text=True,
        check=True,
    )
    password = result.stdout.strip().encode()

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA1(),
        length=16,
        salt=b"saltysalt",
        iterations=1003,
    )
    _key_cache = kdf.derive(password)
    return _key_cache



def _decrypt(encrypted: bytes, key: bytes) -> str:
    iv = encrypted[3:19]
    ciphertext = encrypted[19:]

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    raw = decryptor.update(ciphertext) + decryptor.finalize()

    # Strip PKCS7 padding
    pad = raw[-1]
    raw = raw[:-pad]

    # Strip 16-byte metadata prefix Chrome prepends before the actual value
    return raw[16:].decode("utf-8")



def get_cookies(domain: str) -> dict:
    """
    Return a dict of cookie name -> decrypted value for the given domain.

    Args:
        domain: Host key to filter by (e.g. ".x.com", ".google.com")
    """
    key = _chrome_key()

    # Chrome locks the DB while running — copy to a temp file first
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        shutil.copy2(CHROME_COOKIES_PATH, tmp_path)
        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, value, encrypted_value FROM cookies WHERE host_key = ?",
            (domain,),
        )
        cookies = {}
        for name, value, encrypted_value in cursor.fetchall():
            if encrypted_value and encrypted_value[:3] == b"v10":
                cookies[name] = _decrypt(encrypted_value, key)
            else:
                cookies[name] = value
        conn.close()
        return cookies
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    import json
    cookies = get_cookies(".x.com")
    print(json.dumps({k: v[:20] + "..." for k, v in cookies.items()}, indent=2))
