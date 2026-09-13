import hashlib, hmac, os

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 180000)
    return salt.hex() + ':' + dk.hex()

def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, hash_hex = stored.split(':', 1)
        dk = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt_hex), 180000)
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False
