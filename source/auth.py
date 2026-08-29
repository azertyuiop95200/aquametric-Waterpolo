import hashlib
import hmac
import os

PBKDF2_ITERATIONS = 310_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        if stored.startswith("pbkdf2_sha256$"):
            _, iterations, salt_hex, hash_hex = stored.split("$", 3)
            dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations))
            return hmac.compare_digest(dk.hex(), hash_hex)

        # Legacy V11 hashes: salt:hash using 180k iterations. Kept read-only so
        # existing local/demo accounts are not invalidated by the security upgrade.
        salt_hex, hash_hex = stored.split(":", 1)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 180_000)
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False


# main.py imports auth before the shared scouting and extension installers. Register
# additive patches here so the normal startup path keeps a single source of truth.
from services.scouting_eu_2026_runtime import install_scouting_seed_patch as _install_scouting_seed_patch
from prospect_routes import install_prospect_routes_patch as _install_prospect_routes_patch

_install_scouting_seed_patch()
_install_prospect_routes_patch()
