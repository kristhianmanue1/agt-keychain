# ADR-018: coherencia de autoridad general y restricción local

Estado: aceptado el 2026-09-07. Implementado en
`29243f1548413a2d3b1f1e873e5eca019637de3c` (F1 §3.3).

Contexto: T05 detectó copias divergentes entre índice, F3, guía de memoria,
AGENTS y manifest. El estándar ya define el modelo general de ADR-017;
AGENTS mantiene una restricción humana local de mayor prioridad.
La [deliberación](https://github.com/kristhianmanue1/skevi/blob/d7a80b26962cd66a806943ff46f779de14c16708/docs/history/AUDIT-authority-consistency.md) conserva M1-M8,
REQ-T05-01/02/03, SPEC-AUD-03 y casos C1-C9 como evidencia, no autoridad.

Decisión: adoptar la opción A, remitiendo la política general al estándar y
explicitando la restricción humana local sin habilitar delegación en Skevi.
Aceptante: humano de esta conversación, «adelante» a «¿Apruebas la opción A
para aplicarla?», el 2026-09-07. No es aceptación inferida de memoria.

Alternativas descartadas:

- B, habilitar delegación local: cambia permisos, no es necesario para
  corregir la coherencia y no fue la alternativa aprobada.
- C, conservar los textos: mantiene deriva y carga de interpretación.

Consecuencias:

- Índice regla 2 declara estándar sobre guía y preserva AGENTS aplicable
  aun cuando no declare jerarquía; las instrucciones del entorno prevalecen.
- F3 §7 conserva operaciones protegidas y remite alcance, vigencia y
  otorgante a estándar y restricciones superiores; no renueva permisos.
- Guía 05 §2 separa memoria de autoridad y mantiene su adopción opcional.
- AGENTS conserva literalmente la regla humana y añade excepción local.
- Manifest no concede autoridad. No se modifica ningún ítem de pospuesto.
- Estándar y ADR-017 permanecen intactos; esta decisión los concilia con
  las guías, no sustituye ni reescribe la decisión general.

Compatibilidad: adoptantes con restricciones propias las conservan. Ningún
consumidor se actualiza automáticamente; no se requiere orquestador ni AN-KLA.
El cambio es documental y reversible por una decisión posterior, no por
alteración silenciosa de este ADR.
