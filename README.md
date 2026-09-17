# Punto 0.3.1 — base con servidor

Esta entrega continúa la versión 0.3. Incluye el punto de venta conectado a un servidor, cuentas por negocio y panel de administrador. Es una base de desarrollo/piloto, no una versión 1.0 lista para clientes de pago. No está alojada en internet ni conectada a BAC HIT.

## Qué funciona

- Registro de propietario y negocio, inicio y cierre de sesión. Un propietario y un negocio por cuenta en esta etapa.
- Contraseñas con scrypt y sal individual; no se guardan ni se muestran contraseñas originales.
- Sesión mediante cookie HttpOnly, SameSite=Strict, vencimiento de ocho horas y protección CSRF. La cookie usa Secure cuando PUNTO_ORIGIN es HTTPS.
- Catálogo, imágenes, logo, plantillas y recibos centrados de la versión anterior.
- Productos y ventas guardados en SQLite en el servidor. Los datos se conservan al reiniciarlo.
- Cálculo del importe y descuento de inventario en el servidor dentro de una transacción.
- Prevención de cobros duplicados al reintentar la misma solicitud; detección de cambios concurrentes.
- Efectivo y tarjetas simuladas. Las simulaciones se identifican en los recibos y reportes.
- Administrador global: lista de negocios, usuario propietario, estado, plan, vencimiento y número de ventas.
- Alta con prueba gratuita de 14 días (decisión provisional configurable en server.py). No genera cobros.
- Activar/suspender/extender acceso, con motivo y registro de cambios. Al vencer o suspender, se bloquean escrituras; se permite consultar/exportar datos.
- Basic y Pro son etiquetas administrativas: todavía no tienen diferencias de funciones ni precios.

## Hosting elegido: Railway

Incluye Dockerfile, railway.json, arranque con PORT y comprobación de salud. Consulta **RAILWAY.md** para configurar el volumen, dominio HTTPS y administrador. No se ha desplegado todavía. El piloto mantiene SQLite persistente; PostgreSQL está pendiente para la 0.4.

## Ejecutar en Windows

Requiere Python 3.12 o posterior compatible, instalado con el lanzador `py`. La primera instalación necesita internet para descargar dependencias.

1. Extraer toda la carpeta del ZIP.
2. Ejecutar `Iniciar-Punto.bat`. Instala las dependencias en `.venv` y abre el servidor local.
3. Abrir **http://127.0.0.1:8000** con Edge o Chrome. Usar exactamente esta dirección.
4. Pulsar **Registrar negocio** para crear una cuenta de prueba. Las cuentas nuevas empiezan sin productos.
5. Para tu cuenta de administrador, abrir otra ventana y ejecutar `Crear-Administrador.bat`. Pedirá usuario y contraseña de al menos 12 caracteres; no hay una clave predeterminada.
6. Cerrar la sesión del negocio y entrar con la cuenta de administrador para ver el panel de control.

Si los archivos BAT no funcionan, ejecutar desde la carpeta del proyecto:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe manage.py create-admin
.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Mantener abierta la terminal mientras se usa el programa. Ctrl+C detiene el servidor. Los BAT se incluyen como ayuda; el servidor se probó en Linux con Python 3.12, no se ejecutaron los BAT en Windows.

## Cambio respecto al HTML anterior

`static/index.html` se abre a través del servidor; no funciona por doble clic. La versión local 0.3 sigue siendo un archivo separado y no fue reemplazada.

No se importan automáticamente perfiles, contraseñas ni ventas del HTML anterior. Exporta y conserva tus datos antiguos. La migración validada con conciliación de totales forma parte de la 0.4. No copies manualmente contraseñas entre las bases.

El servidor es la fuente de datos. Esta entrega requiere conexión con él para trabajar; no implementa ventas sin conexión ni sincronización en segundo plano. Dos equipos pueden usar el mismo backend cuando esté desplegado y configurado, pero la interfaz no se actualiza en tiempo real: ante un conflicto pide recargar para evitar sobrescrituras.

## Administración y futuro cobro de suscripciones

En el panel puedes cambiar el estado, plan y último día de acceso (UTC). No se borran negocios al suspenderlos. La cuenta de administrador no tiene una caja propia ni una pantalla para ver contraseñas.

Este control de acceso NO cobra una suscripción: no hay pasarela de suscripciones, facturas de la plataforma, cobros recurrentes, devoluciones, correos ni renovación automática. Se añadirán por separado de los pagos que los clientes hagan al negocio.

## BAC HIT

La pantalla de personalización informa que la integración está pendiente. `/api/payments/bac-hit/status` indica `connected: false`. La ruta de cobro devuelve HTTP 501 y no envía tráfico a BAC. El método tarjeta de la caja es un simulador del servidor.

No se inventaron endpoints, enlaces de apertura de HIT, SDK, credenciales ni respuestas bancarias. Consulta `BAC-HIT.md` para la investigación y los requisitos de la conexión real.

## Base de datos y copias

Base predeterminada: `data/punto.sqlite3`. No eliminar esa carpeta al actualizar el código.

Para crear una copia consistente, incluso si hay archivos WAL:

```powershell
.venv\Scripts\python.exe manage.py backup copias\punto-2026-09-17.sqlite3
```

El comando no sobrescribe archivos existentes. La copia incluye información privada de todos los negocios, hashes y sesiones: restringe su acceso. No está cifrada. La exportación JSON de un negocio es distinta de una copia completa del servidor.

La restauración operativa y las pruebas programadas de recuperación están pendientes para la 0.4. Para una restauración manual de desarrollo: detener el servidor, preservar la carpeta data completa, restaurar la copia en una carpeta nueva y usar PUNTO_DB para apuntar a ella. No mezclar un archivo restaurado con WAL antiguos.

## Configuración y despliegue posterior

- `PUNTO_DB`: ruta del archivo SQLite.
- `PUNTO_ORIGIN`: URL exacta, sin barra final, permitida para la interfaz. Predeterminado `http://127.0.0.1:8000`.
- Para un servidor público: dominio HTTPS, proxy configurado, PUNTO_ORIGIN correcto, almacenamiento persistente, copias externas, alertas y revisión de seguridad. Esta entrega no configura hosting, DNS ni certificados.
- Ejecutar un solo proceso para este piloto. La versión multiinstancia requiere PostgreSQL, migraciones y límites de acceso distribuidos.
- La limitación de intentos usa la IP vista por el servidor. Detrás de un proxy debe configurarse y probarse la confianza en encabezados; no confiar en IPs declaradas libremente por el cliente.

## Validación

Quince pruebas del backend y la configuración Railway cubren aislamiento entre negocios, permisos, sesión y CSRF, idempotencia, stock, rechazo de pagos, suspensión/reactivación, expiración, imágenes y bloqueo de BAC real.

```powershell
.venv\Scripts\python.exe -m pytest -q
```

También se verificó la interfaz con happy-dom contra el servidor HTTP: registro, catálogo, efectivo, plantilla, sesión y tarjetas simuladas. Esto verifica la interacción y persistencia, no sustituye una prueba visual en navegador ni una impresión física.

## Límites conocidos antes de venderlo

Faltan recuperación/verificación de cuentas, MFA de administrador, empleados y permisos por rol, auditoría ampliada, facturación fiscal, cierre de caja, anulaciones/devoluciones, reconciliación de pagos reales, paginación de grandes historiales, cuotas de archivos, almacenamiento de imágenes separado, monitoreo y pruebas de carga. El estado del catálogo todavía se almacena como JSON por negocio; una base relacional normalizada es parte de la siguiente fase.

El esquema inicial está marcado con `user_version=1`; no existe aún un motor completo de migraciones. El roadmap define las condiciones necesarias antes de llamar a esto versión 1.0.

Prueba opcional de interfaz: con el servidor de prueba en ejecución, Node.js 24 y una base desechable, ejecutar `npm install` y `npm run test:ui`. La prueba crea un negocio y ventas de prueba; no ejecutarla contra la base de un comercio. Los tests del backend usan una base temporal independiente.
