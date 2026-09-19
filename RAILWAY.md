# Para actualizar un despliegue existente, consulta primero ACTUALIZAR.md.

# Desplegar el piloto de Punto en Railway

Hosting elegido por el propietario: Railway. Esta entrega prepara el despliegue; no crea servicios ni incurre en cargos en tu cuenta.

## Arquitectura de esta entrega

Un servicio Python sirve la interfaz y la API desde el mismo dominio HTTPS. Un volumen persistente conserva SQLite. Una sola réplica y un solo proceso. PostgreSQL sigue pendiente para una fase posterior: añadir un servicio PostgreSQL o DATABASE_URL ahora no hará que este código lo utilice.

## Pasos de despliegue

1. Extrae el ZIP y coloca el **contenido de la carpeta Punto-0.5.1-servidor** en la raíz de un repositorio privado. Dockerfile, railway.json y server.py deben quedar en esa raíz. No subas bases de datos, copias, entornos virtuales ni contraseñas.
2. En Railway crea un proyecto y un servicio conectado a ese repositorio. La configuración incluida selecciona Dockerfile y `python start.py`. Si conservas una carpeta contenedora en el repositorio, configura la raíz del servicio y la ruta del archivo de configuración de Railway para que apunten a ella.
3. Adjunta un volumen al servicio, con ruta de montaje **/data**. Railway proporciona automáticamente RAILWAY_VOLUME_MOUNT_PATH; no simules esa variable manualmente.
4. En el servicio, en Settings → Networking → Public Networking, genera el dominio HTTPS.
5. Configura las variables siguientes y despliega o vuelve a desplegar:

| Variable | Valor |
|---|---|
| PUNTO_DB | `/data/punto.sqlite3` |
| PUNTO_ORIGIN | Tu URL HTTPS exacta generada por Railway, sin ruta; por ejemplo `https://tu-dominio-real` |
| PORT | Usar el puerto que Railway asigne; start.py lo lee automáticamente |

El ejemplo de dominio no es una URL real del proyecto. No uses localhost en PUNTO_ORIGIN para Railway. Si Railway pide un puerto de destino del dominio, debe coincidir con PORT.

6. Mantén una réplica en una región. No configures múltiples instancias para esta base SQLite.
7. Revisa que `/health` responda `{"status":"ok"}` y abre la URL principal. Registra un negocio de prueba.
8. Crea un producto y una venta de prueba, reinicia/redepliega conservando el volumen y comprueba que siguen disponibles.

El primer intento puede fallar si Railway empieza a desplegar antes de configurar el volumen o el dominio. Corrige la configuración y vuelve a desplegar. La aplicación exige esas condiciones para no empezar a guardar datos en almacenamiento efímero.

## Crear tu administrador en el servidor

Abre una sesión remota del servicio con `railway ssh` (CLI autenticada y proyecto/servicio seleccionados). Dentro del contenedor ejecuta:

```sh
python manage.py create-admin
```

El comando pide usuario y contraseña sin imprimirla. Después, entra por la web con esa cuenta. No hay contraseña por defecto ni registro público que pueda crear administradores.

Usa una sesión remota sobre el contenedor desplegado: ejecutar el comando localmente solo crearía un administrador en tu base local. Tampoco uses un pre-deploy para crear la base o el administrador: el volumen se monta al arrancar el servicio, no en esa fase.

## Persistencia y copias

- El archivo `/data/punto.sqlite3` y sus archivos WAL viven en el volumen; no borres ni desconectes ese volumen al actualizar el código.
- Activa y verifica las copias del volumen disponibles en tu proyecto Railway. No quedan activadas por el archivo railway.json.
- También puedes crear una copia consistente dentro del contenedor con `python manage.py backup /data/copias/punto-fecha.sqlite3` y descargarla de forma privada. Una copia dentro del mismo volumen no es una copia externa.
- Antes del uso comercial: realizar y documentar una restauración de prueba, configurar retención y alertas de espacio. Un volumen persistente no sustituye una estrategia de recuperación.

## Dominio, sesiones y límites del piloto

Railway termina HTTPS; PUNTO_ORIGIN hace que Punto emita cookies Secure. La API solo acepta cambios desde ese origen exacto. Si cambias de dominio, actualiza la variable y vuelve a iniciar sesión.

No se confía automáticamente en encabezados X-Forwarded-For. El límite de intentos puede agrupar usuarios que lleguen desde una misma IP del proxy. Antes de abrir el registro masivo, verificar el contrato de proxy/IP de Railway y adaptar los límites por usuario e IP sin aceptar encabezados falsificables.

El proyecto todavía no incluye recuperación de contraseña, MFA, copias automáticas configuradas, migración de datos del HTML ni PostgreSQL. Estos puntos siguen pendientes. HIT permanece desconectado.

## Actualizaciones

Los despliegues actualizan la interfaz servida por el servidor; los clientes la obtienen al recargar. Eso no equivale al actualizador firmado del futuro instalador Windows. No cambies el esquema de datos en producción sin migración y copia previa.

## Verificación realizada

Probados localmente: los controles de configuración de Railway, /health y las funciones del backend. No se ha construido la imagen con Docker ni efectuado un despliegue real en Railway desde esta tarea.

## Referencias oficiales consultadas

- [Configuración como código](https://docs.railway.com/config-as-code/reference)
- [Volúmenes persistentes](https://docs.railway.com/volumes)
- [Dominios y HTTPS](https://docs.railway.com/networking/public-networking)
- [Acceso remoto mediante SSH](https://docs.railway.com/cli/ssh)
