"""Read secrets only from the project's .env file; shell values are ignored."""

from pathlib import Path

from pydantic import SecretStr

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def read_env_file(name: str, env_file: Path = ENV_FILE) -> SecretStr | None:
    if not env_file.is_file():
        return None

    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if separator and key.removeprefix("export ").strip() == name:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            return SecretStr(value)
    return None
