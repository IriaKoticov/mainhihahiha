""" Модуль авторизации и аутентификации команд"""
import os
import bcrypt  # optional if you plan to use bcrypt hashes
from typing import Optional

class AuthError(Exception):
    pass

def find_users_file(candidate: str = None) -> Optional[str]:
    search = []
    if candidate:
        search.append(candidate)
    # cwd
    search.append(os.path.join(os.getcwd(), "config/users.txt"))
    # same dir as this file
    here = os.path.dirname(os.path.abspath(__file__))
    search.append(os.path.join(here, "users.txt"))
    # parent dirs
    search.append(os.path.join(here, "..", "users.txt"))
    search.append(os.path.join(here, "..", "..", "users.txt"))
    for p in search:
        p = os.path.normpath(p)
        if os.path.exists(p) and os.path.isfile(p):
            return p
    return None

def _is_bcrypt_hash(field: str) -> bool:
    # bcrypt hashes start with $2b$ or $2a$ or $2y$
    return isinstance(field, str) and field.startswith("$2")

def _verify_bcrypt(stored: str, password: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
    except Exception:
        return False

def authorize(username: str, password: str, users_file: str = None) -> int:
    path = find_users_file(users_file)
    if not path:
        raise AuthError("users.txt not found (searched common locations). Use --users to specify path.")

    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) < 3:
                continue
            user = parts[0]
            pw_field = ":".join(parts[1:-1])
            try:
                role = int(parts[-1])
            except Exception:
                continue
            if user != username:
                continue

            if _is_bcrypt_hash(pw_field):
                if _verify_bcrypt(pw_field, password):
                    return role
                else:
                    raise AuthError("Invalid login or password")
            else:
                # plain-text compare
                if pw_field == password:
                    return role
                else:
                    raise AuthError("Invalid login or password")

    raise AuthError("Invalid login or password")
