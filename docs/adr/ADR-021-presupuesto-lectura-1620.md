# ADR-021: presupuesto de ruta de lectura a 1620 líneas

Fecha: 2026-10-17. Estado: aceptado.

## Contexto

El gate de tamaños presupuesta la ruta de lectura obligatoria del agente
(`reading_path` en `skevi-gate.json`). La actualización de la adopción Skevi
a `v1.5.0` (`1837e64`) re-copia `docs/ai-agent-guide/05-memoria-del-agente.md`
(corpus/v5, PROP-011: frontera de memoria agnóstica), que crece de 116 a 132
líneas. Con la línea base en 1586, la ruta pasaría a medir 1602 y el límite
vigente de 1600 la tumba con BLOQ.

El propio Skevi absorbió este mismo crecimiento subiendo su presupuesto a
1620 en el mismo rango (ADR-042 del upstream). La ronda adversarial de
2026-10-17
(`docs/reviews/2026-10-17-skevi-v150-ronda-adversarial.md`) detectó que la
migración sin este ajuste no queda verde; la instancia principal lo verificó
re-ejecutando el gate sobre la migración simulada: BLOQ 1602/1600 sin el
cambio, verde 1602/1620 con él.

## Decisión

Subir `reading_path.limit` de 1600 a **1620** y absorber el crecimiento del
corpus en el presupuesto por decisión escrita, como exige el mensaje del gate.
El margen resultante es de 18 líneas sobre la ruta medida.

## Consecuencias

- La migración a gate/v11 queda verde sin recortar contenido normativo.
- Crecimientos futuros de los archivos presupuestados exigen una nueva
  decisión; el margen es deliberadamente corto para forzarla a tiempo.
- Queda fuera de este presupuesto cualquier documento nuevo de lectura
  opcional: debe justificar su entrada con decisión propia.
