"""Neutral credential handling primitives for llavero.

This module never logs secret values.  The environment delivery mode remains a
compatibility mechanism: the consumer and its descendants can read the secret.
"""

from __future__ import annotations

import errno
import hmac
import ipaddress
import json
import os
import pathlib
import pty
import re
import select
import stat
import subprocess
import sys
import time
import tempfile
import termios
import unicodedata
import urllib.parse
import urllib.request


KEYCHAIN_SERVICE = "llavero"
SECURITY_BIN = "/usr/bin/security"
CONFIG_DIR = pathlib.Path.home() / ".config" / "llavero"
PROFILE_SCHEMA = "llavero/profile/v1"
PROVIDER_SCHEMA = "llavero/profile/v2"

_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,62}$")
_ENV_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_SENSITIVE_ENV_PATTERN = re.compile(
    r"(?:^|_)(?:API_?KEY|KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)(?:$|_)"
)
_BASE_ENVIRONMENT = {
    "HOME", "USER", "LOGNAME", "SHELL", "TMPDIR", "LANG",
    "TERM", "COLORTERM",
}
_LOCALE_ENVIRONMENT = {
    "LC_ALL", "LC_COLLATE", "LC_CTYPE", "LC_MESSAGES", "LC_MONETARY",
    "LC_NUMERIC", "LC_TIME",
}
_DANGEROUS_ENVIRONMENT = {
    "BASH_ENV", "ENV", "ZDOTDIR", "PYTHONPATH", "PYTHONHOME",
    "NODE_OPTIONS", "RUBYOPT", "PERL5OPT", "LD_PRELOAD", "LD_LIBRARY_PATH",
    "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH", "SSLKEYLOGFILE",
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
}
_PROTECTED_PUBLIC_ENV = (
    _BASE_ENVIRONMENT | _LOCALE_ENVIRONMENT | _DANGEROUS_ENVIRONMENT |
    {"PWD", "OLDPWD", "SHLVL"}
)
_SAFE_PUBLIC_ENV_SUFFIXES = {
    "API", "API_VERSION", "BASE_URL", "ENDPOINT", "MODEL", "MODEL_NAME",
    "ORG_ID", "ORGANIZATION_ID", "PROJECT_ID", "REGION",
}
_SYSTEM_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"


class LlaveroError(ValueError):
    """Expected, safely printable validation or configuration failure."""


def validate_identifier(value: str) -> str:
    if not isinstance(value, str) or not _ID_PATTERN.fullmatch(value):
        raise LlaveroError(
            "identificador inválido: usa 1-63 caracteres [a-z0-9._-] "
            "y comienza con letra o número"
        )
    return value


def validate_environment_name(value: str) -> str:
    if not isinstance(value, str) or not _ENV_PATTERN.fullmatch(value):
        raise LlaveroError(f"nombre de variable de entorno inválido: {value!r}")
    return value


def validate_secret_environment_name(value: str) -> str:
    validate_environment_name(value)
    if value in _PROTECTED_PUBLIC_ENV or not _SENSITIVE_ENV_PATTERN.search(value):
        raise LlaveroError(
            "la variable secreta debe tener un nombre de credencial explícito "
            "(*_API_KEY, *_TOKEN, *_SECRET, *_PASSWORD o *_CREDENTIAL)"
        )
    return value


def validate_public_text(field: str, value: str, max_length: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value) > max_length:
        raise LlaveroError(f"{field} debe ser texto no vacío de máximo {max_length}")
    if any(
        unicodedata.category(character) in {"Cc", "Cf", "Zl", "Zp"}
        for character in value
    ):
        raise LlaveroError(f"{field} no admite caracteres de control")
    return value


def validate_public_environment(name: str, value: str) -> tuple[str, str]:
    validate_environment_name(name)
    if name in _PROTECTED_PUBLIC_ENV:
        raise LlaveroError(f"la variable pública {name!r} está reservada")
    if _SENSITIVE_ENV_PATTERN.search(name):
        raise LlaveroError(
            f"la variable {name!r} parece secreta; usa --secret-env"
        )
    if name not in _SAFE_PUBLIC_ENV_SUFFIXES and not any(
        name.endswith(f"_{suffix}") for suffix in _SAFE_PUBLIC_ENV_SUFFIXES
    ):
        raise LlaveroError(
            f"la variable pública {name!r} no pertenece a la allowlist de configuración"
        )
    validate_public_text(f"valor de {name}", value, max_length=2048)
    return name, value


def validate_secret(secret: str) -> str:
    if not isinstance(secret, str) or not secret:
        raise LlaveroError("la credencial está vacía")
    if "\x00" in secret or "\n" in secret or "\r" in secret:
        raise LlaveroError("la credencial debe ocupar una sola línea")
    return secret


def minimal_environment() -> dict[str, str]:
    result = {
        name: value for name, value in os.environ.items()
        if name in _BASE_ENVIRONMENT or name in _LOCALE_ENVIRONMENT
    }
    result["PATH"] = _SYSTEM_PATH
    return result


def _run_security(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [SECURITY_BIN, *args],
        capture_output=True,
        text=True,
        check=False,
        env=minimal_environment(),
    )


def _write_all(fd: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        offset += os.write(fd, data[offset:])


# The helper becomes a session leader before acquiring the PTY as /dev/tty.
# No credential is present in helper arguments or environment.
_SECURITY_TTY_HELPER = """
import fcntl, os, sys, termios
fcntl.ioctl(0, termios.TIOCSCTTY, 0)
os.execv(sys.argv[1], sys.argv[1:])
"""
_SECURITY_WRITE_TIMEOUT = 30
_SECURITY_PROMPTS = (b"password data for new item:", b"retype password for new item:")


def _run_security_with_secret(args: list[str], secret: str) -> int:
    """Answer both security prompts in its own controlling terminal, without echo."""
    validate_secret(secret)
    # Bound canonical PTY input; oversized writes can otherwise block or truncate.
    encoded = secret.encode("utf-8")
    if len(encoded) > 1024:
        raise LlaveroError("credencial demasiado larga para el transporte Keychain")
    master_fd, slave_fd = pty.openpty()
    attributes = termios.tcgetattr(slave_fd)
    attributes[3] &= ~(termios.ECHO | termios.ECHONL)
    termios.tcsetattr(slave_fd, termios.TCSANOW, attributes)
    process = None
    try:
        process = subprocess.Popen(
            [sys.executable, "-I", "-c", _SECURITY_TTY_HELPER,
             SECURITY_BIN, *args, "-w"],
            stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            start_new_session=True, close_fds=True, env=minimal_environment(),
        )
        os.close(slave_fd)
        slave_fd = -1
        deadline = time.monotonic() + _SECURITY_WRITE_TIMEOUT
        pending = b""
        answered = 0
        while process.poll() is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill(); process.wait()
                return 124
            readable, _, _ = select.select([master_fd], [], [], min(remaining, 0.1))
            if not readable:
                continue
            try:
                block = os.read(master_fd, 4096)
            except OSError as exc:
                if exc.errno != errno.EIO:
                    raise
                block = b""
            if not block:
                # PTY closure may precede waitpid visibility by a few milliseconds.
                time.sleep(0.01)
                continue
            pending = (pending + block)[-4096:]
            if answered < len(_SECURITY_PROMPTS) and _SECURITY_PROMPTS[answered] in pending:
                _write_all(master_fd, encoded + b"\n")
                answered += 1
                pending = b""
        code = process.wait()
        return code if code else (0 if answered == 2 else 125)
    finally:
        if process is not None and process.poll() is None:
            process.kill(); process.wait()
        if slave_fd >= 0:
            os.close(slave_fd)
        os.close(master_fd)


def store_secret(credential_id: str, secret: str, update: bool = True) -> bool:
    validate_identifier(credential_id)
    validate_secret(secret)
    encoded = secret.encode("utf-8")
    if len(encoded) > 1024:
        raise LlaveroError("credencial demasiado larga para el transporte Keychain")
    args = [
        "add-generic-password", "-s", KEYCHAIN_SERVICE,
        "-a", credential_id,
    ]
    if update:
        args.append("-U")
    if len(encoded) > 128:
        if any(not 32 <= ord(character) <= 126 for character in secret):
            raise LlaveroError("el transporte de claves largas admite ASCII imprimible; otra lectura es ambigua")
        # security getpass trunca entradas largas. El modo -i recibe una sola
        # orden por pipe; HEX evita interpretación de comillas/control en el
        # parser. No usar shell, -v, argv secreto, quit (ocultaría el exit code).
        command = " ".join(args) + " -X " + encoded.hex() + "\n"
        try:
            result = subprocess.run(
                [SECURITY_BIN, "-i", "-q"], input=command, text=True,
                capture_output=True, check=False, timeout=_SECURITY_WRITE_TIMEOUT,
                env=minimal_environment(),
            )
            code = result.returncode
        except subprocess.TimeoutExpired:
            return False
    else:
        code = _run_security_with_secret(args, secret)
    if code != 0:
        return False
    saved = read_secret(credential_id)
    return saved is not None and hmac.compare_digest(
        saved.encode("utf-8"), secret.encode("utf-8")
    )


def read_secret(credential_id: str) -> str | None:
    validate_identifier(credential_id)
    result = _run_security(
        "find-generic-password", "-s", KEYCHAIN_SERVICE,
        "-a", credential_id, "-w",
    )
    if result.returncode != 0:
        return None
    return result.stdout.rstrip("\r\n")


def secret_exists(credential_id: str) -> bool:
    """Check presence without asking Keychain to return the secret value."""
    validate_identifier(credential_id)
    return _run_security(
        "find-generic-password", "-s", KEYCHAIN_SERVICE,
        "-a", credential_id,
    ).returncode == 0


def delete_secret(credential_id: str) -> bool:
    validate_identifier(credential_id)
    return _run_security(
        "delete-generic-password", "-s", KEYCHAIN_SERVICE,
        "-a", credential_id,
    ).returncode == 0


def profile_path(credential_id: str) -> pathlib.Path:
    validate_identifier(credential_id)
    return CONFIG_DIR / f"{credential_id}.json"


def _validate_existing_config_directory() -> None:
    try:
        metadata = CONFIG_DIR.lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISDIR(metadata.st_mode) or CONFIG_DIR.is_symlink():
        raise LlaveroError("el directorio de perfiles debe ser real, no un symlink")
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise LlaveroError(
            "el directorio de perfiles debe pertenecer al usuario y tener modo 0700"
        )


def _validate_profile(profile: dict) -> dict:
    if not isinstance(profile, dict):
        raise LlaveroError("el perfil debe ser un objeto JSON")
    allowed = {"schema", "base_url", "modelo", "api", "delivery", "provider"}
    unknown = set(profile) - allowed
    if unknown:
        raise LlaveroError(f"campos de perfil desconocidos: {sorted(unknown)}")
    schema = profile.get("schema")
    if schema is None and "delivery" in profile:
        raise LlaveroError("un perfil genérico requiere schema explícito")
    if schema is not None and schema not in (PROFILE_SCHEMA, PROVIDER_SCHEMA):
        raise LlaveroError("schema de perfil no compatible")
    if schema == PROVIDER_SCHEMA:
        if profile.get("provider") not in ("typesafe-systemone", "openai-compatible"):
            raise LlaveroError("proveedor explícito no compatible")
        if "delivery" in profile or "api" in profile:
            raise LlaveroError("v2 deriva delivery del proveedor; no admite delivery/api")
        if not profile.get("base_url") or not profile.get("modelo"):
            raise LlaveroError("v2 requiere base_url y modelo")
    elif "provider" in profile:
        raise LlaveroError("provider requiere schema v2")
    if "base_url" in profile:
        validate_endpoint(profile["base_url"])
    for field in ("modelo", "api"):
        if field in profile:
            validate_public_text(field, profile[field])
    delivery = profile.get("delivery")
    if delivery is not None:
        if not isinstance(delivery, dict):
            raise LlaveroError("delivery debe ser un objeto")
        unknown_delivery = set(delivery) - {"mode", "secret_env", "public_env"}
        if unknown_delivery:
            raise LlaveroError(
                f"campos delivery desconocidos: {sorted(unknown_delivery)}"
            )
        if delivery.get("mode") != "env":
            raise LlaveroError("Fase 1 sólo implementa delivery mode 'env'")
        validate_secret_environment_name(delivery.get("secret_env", ""))
        public_env = delivery.get("public_env", {})
        if not isinstance(public_env, dict):
            raise LlaveroError("public_env debe ser un objeto")
        for name, value in public_env.items():
            validate_public_environment(name, value)
            if name.endswith(("_BASE_URL", "_ENDPOINT")) and profile.get("base_url"):
                if validate_endpoint(value) != validate_endpoint(profile["base_url"]):
                    raise LlaveroError("destino público contradice base_url")
            if name.endswith(("_MODEL", "_MODEL_NAME")) and profile.get("modelo"):
                if value != profile["modelo"]:
                    raise LlaveroError("modelo público contradice modelo")
    return profile


def save_profile(credential_id: str, profile: dict) -> pathlib.Path:
    path = profile_path(credential_id)
    profile = dict(profile)
    profile.setdefault("schema", PROFILE_SCHEMA)
    _validate_profile(profile)
    _validate_existing_config_directory()
    CONFIG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    CONFIG_DIR.chmod(0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".profile-", dir=CONFIG_DIR)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            json.dump(profile, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory_fd = os.open(CONFIG_DIR, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return path


def load_profile(credential_id: str) -> dict:
    _validate_existing_config_directory()
    path = profile_path(credential_id)
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return {}
    if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
        raise LlaveroError("el perfil debe ser un archivo regular, no un symlink")
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise LlaveroError("el perfil debe pertenecer al usuario y tener modo 0600")
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LlaveroError("el perfil no es JSON legible") from exc
    return _validate_profile(profile)


def validate_endpoint(value: str) -> str:
    validate_public_text("base_url", value, max_length=2048)
    parsed = urllib.parse.urlsplit(value)
    if not parsed.hostname or parsed.username or parsed.password:
        raise LlaveroError("base_url requiere host y no admite credenciales")
    if parsed.query or parsed.fragment:
        raise LlaveroError("base_url no admite query ni fragment")
    try:
        port = parsed.port
    except ValueError as exc:
        raise LlaveroError("puerto inválido en base_url") from exc
    if parsed.scheme == "https":
        pass
    elif parsed.scheme == "http":
        try:
            is_loopback = ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            is_loopback = False
        if not is_loopback:
            raise LlaveroError("HTTP sólo se permite para una IP loopback")
    else:
        raise LlaveroError("base_url debe usar HTTPS o HTTP loopback")
    if port is not None and not 1 <= port <= 65535:
        raise LlaveroError("puerto fuera de rango")
    return value.rstrip("/")


def build_consumer_environment(profile: dict, secret: str) -> dict[str, str]:
    _validate_profile(profile)
    validate_secret(secret)
    environment = minimal_environment()
    if profile.get("schema") == PROVIDER_SCHEMA:
        prefix = "TYPESAFE" if profile["provider"] == "typesafe-systemone" else "OPENAI"
        environment[prefix + "_API_KEY"] = secret
        environment[prefix + "_BASE_URL"] = validate_endpoint(profile["base_url"])
        model_env = "TYPESAFE_DEFAULT_MODEL" if prefix == "TYPESAFE" else "OPENAI_MODEL"
        environment[model_env] = profile["modelo"]
        return environment
    delivery = profile.get("delivery")
    if delivery:
        environment.update(delivery.get("public_env", {}))
        environment[delivery["secret_env"]] = secret
        return environment

    # Backward-compatible Skopos adapter for pre-v1 profiles.
    environment["SKOPOS_LLM_API"] = profile.get("api", "openai")
    if profile.get("base_url"):
        environment["SKOPOS_LLM_BASE_URL"] = profile["base_url"]
    if profile.get("modelo"):
        environment["SKOPOS_LLM_MODELO"] = profile["modelo"]
    environment["SKOPOS_LLM_API_KEY"] = secret
    return environment


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects so Authorization is never replayed to another target."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
