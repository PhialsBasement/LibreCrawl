#!/usr/bin/env bash
set -euo pipefail

CONTAINER="${LIBRECRAWL_CONTAINER:-librecrawl}"

run_python() {
  docker exec -i \
    -e LC_ACTION="${LC_ACTION:-}" \
    -e LC_USERNAME="${LC_USERNAME:-}" \
    -e LC_EMAIL="${LC_EMAIL:-}" \
    -e LC_TIER="${LC_TIER:-}" \
    -e LC_VERIFIED="${LC_VERIFIED:-}" \
    -e LC_IDENTIFIER="${LC_IDENTIFIER:-}" \
    -e LC_PASSWORD="${LC_PASSWORD:-}" \
    "$CONTAINER" python - <<'PY'
import os
import secrets
import sqlite3
import string
import sys

sys.path.insert(0, "/app")
from src.auth_db import hash_password

DB_FILE = "/app/data/users.db"
VALID_TIERS = {"guest", "user", "extra", "admin"}


def connect():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def generated_password(length=20):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def get_user(conn, identifier):
    if identifier.isdigit():
        row = conn.execute("SELECT * FROM users WHERE id = ?", (int(identifier),)).fetchone()
        if row:
            return row
    return conn.execute(
        "SELECT * FROM users WHERE username = ? OR email = ?",
        (identifier, identifier),
    ).fetchone()


action = os.environ.get("LC_ACTION", "")

try:
    with connect() as conn:
        if action == "list":
            rows = conn.execute(
                """
                SELECT id, username, email, verified, tier, created_at, last_login
                FROM users
                ORDER BY id
                """
            ).fetchall()
            if not rows:
                print("No users found.")
            else:
                print(f"{'ID':<4} {'Username':<20} {'Email':<32} {'Verified':<8} {'Tier':<8} Last login")
                print("-" * 95)
                for row in rows:
                    print(
                        f"{row['id']:<4} "
                        f"{row['username']:<20} "
                        f"{row['email']:<32} "
                        f"{row['verified']:<8} "
                        f"{(row['tier'] or 'guest'):<8} "
                        f"{row['last_login'] or '-'}"
                    )

        elif action == "create":
            username = os.environ["LC_USERNAME"].strip()
            email = os.environ["LC_EMAIL"].strip()
            tier = os.environ.get("LC_TIER", "user").strip()
            verified = 1 if os.environ.get("LC_VERIFIED", "1") == "1" else 0
            password = os.environ.get("LC_PASSWORD") or generated_password()

            if tier not in VALID_TIERS:
                raise ValueError(f"Invalid tier: {tier}")
            if len(username) < 3:
                raise ValueError("Username must be at least 3 characters.")
            if "@" not in email:
                raise ValueError("Email must contain @.")
            if len(password) < 8:
                raise ValueError("Password must be at least 8 characters.")

            conn.execute(
                """
                INSERT INTO users (username, email, password_hash, verified, tier)
                VALUES (?, ?, ?, ?, ?)
                """,
                (username, email, hash_password(password), verified, tier),
            )
            print(f"Created user '{username}' with tier '{tier}'.")
            if not os.environ.get("LC_PASSWORD"):
                print(f"Generated password: {password}")

        elif action == "password":
            identifier = os.environ["LC_IDENTIFIER"].strip()
            password = os.environ.get("LC_PASSWORD") or generated_password()
            if len(password) < 8:
                raise ValueError("Password must be at least 8 characters.")

            user = get_user(conn, identifier)
            if not user:
                raise ValueError("User not found.")

            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(password), user["id"]),
            )
            print(f"Password updated for '{user['username']}'.")
            if not os.environ.get("LC_PASSWORD"):
                print(f"Generated password: {password}")

        elif action == "tier":
            identifier = os.environ["LC_IDENTIFIER"].strip()
            tier = os.environ["LC_TIER"].strip()
            if tier not in VALID_TIERS:
                raise ValueError(f"Invalid tier: {tier}")

            user = get_user(conn, identifier)
            if not user:
                raise ValueError("User not found.")

            conn.execute("UPDATE users SET tier = ? WHERE id = ?", (tier, user["id"]))
            print(f"Tier updated for '{user['username']}' to '{tier}'.")

        elif action == "verified":
            identifier = os.environ["LC_IDENTIFIER"].strip()
            verified = 1 if os.environ.get("LC_VERIFIED", "1") == "1" else 0

            user = get_user(conn, identifier)
            if not user:
                raise ValueError("User not found.")

            conn.execute("UPDATE users SET verified = ? WHERE id = ?", (verified, user["id"]))
            print(f"User '{user['username']}' is now {'verified' if verified else 'unverified'}.")

        else:
            raise ValueError("Unknown action.")

except sqlite3.IntegrityError as exc:
    print(f"Database error: {exc}", file=sys.stderr)
    sys.exit(1)
except Exception as exc:
    print(f"Error: {exc}", file=sys.stderr)
    sys.exit(1)
PY
}

require_container() {
  if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
    echo "Container '$CONTAINER' is not running." >&2
    echo "Start it first with: docker compose up -d" >&2
    exit 1
  fi
}

read_password() {
  local first second
  while true; do
    read -rsp "Password: " first
    echo
    read -rsp "Confirm password: " second
    echo
    if [[ "$first" != "$second" ]]; then
      echo "Passwords do not match."
      continue
    fi
    if (( ${#first} < 8 )); then
      echo "Password must be at least 8 characters."
      continue
    fi
    printf '%s' "$first"
    return
  done
}

choose_tier() {
  local tier="${1:-user}"
  while true; do
    read -rp "Tier (guest/user/extra/admin) [$tier]: " input
    tier="${input:-$tier}"
    case "$tier" in
      guest|user|extra|admin) printf '%s' "$tier"; return ;;
      *) echo "Invalid tier." ;;
    esac
  done
}

choose_verified() {
  local default="${1:-y}"
  read -rp "Verified? (y/n) [$default]: " input
  input="${input:-$default}"
  case "${input,,}" in
    y|yes) printf '1' ;;
    *) printf '0' ;;
  esac
}

create_account() {
  local username email tier verified generate password
  read -rp "Username: " username
  read -rp "Email [$username@localhost]: " email
  email="${email:-$username@localhost}"
  tier="$(choose_tier user)"
  echo
  verified="$(choose_verified y)"
  echo
  read -rp "Generate password? (y/n) [y]: " generate
  generate="${generate:-y}"

  if [[ "${generate,,}" =~ ^(y|yes)$ ]]; then
    LC_ACTION=create LC_USERNAME="$username" LC_EMAIL="$email" LC_TIER="$tier" LC_VERIFIED="$verified" run_python
  else
    password="$(read_password)"
    LC_ACTION=create LC_USERNAME="$username" LC_EMAIL="$email" LC_TIER="$tier" LC_VERIFIED="$verified" LC_PASSWORD="$password" run_python
  fi
}

change_password() {
  local identifier generate password
  read -rp "User ID, username, or email: " identifier
  read -rp "Generate password? (y/n) [y]: " generate
  generate="${generate:-y}"

  if [[ "${generate,,}" =~ ^(y|yes)$ ]]; then
    LC_ACTION=password LC_IDENTIFIER="$identifier" run_python
  else
    password="$(read_password)"
    LC_ACTION=password LC_IDENTIFIER="$identifier" LC_PASSWORD="$password" run_python
  fi
}

set_tier() {
  local identifier tier
  read -rp "User ID, username, or email: " identifier
  tier="$(choose_tier user)"
  echo
  LC_ACTION=tier LC_IDENTIFIER="$identifier" LC_TIER="$tier" run_python
}

set_verified() {
  local identifier verified
  read -rp "User ID, username, or email: " identifier
  verified="$(choose_verified y)"
  echo
  LC_ACTION=verified LC_IDENTIFIER="$identifier" LC_VERIFIED="$verified" run_python
}

require_container

while true; do
  echo
  echo "LibreCrawl account management ($CONTAINER)"
  echo "1. List users"
  echo "2. Create account"
  echo "3. Change password"
  echo "4. Set tier"
  echo "5. Set verified/unverified"
  echo "q. Quit"
  read -rp "Choice: " choice

  case "${choice,,}" in
    1) LC_ACTION=list run_python ;;
    2) create_account ;;
    3) change_password ;;
    4) set_tier ;;
    5) set_verified ;;
    q) exit 0 ;;
    *) echo "Invalid choice." ;;
  esac
done
