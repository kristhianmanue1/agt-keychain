# Ronda adversarial fresca — Fase 1 de Llavero

Fecha local: 2026-09-18

Estado: **FIX-AND-RETRY aplicado; bloqueadores arquitectónicos pendientes**

## Alcance y método

Tres revisores con contexto separado inspeccionaron el mismo árbol local sin
editarlo:

- revisor de seguridad/runtime;
- revisor de contrato, neutralidad y portabilidad;
- revisor de pruebas y condiciones de falsación.

La instancia principal contrastó sus hallazgos contra código y pruebas. Esto es
una ronda multiagente separada, no una auditoría externa ni independencia
institucional. No se infiere consenso por participación.

No se usaron credenciales reales ni Keychain real. Las sondas utilizaron
canarios, mocks y servidores loopback.

## Hallazgos reproducidos y corregidos

### F-01 — Proxy ambiental sobre HTTP loopback — P1

El opener estándar podía obedecer `HTTP_PROXY` y enviar el Bearer fuera del
loopback autorizado. Se añadió `ProxyHandler({})` y una regresión con proxy
ambiental hostil y `NO_PROXY` vacío.

### F-02 — Hooks ejecutables en `public_env` — P1

Se aceptaban `BASH_ENV`, `PYTHONPATH`, `NODE_OPTIONS`, `DYLD_*`, proxies y
otras variables que pueden cargar código o interceptar tráfico. Una primera
denylist resultó insuficiente en la segunda revisión; se reemplazó por una
allowlist cerrada de categorías públicas. `secret_env` ahora debe parecer
explícitamente una variable de credencial.

### F-03 — Herencia abierta de `LC_*` — P1

`LC_SECRET` atravesaba la supuesta allowlist. Se sustituyó el prefijo abierto
por la lista cerrada de locales POSIX usados.

### F-04 — Falso OK y excepciones en respuesta 2xx — P1

`{}` se declaraba éxito y `{"choices":[]}` producía `IndexError`. Se añadió
límite de 1 MiB y validación cerrada de `choices[0].message.content`.

### F-05 — Captura sin TTY — P2

`getpass` podía degradarse a stdin redirigido. La captura interactiva ahora
rechaza la operación antes de leer cuando stdin no es TTY.

### F-06 — Resolución tardía del consumidor — P2

`execvpe` resolvía el comando después de recuperar la credencial. Una primera
corrección seguía confiando en `PATH`; la segunda exige ruta absoluta, fija un
`PATH` del sistema y rechaza scripts con shebang `/usr/bin/env`. Esto reduce
riesgo, pero no autentica el binario ni elimina carreras de sustitución.

### F-07 — Controles de prueba insuficientes — P2

Se fortalecieron pruebas de TTY/no-echo, entorno, respuesta HTTP, redirect,
atomicidad, schema genérico, hooks peligrosos y orden de resolución/lectura.

### F-08 — Controles Unicode en metadatos — P2

La contraprueba final reprodujo aceptación de controles C1, formato bidi y
separadores Unicode que podían falsear salida visual o de terminal. Los campos
públicos rechazan ahora las categorías `Cc`, `Cf`, `Zl` y `Zp`, con regresiones
para `U+009B`, `U+202E` y `U+2028`.

## Bloqueadores no resueltos por el parche

### B-01 — Namespace real

El contrato separa owner, environment y credential_id. La implementación sólo
usa una cadena plana. La convención con puntos reduce errores humanos, pero no
es el contrato ni ofrece CAS para sustituir/borrar.

### B-02 — Política inmutable de destino y consumidor

Un perfil `0600` puede ser reemplazado por otro proceso del mismo UID. El modo
`env/v1` tampoco puede impedir que el consumidor reenvíe la clave.

### B-03 — ACL y lectura cruzada de Keychain

La política real de `/usr/bin/security` no se probó con un Keychain aislado.
No se afirma separación entre credenciales frente a procesos del mismo usuario.

### B-04 — Neutralidad de backend y contrato interoperable

La interfaz es neutral respecto del consumidor, pero el módulo operativo aún
acopla macOS, PTY y Keychain. El contrato propuesto carece todavía de schemas
cerrados, errores tipados, CAS y vectores completos de conformidad.

### B-05 — Adaptador Skopos implícito

La ausencia de `delivery` todavía activa compatibilidad Skopos. Debe migrarse a
un `adapter.kind` explícito antes de declarar neutralidad completa.

## Decisión técnica de esta ronda

La Fase 1 puede continuar como **prototipo defensivo `env/v1` para macOS**, no
como estándar adoptado ni aislamiento por consumidor. Los bloqueadores B-01 a
B-05 deben resolverse antes de adopción o de una declaración de conformidad.

El siguiente incremento recomendado es documental y de diseño: descriptor
cerrado + namespace + adaptador explícito + política versionada. Implementar
`broker/v1` antes de cerrar esas identidades sólo movería la ambigüedad a un
proceso con más privilegios.
