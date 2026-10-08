# Uso de Skevi en Llavero

**Proyecto:** Llavero, checkout `agt-keychain`.
**Fase:** proyecto existente; la clase y el gate se determinan por tarea.
**Procedencia:** registros `installed.json`, `scripts-installed.json` y
`corpus-installed.json` en este directorio, fijados al SHA de Skevi.

## Lectura

1. `AGENTS.md` y este documento.
2. `docs/ai-agent-guide/00-INDICE.md` y la guía de la fase aplicable.
3. `docs/estandar-diseno-software-github.md`.
4. Para trabajo material de memoria, `docs/ai-agent-guide/05-memoria-del-agente.md`
   y `AN-KLA.md`. AN-KLA no almacena credenciales ni cierra gates.

Las recomendaciones de checkpoint de Skevi no autorizan escrituras en AN-KLA;
esas operaciones siguen requiriendo la autoridad explícita del Operador.

La ruta de lectura declarada en `skevi-gate.json` cuenta el caso máximo de
fase junto al contrato de AN-KLA. Su límite de 1600 líneas es una decisión
local para este conjunto medido; no modifica el límite de 1000 de Skevi en
su propio repositorio. Revísalo antes de añadir lectura obligatoria.

## Elecciones locales

- Comunicación humana, documentación, mensajes y comentarios: español, según
  la documentación existente y las instrucciones del Operador.
- Identificadores estructurales nuevos: inglés; se preservan contratos y
  nombres existentes como `llavero` y `AN-KLA`.
- `AN-KLA.md` es Markdown operativo permitido en la raíz. `.memos/` es estado
  local ignorado por Git; `.DS_Store` es un archivo generado por macOS.
- `scripts/check_sizes.py` conserva las 870 líneas del origen y recibe un
  límite específico. Los demás archivos usan los límites predeterminados.

## Alcance adoptado

Se copiaron el estándar, la guía, sus manifiestos y los cuatro scripts
versionados sin editar su código. El gate de tamaños queda configurado para
este árbol. `check_plans.py` y `check_reports.py` permanecen inactivos porque
Llavero no declaró directorios sujetos a esos contratos; un `OK` de esos
scripts no contaría planes ni reportes revisados.
La evaluación y las decisiones de esta adopción constan en
`docs/skevi-adoption.md`.

Skevi guía el desarrollo, no forma parte del runtime de captura, Keychain o
entrega de credenciales. El modo iCloud requiere su validación propia; un gate
de Skevi no demuestra sincronización, firma válida ni aislamiento de secretos.

## Verificación

```bash
python3 scripts/check_sizes.py
python3 scripts/check_plans.py
python3 scripts/check_reports.py
python3 scripts/check_templates.py --manifest .skevi/template-manifest.json --installed .skevi/installed.json
python3 scripts/check_templates.py --manifest scripts/MANIFEST.json --installed .skevi/scripts-installed.json
python3 scripts/check_templates.py --manifest docs/MANIFEST.json --installed .skevi/corpus-installed.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
```

Los tres registros indican versión y procedencia. Una comparación `OK` con
manifiestos locales no certifica que el upstream siga en esa versión. Antes de
actualizar, compara el SHA remoto, los manifiestos y los archivos copiados.

No se instala un hook local. `.github/workflows/skevi-gate.yml` ejecuta la
verificación en macOS; su mera presencia no equivale a un check requerido.
Falta comprobar un fallo deliberado en CI y configurar la protección de rama
por separado antes de llamarlo gate obligatorio de publicación.
