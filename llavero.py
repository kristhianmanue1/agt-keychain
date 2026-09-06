#!/usr/bin/env python3
"""llavero — configuración segura de API keys para skopos (y lo que venga).

El problema que resuelve: una API key pegada en un chat con un modelo de
IA queda expuesta al proveedor de ese modelo (y al historial de la
sesión). La regla es: la key se escribe a ciegas en TU terminal, se
guarda cifrada en el Llavero de macOS, y se inyecta por entorno SOLO al
proceso que la necesita. El modelo de IA jamás la ve.

Flujo recomendado para skopos + z.ai:

  ./llavero.py perfil zai --base-url https://api.z.ai/api/paas/v4 \\
      --modelo glm-4.7 --api openai
  ./llavero.py guardar zai            # teclado oculto; nunca en chat
  ./llavero.py probar zai             # llamada mínima de verificación
  ./llavero.py ejecutar zai -- skopos watch --solo-indice

Comandos:
  guardar <servicio>   lee la key oculta (getpass) y la guarda cifrada
  ver <servicio>       confirma presencia: muestra sólo los últimos 4
  probar <servicio>    llamada mínima al proveedor; imprime OK/FALLO
  perfil <servicio>    guarda los campos NO secretos del proveedor
  ejecutar <servicio>  inyecta SKOPOS_LLM_* en el entorno y exec el comando
  borrar <servicio>    elimina la entrada del llavero de macOS

Almacén: Llavero de macOS (`security`), cifrado con tu sesión. Fallback
declarado: ninguno — sin llavero no hay llavero.

Vía automática (tests/CI): `guardar --des-entorno LLAVERO_ENTRADA` lee la
key de la variable de entorno indicada — para automatización, nunca como
excusa para pegarla en un chat.

Tradeoff declarado (v0): la key pasa por el argv de `security` durante
la escritura (ventana de visibilidad para procesos del MISMO usuario,
microsegundos). v1 podrá usar un pty para eliminarla.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request

SERVICIO = "llavero"
CONFIG_DIR = pathlib.Path.home() / ".config" / "llavero"


# --- llavero de macOS ---------------------------------------------------

def _security(*args: str, entrada_tty: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["security", *args], capture_output=True, text=True,
        check=False,
    )


def guardar_key(servicio: str, key: str, actualizar: bool = True) -> bool:
    args = ["add-generic-password", "-s", SERVICIO, "-a", servicio]
    if actualizar:
        args.append("-U")
    args += ["-w", key]
    return _security(*args).returncode == 0


def leer_key(servicio: str) -> str | None:
    r = _security("find-generic-password", "-s", SERVICIO, "-a", servicio, "-w")
    return r.stdout.strip() if r.returncode == 0 else None


def borrar_key(servicio: str) -> bool:
    return _security("delete-generic-password", "-s", SERVICIO,
                     "-a", servicio).returncode == 0


# --- perfiles (campos NO secretos) --------------------------------------

def ruta_perfil(servicio: str) -> pathlib.Path:
    return CONFIG_DIR / f"{servicio}.json"


def guardar_perfil(servicio: str, datos: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    ruta_perfil(servicio).write_text(
        json.dumps(datos, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    ruta_perfil(servicio).chmod(0o600)


def leer_perfil(servicio: str) -> dict:
    try:
        return json.loads(ruta_perfil(servicio).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


# --- comandos ------------------------------------------------------------

def cmd_guardar(servicio: str, var_entorno: str | None) -> int:
    if var_entorno:
        key = os.environ.get(var_entorno, "")
        origen = f"entorno ${var_entorno}"
    else:
        key = getpass.getpass(f"API key para '{servicio}' (entrada oculta): ")
        origen = "teclado oculto"
        if not key:
            print("llavero: vacía — nada guardado", file=sys.stderr)
            return 1
        confirmacion = getpass.getpass("repite para confirmar: ")
        if key != confirmacion:
            print("llavero: no coinciden — nada guardado", file=sys.stderr)
            return 1
    if not key:
        print("llavero: vacía — nada guardado", file=sys.stderr)
        return 1
    if not guardar_key(servicio, key):
        print("llavero: el llavero de macOS rechazó la escritura",
              file=sys.stderr)
        return 1
    print(f"llavero: guardada para '{servicio}' (origen: {origen}, "
          f"cifrada en el llavero de macOS)")
    return 0


def cmd_ver(servicio: str) -> int:
    key = leer_key(servicio)
    if key is None:
        print(f"llavero: no hay key para '{servicio}'", file=sys.stderr)
        return 1
    print(f"llavero: '{servicio}' presente — termina en …{key[-4:]} "
          f"({len(key)} caracteres)")
    return 0


def cmd_borrar(servicio: str) -> int:
    if borrar_key(servicio):
        print(f"llavero: entrada de '{servicio}' eliminada")
        return 0
    print(f"llavero: no se pudo eliminar (¿existía?)", file=sys.stderr)
    return 1


def cmd_perfil(servicio: str, args) -> int:
    datos = leer_perfil(servicio)
    for campo in ("base_url", "modelo", "api"):
        valor = getattr(args, campo.replace("-", "_"), None)
        if valor:
            datos[campo] = valor
    guardar_perfil(servicio, datos)
    print(f"llavero: perfil de '{servicio}' en {ruta_perfil(servicio)} (0600)")
    print(json.dumps(datos, ensure_ascii=False, indent=2))
    return 0


def cmd_probar(servicio: str, base_url: str | None, modelo: str | None,
               timeout: float) -> int:
    key = leer_key(servicio)
    if key is None:
        print(f"llavero: no hay key para '{servicio}'", file=sys.stderr)
        return 1
    perfil = leer_perfil(servicio)
    base_url = base_url or perfil.get("base_url")
    modelo = modelo or perfil.get("modelo")
    if not base_url or not modelo:
        print("llavero: faltan base_url/modelo — define el perfil primero "
              "(llavero.py perfil <servicio> ...)", file=sys.stderr)
        return 2
    payload = json.dumps({
        "model": modelo,
        "messages": [{"role": "user",
                      "content": "Responde únicamente: {\"ok\": true}"}],
        "stream": False,
    }).encode("utf-8")
    peticion = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            cuerpo = json.loads(respuesta.read())
    except urllib.error.HTTPError as exc:
        print(f"llavero: FALLO — el proveedor respondió HTTP {exc.code} "
              f"(key rechazada o endpoint equivocado)", file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"llavero: FALLO — sin respuesta del proveedor: {exc}",
              file=sys.stderr)
        return 1
    contenido = cuerpo.get("choices", [{}])[0].get("message", {}).get("content")
    print(f"llavero: OK — '{modelo}' respondió "
          f"({len(contenido or '')} caracteres) vía {base_url}")
    return 0


def cmd_ejecutar(servicio: str, comando: list[str]) -> int:
    key = leer_key(servicio)
    if key is None:
        print(f"llavero: no hay key para '{servicio}'", file=sys.stderr)
        return 1
    perfil = leer_perfil(servicio)
    entorno = dict(os.environ)
    entorno["SKOPOS_LLM_API"] = perfil.get("api", "openai")
    if perfil.get("base_url"):
        entorno["SKOPOS_LLM_BASE_URL"] = perfil["base_url"]
    if perfil.get("modelo"):
        entorno["SKOPOS_LLM_MODELO"] = perfil["modelo"]
    entorno["SKOPOS_LLM_API_KEY"] = key
    os.execvpe(comando[0], comando, entorno)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="llavero", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("guardar", help="lee la key oculta y la guarda cifrada")
    p.add_argument("servicio")
    p.add_argument("--des-entorno", metavar="VAR",
                   help="lee la key de esta variable de entorno (automatización)")
    p.set_defaults(func=lambda a: cmd_guardar(a.servicio, a.des_entorno))

    p = sub.add_parser("ver", help="presencia de la key: últimos 4 caracteres")
    p.add_argument("servicio")
    p.set_defaults(func=lambda a: cmd_ver(a.servicio))

    p = sub.add_parser("borrar", help="elimina la entrada")
    p.add_argument("servicio")
    p.set_defaults(func=lambda a: cmd_borrar(a.servicio))

    p = sub.add_parser("perfil", help="campos NO secretos del proveedor")
    p.add_argument("servicio")
    p.add_argument("--base-url")
    p.add_argument("--modelo")
    p.add_argument("--api", choices=["openai", "ollama"])
    p.set_defaults(func=lambda a: cmd_perfil(a.servicio, a))

    p = sub.add_parser("probar", help="llamada mínima de verificación")
    p.add_argument("servicio")
    p.add_argument("--base-url")
    p.add_argument("--modelo")
    p.add_argument("--timeout", type=float, default=30.0)
    p.set_defaults(func=lambda a: cmd_probar(a.servicio, a.base_url,
                                             a.modelo, a.timeout))

    p = sub.add_parser("ejecutar", help="inyecta SKOPOS_LLM_* y exec")
    p.add_argument("servicio")
    p.add_argument("comando", nargs="+")
    p.set_defaults(func=lambda a: cmd_ejecutar(a.servicio, a.comando))

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
