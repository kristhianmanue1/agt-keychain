#!/usr/bin/env python3
"""llavero — credenciales de modelos de IA para cualquier proyecto.

La credencial se captura a ciegas en la terminal, se almacena en Keychain y se
entrega según el perfil del consumidor. Fase 1 implementa `env/v1`: evita
incluir deliberadamente la credencial en prompts y configuración, pero el
proceso consumidor y sus descendientes pueden leerla.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import time
import math
import llavero_core as core
import urllib.error
import urllib.request

from llavero_core import (
    LlaveroError,
    NoRedirectHandler,
    build_consumer_environment,
    delete_secret,
    load_profile,
    profile_path,
    read_secret,
    save_profile,
    secret_exists,
    store_secret,
    validate_endpoint,
    validate_environment_name,
    validate_identifier,
    validate_public_environment,
    validate_public_text,
    validate_secret_environment_name,
)


MAX_RESPONSE_BYTES = 1024 * 1024


def cmd_store(credential_id: str, environment_source: str | None,
              replace: bool = False, icloud: bool = False) -> int:
    validate_identifier(credential_id)
    if environment_source:
        validate_environment_name(environment_source)
        secret = os.environ.pop(environment_source, "")
        source = f"entorno ${environment_source} (modo degradado)"
    else:
        if not sys.stdin.isatty():
            raise LlaveroError("captura interactiva requiere un TTY")
        secret = getpass.getpass(
            f"Credencial para '{credential_id}' (entrada oculta): "
        )
        source = "teclado oculto"
        if not secret:
            raise LlaveroError("credencial vacía — nada guardado")
        confirmation = getpass.getpass("Repite para confirmar: ")
        if secret != confirmation:
            raise LlaveroError("las entradas no coinciden — nada guardado")
    if not secret:
        raise LlaveroError("credencial vacía — nada guardado")
    if icloud and not core.sync_load_profile(credential_id):
        raise LlaveroError("crea primero el perfil en iCloud con --icloud perfil")
    exists = core.sync_secret_exists(credential_id) if icloud else secret_exists(credential_id)
    if exists and not replace:
        raise LlaveroError("ya existe: usa --replace para sustituir explícitamente")
    stored = (core.sync_store_secret(credential_id, secret, update=replace)
              if icloud else store_secret(credential_id, secret, update=replace))
    if not stored:
        raise LlaveroError("no se pudo guardar y verificar la credencial; el estado de Keychain debe comprobarse")
    print(
        f"llavero: credencial guardada para '{credential_id}' "
        f"(origen: {source}; almacén: {'iCloud' if icloud else 'local'})"
    )
    return 0


def cmd_status(credential_id: str, icloud: bool = False) -> int:
    exists = core.sync_secret_exists(credential_id) if icloud else secret_exists(credential_id)
    if not exists:
        print(
            f"llavero: no existe credencial para '{credential_id}'",
            file=sys.stderr,
        )
        return 1
    print(f"llavero: credencial presente para '{credential_id}'")
    return 0


def cmd_delete(credential_id: str, icloud: bool = False) -> int:
    deleted = core.sync_delete_secret(credential_id) if icloud else delete_secret(credential_id)
    if deleted:
        location = "iCloud (se propagará a otros dispositivos)" if icloud else "local"
        print(f"llavero: entrada {location} de '{credential_id}' eliminada")
        print("llavero: eliminar la entrada no revoca la credencial ante el proveedor")
        return 0
    print("llavero: no se pudo eliminar la entrada local", file=sys.stderr)
    return 1


def _parse_public_environment(values: list[str]) -> dict[str, str]:
    result = {}
    for item in values:
        if "=" not in item:
            raise LlaveroError("--env requiere NAME=VALUE")
        name, value = item.split("=", 1)
        validate_public_environment(name, value)
        result[name] = value
    return result


def cmd_profile(credential_id: str, args, icloud: bool = False) -> int:
    validate_identifier(credential_id)
    profile = core.sync_load_profile(credential_id) if icloud else load_profile(credential_id)
    existing_profile = bool(profile)
    for field in ("base_url", "modelo", "api"):
        value = getattr(args, field, None)
        if value:
            profile[field] = value
    provider = getattr(args, "provider", None)
    if provider:
        if args.secret_env or args.env:
            raise LlaveroError("--provider deriva variables; no combinar con --env/--secret-env")
        if existing_profile and profile.get("schema") != core.PROVIDER_SCHEMA:
            raise LlaveroError("usa un identificador nuevo para migrar un perfil v1")
        profile.update(schema=core.PROVIDER_SCHEMA, provider=provider)
    if profile.get("schema") == core.PROVIDER_SCHEMA and (args.secret_env or args.env):
        raise LlaveroError("v2 no admite variables manuales")
    if args.secret_env or args.env:
        current_delivery = profile.get("delivery", {})
        secret_env = args.secret_env or current_delivery.get("secret_env")
        if not secret_env:
            raise LlaveroError("--secret-env es obligatorio para un perfil genérico")
        validate_secret_environment_name(secret_env)
        public_env = dict(current_delivery.get("public_env", {}))
        public_env.update(_parse_public_environment(args.env))
        profile["delivery"] = {
            "mode": "env",
            "secret_env": secret_env,
            "public_env": public_env,
        }
    if icloud:
        core.sync_save_profile(credential_id, profile)
        print(f"llavero: perfil público de '{credential_id}' en iCloud Keychain")
    else:
        path = save_profile(credential_id, profile)
        print(f"llavero: perfil público de '{credential_id}' en {path} (0600)")
    print(json.dumps(profile, ensure_ascii=False, indent=2))
    return 0


def _resolved_endpoint(cli_value: str | None, profile: dict) -> str:
    configured = profile.get("base_url")
    if cli_value and configured:
        if validate_endpoint(cli_value) != validate_endpoint(configured):
            raise LlaveroError(
                "--base-url no puede ampliar o cambiar el destino del perfil"
            )
    value = cli_value or configured
    if not value:
        raise LlaveroError("falta base_url — define el perfil primero")
    return validate_endpoint(value)


def cmd_test(
    credential_id: str,
    base_url: str | None,
    model: str | None,
    timeout: float,
    icloud: bool = False,
) -> int:
    profile = core.sync_load_profile(credential_id) if icloud else load_profile(credential_id)
    endpoint = _resolved_endpoint(base_url, profile)
    if not math.isfinite(timeout) or not 0 < timeout <= 300:
        raise LlaveroError("timeout debe estar entre 0 y 300 segundos")
    if model and profile.get("modelo") and model != profile["modelo"]:
        raise LlaveroError("--modelo no puede cambiar el modelo del perfil")
    model = model or profile.get("modelo")
    if not model:
        raise LlaveroError("falta modelo — define el perfil primero")
    validate_public_text("modelo", model)
    secret = core.sync_read_secret(credential_id) if icloud else read_secret(credential_id)
    if secret is None:
        raise LlaveroError(f"no existe credencial para '{credential_id}'")
    payload_data = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": "Responde únicamente: {\"ok\": true}",
        }],
        "stream": False,
        "max_tokens": 256,
    }
    path = "/chat/completions"
    is_typesafe = profile.get("provider") == "typesafe-systemone"
    if is_typesafe:
        path = "/v1/systemone"
        payload_data = {"model": model, "state": {"color": "blue"},
                        "questions": {"color": {"type": "choice",
                            "instructions": "Which color is explicitly stated?",
                            "criteria": {"blue": "Blue", "red": "Red"}}}}
    payload = json.dumps(payload_data).encode("utf-8")
    request = urllib.request.Request(
        f"{endpoint}{path}",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {secret}",
        },
        method="POST",
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), NoRedirectHandler()
    )
    started = time.monotonic()
    try:
        with opener.open(request, timeout=timeout) as response:
            encoded_body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(encoded_body) > MAX_RESPONSE_BYTES:
                raise LlaveroError("respuesta excede el límite de 1 MiB")
            body = json.loads(encoded_body)
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            message = "redirect rechazado por política"
        else:
            message = f"proveedor respondió HTTP {exc.code}"
        print(f"llavero: FALLO — {message}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        print(
            "llavero: FALLO — proveedor inaccesible o respuesta inválida",
            file=sys.stderr,
        )
        return 1
    if not isinstance(body, dict):
        print("llavero: FALLO — respuesta JSON no es un objeto", file=sys.stderr)
        return 1
    if is_typesafe:
        try:
            answer = body["answers"]["color"]
            probabilities = answer["probabilities"]
            values = list(probabilities.values())
            confidence = answer["confidence"]
            valid = (
                set(body["answers"]) == {"color"} and answer["type"] == "choice"
                and answer["choice"] == "blue" and set(probabilities) == {"blue", "red"}
                and all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in values)
                and abs(sum(values) - 1) <= 1e-5
                and probabilities["blue"] >= probabilities["red"]
                and type(confidence) in (int, float) and math.isfinite(confidence) and 0 <= confidence <= 1
            )
            validate_public_text("modelo reportado", body["model"])
            if secret in body["model"]:
                valid = False
            usage = body.get("usage", {})
            if type(usage) is not dict:
                valid = False
            if not valid:
                raise ValueError()
        except (KeyError, TypeError, ValueError, AttributeError):
            print("llavero: FALLO — respuesta TypeSafe inválida", file=sys.stderr)
            return 1
        safe_usage = {k: v for k, v in usage.items()
                      if k in ("input_tokens", "output_tokens") and type(v) is int and v >= 0}
        print(json.dumps({"status": "ok", "protocol": "typesafe-systemone",
                          "model_requested": model, "model_reported": body["model"],
                          "seconds": round(time.monotonic() - started, 3),
                          "usage": safe_usage, "attempts": 1}))
        return 0
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        print("llavero: FALLO — respuesta sin choices", file=sys.stderr)
        return 1
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        print("llavero: FALLO — choice inválido", file=sys.stderr)
        return 1
    message = first_choice.get("message")
    if not isinstance(message, dict):
        print("llavero: FALLO — mensaje inválido", file=sys.stderr)
        return 1
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        print("llavero: FALLO — contenido vacío o inválido", file=sys.stderr)
        return 1
    print(
        f"llavero: OK — respuesta compatible recibida para '{model}' "
        f"({len(content or '')} caracteres) vía {endpoint}"
    )
    return 0


def cmd_run(credential_id: str, command: list[str], icloud: bool = False) -> int:
    executable = command[0]
    if not os.path.isabs(executable):
        raise LlaveroError("el consumidor debe indicarse con ruta absoluta")
    executable = os.path.realpath(executable)
    if not os.path.isfile(executable) or not os.access(executable, os.X_OK):
        raise LlaveroError("el consumidor no es un archivo ejecutable")
    profile = core.sync_load_profile(credential_id) if icloud else load_profile(credential_id)
    if not profile:
        raise LlaveroError("falta perfil explícito para el consumidor")
    with open(executable, "rb") as handle:
        first_line = handle.readline(512)
    if first_line.startswith(b"#!"):
        shebang = first_line[2:].strip().split(b" ", 1)[0]
        if shebang == b"/usr/bin/env" or not shebang.startswith(b"/"):
            raise LlaveroError(
                "el script consumidor requiere un intérprete absoluto, no /usr/bin/env"
            )
        interpreter = os.fsdecode(shebang)
        if not os.path.isfile(interpreter) or not os.access(interpreter, os.X_OK):
            raise LlaveroError("el intérprete del consumidor no es ejecutable")
    secret = core.sync_read_secret(credential_id) if icloud else read_secret(credential_id)
    if secret is None:
        raise LlaveroError(f"no existe credencial para '{credential_id}'")
    environment = build_consumer_environment(profile, secret)
    command = [executable, *command[1:]]
    try:
        os.execve(executable, command, environment)
    except OSError as exc:
        raise LlaveroError(
            f"no se pudo ejecutar el consumidor: {exc.strerror}"
        ) from exc


def cmd_validate(credential_id: str, icloud: bool = False) -> int:
    profile = core.sync_load_profile(credential_id) if icloud else load_profile(credential_id)
    if not profile:
        raise LlaveroError("perfil inexistente")
    print(json.dumps({"credential_id": credential_id, "valid": True,
                      "schema": profile.get("schema", "legacy"),
                      "provider": profile.get("provider", "legacy"),
                      "delivery": "env/v1"}))
    return 0


def cmd_list(icloud: bool = False) -> int:
    if icloud:
        for credential_id in core.sync_list_profiles():
            cmd_validate(credential_id, icloud=True)
        return 0
    core._validate_existing_config_directory()
    for path in sorted(core.CONFIG_DIR.glob("*.json")):
        # Do not print arbitrary filenames, values or malformed profile contents.
        try:
            validate_identifier(path.stem)
            cmd_validate(path.stem)
        except LlaveroError:
            print("llavero: perfil inválido omitido", file=sys.stderr)
            return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llavero", description=__doc__.splitlines()[0]
    )
    parser.add_argument("--icloud", action="store_true",
                        help="usa entradas sincronizables mediante el helper firmado")
    sub = parser.add_subparsers(dest="command_name", required=True)

    command = sub.add_parser("listar", help="lista perfiles públicos sin consultar secretos")
    command.set_defaults(function=lambda args: cmd_list(args.icloud))
    command = sub.add_parser("validar", help="valida configuración sin red ni Keychain")
    command.add_argument("credential_id")
    command.set_defaults(function=lambda args: cmd_validate(args.credential_id, args.icloud))

    command = sub.add_parser("guardar", help="captura y almacena una credencial")
    command.add_argument("credential_id")
    command.add_argument(
        "--des-entorno", metavar="VAR",
        help="importa desde una variable (modo degradado para migración/CI)",
    )
    command.add_argument("--replace", action="store_true", help="sustituye una entrada existente")
    command.set_defaults(
        function=lambda args: cmd_store(args.credential_id, args.des_entorno, args.replace, args.icloud)
    )

    command = sub.add_parser("ver", help="confirma presencia sin revelar metadatos")
    command.add_argument("credential_id")
    command.set_defaults(function=lambda args: cmd_status(args.credential_id, args.icloud))

    command = sub.add_parser("borrar", help="elimina la entrada local")
    command.add_argument("credential_id")
    command.set_defaults(function=lambda args: cmd_delete(args.credential_id, args.icloud))

    command = sub.add_parser("perfil", help="configura datos públicos del consumidor")
    command.add_argument("credential_id")
    command.add_argument("--base-url")
    command.add_argument("--modelo")
    command.add_argument("--provider", choices=["typesafe-systemone", "openai-compatible"])
    command.add_argument("--api", choices=["openai", "ollama"])
    command.add_argument(
        "--secret-env",
        help="variable que recibirá la credencial, por ejemplo OPENAI_API_KEY",
    )
    command.add_argument(
        "--env", action="append", default=[], metavar="NAME=VALUE",
        help="variable pública explícita; repetible",
    )
    command.set_defaults(function=lambda args: cmd_profile(args.credential_id, args, args.icloud))

    command = sub.add_parser("probar", help="prueba el protocolo configurado, una llamada sin reintentos")
    command.add_argument("credential_id")
    command.add_argument("--base-url")
    command.add_argument("--modelo")
    command.add_argument("--timeout", type=float, default=30.0)
    command.set_defaults(function=lambda args: cmd_test(
        args.credential_id, args.base_url, args.modelo, args.timeout, args.icloud
    ))

    command = sub.add_parser("ejecutar", help="ejecuta con delivery env/v1")
    command.add_argument("credential_id")
    command.add_argument("consumer_command", nargs="+")
    command.set_defaults(function=lambda args: cmd_run(
        args.credential_id, args.consumer_command, args.icloud
    ))
    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.function(args)
    except LlaveroError as exc:
        print(f"llavero: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
