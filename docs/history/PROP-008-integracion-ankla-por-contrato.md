# PROP-008 — Integración skevi↔AN-KLA por contrato

> **Estado:** ADOPTADA — D1-D2 aprobadas por el humano (2026-09-07,
> en conversación). Piloto K1-K4 corrido sobre la propia sesión de
> adopción; D3 ejecutada vía [ADR-019](../adr/ADR-019-integracion-ankla-por-contrato.md)
> y el cambio de adopción (05 §6, 04 §7). Registro histórico: evidencia
> de decisión, no norma vigente. Decisión y piloto:
> [PROP-008-decision](https://github.com/kristhianmanue1/skevi/blob/d7a80b26962cd66a806943ff46f779de14c16708/docs/history/PROP-008-decision-2026-09-07.md).
> **Origen:** instrucción directa del humano (2026-09-07: «analiza que esta
> integración sea por contrato») y análisis de complementariedad de la
> misma sesión, refinado por ronda adversarial en contexto fresco
> (subagente independiente: 2 BLOCKER y 1 HIGH corregidos — las
> recomendaciones originales R1 y R2 quedaron retiradas por esa ronda y
> no aparecen aquí).

## Contexto

Skevi consume AN-KLA de forma declarada (`project-manifest.yaml`:
`consume: an-kla-memory, requerido: false`, «Skevi opera igual sin
ella»), pero la integración funciona hoy por **convención**: el bloque
administrado en `AGENTS.md` anuncia la memoria, el agente hace preflight
si el protocolo lo dicta, y los códigos de diagnóstico de `context
status` no tienen acción skevi mapeada por escrito. Este contrato hace
la integración **condicional y verificable por comando**, protegiendo la
independencia del manifest. En paralelo, la ronda adversarial dejó tres
reglas derivadas que aterrizan aquí: el mecanismo del folio quedó
pendiente en PROP-006, la procedencia `attest` fue mal posicionada como
evidencia (es trazabilidad de sesión), y el hueco textual de `04` §7
(«dependencias nuevas» no cubre upgrades) quedó expuesto.

## D1 — Contrato `skevi/an-kla-integration v1`

**Propuesta:** adoptar el contrato en el formato de `02` §4:

```text
CONTRATO: skevi/an-kla-integration v1
Entrada (detección):
  - `context status` -> {installed: true, ok: true, diagnostics: []}
  - bloque administrado vigente + AN-KLA.md presente
  - activación condicional: sin detección positiva, el contrato no
    existe; ninguna regla obligatoria de skevi referencia memoria
Salida (efecto):
  - 05 pasa a obligatorio-para-memoria-adoptada
  - preflight al iniciar sesión material; checkpoint al cierre
  - decisiones del checkpoint = punteros (PR, folio, ADR), nunca
    re-enunciado de normas
Errores (fail-closed, diagnóstico -> acción):
  - managed_contract_modified | managed_block_modified |
    managed_block_structure_invalid | orphan_managed_contract |
    legacy_an_kla_context_detected -> reportar y BLOQ en la costura
    memoria; nunca auto-reparar ni sobrescribir
  - memoria ausente -> no inicializar sin habilitación del humano
  - verify fallido -> sin escrituras de memoria esa sesión
Invariantes:
  - la memoria jamás cierra un gate ni autoriza operaciones
  - docs/ + Git canónicos; memoria = punteros y estado de sesión
  - receipts attest = procedencia de sesión, nunca prueba de gates
  - upgrade de AN-KLA = tarea Bounded con checklist de AN-KLA.md
Compatibilidad:
  - instalación por etiqueta exacta; plantilla del bloque fijada
  - cambios del contrato -> v2, nunca mutación in situ
```

**Alternativa descartada:** integración por convención (statu quo) —
sin acciones mapeadas por diagnóstico, el fallo en la costura se
resuelve por improvisación, contra §6.7.

## D2 — Reglas derivadas (aterrizan con el contrato)

1. **Mecanismo del folio (cierra el pendiente de PROP-006):** secuencia
   en archivo versionado con escritura atómica (§2.2 del estándar) o
   derivada de Git. Queda **prohibido** derivarlo de la revisión del
   store de memoria: es local, sin exclusión entre máquinas, y su
   compactación destruye el rastro (hallazgos BLOCKER de la ronda).
2. **Procedencia `attest`:** permitida como trazabilidad de sesión;
   **prohibida** como prueba de gates — el receipt acredita invocación,
   no resultado, y no sobrevive export/restore (hallazgo HIGH).
3. **Hueco textual:** añadir a `04` §7 (o `01` §2) que instalar o
   **actualizar** una dependencia con efecto en archivos del repo es
   operación con autoridad separada y tarea Bounded como mínimo.

## Criterios de aceptación (falsables)

- K1: con detección positiva el efecto se observa por comando (05
  vinculante, preflight ejecutado); con ausencia de memoria, ninguna
  regla obligatoria exige memoria — auditable barriendo la norma.
- K2: cada diagnóstico del contrato tiene una sola acción mapeada y
  cero rutas de auto-reparación — verificable por inspección del texto
  y por ejercicio del caso (diagnóstico inyectado en sesión de prueba).
- K3: en el cierre de toda tarea material con memoria, las decisiones
  del checkpoint contienen sólo punteros — auditable con `checkpoint
  show`.
- K4: un adoptante sin AN-KLA cumple la totalidad de la norma skevi
  (independencia) — auditable igual que K1.

## D3 — Aterrizaje normativo

Si se aprueba: añadir la sección del contrato a `05` (nuevo §, sin
cambiar su naturaleza de recomendación con reglas obligatorias-si-se-
adopta); la línea de D2.3 en `04` §7; el ADR de la decisión; y mover
esta PROP a `docs/history/` en el mismo cambio (patrón PROP-004). El
gate de tamaños no verifica este contrato: su frontera es forma/tamaño
y la verificación es el preflight comandado.

## Criterios de decisión aplicados

§8 del estándar: el contrato es lo más simple de entender (una tabla
diagnóstico→acción), lo más fácil de revertir (dejar de detectar = no
existe), minimiza superficie (cero acoplamiento del gate) y no añade
dependencias (activación condicional). Las retiradas de la ronda
adversarial se registran como procedencia, no se ocultan.

## Adopción

D1-D2 quedan aceptadas o rechazadas por el humano en conversación; con
la aprobación, un PR ejecuta D3 con el piloto documentado (K1-K4 sobre
la propia sesión de adopción). Mientras tanto, este documento no obliga
a nada.
