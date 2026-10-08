# Modelo de amenazas de Llavero v1

Estado: **PROPUESTO**

Ámbito observado: `llavero` v0 en macOS, commit
`d9b829eb7fe9dff7add7f6af6d441b7087df52f6`

Última revisión documental: 2026-09-18

Este documento define qué debe proteger una evolución de Llavero. No adopta
el contrato, no modifica el runtime y no certifica la implementación actual.
El commit citado identifica el v0 histórico; la Fase 1 permanece en un árbol
local no comprometido y debe identificarse por artefacto antes de adopción.

## 1. Objetivo de seguridad

Permitir que un consumidor autorizado use una credencial sin introducirla en
un chat, prompt, repositorio, argumento de proceso, salida, log o archivo de
configuración en claro.

La garantía se expresa por mecanismo. Ningún modo puede prometer que “el
modelo jamás ve la clave” sin definir proceso, runtime, herramientas,
descendientes y proveedor. La formulación verificable mínima es:

> El host no incluye deliberadamente el secreto en el prompt ni en el cuerpo
> de la solicitud. Su exposición restante depende del modo de entrega.

## 2. Activos

- Valor de la credencial.
- Identificador y metadatos de la credencial.
- Política que fija consumidor, destino y uso permitido.
- Integridad del perfil de proveedor y del endpoint.
- Registro de accesos, sin contenido secreto.

Los últimos cuatro caracteres y la longitud también son metadatos sensibles:
pueden ayudar a correlacionar o identificar una credencial.

## 3. Actores y fronteras

- **Operador:** introduce, rota y revoca credenciales.
- **Capturador:** recibe el secreto desde una fuente autorizada.
- **Almacén:** Keychain u otro gestor; protege el secreto en reposo.
- **Broker de credenciales:** aplica política y obtiene el secreto.
- **Consumidor:** Skopos u otro programa que necesita usarlo.
- **Descendiente:** proceso iniciado por el consumidor.
- **Proveedor:** endpoint remoto que autentica la petición.
- **Modelo:** inferencia que recibe el contenido serializado como prompt.

El proveedor y el modelo no son sinónimos. El gateway del proveedor procesa la
credencial de transporte aunque el valor no forme parte del prompt.

## 4. Adversarios considerados

1. Texto hostil o instrucciones dentro de una conversación procesada.
2. Consumidor comprometido o con herramientas capaces de leer su entorno.
3. Descendiente innecesario que hereda variables de entorno.
4. Perfil alterado para enviar la credencial a otro endpoint.
5. Nombre de credencial con traversal o colisión de namespace.
6. Observador local capaz de inspeccionar argumentos del mismo usuario.
7. Logs, errores, trazas, volcados o diagnósticos demasiado verbosos.
8. Redirección HTTP, transporte no cifrado o DNS/TLS no esperado.
9. Reutilización de una credencial expirada, revocada o de otro entorno.

## 5. Fuera de alcance inicial

- Compromiso del kernel, Secure Enclave o cuenta raíz.
- Garantizar el comportamiento interno de un proveedor remoto.
- Recuperar una credencial ya expuesta; requiere revocación externa.
- Convertir una API key estática en identidad de corta duración cuando el
  proveedor no ofrece ese mecanismo.

Estas exclusiones no autorizan ignorar controles disponibles del sistema
operativo ni ampliar el alcance de una credencial.

## 6. Riesgos del v0 observado

### R-01 — Entorno heredable — ALTO

`ejecutar` copia el entorno completo, añade `SKOPOS_LLM_API_KEY` y hace
`execvpe`. El consumidor y sus descendientes pueden leer la credencial.

### R-02 — Destino no fijado — ALTO

El perfil acepta un `base_url` arbitrario. La verificación envía un Bearer al
destino configurado sin una política de esquema, host, puerto o redirección.

### R-03 — Traversal de identificador — ALTO

El nombre del servicio forma directamente una ruta de perfil. Un valor con
`../` puede escapar de `~/.config/llavero` y sobrescribir un JSON accesible.

### R-04 — Secreto en argv durante alta — MEDIO

`security add-generic-password -w <secreto>` expone temporalmente el valor en
los argumentos del proceso.

### R-05 — Política de Keychain no especificada — MEDIO

El v0 usa Keychain, pero no declara ni verifica ACL, presencia del usuario,
accesibilidad, sincronización ni aplicación autorizada.

### R-06 — Sin ciclo de vida — MEDIO

No hay expiración, rotación asistida, revocación remota ni auditoría de uso.

### R-07 — Metadatos revelados — BAJO

`ver` imprime longitud y cuatro caracteres. Es útil para diagnóstico, pero no
es necesario para confirmar presencia.

### R-08 — Política mutable bajo el mismo UID — ALTO

El modo `env/v1` lee consumidor y destino desde un perfil `0600`. Esos permisos
excluyen a otros usuarios, no a procesos comprometidos de la misma cuenta. Una
sustitución válida del perfil puede redirigir el siguiente uso.

### R-09 — Aislamiento Keychain no demostrado — ALTO

El backend usa `/usr/bin/security` y su política predeterminada. Sin una prueba
de ACL con Keychain aislado no se afirma que un proceso del mismo usuario quede
impedido de recuperar otras credenciales de Llavero.

### R-10 — Namespace plano — MEDIO

La Fase 1 recomienda `proyecto.entorno.credencial`, pero almacena una sola
cadena como cuenta. La convención no sustituye los campos normativos separados
ni una operación con versión esperada.

## 7. Niveles de entrega

| Nivel | Mecanismo | Quién puede obtener el secreto | Garantía |
|---|---|---|---|
| L0 | Configuración en archivo/chat | Superficie amplia | Prohibido |
| L1 | Variable de entorno | Consumidor y descendientes | Compatibilidad |
| L2 | Descriptor o pipe | Proceso con el descriptor | Exposición reducida |
| L3 | Broker HTTP local | Sólo el broker | Consumidor usa, no recibe |

L2 no protege frente a un consumidor comprometido: éste puede leer el
descriptor. L3 evita entregar el valor, pero el broker ve la solicitud y debe
estar dentro de la frontera de confianza.

## 8. Controles requeridos para v1

- Identificadores con gramática cerrada y ruta confinada tras resolverla.
- HTTPS obligatorio para red remota; HTTP sólo para loopback autorizado.
- Destino fijado por credencial y redirecciones deshabilitadas por defecto.
- Entorno del consumidor construido desde una allowlist mínima.
- Captura TTY sin secreto en argv; entrada vacía y discrepancia fallan cerrado.
- Adaptadores `env`, `fd` y `broker` con garantías distintas y explícitas.
- Keychain con política declarada y comprobable.
- Logs estructurados de metadatos, nunca valores ni huellas reversibles.
- Revocación, sustitución y expiración representables en el contrato.
- Errores saneados; ninguna excepción imprime headers o cuerpos sensibles.

## 9. Condiciones de falsación

Una garantía falla si una prueba con secreto canario lo encuentra en una
superficie prohibida: `argv`, entorno no autorizado, stdout, stderr, logs,
perfil, prompt, cuerpo HTTP, historial o archivo temporal persistente.

La ausencia observada sólo es válida si el arnés incluye un control positivo
que demuestre que puede detectar el canario en esa superficie.

## 10. Matriz mínima de pruebas

| Caso | Resultado esperado |
|---|---|
| Captura TTY | Sin eco y sin secreto en argv |
| Identificador `../x` | Rechazo antes de acceder al disco |
| Symlink de perfil | Rechazo fail-closed |
| Endpoint remoto HTTP | Rechazo |
| Redirect a otro host | Rechazo sin reenviar autorización |
| Hijo no autorizado imprime entorno | Canario ausente en L2/L3 |
| Consumidor lee descriptor | Canario presente una vez en L2 |
| Broker agrega autorización | Proveedor falso la recibe; consumidor no |
| stdout/stderr/logs | Canario ausente |
| Credencial revocada/expirada | Uso rechazado antes de red |

Las pruebas usan secretos falsos y servidores locales controlados. Las pruebas
con Keychain real deben ser manuales, aisladas y borrar sólo sus fixtures.

## 11. Riesgo residual

Llavero reduce exposición; no transforma un proceso no confiable en uno
confiable. Si un agente dispone de terminal, depurador o ejecución con la misma
autoridad del broker, la separación necesita además sandbox, identidad de
proceso, mínimo privilegio y restricciones de herramientas.
