# ADR-019: Integración skevi↔AN-KLA por contrato condicional

Estado: aceptado

Contexto: skevi consume AN-KLA de forma declarada
(`project-manifest.yaml`: `consume: an-kla-memory, requerido: false`),
pero la integración funcionaba por convención: el bloque administrado
de `AGENTS.md` anuncia la memoria y los diagnósticos de `context
status` no tenían acción mapeada por escrito. Quedaban además abiertos
el mecanismo del folio (PROP-006 D2), la posición de la procedencia
`attest` — mal posicionada como evidencia; es trazabilidad de sesión —
y el hueco textual de `04` §7, donde «dependencias nuevas» no cubría
los upgrades.

Decisión: adoptar el contrato `skevi/an-kla-integration v1`
(`05-memoria-del-agente.md` §6), con activación condicional: sin
detección positiva de la memoria, el contrato no existe y ninguna
regla obligatoria de skevi la referencia. Cada diagnóstico de la
costura memoria tiene una sola acción, fail-closed, sin rutas de
auto-reparación. Las reglas derivadas aterrizan con el contrato:
receipts `attest` son trazabilidad de sesión, nunca prueba de gates;
el folio del reporte jamás se deriva de la revisión del store; e
instalar o actualizar una dependencia con efecto en archivos del repo
es operación con autoridad separada y tarea Bounded como mínimo
(`04` §7).

Alternativas descartadas:
  - Integración por convención (statu quo): sin acciones mapeadas por
    diagnóstico, el fallo en la costura se resuelve por improvisación.
  - Integración obligatoria o acoplada al gate de tamaños: rompe la
    independencia declarada en el manifest y añade superficie sin
    requisito que la pida.

Consecuencias: un adoptante sin AN-KLA cumple la totalidad de la norma
skevi (activación condicional); con memoria adoptada, el preflight al
iniciar sesión material y el checkpoint al cierre pasan a ser
exigibles, y las decisiones del checkpoint contienen sólo punteros.
El gate de tamaños no verifica este contrato: su frontera es
forma/tamaño y la verificación es el preflight comandado. Cambios del
contrato producen una v2, nunca mutación in situ.

Procedencia: aprobación humana de D1/D2 en conversación (2026-09-07).
Deliberación, piloto K1-K4 y evidencia del aterrizaje:
[PROP-008-decision](https://github.com/kristhianmanue1/skevi/blob/d7a80b26962cd66a806943ff46f779de14c16708/docs/history/PROP-008-decision-2026-09-07.md).
