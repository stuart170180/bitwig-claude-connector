"""Anthropic API key in Windows Credential Manager (keyring); ANTHROPIC_API_KEY in the environment wins. Never written to a file or log."""
import os

SERVICE, USER = "bitwig-remote", "anthropic-api-key"


def get():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    try:
        import keyring
        return keyring.get_password(SERVICE, USER)
    except Exception:  # noqa: BLE001
        return None


def put(key: str):
    import keyring
    keyring.set_password(SERVICE, USER, key.strip())


def clear():
    try:
        import keyring
        keyring.delete_password(SERVICE, USER)
    except Exception:  # noqa: BLE001
        pass
