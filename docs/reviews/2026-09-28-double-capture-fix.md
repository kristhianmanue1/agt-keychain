# Corrección de doble captura — 2026-09-28

## Problema y causa

El usuario observó las dos capturas de Llavero y después las dos de security.
El código conectaba stdin a una pseudoterminal, pero dejaba la terminal controladora
heredada. getpass/readpassphrase pueden abrir /dev/tty en lugar de stdin.
Además sólo enviaba una línea y declaraba éxito según el código de salida, sin
comparar el valor guardado. El test anterior sólo leía stdin y no reproducía el caso.

## Cambio

El hijo inicia una sesión nueva, adquiere explícitamente la pseudoterminal como
terminal controladora y ejecuta security. stdout/stderr también quedan en esa
terminal interna, sin eco. El padre espera los dos prompts conocidos y responde
con la clave capturada; no la coloca en argv ni entorno. Termina al vencer 30 s.
Un diálogo distinto falla cerrado, sin volver a preguntar al usuario.

Se limita el transporte a 1024 bytes UTF-8 para evitar desbordar la entrada canónica.
Tras guardar se relee y compara el valor. Si falta o difiere, se informa fallo y
no se promete que la escritura no haya ocurrido. No hay rollback automático.

## Verificación

41 tests pasan con LLAVERO_KEYCHAIN_INTEGRATION=1. Incluyen terminal controladora
real del hijo, ambas capturas internas, timeout, salida cero sin captura, lectura
posterior incorrecta/ausente y tamaño excesivo. El primer fallo de test fue una
apertura r+ no seekable del dispositivo /dev/tty en el doble; corregida a lectura
binaria sin buffering, sin cambiar la implementación para eludir la prueba.

Prueba con macOS Keychain real: crear, sustituir, leer y borrar una entrada canario;
valores coincidentes y ausencia final verificada. Prueba adicional de CLI real bajo
PTY: exactamente dos prompts de Llavero, cero prompts nativos visibles, ningún eco
del canario y lectura correcta. Entrada temporal eliminada. Cero llamadas a Jev;
ninguna modificación a credenciales de uso, perfiles o memoria.

## Autorrevisión y límites

Mismo productor y revisor. El helper sólo recibe ejecutable y argumentos públicos;
el canario comprueba que no hereda variables sensibles. Depende de prompts de
security observados en este macOS: si cambian, expira o rechaza sin proclamar éxito.
Las ventanas de autorización de Keychain pueden aparecer según ACL/desbloqueo;
no se suprimen ni se modifica su política. Verificar coincidencia no valida la clave
ante un proveedor. El estado de escritura tras un timeout continúa siendo incierto.

El repositorio ya tenía cambios en README.md y llavero.py, y core/tests/docs sin
seguimiento. Se conservaron. Esta corrección no atribuye ese conjunto previo a este
encargo ni lo publica automáticamente.
