# `llavero/credential-delivery/v1`

Estado: **PROPUESTO — NO ADOPTADO**

Tipo: contrato neutral de captura, almacenamiento y entrega de credenciales

Implementación observada: ninguna conformidad v1 reclamada

## 1. Propósito

Definir una interfaz independiente del consumidor y del almacén para usar
credenciales sin incorporarlas a prompts, repositorios o configuración en
claro. Puede adoptarlo cualquier proyecto que consuma modelos de IA, dentro o
fuera de ARIA. Skopos es sólo el primer adaptador de compatibilidad.

El contrato separa:

1. captura del secreto;
2. referencia persistida;
3. autorización de uso;
4. entrega al consumidor;
5. aplicación de autenticación al destino;
6. evidencia saneada de la operación.

## 2. No objetivos

- No define el formato interno del almacén.
- No obliga a usar macOS Keychain.
- No convierte variables `SKOPOS_LLM_*` en estándar del ecosistema.
- No acredita que un proveedor remoto elimine o no registre credenciales.
- No autoriza instalar, activar o migrar consumidores.

## 3. Términos normativos

`REQUIRED`, `FORBIDDEN` y `OPTIONAL` expresan requisitos de conformidad. Un
adaptador que no pueda satisfacer un requisito debe rechazar la operación o
declarar un modo degradado definido; nunca reinterpretarlo silenciosamente.

## 4. Identidad de credencial

`credential_id` es opaco para el consumidor y debe cumplir:

```text
^[a-z0-9][a-z0-9._-]{0,62}$
```

Los identificadores no contienen `/`, `\\`, espacios, segmentos `..`, nombre
de variable, valor secreto ni datos personales. El namespace completo es:

```text
<owner>/<environment>/<credential_id>
```

Cada segmento se valida antes de construir rutas o consultas al almacén.

## 5. Descriptor público

El descriptor no contiene el secreto:

```json
{
  "schema": "llavero/credential-descriptor/v1",
  "credential_id": "zai-analysis",
  "owner": "skopos",
  "environment": "development",
  "store": {
    "backend": "macos-keychain/v1",
    "reference": "opaque-store-reference"
  },
  "usage": {
    "kind": "http-bearer",
    "destinations": [
      {
        "scheme": "https",
        "host": "api.z.ai",
        "port": 443,
        "path_prefix": "/api/coding/paas/v4/"
      }
    ]
  },
  "allowed_consumers": ["skopos"],
  "allowed_delivery": ["broker/v1", "fd/v1"],
  "expires_at": null
}
```

`reference` identifica un objeto del almacén; no es el secreto, una copia
cifrada ni una instrucción ejecutable.

### Identidad del consumidor

`allowed_consumers` declara nombres lógicos; no autentica procesos. Antes de
entregar o usar una credencial, el runtime debe enlazar el nombre con evidencia
de identidad apropiada para la plataforma, por ejemplo un requisito de firma
de código o un digest de ejecutable fijado en una política versionada.

PID, nombre de proceso y ruta declarada no bastan por sí solos. Si el modo
seleccionado requiere autenticar al consumidor y el host no puede establecer
esa identidad, la operación falla cerrado; no degrada automáticamente a `env`.

## 6. Métodos de captura

### `interactive-tty/v1` — REQUIRED para el piloto

- Lee desde un TTY controlado por el Operador.
- Desactiva eco.
- Confirma dos veces cuando se crea o sustituye una credencial estática.
- No recibe el valor mediante argumento, historial ni texto de chat.
- Falla cerrado si no existe TTY o las entradas difieren.

### `stdin-fd/v1` — OPTIONAL

- Lee desde un descriptor indicado numéricamente.
- No acepta el valor como argumento.
- Documenta quién crea y hereda el descriptor.
- Cierra el descriptor después de consumirlo.

### `environment-import/v1` — DEGRADADO

Sólo para migración o automatización heredada. Debe advertir que el origen
permanece accesible en el entorno del llamador y eliminarlo del entorno de todo
subproceso que no lo requiera. No es el método recomendado de v1.

## 7. Backends de almacenamiento

Un backend implementa:

```text
put(reference, secret, policy) -> receipt
get(reference, requester, purpose) -> secret_handle
delete(reference, expected_version) -> receipt
status(reference) -> metadata
```

Reglas:

- El valor nunca aparece en receipts, metadata, errores o logs.
- `get` verifica consumidor y propósito antes de revelar o usar el valor.
- `delete` local no se presenta como revocación ante el proveedor.
- La sustitución es explícita y deja evidencia de versión, no del valor.
- Cada backend declara controles de acceso, sincronización y disponibilidad.

Backends inicialmente contemplados:

- `macos-keychain/v1`;
- `memory-ephemeral/v1` para pruebas;
- `external-command/v1`, sólo con protocolo cerrado y ejecutable fijado.

Linux, Windows y gestores cloud requieren contratos de backend separados; no
se simula portabilidad con archivos cifrados propios.

## 8. Modos de entrega

### `env/v1` — compatibilidad

El broker crea un entorno desde allowlist y añade únicamente los nombres
declarados por el adaptador. Debe declarar:

```text
exposure = consumer-and-descendants
```

Está prohibido afirmar que el consumidor no puede leer el secreto.

### `fd/v1` — recomendado cuando el consumidor coopera

El broker crea un pipe, entrega el extremo de lectura mediante un descriptor
fijo y cierra las copias innecesarias. El consumidor lee una vez y cierra.

```text
exposure = descriptor-holders
```

El valor aún existe en memoria del consumidor después de leerlo.

### `broker/v1` — aislamiento del valor

El consumidor envía la petición sin autenticación a un broker local. El broker:

1. autentica al consumidor contra la política de identidad fijada;
2. valida método y destino contra el descriptor;
3. rechaza redirects no autorizados;
4. agrega autenticación;
5. transmite por TLS;
6. devuelve sólo la respuesta saneada necesaria.

```text
exposure = broker-and-provider-gateway
```

El consumidor no recibe el valor. El broker entra en la frontera de confianza
y puede observar el contenido de la petición; esta consecuencia debe aceptarse
antes de activarlo.

## 9. Adaptadores de consumidor

Un adaptador traduce configuración pública, nunca almacenamiento. Interfaz:

```text
prepare(descriptor, public_profile, delivery_mode) -> execution_plan
validate(execution_plan) -> decision
execute(execution_plan, secret_handle) -> execution_receipt
```

`skopos-env/v1` puede mapear temporalmente:

- `api` -> `SKOPOS_LLM_API`
- `base_url` -> `SKOPOS_LLM_BASE_URL`
- `model` -> `SKOPOS_LLM_MODELO`
- secreto -> `SKOPOS_LLM_API_KEY`

Este mapa es compatibilidad L1, no el contrato neutral. La evolución preferida
de Skopos es `fd/v1` o `broker/v1`.

## 10. Validación de destino

- Destinos remotos usan `https` y nombre de host exacto.
- `http` sólo se admite para IP loopback fijada explícitamente.
- No se aceptan credenciales embebidas en URL.
- El puerto efectivo debe coincidir con el descriptor.
- El path debe comenzar con `path_prefix` en frontera de segmentos.
- Redirects se rechazan salvo política explícita que fije también el destino.
- Un argumento de CLI no puede ampliar el destino del descriptor.

## 11. Evidencia y auditoría

Cada operación produce un receipt sin secreto:

```json
{
  "schema": "llavero/execution-receipt/v1",
  "operation_id": "host-generated-id",
  "credential_id": "zai-analysis",
  "consumer": "skopos",
  "delivery": "broker/v1",
  "destination": "https://api.z.ai:443/api/coding/paas/v4/",
  "decision": "allowed",
  "observed_at": "RFC3339 timestamp"
}
```

El receipt demuestra la decisión observada del broker, no que el proveedor
protegió la credencial ni que el modelo efectivo fue el solicitado.

## 12. Errores y salida

- Los errores son códigos cerrados y mensajes saneados.
- Está prohibido incluir valores, headers de autorización o cuerpos completos.
- “No existe” y “no autorizado” pueden compartir mensaje externo para evitar
  enumeración, conservando detalle sólo en auditoría protegida.
- Un fallo del almacén, política o validación del destino es fail-closed.

## 13. Conformidad

Una implementación sólo declara conformidad si:

1. identifica backend, modo y adaptador exactos;
2. pasa la matriz obligatoria del modelo de amenazas;
3. demuestra con canario y controles positivos las superficies prohibidas;
4. documenta riesgo residual y plataformas probadas;
5. no usa “el modelo jamás ve la clave” fuera de la garantía de su nivel;
6. distingue almacenamiento local, entrega, uso remoto y revocación.
7. demuestra el enlace entre consumidor lógico e identidad de proceso.

Ni el v0 ni la Fase 1 local declaran conformidad con este contrato. La Fase 1
implementa sólo transporte `env/v1` y controles defensivos parciales; no aplica
todavía namespace, identidad de consumidor ni política inmutable de destino.

## 14. Piloto propuesto

Alcance inicial:

- macOS;
- una credencial falsa y después una credencial de desarrollo de bajo alcance;
- un consumidor fixture neutral y el adaptador de compatibilidad Skopos;
- `interactive-tty/v1` + `macos-keychain/v1`;
- comparación de `env/v1`, `fd/v1` y `broker/v1`;
- servidor local controlado antes de cualquier proveedor remoto.

Criterio de salida: seleccionar un modo por evidencia, no por conveniencia, y
registrar incompatibilidades que requieran cambios en Skopos.

## 15. Adopción

La adopción requiere una decisión explícita del Operador que identifique:

- versión exacta;
- consumidores incluidos;
- backends y modos aceptados;
- garantías aceptadas;
- riesgo residual;
- autoridad separada para implementar y activar.

Publicar este documento no adopta ni activa el contrato.
