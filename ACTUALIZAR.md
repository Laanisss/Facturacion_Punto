# Actualizar a Punto 0.5.1 beta

Este ZIP actualiza el código; no modifica automáticamente GitHub ni Railway. Puedes actualizar desde el servidor 0.3.1, 0.4 o 0.5. No importa datos del antiguo HTML sin servidor.

1. Antes de actualizar, conserva una copia privada de la base. Dentro del contenedor remoto: `python manage.py backup /data/copias/antes-0.5.1.sqlite3`. Descárgala fuera del volumen por un medio privado. No subas bases ni copias a GitHub.
2. Extrae el ZIP y sube **el contenido de la carpeta Punto-0.5.1-servidor** a la raíz del mismo repositorio, reemplazando los archivos anteriores. Incluye `static/index.html`. Dockerfile, server.py y railway.json deben seguir en la raíz.
3. Conserva tu servicio, dominio, volumen, PUNTO_DB y PUNTO_ORIGIN. Mantén una sola réplica; no borres ni desconectes el volumen.
4. Despliega el commit nuevo mediante tu conexión existente a Railway. Al arrancar, Punto migra de esquema v1/v2/v3 a v4 y guarda antes una copia SQLite consistente en la carpeta `backups` junto a la base; normalmente `/data/backups/`. No sustituye la copia externa del paso 1.
5. Espera el estado saludable y recarga Punto. Verifica que un negocio existente conserva catálogo, usuarios, ventas y suscripción.
6. Entra al negocio y abre Caja. Registra el efectivo físico inicial. Las ventas anteriores a la apertura no se incorporarán a esa caja.
7. Si quieres impedir ventas sin caja, activa **Personalizar → Exigir apertura de caja antes de vender**.
8. Haz la revisión de PRUEBA-NEGOCIO.md en un negocio separado de prueba antes de usar los procesos nuevos con dinero real.

## Empezar con promociones

Tras recargar, abre **Promociones → Crear promoción**. Al cobrar podrás seleccionar una oferta válida. Consulta PROMOCIONES.md. No necesitas cambiar variables de Railway ni instalar dependencias nuevas.

## Administrador

No existe usuario ni contraseña predeterminados. Tu administrador anterior se conserva. Si nunca lo creaste, ejecuta dentro del contenedor remoto del servicio:

```sh
python manage.py create-admin
```

Elige usuario y contraseña de al menos 12 caracteres. Entra con esa cuenta en la misma pantalla de Punto. Registrar un negocio no crea un administrador. Crear-Administrador.bat en tu PC modifica solo la base LOCAL.

## Suscripciones

Los planes y precios de 0.4 se conservan. Si vienes de 0.3.1, configura los precios en **Planes y cobros**. Se cobran períodos de 30 días mediante comprobación manual del pago, sin pasarela automática. Una solicitud conserva el importe aceptado. Renovar el mismo plan activo suma 30 días; cambiar de plan inicia 30 días desde la aprobación sin trasladar tiempo anterior ni prorratear. Suspender no elimina datos.

## Recuperación si falla

Lee el log antes de cambiar variables o borrar archivos. No ejecutes el servidor anterior sobre una base migrada. Para volver atrás: detén el servicio, conserva por separado la base nueva y sus archivos asociados, restaura una copia anterior en una carpeta limpia y apunta PUNTO_DB a esa copia con el código correspondiente. Nunca mezcles una copia con archivos WAL antiguos. Restaurar una copia pierde cambios posteriores: revísalos antes de hacerlo.
