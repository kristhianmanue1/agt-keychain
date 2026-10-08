# Sincronización opcional mediante iCloud Keychain

Estado: **implementación local no activada ni validada entre dos Macs**.

## Mecanismo

El modo `--icloud` usa el helper Swift en `native/llavero_sync.swift`. Este llama
a `SecItemAdd`, `SecItemCopyMatching`, `SecItemUpdate` y `SecItemDelete` con
`kSecAttrSynchronizable=true`. Guarda por separado credenciales y perfiles en
servicios versionados de Keychain; el perfil es público, pero se guarda como
datos de un elemento genérico para que también viaje con iCloud.

El helper recibe solicitudes JSON por stdin y devuelve respuestas JSON por
stdout. Los valores no van en argumentos ni variables de entorno. Llavero
comprueba la firma del ejecutable antes de entregarle cualquier dato. Requiere
un ejecutable provisionado con un identificador y Team ID estables en todas las
Macs. La identidad esperada se configura en
`~/.config/llavero/icloud-helper.json` (directorio 0700, archivo 0600):

```json
{"team_id":"ABCDEFGHIJ","identifier":"com.example.LlaveroSync"}
```

Los valores de ejemplo deben sustituirse por los de la firma real. El helper
firmado debe instalarse en
`~/.local/libexec/LlaveroSync.app/Contents/MacOS/llavero-sync`. Compilar
`native/llavero_sync.swift` con `swiftc` verifica sintaxis, pero **no** entrega
una app provisionada. Una firma ad hoc no basta: la prueba local devolvió
`errSecMissingEntitlement` (-34018). No hay una identidad válida instalada en
el entorno de desarrollo examinado; no se instaló el helper.

## Uso tras instalar y verificar la firma

En la primera Mac, para una credencial nueva:

```bash
./llavero.py --icloud perfil ejemplo.dev.api --base-url https://api.example.org/v1 \
  --modelo MODELO --secret-env EXAMPLE_API_KEY
./llavero.py --icloud guardar ejemplo.dev.api
```

En otra Mac autorizada, con la misma identidad de helper y iCloud Keychain:

```bash
./llavero.py --icloud listar
./llavero.py --icloud ver ejemplo.dev.api
./llavero.py --icloud ejecutar ejemplo.dev.api -- /ruta/absoluta/al/consumidor
```

`--icloud` se indica en cada comando para separar explícitamente los dos
almacenes. No busca ni copia automáticamente entradas locales. Las credenciales
existentes requieren una migración autorizada y verificada por separado.

## Límites y condiciones de validación

- Una lectura posterior en la misma Mac verifica la escritura local, no la
  recepción en otra Mac. Se necesita comprobar la misma entrada y perfil con
  un canario en una segunda Mac, sin imprimir el valor.
- iCloud Keychain debe estar activado en ambas Macs con el mismo Apple Account.
  La sincronización puede ser eventual y su disponibilidad depende de Apple.
- `--icloud borrar` elimina la credencial sincronizable y Apple propagará esa
  eliminación; no revoca la llave ante el proveedor. El perfil permanece.
- Perfil y credencial son elementos distintos. Durante la propagación, uno
  puede llegar antes que el otro; `ejecutar` falla si falta alguno.
- El helper firmado debe tener un grupo de acceso de Keychain estable. Una
  compilación o firma diferente puede dejar de poder leer entradas anteriores.
- La firma reduce el riesgo de ejecutar un helper sustituido; un proceso con
  el mismo UID aún puede cambiar la configuración local de identidad. No se
  reclama aislamiento frente a ese adversario.

Fuentes de plataforma: [TN3137](https://developer.apple.com/documentation/Technotes/tn3137-on-mac-keychains),
[`kSecAttrSynchronizable`](https://developer.apple.com/documentation/security/ksecattrsynchronizable),
[grupos de acceso](https://developer.apple.com/documentation/security/sharing-access-to-keychain-items-among-a-collection-of-apps).
