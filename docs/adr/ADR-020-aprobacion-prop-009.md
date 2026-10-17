# ADR-020: Aprobación de PROP-009 sin inicio de ejecución

Estado: aceptado (aprobación documental; sin efecto en runtime)

Contexto: PROP-009 (plan incremental I0–I7 para superficie de agentes,
multi-proveedor, ciclo de vida y entregas superiores) fue escrito en v2
tras una ronda adversarial de tres revisores en contexto fresco
(2026-10-17, registro en `docs/reviews/2026-10-17-prop009-ronda-adversarial.md`)
que refutó y corrigió dos diseños estructurales, una atribución falsa y
siete criterios de aceptación. El plan exige decisión explícita del
Operador antes de cualquier efecto (§8, D1–D8).

Decisión: el Operador aprueba el plan PROP-009 v2 con su orden I0→I7 y su
protocolo de fallo (§9: criterio fallido bloquea el incremento;
FIX-AND-RETRY; un issue no pospone criterios). La aprobación es
deliberadamente **sin ejecución**: ningún incremento, issue, milestone,
label, release ni cambio de código queda autorizado por este ADR; cada
incremento inicia sólo con instrucción expresa posterior del Operador y
re-verificación de contexto AN-KLA. D1 queda resuelta; D2–D8 se resuelven
al iniciar el incremento que las toca.

Alternativas descartadas:
  - Aprobar e iniciar I0 de inmediato: el Operador decidió no ejecutar
    por el momento.
  - Rechazar o reordenar (p. ej. adelantar I4 según la recomendación
    literal de la ronda 2026-09-18): el Operador mantuvo el orden propuesto.

Consecuencias:
  - PROP-009 v2 es la línea base para trabajo futuro; cualquier sesión
    que retome el proyecto parte del plan aprobado y de sus compuertas.
  - La aprobación no publica nada: issues, milestones, protección de
    `main` y dependencias siguen requiriendo autorización específica (D2–D8).
  - Si el plan se revisa antes de ejecutarse, la revisión exige nueva
    ronda adversarial si toca superficie de seguridad (§9) y un sucesor
    de este ADR.
