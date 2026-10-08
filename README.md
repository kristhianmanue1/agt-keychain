# llavero

Captura, almacenamiento y entrega de credenciales para proyectos que consumen
modelos de IA. La interfaz de consumidor no depende de ARIA ni de Skopos; el
backend implementado en esta fase sí es específico de macOS Keychain.

**Regla:** una credencial no se pega en chats, prompts, repositorios ni
argumentos de proceso. Se introduce a ciegas en una terminal y se entrega según
un perfil explícito del consumidor.

La Fase 1 implementa `env/v1`: la credencial no se incluye deliberadamente en
el prompt o cuerpo HTTP, pero el proceso consumidor y sus descendientes pueden
leerla. No es una frontera de aislamiento frente a código con la misma
autoridad.

## Uso genérico

Este ejemplo configura cualquier aplicación que lea `OPENAI_API_KEY` y
`OPENAI_BASE_URL`. Para evitar colisiones entre proyectos, usa identificadores
con la convención `proyecto.entorno.credencial`:

```bash
./llavero.py perfil miapp.dev.openai \
    --base-url https://api.openai.com/v1 \
    --modelo MODELO_ELEGIDO \
    --secret-env OPENAI_API_KEY \
    --env OPENAI_BASE_URL=https://api.openai.com/v1

./llavero.py guardar miapp.dev.openai
./llavero.py ver miapp.dev.openai
./llavero.py ejecutar miapp.dev.openai -- /ruta/absoluta/al/consumidor
```

`--env` sólo admite configuración pública. Los nombres que parecen secretos
(`*_TOKEN`, `*_PASSWORD`, `*_API_KEY`, etc.) se rechazan; la credencial se
declara exclusivamente con `--secret-env`. Los nombres públicos se limitan a
categorías de configuración como `*_BASE_URL`, `*_MODEL`, `*_API_VERSION`,
`*_PROJECT_ID` y `*_REGION`. Llavero valida forma, no puede determinar si el
Operador colocó accidentalmente un secreto dentro de un valor declarado público.

## Proveedores explícitos: TypeSafe/Jev

Los perfiles nuevos pueden usar `llavero/profile/v2` con proveedor explícito.
El almacén continúa siendo Keychain y la entrega continúa siendo `env/v1`.
Este formato local no implica adopción del contrato propuesto de entrega v1.

Ejemplo para ejecutar manualmente en una terminal (no contiene ninguna llave):

```bash
python3 llavero.py perfil agora.dev.typesafe \
    --provider typesafe-systemone \
    --base-url https://api.typesafe.ai \
    --modelo jev-1.13.0
python3 llavero.py validar agora.dev.typesafe
python3 llavero.py guardar agora.dev.typesafe
python3 llavero.py ver agora.dev.typesafe
python3 llavero.py probar agora.dev.typesafe --timeout 30
```

`guardar` solicita la llave dos veces con entrada oculta. El subproceso de
Keychain usa su propia terminal controladora y responde internamente a sus dos
solicitudes: no deben aparecer `password data for new item` ni `retype password`.
Antes de mostrar «guardada», Llavero relee la entrada y compara su valor sin
imprimirlo. Si la verificación falla, no anuncia éxito; la escritura puede haber
ocurrido y debe comprobarse su estado. Una ventana gráfica de macOS para autorizar
acceso a Keychain es distinta y puede seguir apareciendo según la configuración.
Hasta 128 bytes se conserva el transporte por pseudo-TTY. Entre 129 y 1024
bytes se usa una orden hexadecimal por pipe al modo interactivo de `security`,
sin shell ni secreto en argumentos o entorno, con límite de 30 segundos.
Las claves largas deben ser ASCII imprimible: Unicode y controles se rechazan
antes de escribir, porque la lectura textual de Keychain puede ser ambigua.
La comparación de lectura sigue siendo obligatoria antes de anunciar éxito.

Para sustituir una entrada existente hay que indicar `guardar ID --replace`. Esto sólo sustituye
la copia local; no rota ni revoca credenciales ante el proveedor.

`listar` enumera perfiles válidos sin consultar Keychain. `validar ID` comprueba
configuración, no existencia de la llave ni acceso remoto.
`probar` hace **una llamada remota que puede tener coste**, sin reintentos:
TypeSafe recibe una clasificación sintética en `/v1/systemone`; el resultado
debe tener la forma esperada, probabilidades válidas y la opción correcta.
El recibo impreso contiene modelo solicitado/reportado, duración y consumo
disponible, sin la respuesta completa. No acredita capacidad semántica general.
Los errores HTTP conservan su código sin imprimir cuerpo ni cabeceras.

Variables generadas desde el perfil, sin duplicación editable:

| Proveedor | Secreto | Destino | Modelo |
|---|---|---|---|
| typesafe-systemone | TYPESAFE_API_KEY | TYPESAFE_BASE_URL | TYPESAFE_DEFAULT_MODEL |
| openai-compatible | OPENAI_API_KEY | OPENAI_BASE_URL | OPENAI_MODEL |

TypeSafe usa la raíz `https://api.typesafe.ai`; el adaptador añade
`/v1/systemone`. OpenAI-compatible usa su base que normalmente termina en
`/v1`; el adaptador añade `/chat/completions`. El consumidor debe admitir las
variables declaradas; `OPENAI_MODEL` no es una garantía universal de los SDK.

```bash
python3 llavero.py ejecutar agora.dev.typesafe -- /ruta/absoluta/al/python /ruta/al/piloto.py
```

El piloto debe leer esas variables. No se instala un SDK ni se conecta Ágora
automáticamente. El proceso receptor y sus descendientes pueden leer la llave
y elegir otros destinos: la configuración coherente **no es aislamiento de red**.

Compatibilidad: los perfiles v1 y heredados conservan su interpretación.
No se migran automáticamente; para pasar a v2 se utiliza un identificador nuevo.
V2 rechaza `delivery`, `api` y variables manuales. En perfiles genéricos v1
se rechazan contradicciones entre `base_url`/`modelo` y las variables públicas
con sufijos reconocidos de destino/modelo. Una configuración antes contradictoria
puede ahora requerir corrección explícita del Operador.

API consultada: https://docs.typesafe.ai/api y
https://docs.typesafe.ai/sdk/python/api/constants.
La versión del modelo es configuración fijada para reproducibilidad, no una
garantía de disponibilidad de la cuenta.

## Compatibilidad con Skopos

Un perfil sin bloque genérico conserva el adaptador histórico
`SKOPOS_LLM_*`:

```bash
./llavero.py perfil zai \
    --base-url https://api.z.ai/api/coding/paas/v4 \
    --modelo glm-4.7 --api openai
./llavero.py guardar zai
./llavero.py probar zai
./llavero.py ejecutar zai -- /ruta/absoluta/a/skopos watch --solo-indice
```

Esta compatibilidad no convierte las variables de Skopos en estándar de
Llavero.

## Controles implementados en Fase 1

- Identificadores cerrados: `^[a-z0-9][a-z0-9._-]{0,62}$`.
- Perfiles atómicos con modos `0700/0600`; symlinks rechazados al cargar.
- HTTPS obligatorio para destinos remotos; HTTP sólo para IP loopback.
- Redirecciones HTTP rechazadas durante `probar`.
- Destino del perfil no ampliable desde `--base-url`.
- Entorno base desde lista cerrada; hooks de loader, intérprete y proxy
  rechazados en `--env`.
- Captura interactiva por TTY obligatoria, oculta y confirmada dos veces.
- Entrega a Keychain mediante pseudo-TTY sin secreto en `argv`.
- `ver` confirma presencia sin imprimir longitud o sufijo.
- El consumidor requiere ruta absoluta; scripts con `/usr/bin/env` se rechazan
  y el `PATH` entregado queda fijado a directorios del sistema.

## Almacenamiento y límites

- **Credencial:** Keychain de macOS, servicio `llavero`.
- **Perfil público:** `~/.config/llavero/<credential_id>.json`.
- **Modo implementado:** `env/v1`, exposición
  `consumer-and-descendants`.
- **No implementado todavía:** `fd/v1`, `broker/v1`, identidad fuerte del
  consumidor, rotación o revocación ante el proveedor.

La convención `proyecto.entorno.credencial` aún no es un namespace tipado ni
impide por sí sola colisiones. El perfil `0600` tampoco es una política
inmutable: otro proceso con el mismo UID puede sustituir destino o consumidor.
La ACL efectiva de entradas creadas mediante `/usr/bin/security` no se ha
verificado contra lectura cruzada por otros procesos de la misma cuenta.

Eliminar una entrada local no revoca la credencial en el proveedor.

### Sincronización iCloud: implementación local pendiente de activación

`--icloud` selecciona una ruta separada para perfiles y credenciales nuevas.
Requiere un helper macOS firmado con identidad Apple Developer estable y
aprovisionamiento para el llavero de protección de datos. Sin ese helper falla
cerrado; no cambia ni migra las entradas existentes del llavero `login`.
La disponibilidad en otra Mac requiere iCloud Keychain activo, el mismo Apple
Account y una instalación del helper con la misma identidad de firma.
Consulta [diseño y límites de iCloud](docs/icloud-sync.md). La escritura local
con lectura posterior no demuestra que Apple haya completado la sincronización.

`guardar --des-entorno VAR` permanece sólo para migración o CI y se identifica
como modo degradado. Llavero elimina esa variable de su propio entorno antes de
invocar Keychain y no la hereda al subproceso.

## Diseño

- [Modelo de amenazas](docs/threat-model-v1.md)
- [Contrato neutral `llavero/credential-delivery/v1`](docs/contracts/credential-delivery-v1.md)

El contrato continúa **PROPUESTO — NO ADOPTADO**. Esta Fase 1 implementa un
subconjunto defensivo; no reclama conformidad completa.

## Contexto de agentes con AN-KLA

Este checkout usa AN-KLA como memoria local de trabajo de agentes. No forma
parte del runtime de Llavero ni almacena credenciales. La integración se define
en `AGENTS.md` y `AN-KLA.md`; el store `.an-kla/` permanece local y está excluido
de Git. Para reproducir la instalación desde la etiqueta fijada:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-an-kla.txt
.venv/bin/python -m an_kla --project-root . init
.venv/bin/python -m an_kla --project-root . context status
.venv/bin/python -m an_kla --project-root . verify
```

En una copia donde falte el bloque gestionado, ejecuta primero
`context plan --operation install` y después `context install`. No vuelvas a
ejecutar `context install` encima de archivos administrados modificados. En un
clon nuevo con `AGENTS.md` y `AN-KLA.md` versionados pero sin `.an-kla/`, el
aviso `context_manifest_missing` es esperable: el manifiesto es local y el
bloque canónico sigue verificándose por su contenido.

## Método de desarrollo Skevi

Se adoptó el corpus de Skevi fijado al SHA y versiones declarados en `.skevi/`.
El [registro de uso](.skevi/usage-guide.md) delimita qué se aplica a Llavero,
qué verifican los scripts y qué permanece inactivo. El gate de estructura se
ejecuta con `python3 scripts/check_sizes.py`; su resultado no prueba seguridad
del Keychain ni sincronización entre Macs. El workflow de CI verifica también
la suite de Llavero y la sintaxis Swift, pero no sustituye la validación con
un helper firmado y dos equipos.

## Pruebas

```bash
python3 -m unittest discover -s tests
```

Las pruebas usan credenciales canario y un ejecutable Keychain falso. No leen,
crean ni eliminan entradas reales del Keychain.

### Prueba real opcional de captura

```bash
LLAVERO_KEYCHAIN_INTEGRATION=1 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests
```

Crea y elimina una entrada sintética de nombre aleatorio en Keychain. Verifica la
CLI desde una terminal controladora: dos capturas ocultas, ausencia de los prompts
nativos adicionales y lectura correcta. Sin esa variable la prueba real se omite;
las demás usan dobles y canarios. No consulta proveedores ni modifica claves de uso.
