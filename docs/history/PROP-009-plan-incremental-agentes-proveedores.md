# PROP-009 — Plan incremental: superficie para agentes, multi-proveedor y ciclo de vida

> **Estado:** APROBADA por el Operador (2026-10-17, en conversación) —
> **sin ejecutar**: ningún incremento inicia sin instrucción expresa
> posterior. La decisión se asienta en
> [ADR-020](../adr/ADR-020-aprobacion-prop-009.md). Con la aprobación
> queda resuelta D1 (orden I0→I7 y protocolo de fallo §9); D2–D8 siguen
> abiertas y se resuelven al iniciar el incremento correspondiente.
> **Origen:** instrucción directa del humano (2026-10-17), incluyendo un
> propósito más amplio que el hoy declarado —guardar «claves, contraseñas,
> secretos y keys de diferentes proyectos y ecosistemas»—. **Esa amplitud es
> de la instrucción, no de los documentos vigentes**: README y
> `project-manifest.yaml` declaran hoy «credenciales para proyectos que
> consumen modelos de IA»; ampliar el alcance requiere decisión explícita
> (D6, §8). También pidió: plan iterativo incremental con funcionalidad por
> incremento; contrato base para agentes (CLI, MCP); otras formas de
> autenticación (p. ej. GitHub App); claves de APIs de IA como incremento
> primario; integración con `escrubery` por contrato; mecanismos GitHub.
> **Ámbito observado:** árbol local en `1fcf0d4`, suite 51 pruebas OK
> (2 live omitidas), 0 issues abiertos, repo público
> `kristhianmanue1/agt-keychain`, `main` sin protección.
> **Ronda adversarial:** tres revisores en contexto fresco (seguridad,
> contrato, pruebas) intentaron refutar este plan; los veredictos y ajustes
> están en
> [docs/reviews/2026-10-17-prop009-ronda-adversarial.md](../reviews/2026-10-17-prop009-ronda-adversarial.md).
> Esta v2 incorpora: dos ataques estructurales aceptados (I5 inviable tal
> como estaba; «garantía estructural» de I6 refutada), la corrección de una
> atribución falsa (§1), criterios reescritos con control positivo (TM §9)
> y seis hallazgos nuevos del código (G-13…G-17, §2.3).
> **Nota de proceso:** este documento vive en `docs/history/` siendo
> PROPUESTA; `docs/history/README.md` describe el directorio como
> procedencia histórica de Skevi. Se registra la desviación; la decisión del
> Operador, si se aprueba, se asienta en un ADR propio y la ubicación final
> (history vs docs/) queda en esa decisión. No se modifica el README de
> history sin autoridad.

## 1. Contexto

Llavero captura, almacena (macOS Keychain) y entrega credenciales para
consumidores de modelos de IA bajo `env/v1`. La Fase 1 es un prototipo
defensivo: la ronda adversarial 2026-09-18 dejó cinco bloqueadores
arquitectónicos (B-01…B-05) y recomendó como siguiente incremento
«descriptor cerrado + namespace + adaptador explícito + política versionada»
— contenido que este plan asigna a I4 y no a I0/I1. Este plan **reordena**
esa recomendación para entregar valor de uso antes (proveedores IA en I2),
ampliando superficie sobre namespace plano: es una apuesta consciente, no
continuidad, y el Operador puede revertirla (D1, §8).

## 2. Análisis crítico — código vs. documento

### 2.1 Fortalezas verificadas en código

- Validación cerrada y fail-closed: identificador `^[a-z0-9][a-z0-9._-]{0,62}$`,
  endpoints HTTPS (HTTP sólo loopback), allowlist de variables públicas,
  reject de hooks de loader/intérprete/proxy, redirects rechazados,
  entorno mínimo con `PATH` de sistema, consumidor con ruta absoluta y
  shebang sin `/usr/bin/env` (`llavero_core.py`, `llavero.py`).
  **Matiz de la ronda:** «HTTP sólo loopback» es fortaleza frente a red
  remota, pero no frente al adversario mismo-UID del propio modelo (G-16).
- Captura TTY oculta con doble confirmación; transporte a Keychain sin
  secreto en `argv` (PTY ≤128 B; orden hex por pipe 129–1024 B, timeout 30 s);
  relectura y comparación obligatoria antes de anunciar éxito.
- Perfiles atómicos `0600` con fsync + rename; verificación de uid/modo/symlink
  al leer; validación de coherencia `base_url`↔`public_env`.
- Pruebas con canarios y dobles (51), condiciones de falsación y ronda
  adversarial multiagente documentada.
- Manifiesto honesto (`ofrece`/`no_ofrece`), modelo de amenazas con niveles
  L0–L3 y contrato propuesto con recibos saneados.
- CI en macOS real: gate de estructura, suite, `swiftc -typecheck`.

### 2.2 Brechas — código vs. aspiración

| # | Brecha | Evidencia | Ataca |
|---|---|---|---|
| G-1 | Namespace plano: una sola cadena como `credential_id`; el patrón ni siquiera admite `/`; sin CAS al sustituir/borrar | `llavero_core.py:39,196-202`; `expected_version` sólo existe en el contrato | I4 |
| G-2 | Sin ciclo de vida: el conjunto de campos cerrado no representa `expires_at`; sin rotación ni auditoría (receipts §11 sin implementar) | `llavero_core.py:438`; R-06 | I4 |
| G-3 | Contrato `credential-delivery/v1` sigue PROPUESTO: sin schemas JSON cerrados, errores tipados ni matriz de conformidad ejecutable | B-04 | I1, I4 |
| G-4 | Núcleo acoplado a macOS/Keychain: no existe la interfaz de backend `put/get/delete/status` del contrato §7 como frontera implementada | `llavero_core.py` mezcla capas | I2 (origen único), I4 (schema), I7 (backends) |
| G-5 | **Matizada por la ronda:** los perfiles genéricos v1 ya admiten hoy cualquier proveedor vía `--secret-env` (p. ej. `ANTHROPIC_API_KEY` pasa el patrón sensible y `ANTHROPIC_BASE_URL` la allowlist). La brecha real es declarativa y de `probar`: sólo 2 proveedores v2 explícitos (`llavero.py:397`, `llavero_core.py:448`) y sólo 2 shapes de prueba (`/chat/completions` Bearer, `/v1/systemone`); `build_consumer_environment` deriva prefijos hardcodeados | `llavero.py:199-206,213`; `llavero_core.py:565-575` | I2 |
| G-6 | Una sola forma de autenticación aplicada: `Authorization: Bearer` fijo en `probar` (`llavero.py:213`); la entrega `env/v1` no impone semántica de auth al consumidor, así que la brecha es de `probar`/descriptor | `cmd_test` | I2, I5 |
| G-7 | **Extendida por la ronda:** `listar` local aborta al primer perfil inválido (`llavero.py:354-356`) y `listar --icloud` es peor: el bucle no maneja errores (`llavero.py:344-347`) y `sync_list_profiles` lanza al primer identificador hostil sincronizado — un id malicioso desde otra Mac deja mudo todo el listado. `main` devuelve 2 para todo `LlaveroError` (`llavero.py:432-434`) | `llavero_core.py:189-193` | I0 |
| G-8 | **Extendida por la ronda:** `_run_security` sin timeout en lectura/borrado (`llavero_core.py:267-274`) y la relectura post-escritura de `store_secret` (`:383`) también puede colgar — incluso el camino «con timeout» se bloquea en su verificación | vs `_SECURITY_WRITE_TIMEOUT=30` | I0 |
| G-9 | Adaptador Skopos implícito: perfil sin `delivery` activa `SKOPOS_LLM_*` sin declaración | B-05; `llavero_core.py:582-589` | I4 |
| G-10 | `probar` imprime el endpoint completo en stdout (metadato de destino fuera de receipts) | `llavero.py:293` | I1 |
| G-11 | ACL efectiva de Keychain no verificada (R-09/B-03) | manifest `no_ofrece` | I7 |
| G-12 | Proceso: repo público con `main` sin protección de rama y push directo historizado; sin labels/milestones/issues que materialicen la deuda B-01…B-05 ni la deuda iCloud | API GitHub: 404 protection; 0 issues | §7 |
| G-13 | Excepciones no-`LlaveroError` producen traceback y exit 1: `main` sólo captura `LlaveroError`; p. ej. `security` con bytes no-UTF-8 → `UnicodeDecodeError` crudo (`text=True` en `_run_security`) | `llavero.py:432-434`; `llavero_core.py:267-274` | I0, I1 |
| G-14 | Asimetría de capacidad entre backends: local tope 1024 B congelado por suite; helper iCloud 16 KiB (`llavero_sync.swift:82`). Cualquier secreto largo (¡PEM de I5!) se vuelve de facto iCloud-only sin decisión | `tests/test_long_secrets.py`; `native/llavero_sync.swift:82` | I5 |
| G-15 | TOCTOU del consumidor sin incremento asignado: realpath → chequeo → secret → exec no elimina carreras de sustitución (F-06 lo admitió); ningún I0–I7 lo recoge | `llavero.py:302-325`; review F-06 | I6/I7 (residual documentado) |
| G-16 | Exfiltración mismo-UID hoy, sin MCP: `http://127.0.0.1` es legal como `base_url` y `probar` envía el Bearer allí; con perfil mutable (R-08) un proceso del mismo UID que escucha en loopback captura el secreto con la suite verde | `llavero_core.py:551-557`; `llavero.py:213` | I4/I7 (política), residual |
| G-17 | Inyección de reloj inexistente: las únicas lecturas de tiempo son `time.monotonic` (deadline de escritura, duración del recibo); no hay `time.time`/`datetime` en runtime. Expiración (I4) y refresco de token (I5) son impruebas sin un seam de tiempo | `llavero_core.py:315,319`; `llavero.py:220,272` | I4 (tarea previa) |

Menores observados y no bloqueantes: `cmd_list` accede a API privada
(`core._validate_existing_config_directory`); `read_secret` normaliza con
`rstrip("\r\n")` (coherente porque la escritura rechaza CR/LF).

### 2.3 Lectura propositiva

El activo diferencial de Llavero no es el almacén (Keychain) sino la
**disciplina de frontera**: captura a ciegas, destino cerrado, allowlists y
falsación con canarios. Los incrementos deben ampliar cobertura (proveedores,
kinds de auth, consumidores-agentes) **sin diluir esa disciplina**: cada
superficie nueva llega con su contrato, sus pruebas de falsación con control
positivo (TM §9), su entrada en `ofrece`/`no_ofrece` y la actualización del
manifiesto en el mismo cambio.

## 3. Principios de los incrementos

1. **Contrato antes que mecanismo**: cada superficie nueva se publica como
   schema versionado y cerrado antes (o junto con) su implementación.
2. **Funcionalidad en cada incremento**: cada I-n termina con algo usable
   por el Operador o por un agente, verificado por pruebas.
3. **Sin secreto en superficies nuevas**, con criterio de ausencia siempre
   acompañado de control positivo que demuestre que el arnés podría
   detectarlo (TM §9). La ausencia sin control positivo no acredita nada.
4. **Compatibilidad con pérdida**: los perfiles v1/v2 existentes siguen
   legibles; los cambios de interpretación exigen schema nuevo
   (`llavero/profile/v3`, D7) o migración explícita.
5. **Deuda visible**: cada incremento abre/cierra issues GitHub (§7); un
   criterio de aceptación fallido **bloquea el incremento** (FIX-AND-RETRY,
   §9) — abrir un issue no pospone un criterio.
6. **Manifiesto sincronizado**: `project-manifest.yaml` se actualiza en el
   mismo cambio que altera lo ofrecido/pospuesto/consumido; un criterio
   documental explícito por incremento.

## 4. Hoja de ruta I0–I7

### I0 — Higiene y línea base de superficie

**Funcionalidad entregada:** CLI predecible para scripts: listado
resiliente (local e iCloud), timeouts de lectura, errores tipados, exit
codes documentados.

- `cmd_list` local: continuar tras perfil inválido, resumir al final
  (`N válidos, M inválidos`), exit 1 sólo si hay inválidos; enumerar las
  clases de corrupción probadas (JSON roto, identificador inválido, symlink,
  permisos) con una `subTest` por clase.
- `cmd_list --icloud`: tolerar identificadores hostiles sin abortar el
  listado completo (G-7, rama iCloud).
- Timeout en `_run_security` vía constante de módulo parcheable (patrón
  existente `_SECURITY_WRITE_TIMEOUT` y su prueba a 0.2 s); al vencer,
  error tipado (subclase de `LlaveroError`), no `subprocess.TimeoutExpired`
  crudo; `main` lo mapea al exit code documentado.
- Captura de excepciones no-`LlaveroError` (G-13): `UnicodeDecodeError`,
  `OSError` de almacén → error tipado saneado sin traceback.
- Eliminar uso de API privada desde `llavero.py`.
- Documentar exit codes vigentes por operación en `docs/cli.md` (nuevo; el
  README tiene presupuesto de 300 líneas con 240 usadas — no engordarlo).

**Criterios de aceptación:**
- Listado con un perfil de cada clase corrupta: los demás perfiles siguen
  listándose; el resumen cuenta las clases; exit 1 al final.
- Listado iCloud con un identificador inválido inyectado por doble: el
  resto se lista; sin traceback.
- `security` doble dormido con constante a 0.2 s: termina con error tipado
  y exit code documentado (no traceback); la suite completa sigue cabiendo
  en el CI (`timeout-minutes: 15`).
- Bytes no-UTF-8 devueltos por el doble de `security`: error tipado, sin
  traceback (control positivo: la prueba demuestra que el arnés ve el byte
  hostil antes de la captura).
- Ningún cambio de interpretación de perfiles (suite vigente verde).

**Riesgos:** timeout en lectura puede cortar un flujo humano legítimo con
prompt GUI (indistinguible externamente de un cuelgo): el mensaje es
consejo estático honesto («puede requerir desbloqueo del llavero»), no un
diagnóstico; la constante queda parcheable y documentada.

### I1 — Contrato de superficie para agentes `llavero/agent-surface/v1`

**Funcionalidad entregada:** cualquier agente o script consume Llavero con
contrato JSON estable y puede confiar en que ninguna respuesta emitida por
Llavero contiene el secreto.

- Documento `docs/contracts/agent-surface-v1.md`: operaciones `listar`,
  `descriptor`, `presencia`, `validar`, `probar`, `ejecutar`; shapes
  (`llavero/response/v1`); exit codes cerrados por clase; regla dura:
  ninguna operación de lectura devuelve el valor, su longitud ni sufijo.
- Exit codes alineados con el servicio hermano para el mismo público-agente
  (escrubery usa 0/1/2/3 = ok/sin-datos/uso/infraestructura): `0` ok,
  `1` sin datos, `2` uso/validación, `3` almacén/infraestructura local,
  `4` conflicto (CAS, ya-existe), `5` red/proveedor. La divergencia se
  registra en el contrato.
- Flag `--json` uniforme en operaciones de consulta.
- `probar` deja de imprimir el endpoint en stdout (G-10); el destino vive
  sólo en receipt/auditoría.
- Inventario de consumidores de exit codes: la suite actual aserta códigos
  (`test_llavero.py`, `test_providers.py`) y CI los ejecuta — la
  renumeración actualiza la suite en el mismo cambio.

**Criterios de aceptación:**
- Contrato con schemas; suite de contrato con golden files por operación.
- Falsación: canario sembrado como credencial; ausencia en **stdout/stderr
  emitidos por Llavero** en todas las operaciones; para `ejecutar`, sólo
  hasta antes del `execve` (mock del exec, patrón existente) — el entorno
  del consumidor **sí** contiene el secreto por diseño (`env/v1`, L1) y no
  es superficie de este criterio. Control positivo incluido: el arnés
  demuestra que detectaría el canario en esa salida si estuviera.
- Suite actualizada y verde tras la renumeración (regresión de consumidores
  automatizados, incluida CI).

**Riesgos:** la renumeración rompe scripts externos no inventariados; se
anuncia en el release y el contrato versiona ambos esquemas durante una
versión de gracia.

### I2 — Registro de proveedores IA como datos (incremento primario)

**Funcionalidad entregada:** alta, entrega y prueba explícitas para los
principales APIs de modelos de IA, declaradas como datos y con origen único
(hoy la lista vive duplicada a mano en `llavero_core.py:448` y
`llavero.py:397`).

- Nuevo módulo `llavero_providers.py`: registro declarativo — `secret_env`,
  `public_env`, `base_url` canónica, `auth.kind` (`http-bearer` |
  `http-header`), `header` (p. ej. `x-api-key` + `anthropic-version`),
  `probe.path` y `probe.shape`. Un único origen alimenta `_validate_profile`,
  `build_consumer_environment`, los `choices` del argparse y la tabla de
  documentación.
- Cobertura inicial: anthropic, openai, openai-compatible, google, xai,
  moonshot, zhipu, qwen, typesafe-systemone. Evolución **aditiva** de
  `llavero/profile/v2` (no rompe la regla de compatibilidad del README, que
  gobierna migraciones v1→v2).
- `probar` habla el shape de cada proveedor según el registro.
- Fábrica/módulo de fixtures de proveedores (golden petición/respuesta por
  shape) — hoy `test_providers.py` duplica mocks a mano.
- Documentación de variables por proveedor en `docs/proveedores.md`
  generado/validado desde el registro (README enlaza; no crece).

**Criterios de aceptación (dos niveles, separados):**
- Automático (falsable hoy): la petición construida coincide con un golden
  por proveedor (URL, headers, body) generado desde el registro; alta→
  guardar→probar→ejecutar con dobles para cada proveedor; proveedor
  desconocido rechazado cerrado; `docs/proveedores.md` validado contra el
  registro en CI.
- Vivo (manual, opt-in, análogo a `LLAVERO_KEYCHAIN_INTEGRATION=1`): golden
  capturado una vez contra el proveedor real por proveedor, con fecha
  registrada — único modo de que «acreditar protocolo» deje de ser circular
  (un doble local verifica autoconsistencia, no el protocolo real; la ronda
  lo demostró con el mock de TypeSafe escrito por el mismo autor del
  cliente).
- Recibo saneado de `probar` con control positivo: canario sembrado en un
  campo que el recibo podría reflejar (p. ej. `model_reported`) — la prueba
  demuestra que el filtro lo detecta y que el recibo lo excluye (patrón
  existente `test_providers.py:75`).

**Riesgos:** los shapes reales cambian sin aviso → el golden vivo con fecha
hace visible la caducidad; I3 (escrubery) aporta vigencia de metadatos
después.

### I3 — Integración escrubery por contrato

**Funcionalidad entregada:** perfiles enriquecidos con metadatos verificados
del catálogo de modelos — **modelo, ventana de contexto, precios, vigencia y
procedencia**; resolución de identidad vía `resolver`. **`base_url` no está
disponible en el contrato v0 de escrubery** (ninguna operación la sirve; la
ronda lo verificó contra `CONTRATO_API_v0` §3.1/§3.3/§3.7/§3.8): pre-llenar
base_url desde la ficha queda fuera hasta que el repo hermano exponga un
catálogo de endpoints (issue cruzado, §6) — no bloquea este incremento.

- Contrato de consumo `docs/contracts/escrubery-consumption-v1.md`:
  operaciones usadas — CLI `scripts/consultar modelo <proveedor>
  <modelo_id>` (alias posicional, no `consultar_modelo`) y `resolver`;
  exit codes 0/1/2/3 del contrato v0; caché local con TTL = `vigente_hasta`
  (24 h modelos/precios) y **regla explícita para `vigente_hasta: null`**
  (sin caché indefinida; se trata como dato sin vigencia acreditada);
  fail-closed si el servicio no está disponible.
- Tabla de mapeo llavero-provider ↔ escrubery-proveedor: el enum v0 es
  `{anthropic, xai, google, moonshot, zhipu, qwen, meta, typesafe, otro}` —
  **no incluye `openai`** y `typesafe` ≠ `typesafe-systemone`; el mapeo
  declara los pares exactos y usa `otro`/sin-enriquecer para lo no cubierto,
  documentado, nunca adivinado.
- `resolver`: cobertura actual con semilla curada sintética (decisión
  escrubery 2026-08-18) — muchos `issuer_id` reales caerán en `sin_datos`;
  el contrato de consumo lo declara para no vender la resolución como
  completa.
- La API key de escrubery es credencial Llavero (perfil
  `escrubery.<entorno>.api`). Bootstrap preferido: captura TTY. El modo
  `--des-entorno` es DEGRADADO (contrato §6) y queda restringido a CI con
  aviso impreso; el plan no lo normaliza como vía de agentes: el entorno de
  un agente es justo la superficie que Llavero evita.
- Campos importados (`fuente_url`, `fecha_obtencion`, `hash`,
  `estado_verificacion`) pasan obligatoriamente por `validate_public_text`
  (rechaza `Cc/Cf/Zl/Zp`) — la puerta Unicode cerrada en F-08 no se reabre
  por la vía escrubery.
- `validar --json` muestra procedencia y `advertencia_caducidad`.
- `project-manifest.yaml`: `consume: escrubery, requerido: false` en el
  mismo cambio (criterio documental).

**Criterios de aceptación:**
- Dobles de `consultar` (CLI y HTTP) con exit codes v0; perfil generado con
  procedencia completa y campos pasando `validate_public_text` (control
  positivo: doble que devuelve bidi/controles → perfil rechazado).
- Canario-traza devuelto por el doble: ausencia en entorno del consumidor y
  en receipts; presencia **sólo** en el bloque `procedencia` del perfil
  (superficie declarada); control positivo que muestra al arnés
  detectándolo donde no debiera estar.
- Sin escrubery disponible: `perfil` manual funciona igual (mock que lanza).
- Manifiesto actualizado.

**Riesgos:** dependencia de servicio hermano → opcional, cacheada,
`requerido: false`. Los perfiles `--icloud` llevarán procedencia al Keychain
sincronizable: ampliación de superficie de metadatos a la infraestructura de
Apple, declarada en el manifiesto antes de activarse.

### I4 — Namespace, CAS, expiración y auditoría (B-01, R-06, G-1, G-2, G-9)

**Funcionalidad entregada:** multi-entorno real con dueño, sustitución con
versión esperada, expiración y bitácora local post-mortem.

- **Tarea previa (G-17): seam de reloj inyectable** en runtime (hoy no
  existe `time.time`/`datetime`); sin él, expiración y refresco son
  impruebas.
- **Schema `llavero/profile/v3` (D7)**: campos `version`, `expires_at`,
  `adapter.kind`, `procedencia`; los perfiles v1 con rama Skopos implícita
  se leen como `legacy` declarado (grandfathering); nada cambia de
  interpretación sin schema nuevo.
- Namespace `<owner>/<environment>/<credential_id>` con segmentos validados
  independientes y **layout de almacenamiento definido** (subdirectorios por
  segmento o codificación plana en `CONFIG_DIR`; el patrón actual con `/`
  rompería `profile_path`); prueba de traversal por segmento; ids planos
  siguen legibles como `legacy`.
- CAS: `guardar --replace --expected-version`, `borrar
  --expected-version`; conflicto → exit 4. **Alcance honesto:** CAS protege
  contra lost-updates entre invocaciones honestas; **no** contra R-08 (un
  atacante mismo-UID reescribe el artefacto completo, versión incluida).
- `expires_at` RFC3339: `ver`/`ejecutar`/`probar` rechazan expiradas antes
  de tocar almacén o red (patrón `assert_not_called` existente), con reloj
  de prueba.
- `adapter.kind` explícito (B-05/G-9).
- Bitácora `~/.config/llavero/audit.jsonl` con receipts
  `llavero/execution-receipt/v1`: **declarada como contabilidad post-mortem,
  no evidencia forense** — el modo 0600 no la hace append-only ni
  inmutable frente al adversario mismo-UID (que puede truncarla o
  falsificarla); el manifiesto no la venderá como auditoría fuerte.
  El receipt de `ejecutar` se escribe y hace fsync **antes** del `execve`;
  política de fallo decidida en el incremento (fail-closed con DoS posible
  vs. hueco de bitácora: propuesta fail-closed, D8).
- Manifiesto actualizado (mueve `pospuesto` → `ofrece` lo que corresponda).

**Criterios de aceptación:**
- CAS: dos escrituras con la misma base → la segunda falla con exit 4 y
  mensaje cerrado; la primera queda intacta.
- Expiración con reloj de prueba: credencial vencida rechazada antes de
  almacén/red (`read_mock.assert_not_called()`).
- Receipts: canario sembrado en un campo que el recibo refleja → el arnés
  lo detecta (control positivo) y el recibo lo excluye; ejecución normal:
  canario ausente en `audit.jsonl`, stdout y stderr.
- Traversal: id con `..` por segmento rechazado antes de construir ruta.
- Migración legacy documentada y probada.

**Riesgos:** namespace rompe consumidores de id plano → lectura legacy con
aviso en `validar`; la ambigüedad de layout se resuelve dentro del
incremento con la prueba de traversal como árbitro.

### I5 — Kinds de autenticación: GitHub App y header fijo

**Funcionalidad entregada:** autenticación de corta duración para GitHub
(installation token ≤1 h) sin exponer la clave privada de larga vida;
`x-api-key` ya llegado de I2.

- **Bloqueador declarado (ataque aceptado de la ronda): el transporte
  actual no soporta un PEM.** Tope local 1024 B (congelado por suite),
  ASCII imprimible >128 B, `validate_secret` rechaza CR/LF; un PEM RSA-2048
  mide ~1.7 KB. I5 incluye por tanto una workstream previa de
  **secretos largos/multilínea** (nuevo alistamiento de transporte o
  codificación de una línea; decisión en ADR), sin la cual el incremento no
  inicia. La asimetría iCloud 16 KiB vs local 1 KiB (G-14) se decide ahí,
  no por accidente.
- `usage.kind` en el descriptor: `http-bearer`, `http-header`,
  `github-app/v1`.
- Modelo de proceso honesto: Llavero es un CLI que muere tras `ejecutar`
  (`os.execve`) — no hay caché en memoria entre invocaciones. El token de
  instalación se obtiene **por invocación** (dos llamadas a GitHub:
  JWT + canje) o, si el coste molesta, un démon opt-in es decisión futura
  fuera de I5. El PEM nunca se entrega al consumidor: `ejecutar` entrega
  `GH_TOKEN` efímero.
- **Riesgo residual declarado:** el token de instalación porta todos los
  permisos de la instalación (GitHub no permite acotarlos por debajo de
  ella) y es reutilizable fuera del host durante su vigencia ≤1 h — misma
  clase de exposición L1 (`consumer-and-descendants`) que el README
  documenta; la caducidad acota la ventana, no el alcance.
- Dependencia nueva (ADR): `cryptography` o `PyJWT` (stdlib no firma
  RS256); versión fijada.
- `probar` contra `api.github.com` es **llamada viva manual opt-in**
  (patrón `LLAVERO_KEYCHAIN_INTEGRATION=1`), nunca en CI.

**Criterios de aceptación:**
- JWT firmado RS256 verificable por el doble con clave pública de prueba;
  `exp − iat ≤ 3600` afirmado por el doble decodificando el token; rechazo
  de `alg ≠ RS256`.
- PEM ausente en env/argv/stdout/stderr/perfil **y disco, caché y archivos
  temporales** (lista completa de superficies del TM §9, que la v1 del plan
  recortaba), con control positivo por superficie.
- Workstream secretos-largos: secreto de 2 KB multilínea roundtrip local
  (guardar→releer→comparar) con doble; límite nuevo documentado y congelado
  por suite.
- Refresco de token (si se implementa): sólo con reloj de prueba (G-17).
- Manifiesto y modelo de amenazas actualizados con el kind y el residual.

**Compuertas previas (no criterios):** ADR de dependencia; ADR de captura
PEM (`stdin-fd/v1`, contrato §6 OPTIONAL, o captura asistida) — I5 no inicia
sin ambas (D3, D5, §8).

### I6 — Servidor MCP local (adaptador del contrato I1)

**Funcionalidad entregada:** agentes host operan Llavero por MCP en **modo
restringido por defecto**: sólo herramientas de lectura (`listar`,
`descriptor`, `presencia`, `validar`). `probar` y `ejecutar` vienen
**deshabilitadas** salvo política local explícita.

- La v1 del plan reclamaba «garantía estructural: no existe tool leer» —
  **refutado por la ronda y retirado**: `ejecutar` con `/bin/sh -c …` y
  `probar` contra un loopback con perfil mutado (R-08) son lecturas
  estructurales disfrazadas. La garantía real es el modo restringido más
  una política de consumidor.
- Política local para habilitar `probar`/`ejecutar` por MCP: allowlist de
  digest de ejecutable del consumidor (adelanta la identidad mínima de I7);
  sin política, las tools no se publican en `tools/list`.
- Contrato pinado: JSON-RPC 2.0, stdio, JSON por líneas, `protocolVersion`
  MCP exacto negociado en `initialize`; tabla cerrada código-JSON-RPC ↔
  `llavero/response/v1`; golden de `tools/list` (en modo restringido, sin
  `leer`, sin `ejecutar`, sin `probar`).
- `guardar` por MCP: requiere TTY — **declarado gate débil** (cualquier
  software puede asignar un PTY; `isatty` ≠ humano); en modo restringido no
  se publica.
- Empaquetado: `pyproject.toml` + entrypoint; instalación por tag exacto.
- El TOCTOU del consumidor (G-15) no se elimina: el digest se verifica antes
  del exec y la carrera persiste; queda como residual documentado del
  modelo de amenazas.

**Criterios de aceptación:**
- Protocolo contra versión pinada: initialize/tools/list/tools/call y error
  shapes según tabla del contrato.
- Doble stdio por subproceso real con pipes (no sólo handlers in-process):
  el framing queda probado.
- Falsación con control positivo: canario sembrado → ausente en toda
  respuesta MCP; y en modo restringido, `tools/list` no publica
  `ejecutar`/`probar`/`leer` (golden).
- Con política habilitante y digest ajeno al consumidor: `ejecutar` rechaza
  antes de leer el secreto (`read_mock.assert_not_called()`).
- README de agentes en `docs/agentes.md` (no en README raíz; presupuesto
  300/240).

**Riesgos:** un agente host con política habilitante sigue siendo
consumidor L1 completo; la política reduce superficie, no la sustituye.

### I7 — Piloto `broker/v1` (L3) y verificación de ACL (condicionado a I4)

**Funcionalidad entregada:** un consumidor coopera usando la credencial sin
recibir el valor; evidencia de ACL real del Keychain.

- Broker HTTP local: autentica consumidor (digest de ejecutable fijado en
  política versionada), valida destino contra descriptor, agrega auth,
  rechaza redirects, devuelve respuesta saneada.
- **Matriz §10 del modelo de amenazas acotada a niveles implementados**
  (L1/L3): las filas L2 (`fd/v1`, descriptor) se marcan explícitamente
  `no-implementado` con un issue por fila; «completitud» = cero filas sin
  estado. (La v1 prometía la matriz «completa», imposible sin entrega L2.)
- Verificación de ACL con Keychain aislado, **manual, con runbook**
  (creación de llavero desechable, fixtures, desbloqueo, limpieza —
  coherente con TM §10) publicado en `docs/reviews/`.
- Sólo arranca si I4 cerró namespace y política versionada (decisión de la
  ronda 2026-09-18, ahora sí aplicada tras I4).

**Criterios de aceptación:**
- Matriz L1/L3 completa en CI con dobles; filas L2 con issue abierto y
  estado `no-implementado`.
- Canario presente en el gateway falso y ausente en el consumidor (el
  «presente» es el control positivo; precedente existente en suite con
  servidor loopback).
- Informe ACL con runbook ejecutado.

**Riesgos:** el broker entra a la frontera de confianza → aceptación
explícita del residual (contrato §8) antes de activarlo por defecto; el
digest no elimina la carrera TOCTOU (G-15), la acota.

## 5. Borrador normativo mínimo — `llavero/agent-surface/v1`

Extracto; el documento completo se redacta en I1.

- Transportes: CLI JSON (`--json`) y MCP stdio (I6); mismas operaciones.
- Lectura: `listar`, `descriptor`, `presencia`, `validar`, `probar` (red
  opcional, coste declarado). Escritura: `guardar` (TTY obligatorio, gate
  débil declarado). Ejecución: `ejecutar` (ruta absoluta).
- Toda respuesta es `llavero/response/v1`: `{"schema": …, "op": …, "ok":
  true|false, "data"|"error": …, "receipt": …}`; `error` es código cerrado
  + mensaje saneado, nunca valores, headers ni cuerpos.
- Prohibido: cualquier operación que devuelva el valor, su longitud o su
  sufijo; existe `presencia` para eso.
- Exit codes (alineados con escrubery donde coinciden): `0` ok; `1` sin
  datos; `2` uso/validación; `3` almacén/infraestructura local; `4`
  conflicto (CAS/ya-existe); `5` red/proveedor.
- Falsación: toda afirmación de ausencia exige control positivo (TM §9).

## 6. Contrato con escrubery — resumen ejecutivo

- Qué consume Llavero: `modelo` (metadatos de modelo), `resolver` (identidad
  canónica de `issuer_id`, con cobertura sintética actual declarada). Nada
  más; sin escritura, sin eventos, sin firmas.
- Qué **no** consume: `base_url` (no existe en v0), secretos, datos de CLIs.
- Procedencia: cada campo importado conserva `fuente_url`,
  `fecha_obtencion`, `hash` y `estado_verificacion` en el perfil público y
  pasa `validate_public_text`; `pendiente_de_verificar` nunca se presenta
  como confirmado.
- Acoplamiento: `requerido: false` en el manifiesto; caché con TTL y regla
  para `vigente_hasta: null`; la operación local esencial funciona sin
  escrubery.
- **Issue cruzado al repo escrubery** (no bloqueante para I3): exponer
  catálogo de proveedores con `base_url` canónicas y añadir `openai` al
  enum — verificado que v0 no sirve base_urls y que el enum no incluye
  `openai` ni `typesafe-systemone`.

## 7. Mecanismos GitHub

- **Issues**: uno por incremento I0–I7 (milestone propio); issues de deuda
  `debt/B-01…B-05` enlazados a los incrementos que los cierran; **issues de
  deuda iCloud** (activación con helper firmado, compilación con toolchain y
  firma provisionada — hoy `pospuesto` en el manifiesto y huérfanos de
  issue, contradiciendo el principio 5); issues por fila L2 de la matriz
  (I7); issue cruzado a escrubery (§6). Plantilla
  `.github/ISSUE_TEMPLATE/incremento.md` con criterios de aceptación
  copiados de este plan. Labels: `security`, `provider`,
  `agent-surface`, `mcp`, `lifecycle`, `escrubery`, `debt`, `icloud`.
- **Milestones**: `I0-higiene` … `I7-broker`.
- **Protección de `main`** (hoy sin proteger, repo público): requerir PR +
  status checks del workflow antes de merge; releases por tag `v0.x` con
  notas de contrato por versión.
- **Herramientas sugeridas** (vía issue, no imposición): `ruff` (no hay
  linter), `pre-commit` con gitleaks para el repo público, Dependabot
  cuando llegue la primera dependencia runtime (I5). El gate Skevi sigue
  como autoridad de estructura; ninguna herramienta corre sin issue +
  decisión.
- **Presupuesto documental**: README raíz limitado a 300 líneas por el gate
  (240 hoy): los contenidos nuevos van a `docs/cli.md`,
  `docs/proveedores.md`, `docs/agentes.md`, enlazados desde README.

## 8. Decisiones requeridas del Operador

1. Orden: ¿aprobar I0→I7, o seguir la recomendación literal de la ronda
   2026-09-18 (namespace/política primero, esto es, I4 adelantado)? La v2
   hace explícito el trade-off (§1).
2. Autorizar la creación de issues/milestones/labels (§7) — este plan no
   publica nada por sí mismo.
3. ADR de dependencia para I5 (`cryptography` vs `PyJWT`).
4. Activar protección de `main` (requiere admin; propuesto, no ejecutado).
5. Captura PEM multilínea: introducir `stdin-fd/v1` (contrato §6 OPTIONAL)
   y/o workstream de secretos largos (I5).
6. **Ampliación de alcance**: el propósito amplio (contraseñas no-API,
   otros ecosistemas) es de la instrucción del 2026-10-17, no de los
   documentos vigentes; aprobarlo implica actualizar README/manifest o
   mantener el alcance actual y dejarlo como visión.
7. Schema `llavero/profile/v3` para `version`/`expires_at`/`adapter.kind`/
   `procedencia` (I4).
8. Política de bitácora cuando el fsync del receipt falla antes del
   `execve` (propuesta: fail-closed).

## 9. Protocolo de fallo de un incremento

- Un criterio de aceptación fallido **bloquea** el incremento: se corrige y
  se re-verifica (FIX-AND-RETRY), como la ronda 2026-09-18.
- Abrir un issue de deuda **no** pospone un criterio; sólo el Operador
  puede desbloquear un incremento con criterio retirado, y queda registrado
  en el issue del incremento.
- Todo incremento cierra con re-revisión adversarial en contexto fresco si
  tocó superficie de seguridad (I1, I4, I5, I6, I7).
