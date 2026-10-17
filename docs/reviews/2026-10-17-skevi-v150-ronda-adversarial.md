# Ronda adversarial — actualización Skevi a v1.5.0

Fecha local: 2026-10-17

Estado: **aplicada la corrección al plan** — la recomendación original
(«re-copia adaptada a v1.5.0 sin tocar `skevi-gate.json`») quedó falsada en
su cláusula final; los veredictos fueron contrastados por la instancia
principal re-ejecutando los gates antes de aceptarlos.

## Objeto

Auditar la recomendación de actualizar la adopción Skevi de `d7a80b2`
(plantillas/v10, gate/v8, corpus/v4) a `1837e64` / `v1.5.0` (plantillas/v14,
gate/v11, corpus/v5).

## Método

Un revisor en contexto fresco (sin el razonamiento de la sesión que escribió
la recomendación), solo lectura sobre ambos repos, mandato único de falsación
con once afirmaciones (C1–C11) y siete ataques dirigidos. Pruebas producidas
sólo en directorio efímero; `git status` limpio en ambos repos al cierre.
Patrón de las rondas 2026-09-18 y 2026-10-17 (PROP-009).

## Veredictos que la instancia principal verificó y aceptó

- **C1–C6, C8 (hechos), C9–C10 (alcance y línea base): CONFIRMADAS** con
  evidencia de comandos y digest.
- **C3 MATIZADA**: el fail-closed de re-copia parcial lanza `AttributeError`
  con traceback crudo, no el `ImportError` limpio del texto de migración de
  gate/v9. Exit 1 y «sin validación a medias» se cumplen; cosmético.
- **C7 MATIZADA**: entre plantillas/v10 y v14, `usage-guide.md` cambia en v13
  por dos razones (aviso del marcador de dependencias y ejemplo de
  `reading_path` con `AGENTS.md`), no sólo por el aviso. Las customizaciones
  locales no quedan rotas.
- **C11 (la recomendación) FALSADA en su cláusula final** — hallazgo N1.

## Hallazgo decisivo (N1, BLOQ)

`docs/ai-agent-guide/05-memoria-del-agente.md` crece de 116 a 132 líneas
(corpus/v5, PROP-011/ADR-042). Ese archivo está presupuestado en
`reading_path.files`, cuya línea base local es 1586/1600: tras la re-copia la
ruta mediría **1602 > 1600** y `check_sizes.py` (gate/v11) falla con BLOQ.
El propio upstream subió su límite a **1620** en este mismo rango.

Verificación propia de la instancia principal: re-ejecutados los gates sobre
la migración simulada completa — trío de `check_templates` «al día»
(plantillas/v14, gate/v11, corpus/v5) y `check_sizes` BLOQ 1602/1600; subiendo
el límite a 1620, verde en 1602/1620.

## Hallazgos menores e informativos aceptados

- **N2 (menor)**: `AttributeError` cosmético en re-copia parcial (ver C3).
- **N4 (informativo)**: el listado exacto del manifiesto de plantillas sólo
  aplica a manifiestos fuente; en modo `--installed` se comparan versiones, así
  que copiar el manifiesto v14 **no** exige añadir `frozen-trees.md`,
  `plan-de-implementacion.md` ni `registro-contexto.md` a `.skevi/`.
- **N3/N6/N7 (informativos)**: el adoptor debe declarar `source @1837e64`
  completo (los registros dogfood upstream apuntan a fuentes intermedias,
  ancestros verificados); la CI local no ejecuta `check_plans`/`check_reports`
  como pasos propios (asimetría preexistente, sin cambios con la migración);
  el historial de gate v8→v11 es honesto, sin bumps ocultos.

## Plan corregido (pendiente de orden del Operador)

El plan de re-copia de diez pasos queda en pie con un paso adicional
obligatorio: subir `reading_path.limit` de 1600 a **1620** en
`skevi-gate.json`, absorbido por decisión escrita (ADR propio), en línea con
ADR-042 del upstream. Sin ese paso la migración no queda verde; con él, la
simulación completa pasa todos los gates.
