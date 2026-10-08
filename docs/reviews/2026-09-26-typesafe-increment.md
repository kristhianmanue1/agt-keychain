# Incremento TypeSafe — revisión local

Alcance autorizado: adaptador TypeSafe, configuración consistente, prueba mínima,
listado/validación y sustitución explícita. Backend macOS y env/v1 conservados.
Sin acceso a Keychain real ni llamadas a proveedores; ninguna credencial capturada.

Cambios: perfiles locales v2 con proveedor explícito, variables derivadas y
validación cerrada; perfiles v1 preservados excepto rechazo de contradicciones.
Prueba TypeSafe de una llamada a systemone, clasificación canario, validación
de probabilidades/opción y salida de metadatos. Tiempo acotado, sin reintentos.
Prueba OpenAI-compatible conserva su ruta y limita salida a 256 tokens.
Listar/validar no leen secretos. Sustitución exige --replace.

Autorrevisión adversarial: se comprobó deriva de destino/modelo en v1,
conflictos delivery/proveedor en v2, respuestas vacías o de otro protocolo,
NaN/booleanos usados como probabilidades, opción equivocada, extra de respuestas,
filtrado del secreto canario en salida, cambios por CLI antes de leer credenciales,
y reemplazo no autorizado. La prueba de creación por CLI detectó una falsa
migración de perfil inexistente; se corrigió y se volvió a ejecutar la suite.

Resultado: 36 pruebas pasan (27 existentes y 9 nuevas), diff --check pasa.
Los ensayos usan canarios, mocks y un servidor loopback para redirecciones.
No son evidencia de ACL del Keychain real ni de disponibilidad de Jev.

Riesgos: env/v1 expone la llave al consumidor; mismo UID puede modificar perfiles.
La ruta absoluta no autentica procesos. Cambiar/borrar la copia local no revoca
la llave remota. No hay adopción del contrato de entrega, broker ni fd.
La validación de forma de TypeSafe no establece precisión semántica.
No hubo revisor independiente. Sin commit/push; cambios previos preservados.

Pendiente operativo: el Operador crea el perfil y captura la llave en su terminal.
Después se podrá hacer una prueba real acotada y conectar el piloto de Ágora.
