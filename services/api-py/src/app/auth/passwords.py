"""Password hashing (argon2id) and policy.

Policy follows NIST 800-63B: length over composition. Minimum length (default
10), maximum 128, no complexity rules, no forced rotation. Rejected: the user's
own email, a short list of the most common passwords, and (optional,
AUTH_PASSWORD_HIBP=1) anything in the Have I Been Pwned range API, queried by
k-anonymity (only a 5 character hash prefix leaves the server; fails open).
"""

from __future__ import annotations

import hashlib

import httpx
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_HASHER = PasswordHasher()  # argon2id, library defaults (RFC 9106 low-memory profile)
# A real hash to verify against when the account does not exist, so response
# time does not reveal which emails are registered.
DUMMY_HASH = _HASHER.hash("ankana-dummy-password")

MAX_LENGTH = 128
COMMON = frozenset("""
password password1 password12 password123 passw0rd 123456789 1234567890 12345678910
qwertyuiop qwerty123 qwertyuiop123 iloveyou123 letmein123 welcome123 admin12345
administrator abc123456 abcd123456 changeme123 0123456789 1q2w3e4r5t 1qaz2wsx3edc
zaq12wsx123 trustno1234 sunshine123 football123 monkey12345 dragon12345 master12345
""".split())


class PasswordPolicyError(ValueError):
    pass


def hash_password(password: str) -> str:
    return _HASHER.hash(password)


def verify_password(stored: str, password: str) -> bool:
    try:
        return _HASHER.verify(stored, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(stored: str) -> bool:
    return _HASHER.check_needs_rehash(stored)


def _pwned(password: str) -> bool:
    digest = hashlib.sha1(password.encode(), usedforsecurity=False).hexdigest().upper()
    prefix, suffix = digest[:5], digest[5:]
    try:
        r = httpx.get(f"https://api.pwnedpasswords.com/range/{prefix}", timeout=3,
                      headers={"Add-Padding": "true"})
        r.raise_for_status()
    except httpx.HTTPError:
        return False
    return any(line.split(":")[0] == suffix and int(line.split(":")[1]) > 0
               for line in r.text.splitlines())


def check_policy(password: str, *, email: str | None, min_length: int, hibp: bool = False) -> None:
    if len(password) < min_length:
        raise PasswordPolicyError(f"Use at least {min_length} characters. A short phrase works well.")
    if len(password) > MAX_LENGTH:
        raise PasswordPolicyError(f"Use at most {MAX_LENGTH} characters.")
    lowered = password.lower()
    if lowered in COMMON or (email and lowered == email.lower()):
        raise PasswordPolicyError("That password is too easy to guess. Try a longer phrase.")
    if len(set(password)) < 4:
        raise PasswordPolicyError("That password is too repetitive. Try a longer phrase.")
    if hibp and _pwned(password):
        raise PasswordPolicyError("That password has appeared in a data breach. Choose another.")
