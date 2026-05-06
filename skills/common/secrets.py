"""
Bitwarden Password Manager backed secret store for Hermes skills.

All secrets (API keys, ID/PW, tokens) are stored in Bitwarden as Login items
and retrieved via the bw CLI.

Registration rules (see 1_myknot/design/Bitwarden運用ルール.md):
  - Item name  : service name (e.g. "Discord", "OpenAI", "GitHub")
  - Username   : client ID / username / account ID
  - Password   : API key / password / client secret / token
  - Custom fields: when 3 or more values are needed

Usage:
    from common.secrets import get_secret, create_secret, update_secret

    # Read
    key           = get_secret("OpenAI")
    client_id     = get_secret("Discord", field="username")
    client_secret = get_secret("Discord", field="password")
    app_id        = get_secret("Discord", field="app_id")

    # Create
    create_secret("NewService", password="apikey123")
    create_secret("Twitter", username="kame-dev", password="pw123")
    create_secret("Discord", custom_fields={"app_id": "x", "token": "y"})

    # Update
    update_secret("Twitter", password="new_pw456")
    update_secret("Discord", custom_fields={"token": "new_token"})
"""

import subprocess
import os
import json
import functools
import logging

logger = logging.getLogger(__name__)

_BW_BIN = "/usr/local/bin/bw"


# -- Session ------------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def _get_session() -> str:
    """Unlock the vault and return a session token (cached per process)."""
    password = os.environ.get("BW_PASSWORD", "")
    if not password:
        raise RuntimeError("BW_PASSWORD is not set in the environment")

    result = subprocess.run(
        [_BW_BIN, "unlock", "--passwordenv", "BW_PASSWORD", "--raw"],
        capture_output=True,
        text=True,
        env={**os.environ, "BW_PASSWORD": password},
    )
    session = result.stdout.strip()
    if not session:
        raise RuntimeError(f"bw unlock failed: {result.stderr.strip()}")
    return session


def clear_cache() -> None:
    """Force re-unlock on next call (e.g. after vault lock timeout)."""
    _get_session.cache_clear()


# -- Read ---------------------------------------------------------------------

def get_secret(item_name: str, field: str = "password") -> str:
    """
    Retrieve a field from a Bitwarden Login item by name.

    Args:
        item_name : Bitwarden item name (exact match, case-sensitive)
        field     : "password" (default) | "username" | "notes" | custom field name

    Returns:
        The field value as a string.

    Raises:
        RuntimeError: if the item is not found or the field is missing.
    """
    session = _get_session()

    result = subprocess.run(
        [_BW_BIN, "get", "item", item_name, "--session", session],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"bw get item '{item_name}' failed: {result.stderr.strip()}"
        )

    try:
        item = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse bw output for '{item_name}': {e}")

    if field == "password":
        return item.get("login", {}).get("password") or ""
    if field == "username":
        return item.get("login", {}).get("username") or ""
    if field == "notes":
        return item.get("notes") or ""

    for f in item.get("fields", []):
        if f.get("name") == field:
            return f.get("value") or ""

    raise RuntimeError(f"Field '{field}' not found in item '{item_name}'")


# -- Create -------------------------------------------------------------------

def create_secret(
    item_name: str,
    username: str = "",
    password: str = "",
    notes: str = "",
    custom_fields: dict = None,
) -> str:
    """
    Create a new Login item in Bitwarden.

    Args:
        item_name     : Bitwarden item name (must be unique)
        username      : username / client ID (optional)
        password      : API key / password / token (optional)
        notes         : free text notes (optional)
        custom_fields : dict of custom field name to value (optional)

    Returns:
        The created item ID.

    Raises:
        RuntimeError: if an item with the same name already exists.
    """
    session = _get_session()

    # 重複チェック
    check = subprocess.run(
        [_BW_BIN, "get", "item", item_name, "--session", session],
        capture_output=True,
        text=True,
    )
    if check.returncode == 0:
        raise RuntimeError(
            f"Item '{item_name}' already exists. Use update_secret() to modify it."
        )

    # テンプレート取得
    tmpl_result = subprocess.run(
        [_BW_BIN, "get", "template", "item", "--session", session],
        capture_output=True,
        text=True,
    )
    item = json.loads(tmpl_result.stdout)

    login_tmpl_result = subprocess.run(
        [_BW_BIN, "get", "template", "item.login", "--session", session],
        capture_output=True,
        text=True,
    )
    login = json.loads(login_tmpl_result.stdout)

    item["type"] = 1  # Login
    item["name"] = item_name
    item["notes"] = notes or None
    login["username"] = username
    login["password"] = password
    login["uris"] = []
    item["login"] = login
    item["fields"] = [
        {"name": k, "value": v, "type": 0}
        for k, v in (custom_fields or {}).items()
    ]

    encoded = subprocess.run(
        [_BW_BIN, "encode"],
        input=json.dumps(item),
        capture_output=True,
        text=True,
    )
    create_result = subprocess.run(
        [_BW_BIN, "create", "item", encoded.stdout.strip(), "--session", session],
        capture_output=True,
        text=True,
    )
    if create_result.returncode != 0:
        raise RuntimeError(f"bw create item failed: {create_result.stderr.strip()}")

    created = json.loads(create_result.stdout)
    logger.info(f"Created Bitwarden item '{item_name}' (id={created['id']})")
    return created["id"]


# -- Update -------------------------------------------------------------------

def update_secret(
    item_name: str,
    username: str = None,
    password: str = None,
    notes: str = None,
    custom_fields: dict = None,
) -> None:
    """
    Update fields of an existing Bitwarden Login item.

    Only the fields explicitly passed (not None) are updated.
    For custom_fields, only the specified keys are updated; others are preserved.

    Args:
        item_name     : Bitwarden item name (exact match, case-sensitive)
        username      : new username value (None = no change)
        password      : new password value (None = no change)
        notes         : new notes value (None = no change)
        custom_fields : dict of custom field name to value (None = no change)

    Raises:
        RuntimeError: if the item is not found.
    """
    session = _get_session()

    result = subprocess.run(
        [_BW_BIN, "get", "item", item_name, "--session", session],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"bw get item '{item_name}' failed: {result.stderr.strip()}"
        )

    item = json.loads(result.stdout)
    item_id = item["id"]

    if username is not None:
        item.setdefault("login", {})["username"] = username
    if password is not None:
        item.setdefault("login", {})["password"] = password
    if notes is not None:
        item["notes"] = notes

    if custom_fields:
        existing = {f["name"]: f for f in item.get("fields", [])}
        for k, v in custom_fields.items():
            if k in existing:
                existing[k]["value"] = v
            else:
                existing[k] = {"name": k, "value": v, "type": 0}
        item["fields"] = list(existing.values())

    encoded = subprocess.run(
        [_BW_BIN, "encode"],
        input=json.dumps(item),
        capture_output=True,
        text=True,
    )
    edit_result = subprocess.run(
        [_BW_BIN, "edit", "item", item_id, encoded.stdout.strip(), "--session", session],
        capture_output=True,
        text=True,
    )
    if edit_result.returncode != 0:
        raise RuntimeError(f"bw edit item failed: {edit_result.stderr.strip()}")

    logger.info(f"Updated Bitwarden item '{item_name}' (id={item_id})")
