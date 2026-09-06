# llavero

Configuración segura de API keys para skopos (y lo que venga). Stdlib
puro, sin dependencias. macOS (usa el Llavero del sistema).

**La regla:** una API key jamás se pega en un chat con un modelo de IA
(queda expuesta al proveedor y al historial). Se escribe a ciegas en tu
terminal, se guarda cifrada, y se inyecta por entorno sólo al proceso
que la necesita — el modelo de IA jamás la ve.

## Uso con skopos + z.ai

```bash
# 1. el perfil (campos NO secretos)
./llavero.py perfil zai --base-url https://api.z.ai/api/paas/v4 \
    --modelo glm-4.7 --api openai

# 2. la key: entrada oculta en TU terminal (nunca en un chat)
./llavero.py guardar zai

# 3. verificar que el proveedor la acepta
./llavero.py probar zai

# 4. correr skopos CON la key inyectada (el modelo no la ve)
./llavero.py ejecutar zai -- skopos watch --solo-indice
```

Otros comandos: `ver <servicio>` (presencia: últimos 4), `borrar
<servicio>`, `guardar --des-entorno VAR` (automatización/tests).

## Almacén

- **Key**: Llavero de macOS, cifrada con tu sesión de usuario
  (`security add-generic-password`, servicio `llavero`).
- **Perfil** (base_url, modelo, api): `~/.config/llavero/<servicio>.json`
  con permisos 0600 — no es secreto, pero no hace ruido.

## Tradeoff declarado (v0)

Durante la escritura, la key pasa por el argv de `security` (ventana de
visibilidad para procesos del MISMO usuario, durante microsegundos).
v1 podrá eliminarlo con un pty. La lectura (`ejecutar`) no tiene esa
ventana: la key va del llavero al entorno del hijo sin pasar por argv.
