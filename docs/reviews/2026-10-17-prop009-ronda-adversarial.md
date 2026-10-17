# Ronda adversarial — PROP-009 (plan de incrementos)

Fecha local: 2026-10-17

Estado: **aplicada** — PROP-009 reescrito a v2 con los ajustes; veredictos
abajo contrastados por la instancia principal contra código antes de aceptar.

## Método

Tres revisores en contexto fresco (sin el razonamiento de la sesión que
escribió el plan), solo lectura, mandatos separados:

- seguridad/runtime;
- contrato, coherencia y viabilidad (incluido `escrubery` y su
  `CONTRATO_API_v0`);
- pruebas y condiciones de falsación.

Patrón de la ronda 2026-09-18. No es auditoría externa ni independencia
institucional; no se infiere consenso por participación.

## Veredictos que la instancia principal verificó y aceptó

### Ataques estructurales aceptados

1. **I5 inviable tal como estaba escrita.** El transporte local admite
   1024 B ASCII imprimible de una línea (`llavero_core.py:299-300,355-365`),
   `validate_secret` rechaza CR/LF (`:253-254`) y la suite congela el
   límite (`tests/test_long_secrets.py`); un PEM RSA-2048 mide ~1.7 KB.
   Además «caché en memoria con refresco» era incoherente con un CLI que
   termina en `os.execve` (`llavero.py:325`). El criterio PEM recortaba las
   superficies del TM §9 (omitía disco/caché/temporales). → v2: workstream
   previa de secretos largos, modelo por-invocación, superficies completas,
   compuertas ADR, llamada viva opt-in.
2. **«Garantía estructural: no existe tool leer» de I6 refutada.**
   `ejecutar` exige ruta absoluta, pero `/bin/sh` lo es y no tiene shebang
   que validar: un llamador MCP puede exfiltrar el entorno; `probar` envía
   el Bearer al `base_url` de un perfil mutable (R-08), incluso a
   `127.0.0.1` legal. La justificación «I6 tras I4 porque I4 controla quién
   llama» era falsa: I4 no autentica llamantes. → v2: modo restringido por
   defecto, `probar`/`ejecutar` fuera salvo política de digest, TTY
   declarado gate débil, protocolo pinado, TOCTOU residual documentado.
3. **Atribución falsa en §1.** La frase «claves, contraseñas, secretos y
   keys de diferentes proyectos y ecosistemas» no existe en README ni
   manifiesto (grep 0 resultados); provenía de la instrucción del Operador
   y el plan la atribuía a los documentos. → v2: atribución corregida y
   decisión D6 creada.
4. **I3 prometía `base_url` de escrubery v0**, campo que ninguna operación
   sirve (`CONTRATO_API_v0` §3.1/§3.3/§3.7/§3.8), con enum de proveedor sin
   `openai` y `typesafe` ≠ `typesafe-systemone`; `resolver` con semilla
   sintética; alias CLI `modelo` (no `consultar_modelo`). → v2: entregable
   sin base_url, tabla de mapeo, cobertura declarada, issue cruzado.

### Criterios refutados por ausencia de control positivo (TM §9)

- «receipts sin canario» (I4) y «ningún dato de escrubery entra en
  superficies de secreto» (I3): ausencias sin control positivo ni superficie
  definida. → reescritos con canario sembrado y arnés que demuestra
  detección (patrón `test_providers.py:75`).
- «matriz §10 completa» (I7): imposible sin entrega L2/fd. → acotada a
  niveles implementados con filas L2 marcadas `no-implementado` + issue.
- «stdout/stderr de todas las operaciones» (I1): `ejecutar` termina en
  `execve`; el stdout del hijo no es de Llavero. → acotado a emisiones de
  Llavero antes del exec (mock del exec).
- «reloj de prueba» (I4): no existe inyección de reloj en runtime (sólo
  `time.monotonic` en `llavero_core.py:315,319` y `llavero.py:220,272`);
  el criterio presuponía un seam que ninguna tarea creaba. → tarea previa
  explícita (G-17).
- «ADR de dependencia aprobada» como criterio (I5): una decisión pendiente
  no es criterio. → movido a compuerta previa del incremento.
- «suite verde» (I0): tautológico. → sustituido por criterios específicos.

### Hallazgos nuevos del código incorporados como brechas

- **G-13**: `main` sólo captura `LlaveroError`; bytes no-UTF-8 de
  `security` producen `UnicodeDecodeError` con traceback y exit 1.
- **G-14**: asimetría de capacidad local 1024 B vs iCloud 16 KiB
  (`native/llavero_sync.swift:82`).
- **G-15**: TOCTOU del consumidor admitido en F-06 y sin incremento
  asignado; queda residual documentado en I6/I7.
- **G-16**: exfiltración mismo-UID vía `base_url` loopback legal + perfil
  mutable, hoy, con suite verde.
- **G-17**: sin seam de reloj, expiración y refresco son impruebas.
- Extensión de **G-7**: `listar --icloud` aborta completo ante un
  identificador hostil (`llavero.py:344-347`, `llavero_core.py:189-193`).
- Extensión de **G-8**: la relectura post-escritura de `store_secret`
  (`llavero_core.py:383`) también cuelga.
- **G-5 matizada**: los perfiles genéricos v1 ya permiten otros
  proveedores vía `--secret-env`; la brecha es declarativa y de `probar`.

### Omisiones de contrato/proceso incorporadas

- Actualización de `project-manifest.yaml` ausente de los criterios →
  principio 6 y criterio documental por incremento.
- iCloud huérfano (0 menciones, 2 entradas `pospuesto`) → issues de deuda
  en §7.
- Presupuesto README 300 líneas (240 usadas) con tres ampliaciones →
  contenidos a `docs/*.md` enlazados.
- Divergencia de exit codes con escrubery (3 = infraestructura allí, 3 =
  conflicto aquí) → alineados en §5.
- «Hoy sólo el Operador consume exit codes» era falso: la suite aserta
  códigos (`test_llavero.py`, `test_providers.py`) y CI los ejecuta →
  inventario de consumidores en I1.
- Ausencia de protocolo de fallo (FIX-AND-RETRY, incremento bloqueado) →
  §9; resquicio cerrado: issue ≠ criterio pospuesto.
- Schema de perfil para campos nuevos sin decidir (`allowed` cerrado en
  `llavero_core.py:438`) → `llavero/profile/v3` (D7) con grandfathering.
- Layout de almacenamiento para ids con `/` (rompe `profile_path`) →
  tarea explícita en I4 con prueba de traversal.
- `docs/history/README.md` describe el directorio como historia de Skevi →
  desviación registrada en el encabezado de PROP-009; ubicación final
  sujeta a la decisión del Operador.

### Defensas retiradas por teatro de seguridad

- «Garantía estructural: no existe tool leer» (I6).
- «append-only 0600» como auditoría fuerte (I4): falseable por el propio
  adversario mismo-UID; reetiquetada post-mortem.
- «Sustitución segura» vía CAS (I4): protege contra lost-updates, no
  contra R-08; salvedad explícita.
- «guardar por MCP sólo con TTY» como gate humano: PTY asignable por
  software; declarado débil.

## Defensas del plan que sobrevivieron al ataque

- Diagnóstico G-1…G-4, G-6, G-9…G-12 confirmado con evidencia por los tres
  revisores.
- I2 como evolución aditiva de v2 sin romper compatibilidad (la regla del
  README gobierna migraciones v1→v2, no evolución de v2).
- I7 condicionado a I4 respeta la decisión de la ronda 2026-09-18.
- Ubicación del documento dentro de límites del gate (history no está en la
  ruta de lectura obligatoria; límite 800 por archivo).
- Diseño fail-closed de I3 sin dependencia dura de escrubery.

## Trazabilidad

PROP-009 v1 → ataques → verificación local → PROP-009 v2 (mismo archivo,
encabezado de estado con referencia a este registro). Este registro conserva
los veredictos para no perder procedencia.
