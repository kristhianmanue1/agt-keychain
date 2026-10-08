# Adopción de Skevi en Llavero

Estado: **aplicada localmente al método de desarrollo**, sujeta a las
verificaciones y límites indicados abajo. Skevi no se ejecuta en el runtime.

## F0 — problema y alcance

Llavero maneja credenciales y ya contiene una ruta opcional iCloud pendiente de
activación. Se requiere que los siguientes cambios sean revisables, con
procedencia de las reglas y comprobaciones reproducibles, sin confundir gates
documentales con protección efectiva del Keychain.

Resultado observable: el checkout conserva una copia versionada de las reglas
e instrumentos de Skevi y `check_sizes.py` detecta violaciones de estructura
y tamaño propias de Llavero.

- REQ-1 [restricción; fuente: instrucción del Operador]. Adopción después de
  publicar el árbol preexistente limpio. Criterio: commit previo separado y
  SHA local igual al remoto antes de empezar esta copia.
- REQ-2 [funcional; fuente: instrucción del Operador y corpus Skevi]. Método
  disponible sin dependencia del runtime. Criterio: registro de procedencia,
  archivos copiados comprobables por sus manifiestos y gate local en verde.
- REQ-3 [no funcional; fuente: riesgo del proyecto]. Ningún gate de Skevi
  inspecciona ni publica secretos. Criterio: CI sin variables de credencial,
  permisos de lectura y pruebas con canarios; la validación real de iCloud
  queda separada.

No objetivos: activar iCloud, instalar un helper firmado, migrar credenciales,
reescribir el contrato `credential-delivery/v1`, afirmar que la suite demuestra
aislamiento o sincronización, ni incorporar esta sesión a AN-KLA.

## F1 — adaptación decidida

Origen fijado:
`https://github.com/kristhianmanue1/skevi@d7a80b26962cd66a806943ff46f779de14c16708`.
La rama `main` local y la referencia remota consultada coincidían al copiar.
Los registros de `.skevi/` declaran `plantillas/v10`, `gate/v8` y `corpus/v4`.
Los scripts y documentos normativos se copian sin editar; las decisiones
locales viven en `.skevi/usage-guide.md` y `skevi-gate.json`.
Dos ADR y un antecedente histórico se copiaron como apoyo de procedencia;
sus enlaces hacia otros documentos históricos se ajustaron a URLs del commit
fijado para evitar referencias locales rotas. No forman parte del manifiesto
del corpus normativo y sus `README.md` aclaran que no son decisiones de Llavero.

El gate considera `.memos/` estado local generado y `.DS_Store` basura de
macOS. `AN-KLA.md` es Markdown operativo permitido en la raíz. Su ruta de
lectura mide la espina común más la fase más larga; se eligió un límite local
de 1600 líneas para incluir el contrato de AN-KLA y la guía de memoria.
No se eximen `llavero.py`, `llavero_core.py` ni los documentos activos.

Se copian los cuatro scripts que cubre el manifiesto, pero los gates de
planes y reportes están inactivos hasta que exista un contrato y directorio
aplicable. No se instala un hook Git. El workflow de CI está configurado para macOS
con permisos de sólo lectura; requerirla para fusionar exige un control
positivo de CI y configuración de protección de rama aparte.

## F3 — evidencia y límites

Verificar con los comandos de `.skevi/usage-guide.md`, revisar el diff y
observar el resultado del workflow del commit publicado. Un control positivo
local debe hacer que `check_sizes.py` falle por un `README.md` de 301 líneas
y pase al reducirlo a 300. Este control demuestra la polaridad del script en
ese fixture; no demuestra que GitHub impida un merge con fallo.

El código Swift permanece pendiente de una compilación con toolchain y SDK
compatibles, una firma provisionada y una prueba de sincronización entre dos
Macs. La suite con dobles valida rutas específicas, no ese comportamiento real.
