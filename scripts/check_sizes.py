#!/usr/bin/env python3
"""Gate de estructura y tamaños de Skevi.

La polaridad es cerrada: todo archivo de texto queda sujeto a un límite salvo
una exención explícita. También falla si falta un archivo canónico o aparece
Markdown operativo suelto en la raíz.

Copiable sin edición a un proyecto adoptante: si su estructura de archivos
canónicos, límites o exenciones difiere de la de Skevi, declara
`skevi-gate.json` en la raíz en vez de editar este script (ADR-006).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path


# Identidad de esta copia del gate (ADR-027). Skevi no puede avisar a un
# adoptante de que existe una versión nueva: el manifiesto le prohíbe observar
# proyectos ajenos. Lo que sí puede es que la copia diga quién es y cuántos
# días tiene, en la salida que el adoptante ya ejecuta. Al cambiar el
# comportamiento del gate se sube GATE_VERSION y se pone la fecha del cambio.
GATE_VERSION = "gate/v8"
GATE_GENERATED_AT = "2026-09-18"
GATE_STALE_AFTER_DAYS = 90

ROOT = Path(__file__).resolve().parent.parent
ROOT_MARKDOWN = {"AGENTS.md", "CLAUDE.md", "README.md"}
REQUIRED = {
    "AGENTS.md",
    "README.md",
    "docs/estandar-diseno-software-github.md",
    "docs/ai-agent-guide/00-INDICE.md",
    "docs/ai-agent-guide/01-analisis-y-requerimientos.md",
    "docs/ai-agent-guide/02-specs-adr-contratos.md",
    "docs/ai-agent-guide/03-cascaron-proyecto.md",
    "docs/ai-agent-guide/04-ejecucion-y-verificacion.md",
    "scripts/check_sizes.py",
    "templates/skevi/registro-contexto.md",
    "templates/skevi/plan-de-implementacion.md",
    "templates/skevi/usage-guide.md",
    "templates/skevi/architecture-overview.md",
}
SKIP_DIRS = {
    ".an-kla",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "data",
    "datos",
    "dist",
    "generated",
    "node_modules",
    "vendor",
}
EXEMPT_SUFFIXES = {
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".lock",
    ".pdf",
    ".png",
    ".pyc",
    ".svg",
    ".tar",
    ".woff",
    ".woff2",
    ".zip",
}
EXEMPT_PATHS: set[str] = set()
# Exención por nombre exacto de archivo (ADR-030): basura que Git no
# versiona, sin declarar su ruta una a una.
EXEMPT_NAMES: set[str] = set()
# Basura del SO que el listado ignora; cerrada, nunca config (issue #59).
LISTING_JUNK = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})
# Presupuesto de la ruta de lectura obligatoria (ADR-021). Vacío =
# inactivo: §3.4 acota cada archivo por separado, y hasta ADR-021
# nada acotaba la suma que un ejecutor debe leer antes de actuar.
READING_PATH: dict = {}
# Ocupación medida en la última corrida; None si el presupuesto está inactivo.
READING_PATH_OBSERVED: int | None = None
LIMITS = {
    "AGENTS.md": 200,
    "README.md": 300,
}
DEFAULT_LIMIT = 800
TEMPLATE_PREFIX = "templates/"
TEMPLATE_LIMIT = 300

# Manifiesto de plantillas (#28 D1 + enmiendas T09, ADR-020): esquema
# cerrado, listado exacto de templates/skevi/ y digests vigentes. Condicional
# a la existencia del MANIFEST: un adoptante sin templates/skevi/ — o con un
# templates/skevi/ previo a este cambio — no se ve afectado; la exigencia
# canónica de Skevi sobre sí mismo vive en su `skevi-gate.json` (`required`),
# no en estos valores por defecto.
TEMPLATE_MANIFEST_NAME = "MANIFEST.json"
TEMPLATE_MANIFEST_SCHEMA = "skevi/template-manifest/v1"
# Segunda familia (ADR-028): mismo check_template_manifest, sobre scripts/
# en vez de templates/skevi/, validación estricta por directorio.
SCRIPT_MANIFEST_SCHEMA = "skevi/script-manifest/v1"
# Tercera familia (ADR-032): el canon normativo (estándar + guía) con
# digests en docs/MANIFEST.json; sin listado de directorio, porque docs/
# anida subdirectorios y el contrato de ADR-020 es plano por diseño.
CORPUS_MANIFEST_SCHEMA = "skevi/corpus-manifest/v1"
# Namespace por esquema (ADR-028), simétrico con check_templates.py.
SCHEMA_NAMESPACE = {
    TEMPLATE_MANIFEST_SCHEMA: "plantillas",
    SCRIPT_MANIFEST_SCHEMA: "gate",
    CORPUS_MANIFEST_SCHEMA: "corpus",
}
TEMPLATE_MANIFEST_KEYS = {"schema", "version", "generated_at", "files",
                          "history"}
TEMPLATE_HISTORY_KEYS = {"from", "to", "breaking", "changes"}
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
# Cubre "plantillas/v1" (ADR-020) y "gate/v2" (ADR-028) con una expresión.
MANIFEST_VERSION_RE = re.compile(r"^[a-z]+/v\d+(\.\d+)*$")

# Instantánea de los valores de Skevi, congelada al importar el módulo, antes
# de que ninguna configuración de proyecto pueda tocarlos. `main()` restaura
# desde aquí en cada invocación: si alguna vez se llama dos veces en el mismo
# proceso (tests, un orquestador), la segunda no hereda la config de la
# primera por acumulación silenciosa.
_SKEVI_DEFAULTS = {
    "ROOT_MARKDOWN": frozenset(ROOT_MARKDOWN),
    "REQUIRED": frozenset(REQUIRED),
    "SKIP_DIRS": frozenset(SKIP_DIRS),
    "EXEMPT_PATHS": frozenset(EXEMPT_PATHS),
    "EXEMPT_NAMES": frozenset(EXEMPT_NAMES),
    "READING_PATH": dict(READING_PATH),
    "LIMITS": dict(LIMITS),
    "DEFAULT_LIMIT": DEFAULT_LIMIT,
}


def reset_to_skevi_defaults() -> None:
    """Restaura el estado de módulo a los valores de Skevi, antes de leer
    la configuración del proyecto. Ver `_SKEVI_DEFAULTS`."""
    global DEFAULT_LIMIT
    ROOT_MARKDOWN.clear()
    ROOT_MARKDOWN.update(_SKEVI_DEFAULTS["ROOT_MARKDOWN"])
    REQUIRED.clear()
    REQUIRED.update(_SKEVI_DEFAULTS["REQUIRED"])
    SKIP_DIRS.clear()
    SKIP_DIRS.update(_SKEVI_DEFAULTS["SKIP_DIRS"])
    EXEMPT_PATHS.clear()
    EXEMPT_PATHS.update(_SKEVI_DEFAULTS["EXEMPT_PATHS"])
    EXEMPT_NAMES.clear()
    EXEMPT_NAMES.update(_SKEVI_DEFAULTS["EXEMPT_NAMES"])
    READING_PATH.clear()
    READING_PATH.update(_SKEVI_DEFAULTS["READING_PATH"])
    LIMITS.clear()
    LIMITS.update(_SKEVI_DEFAULTS["LIMITS"])
    DEFAULT_LIMIT = _SKEVI_DEFAULTS["DEFAULT_LIMIT"]


# Configuración del proyecto adoptante. Los valores de arriba son los de Skevi
# sobre sí mismo; un proyecto que adopta el gate declara los suyos aquí, por
# escrito, conforme a §3.4 del estándar: heredar el valor por defecto sin
# decidirlo es aceptable, cambiarlo en silencio no lo es.
CONFIG_NAME = "skevi-gate.json"
CONFIG_KEYS = {
    "limits", "default_limit", "exempt_paths", "exempt_names", "required",
    "skip_dirs", "root_markdown", "plans", "reading_path", "reports",
}
# "plans" la consume scripts/check_plans.py (gate estructural de planes,
# ADR-014) y "reports" scripts/check_reports.py (gate de reportes de dos
# capas, ADR-022): misma config, polaridad cerrada compartida — ausente =
# inactivo. Un check_sizes desactualizado las rechaza con BLOQ en vez de
# ignorarlas, que es el efecto buscado.


class _ConfigError(ValueError):
    """Diagnóstico interno con constantes/campos conocidos, nunca payload.

    Procedencia: ADR-007 y SPEC-AUD-02. Conserva compatibilidad con quienes
    capturan ValueError; sólo esta variante admite mostrar su mensaje.
    """


def _resolve_project_path(value: object) -> Path | None:
    """Resuelve `value` contra ROOT; None si no es texto, es absoluta,
    empieza por `~` o escapa de ROOT. No exige que el archivo exista: los
    elementos de `required` se declaran antes de comprobarse."""
    if not isinstance(value, str) or value.startswith("/") or value.startswith("~"):
        return None
    candidate = (ROOT / value).resolve()
    try:
        candidate.relative_to(ROOT.resolve())
    except ValueError:
        return None
    return candidate


def _safe_relative_paths(field: str, values: object) -> list[str]:
    """Valida una lista de rutas de `skevi-gate.json`: relativas, dentro de
    ROOT. Rechaza absolutas y saltos hacia fuera (`../..`), con la misma
    frontera que `_resolve_registry_path` aplica al bloque de registro."""
    if not isinstance(values, list):
        raise _ConfigError(f"{CONFIG_NAME}: «{field}» debe ser una lista de rutas")
    safe: list[str] = []
    for value in values:
        if _resolve_project_path(value) is None:
            raise _ConfigError(
                f"{CONFIG_NAME}: «{field}» tiene una ruta inválida "
                "(debe ser relativa a la raíz del proyecto)"
            )
        safe.append(value)
    return safe


def _string_list(field: str, values: object) -> list[str]:
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise _ConfigError(f"{CONFIG_NAME}: «{field}» debe ser una lista de texto")
    return values


def _exempt_names(field: str, values: object) -> list[str]:
    """Nombre de archivo sin ruta (ADR-030); para rutas, «exempt_paths»."""
    names = _string_list(field, values)
    if any(not n or n in {".", ".."} or "/" in n or "\\" in n for n in names):
        raise _ConfigError(
            f"{CONFIG_NAME}: «{field}» sólo admite nombres de archivo sin "
            "ruta; para exentar una ruta usa «exempt_paths»"
        )
    return names


def _reading_path(values: object) -> dict:
    """Valida la clave `reading_path` de `skevi-gate.json` (ADR-021).

    Polaridad cerrada como el resto de la config: subclave desconocida,
    límite no entero o ruta que escapa la raíz fallan en vez de ignorarse.
    Un typo no puede apagar el presupuesto en silencio — mismo criterio que
    `plans` en scripts/check_plans.py.
    """
    if not isinstance(values, dict):
        raise _ConfigError(
            f"{CONFIG_NAME}: «reading_path» debe ser un objeto con "
            "«limit» y «files»"
        )
    unknown = sorted(set(values) - {"limit", "files", "worst_case_of"})
    if unknown:
        raise _ConfigError(
            f"{CONFIG_NAME}: «reading_path» sólo admite «limit», «files» "
            "y «worst_case_of»"
        )
    if "limit" not in values or "files" not in values:
        raise _ConfigError(
            f"{CONFIG_NAME}: «reading_path» exige «limit» y «files»"
        )
    limit = values["limit"]
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        raise _ConfigError(
            f"{CONFIG_NAME}: «reading_path.limit» debe ser un entero positivo"
        )
    files = _safe_relative_paths("reading_path.files", values["files"])
    if not files:
        raise _ConfigError(
            f"{CONFIG_NAME}: «reading_path.files» no puede estar vacía"
        )
    resultado = {"limit": limit, "files": files}
    if "worst_case_of" in values:
        alternativas = _safe_relative_paths(
            "reading_path.worst_case_of", values["worst_case_of"]
        )
        if not alternativas:
            raise _ConfigError(
                f"{CONFIG_NAME}: «reading_path.worst_case_of» no puede "
                "estar vacía"
            )
        resultado["worst_case_of"] = alternativas
    return resultado


def load_config() -> dict:
    """Lee `skevi-gate.json` de la raíz si existe. Ausente = valores de Skevi.

    Polaridad cerrada: una clave desconocida falla en vez de ignorarse, para
    que un error de escritura sea detectable y no silencioso.
    """
    path = ROOT / CONFIG_NAME
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise _ConfigError(f"{CONFIG_NAME}: la raíz debe ser un objeto")
    unknown = sorted(set(data) - CONFIG_KEYS)
    if unknown:
        raise _ConfigError(
            f"{CONFIG_NAME}: claves desconocidas; permitidas: "
            + ", ".join(sorted(CONFIG_KEYS))
        )
    return data


def apply_config(config: dict) -> None:
    """Aplica la configuración del proyecto sobre los valores de Skevi.

    Dos semánticas distintas, a propósito. `limits`, `exempt_paths`,
    `skip_dirs` y `root_markdown` se **añaden** a los de Skevi: un proyecto
    que declara un límite propio no pierde los de `AGENTS.md`/`README.md`, y
    una exención no borra las que ya existían. `required` en cambio
    **reemplaza**: la lista de archivos canónicos de Skevi
    (`docs/estandar-diseno-software-github.md`, la guía en inglés, las
    plantillas) sólo tiene sentido dentro de este repositorio; un proyecto
    adoptante con otra estructura de directorios — como `an-kla-memory`, que
    usa `docs/architecture/`— declara la suya.

    Entradas mal tipadas producen `ValueError`: main las convierte en BLOQ,
    sin traceback (ADR-007).
    """
    global DEFAULT_LIMIT
    if "limits" in config:
        raw = config["limits"]
        if not isinstance(raw, dict):
            raise _ConfigError(f"{CONFIG_NAME}: «limits» debe ser un objeto")
        for name, value in raw.items():
            if not isinstance(value, int) or isinstance(value, bool):
                raise _ConfigError(
                    f"{CONFIG_NAME}: cada valor de «limits» debe ser un entero"
                )
            LIMITS[str(name)] = value
    if "default_limit" in config:
        value = config["default_limit"]
        if not isinstance(value, int) or isinstance(value, bool):
            raise _ConfigError(f"{CONFIG_NAME}: «default_limit» debe ser un entero")
        DEFAULT_LIMIT = value
    if "exempt_paths" in config:
        EXEMPT_PATHS.update(_safe_relative_paths("exempt_paths", config["exempt_paths"]))
    if "exempt_names" in config:
        EXEMPT_NAMES.update(_exempt_names("exempt_names", config["exempt_names"]))
    if "required" in config:
        REQUIRED.clear()
        REQUIRED.update(_safe_relative_paths("required", config["required"]))
    if "skip_dirs" in config:
        SKIP_DIRS.update(_string_list("skip_dirs", config["skip_dirs"]))
    if "root_markdown" in config:
        ROOT_MARKDOWN.update(_string_list("root_markdown", config["root_markdown"]))
    if "reading_path" in config:
        READING_PATH.update(_reading_path(config["reading_path"]))


def limit_for(name: str) -> int:
    if name in LIMITS:
        return LIMITS[name]
    if name.startswith(TEMPLATE_PREFIX):
        return TEMPLATE_LIMIT
    return DEFAULT_LIMIT


REGISTRY_START_RE = re.compile(r"^<!--\s*skevi:registry:start\s*-->$", re.IGNORECASE)
REGISTRY_END_RE = re.compile(r"^<!--\s*skevi:registry:end\s*-->$", re.IGNORECASE)
REGISTRY_HOSTS = {"AGENTS.md", "CLAUDE.md"}


def _resolve_registry_path(value: str) -> Path | None:
    """Resuelve `value` contra ROOT; None si es absoluta o escapa de ROOT."""
    if value.startswith("/") or value.startswith("~"):
        return None
    candidate = (ROOT / value).resolve()
    try:
        candidate.relative_to(ROOT.resolve())
    except ValueError:
        return None
    return candidate


def check_registry_block(relative: Path, text: str) -> list[str]:
    """Valida el bloque delimitado de §3.5 si el archivo lo trae."""
    if relative.name not in REGISTRY_HOSTS:
        return []

    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if REGISTRY_START_RE.match(line.strip())]
    ends = [i for i, line in enumerate(lines) if REGISTRY_END_RE.match(line.strip())]

    if not starts and not ends:
        return []
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        return [f"{relative}: bloque skevi:registry con delimitadores desbalanceados"]

    failures: list[str] = []
    raw_body = [line.strip() for line in lines[starts[0] + 1 : ends[0]] if line.strip()]
    body = [line for line in raw_body if not line.startswith((";", "#"))]

    if not body or body[0] != "[skevi]":
        failures.append(f"{relative}: bloque skevi:registry sin sección [skevi]")
        entries = body
    else:
        entries = body[1:]
        if any(line == "[skevi]" for line in entries):
            failures.append(f"{relative}: bloque skevi:registry con sección [skevi] duplicada")
            entries = [line for line in entries if line != "[skevi]"]

    if not entries:
        failures.append(f"{relative}: bloque skevi:registry sin entradas")

    for line in entries:
        if "=" not in line:
            failures.append(f"{relative}: línea de registro inválida: {line!r}")
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not key or not value:
            failures.append(f"{relative}: línea de registro inválida: {line!r}")
            continue
        target = _resolve_registry_path(value)
        if target is None:
            failures.append(
                f"{relative}: skevi:registry.{key} usa ruta fuera de la raíz del "
                f"proyecto: {value}"
            )
        elif not target.is_file():
            failures.append(
                f"{relative}: skevi:registry.{key} apunta a ruta inexistente: {value}"
            )
    return failures


def _check_namespace(version, expected_schema: str, where: str) -> str | None:
    if not isinstance(version, str):
        return None
    # Fail-closed: esquema sin namespace registrado es olvido de
    # mantenimiento, no motivo para omitir la comprobación.
    expected_namespace = SCHEMA_NAMESPACE.get(expected_schema)
    if expected_namespace is None:
        return f"{where}: {expected_schema} no tiene namespace registrado"
    if version.startswith(expected_namespace + "/"):
        return None
    return (f"{where}: version «{version}» no corresponde al espacio de "
            f"nombres de {expected_schema} (se espera {expected_namespace}/vN)")


def _validate_template_manifest(
    data, label: str, expected_schema: str = TEMPLATE_MANIFEST_SCHEMA
) -> list[str]:
    """Esquema cerrado del MANIFEST (formato de ADR-020, familias en ADR-028).
    Falla por campo, con motivo fijo, sin volcar contenido. Validación
    estricta: cada manifiesto se valida contra un único esquema esperado,
    no contra cualquiera que Skevi reconozca — un manifiesto de scripts no
    puede colarse donde se espera uno de plantillas."""
    failures: list[str] = []
    if not isinstance(data, dict):
        return [f"{label}: la raíz debe ser un objeto"]
    missing = sorted(TEMPLATE_MANIFEST_KEYS - set(data))
    if missing:
        return [f"{label}: campos obligatorios ausentes: {', '.join(missing)}"]
    if data.get("schema") != expected_schema:
        failures.append(
            f"{label}: schema desconocido (se espera {expected_schema})"
        )
    unknown = sorted(set(data) - TEMPLATE_MANIFEST_KEYS)
    if unknown:
        failures.append(
            f"{label}: campo desconocido: {', '.join(unknown)}"
        )
        return failures
    if not isinstance(data["version"], str) \
            or not MANIFEST_VERSION_RE.match(data["version"]):
        failures.append(f"{label}: version no coincide con <namespace>/v<n>")
    else:
        ns_fallo = _check_namespace(data["version"], expected_schema, label)
        if ns_fallo:
            failures.append(ns_fallo)
    if not isinstance(data["generated_at"], str) or not data["generated_at"]:
        failures.append(f"{label}: generated_at debe ser texto con fecha")
    if not isinstance(data["files"], dict) or not data["files"]:
        failures.append(
            f"{label}: files debe ser un objeto con entradas"
        )
        return failures
    for name, digest in data["files"].items():
        if not isinstance(digest, str) or not DIGEST_RE.match(digest):
            failures.append(
                f"{label}: files.{name} no es un digest con formato "
                "sha256:<hex>"
            )
    if not isinstance(data["history"], list):
        failures.append(f"{label}: history debe ser una lista")
        return failures
    for index, jump in enumerate(data["history"]):
        where = f"{label}: history[{index}]"
        if not isinstance(jump, dict) or set(jump) != TEMPLATE_HISTORY_KEYS:
            failures.append(
                f"{where} debe tener exactamente from/to/breaking/changes"
            )
            continue
        for extremo in ("from", "to"):
            valor = jump[extremo]
            if extremo == "from" and valor is None:
                continue
            if not isinstance(valor, str) or not MANIFEST_VERSION_RE.match(valor):
                failures.append(f"{where}.{extremo} no es una versión válida")
                continue
            ns_fallo = _check_namespace(valor, expected_schema, f"{where}.{extremo}")
            if ns_fallo:
                failures.append(ns_fallo)
        if not isinstance(jump["breaking"], bool):
            failures.append(f"{where}.breaking debe ser booleano")
        if not isinstance(jump["changes"], dict):
            failures.append(f"{where}.changes debe ser un objeto")
            continue
        for name, summary in jump["changes"].items():
            if not isinstance(summary, str):
                failures.append(f"{where}.changes.{name} debe ser texto")
    return failures


def check_template_manifest(
    manifest_path: Path,
    templates_dir: Path,
    expected_schema: str = TEMPLATE_MANIFEST_SCHEMA,
    verify_listing: bool = True,
) -> list[str]:
    """Valida un MANIFEST fuente de Skevi (#28 D1 + T09; familias ADR-028 y
    ADR-032): esquema cerrado, digests vigentes y —para las familias planas—
    listado exacto del directorio. Fail-closed, sin tracebacks."""
    # Bajo ROOT: etiqueta real ("scripts/..."). Fuera de ROOT (tests): se
    # degrada al nombre del directorio.
    try:
        dir_label = templates_dir.relative_to(ROOT).as_posix()
    except ValueError:
        dir_label = templates_dir.name
    label = f"{dir_label}/{TEMPLATE_MANIFEST_NAME}"
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return [f"{label}: contenido no válido como UTF-8"]
    except OSError:
        return [f"{label}: no se pudo leer el archivo"]
    except json.JSONDecodeError as exc:
        return [
            f"{label}: JSON inválido (línea {exc.lineno}, columna {exc.colno})"
        ]
    except RecursionError:
        return [f"{label}: JSON inválido o demasiado anidado"]
    failures = _validate_template_manifest(data, label, expected_schema)
    if failures:
        return failures
    if not verify_listing:
        # Familia corpus (ADR-032): se verifica el digest de cada archivo
        # declarado, con ruta relativa al directorio del manifiesto y sin
        # escapar de la raíz. Un archivo ausente es fallo, nunca omisión.
        for name, digest in data["files"].items():
            candidate = manifest_path.parent / name
            try:
                candidate.resolve().relative_to(ROOT.resolve())
            except ValueError:
                failures.append(
                    f"{label}: files.{name} escapa de la raíz del proyecto"
                )
                continue
            try:
                observed = "sha256:" + hashlib.sha256(
                    candidate.read_bytes()
                ).hexdigest()
            except OSError:
                failures.append(f"{label}: no se pudo leer {name}")
                continue
            if observed != digest:
                failures.append(
                    f"{label}: digest desactualizado para {name} "
                    "(¿cambió el canon sin bump?)"
                )
        return failures
    try:
        entries = sorted(templates_dir.iterdir(), key=lambda path: path.name)
    except OSError:
        return [f"{label}: no se pudo leer {dir_label}/"]
    on_disk = []
    for path in entries:
        if not path.is_file():
            continue
        if path.name == TEMPLATE_MANIFEST_NAME:
            continue
        if path.is_symlink():
            # Los symlinks no se siguen: la frontera de raíz vale también
            # para el listado de plantillas (ronda adversarial, LOW).
            failures.append(
                f"{label}: symlink no permitido en {dir_label}/: {path.name}"
            )
            continue
        if path.name not in LISTING_JUNK or path.name in data["files"]:
            on_disk.append(path.name)
    listed = sorted(data["files"])
    if listed != on_disk:
        missing = sorted(set(on_disk) - set(listed))
        extra = sorted(set(listed) - set(on_disk))
        if missing:
            failures.append(
                f"{label}: archivos sin entrada en el manifiesto: "
                + ", ".join(missing)
            )
        if extra:
            failures.append(
                f"{label}: entradas sin archivo real: " + ", ".join(extra)
            )
        return failures
    for name, digest in data["files"].items():
        try:
            actual = "sha256:" + hashlib.sha256(
                (templates_dir / name).read_bytes()
            ).hexdigest()
        except OSError:
            failures.append(f"{label}: no se pudo leer {name}")
            continue
        if digest != actual:
            failures.append(
                f"{label}: digest desactualizado para {name} "
                "(¿cambió la plantilla sin bump?)"
            )
    return failures


def discover() -> list[Path]:
    paths: list[Path] = []
    for path in ROOT.rglob("*"):
        # Los symlinks no se siguen: la frontera de raíz vale también para el
        # listado. Sin esto el gate medía y reportaba el tamaño de un archivo
        # ajeno al repositorio, y el nombre del enlace bastaba para inferirlo.
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in relative.parts[:-1]):
            continue
        paths.append(relative)
    return sorted(paths)


def count_text_lines(relative: Path) -> int | None:
    """None significa exención; los errores de lectura los reporta main.

    Procedencia: estándar §3.4 y ADR-007; una lectura fallida no acredita
    tamaño ni permite omitir el archivo como si estuviera exento.
    """
    if relative.as_posix() in EXEMPT_PATHS:
        return None
    if relative.name in EXEMPT_NAMES:
        return None
    if relative.suffix.lower() in EXEMPT_SUFFIXES:
        return None
    text = (ROOT / relative).read_text(encoding="utf-8")
    return len(text.splitlines())


def check_corpus_manifest(manifest_path: Path) -> list[str]:
    """Familia corpus (ADR-032): docs/MANIFEST.json declara el canon
    (estándar + guía) y aquí se verifica su estructura y sus digests, sin
    listado de directorio — docs/ anida subdirectorios y el contrato de
    ADR-020 es plano por diseño."""
    return check_template_manifest(
        manifest_path, manifest_path.parent,
        expected_schema=CORPUS_MANIFEST_SCHEMA, verify_listing=False)


def check_reading_path() -> list[str]:
    """Suma las líneas de la ruta de lectura obligatoria (ADR-021).

    Un archivo ausente o ilegible no acredita tamaño cero: es un fallo, con
    la misma lógica que `count_text_lines` aplica a la exención (ADR-007).
    Nunca vuelca la excepción: puede llevar rutas o datos del host.
    """
    global READING_PATH_OBSERVED
    READING_PATH_OBSERVED = None
    if not READING_PATH:
        return []
    failures: list[str] = []

    def contar(name: str) -> int | None:
        path = ROOT / name
        if not path.is_file():
            failures.append(f"ruta de lectura obligatoria: falta {name}")
            return None
        try:
            return len(path.read_text(encoding="utf-8").splitlines())
        except UnicodeDecodeError:
            failures.append(
                f"ruta de lectura obligatoria: {name} no es UTF-8 válido"
            )
        except OSError:
            failures.append(
                f"ruta de lectura obligatoria: no se pudo leer {name}"
            )
        return None

    total = 0
    for name in READING_PATH["files"]:
        observado = contar(name)
        if observado is not None:
            total += observado
    # De las alternativas sólo cuenta la mayor: son excluyentes entre sí —
    # un ejecutor lee el archivo de la fase en la que está, no las cinco.
    alternativas = [
        observado
        for name in READING_PATH.get("worst_case_of", [])
        if (observado := contar(name)) is not None
    ]
    if alternativas:
        total += max(alternativas)
    if failures:
        return failures
    limit = READING_PATH["limit"]
    if total > limit:
        failures.append(
            f"ruta de lectura obligatoria: {total} líneas > límite {limit}"
        )
    else:
        # La norma (§3.4 y ADR-025) delega en el gate la cifra vigente; si
        # sólo se emitiera al fallar, el trinquete no sería auditable sin un
        # script ad-hoc. Se publica aparte, no dentro de READING_PATH: ese
        # dict modela la configuración del adoptante y no debe llevar estado
        # de salida.
        READING_PATH_OBSERVED = total
    return failures


def gate_staleness(hoy: date | None = None) -> str | None:
    """Aviso de vejez de esta copia, o None si aún no lo amerita.

    Dice «soy vieja», nunca «existe una nueva»: lo segundo exigiría observar
    el origen, y `project-manifest.yaml` §no_ofrece lo cede. Un adoptante que
    ve la edad decide si comprobar; el gate no decide por él, ni falla por
    ello — la polaridad de aviso la hereda de ADR-020.
    """
    hoy = hoy or date.today()
    try:
        generado = date.fromisoformat(GATE_GENERATED_AT)
    except (ValueError, TypeError):
        # Constante mal editada al copiar —formato roto, comillas borradas—:
        # la identidad de la copia no es frontera de seguridad y no puede
        # tumbar el gate de nadie.
        return None
    dias = (hoy - generado).days
    if dias < GATE_STALE_AFTER_DAYS:
        return None
    return (
        f"AVISO: esta copia del gate ({GATE_VERSION}, {GATE_GENERATED_AT}) "
        f"tiene {dias} días. Comprueba contra su origen si sigue vigente; "
        "este gate no consulta la red ni observa el repositorio de origen."
    )


def main() -> int:
    failures: list[str] = []

    config_error = None
    try:
        reset_to_skevi_defaults()
        apply_config(load_config())
    except _ConfigError as exc:
        config_error = str(exc)
    except UnicodeDecodeError:
        config_error = f"{CONFIG_NAME}: contenido no válido como UTF-8"
    except json.JSONDecodeError as exc:
        config_error = (
            f"{CONFIG_NAME}: JSON inválido "
            f"(línea {exc.lineno}, columna {exc.colno})"
        )
    except OSError:
        config_error = f"{CONFIG_NAME}: no se pudo leer la configuración"
    except ValueError:
        config_error = f"{CONFIG_NAME}: valor no válido en la configuración"
    if config_error is not None:
        print("BLOQ — check_sizes encontró configuración inválida")
        print(f"- {config_error}")
        return 1

    for relative in sorted(REQUIRED):
        if not (ROOT / relative).is_file():
            failures.append(f"falta archivo requerido: {relative}")

    manifest_path = ROOT / "templates" / "skevi" / TEMPLATE_MANIFEST_NAME
    if manifest_path.is_file():
        failures.extend(
            check_template_manifest(manifest_path, manifest_path.parent)
        )

    scripts_manifest_path = ROOT / "scripts" / TEMPLATE_MANIFEST_NAME
    if scripts_manifest_path.is_file():
        failures.extend(check_template_manifest(
            scripts_manifest_path, scripts_manifest_path.parent,
            expected_schema=SCRIPT_MANIFEST_SCHEMA))

    corpus_manifest_path = ROOT / "docs" / TEMPLATE_MANIFEST_NAME
    if corpus_manifest_path.is_file():
        failures.extend(check_corpus_manifest(corpus_manifest_path))

    unexpected_markdown = sorted(
        path.name
        for path in ROOT.glob("*.md")
        if path.name not in ROOT_MARKDOWN
    )
    if unexpected_markdown:
        failures.append(
            "Markdown operativo suelto en raíz: "
            + ", ".join(unexpected_markdown)
            + " (decláralo en «root_markdown» de " + CONFIG_NAME + ")"
        )

    failures.extend(check_reading_path())

    rows: list[tuple[str, int, int]] = []
    for relative in discover():
        name = relative.as_posix()
        try:
            observed = count_text_lines(relative)
            if observed is None:
                continue
            if relative.name in REGISTRY_HOSTS:
                text = (ROOT / relative).read_text(encoding="utf-8")
                failures.extend(check_registry_block(relative, text))
        except UnicodeDecodeError:
            failures.append(
                f"{name}: contenido no válido como UTF-8 "
                "(si es binario, exéntalo con «exempt_paths» o "
                f"«exempt_names» en {CONFIG_NAME})"
            )
            continue
        except OSError:
            # No volcar la excepción: puede contener rutas o datos del host.
            failures.append(f"{name}: no se pudo leer el archivo")
            continue
        limit = limit_for(name)
        rows.append((name, observed, limit))
        if observed > limit:
            failures.append(f"{name}: {observed} líneas > límite {limit}")

    aviso = gate_staleness()

    if failures:
        print(
            "BLOQ — check_sizes encontró incumplimientos "
            f"({GATE_VERSION}, {GATE_GENERATED_AT})"
        )
        for failure in failures:
            print(f"- {failure}")
        if aviso:
            print(aviso)
        return 1

    observado = READING_PATH_OBSERVED
    ruta = (
        f"; ruta de lectura {observado}/{READING_PATH['limit']}"
        if observado is not None
        else ""
    )
    print(
        "OK — "
        f"{len(rows)} archivos de texto dentro de límites; "
        f"estructura y hogares canónicos verificados{ruta}"
        f"; {GATE_VERSION} ({GATE_GENERATED_AT})"
    )
    if aviso:
        print(aviso)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
