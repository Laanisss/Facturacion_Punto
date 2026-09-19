# Punto 0.5.1 beta — Promociones

Actualización del piloto con servidor para negocios de comida y productos. Conserva caja, catálogo con fotos, logo, tres plantillas, recibos centrados, usuarios separados por negocio y administración global. Esta beta sigue usando SQLite con una sola réplica. No es todavía la versión comercial 1.0.

**Para actualizar tu Railway existente, empieza por ACTUALIZAR.md.** No hay credenciales de administrador predeterminadas.

## Promociones

Nuevo menú para crear descuentos de porcentaje, monto fijo, 2×1, 3×2 y “lleva X, paga Y”, con vigencia, compra mínima y productos específicos. Se seleccionan al cobrar, se verifican en el servidor y quedan reflejados en el recibo. Incluido en ambos planes. Consulta **PROMOCIONES.md**.

## Novedades de operación y diseño

Consulta **NOVEDADES-0.5.md** para los detalles. Incluye inicio renovado, clientes, descuentos, apertura/cierre de caja, entradas/salidas, anulaciones completas, inventario con historial y exportación ampliada. **PRUEBA-NEGOCIO.md** guía una revisión de punta a punta. Las funciones operativas nuevas están en ambos planes.

## Planes implementados

| Ventaja | Básico | Pro / prueba de 14 días |
|---|---|---|
| Productos | Hasta 100 | Hasta 1.000 |
| Fotos, logo, personalización y recibos | Sí | Sí |
| Caja en efectivo y control de existencias | Sí | Sí |
| Tarjetas de prueba, sin cobros reales | Sí | Sí |
| Historial y exportación completa JSON | Sí | Sí |
| Reportes por fechas de Honduras | — | Sí |
| Promedio de venta y 10 productos más vendidos en efectivo | — | Sí |
| Filtros de existencias bajas en catálogo | Sí | Sí |
| Exportación CSV de ventas por período | — | Sí |
| Cuenta propietaria por negocio | 1 | 1 |

Los precios se definen desde Administración → Planes y cobros. Moneda de suscripción: HNL, independiente de la moneda que use el comercio. Períodos de **30 días**, no meses calendario. Al instalar no se inventa un precio ni se cobra nada.

## Suscripciones

El negocio ve su plan, vencimiento, consumo del catálogo, ventajas y solicitudes. Puede pedir activación/renovación y cancelar una solicitud pendiente. El administrador configura precios, revisa solicitudes, aprueba pagos comprobados manualmente o rechaza con una nota. Las decisiones quedan auditadas y no se pueden repetir para duplicar días. También conserva el control manual de suspensión y vencimiento.

Cambiar de plan inicia un ciclo nuevo sin prorrateo. Renovar el mismo plan activo suma 30 días al vencimiento. Más reglas en ACTUALIZAR.md. Los límites y permisos se verifican en el servidor, no solo en la interfaz.

## Reportes

Filtros por fecha inclusivos en hora de Honduras (UTC−6). Efectivo y tarjetas simuladas se separan; promedio y productos más vendidos incluyen únicamente efectivo y excluyen anuladas. Más vendidos muestra importes antes del descuento global; el total y promedio usan el importe neto. Las alertas muestran inventario actual, independientemente de las fechas seleccionadas. CSV incluye referencia, fecha, método, moneda, total, unidades, estado y descuento; no incluye nombres libres que puedan convertirse en fórmulas de hoja de cálculo.

## Instalación local en Windows

Requiere Python 3.12 compatible y el lanzador `py`. Extrae el ZIP completo, ejecuta `Iniciar-Punto.bat` y abre http://127.0.0.1:8000. Mantén abierta la terminal. `Crear-Administrador.bat` crea un administrador LOCAL. No funciona por doble clic en el HTML; necesitas el servidor. Los BAT no fueron ejecutados en Windows en esta entrega.

Instalación manual:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe manage.py create-admin
.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Para Railway consulta RAILWAY.md y ACTUALIZAR.md. No cambies el volumen al actualizar. PUNTO_DB determina la base; PUNTO_ORIGIN determina el dominio permitido. `start.py` respeta PORT. Solo un proceso y una réplica. Dockerfile y configuración de Railway incluidos.

## Datos y seguridad

SQLite con migración automática de esquema v1/v2/v3 a v4 y copia previa consistente. No migra perfiles del antiguo HTML sin servidor. Contraseñas con scrypt y sal, cookies HttpOnly/SameSite, Secure bajo HTTPS, CSRF, permisos por negocio, auditoría, control de revisiones y operaciones de venta transaccionales. No almacena números completos de tarjeta, CVV o PIN.

Puedes crear una copia completa con `python manage.py backup RUTA_NUEVA.sqlite3`. Contiene datos privados: consérvala fuera del repositorio. Las copias automáticas del proveedor y su retención deben configurarse aparte. Una copia en el mismo volumen no protege contra perder ese volumen.

## Verificación

En esta entrega pasaron 41 pruebas de backend/configuración y cuatro recorridos funcionales de interfaz contra el servidor HTTP. No se completó revisión visual en navegador: falló la descarga de Chromium. Windows e impresión física siguen pendientes.

Ejecuta `python -m pytest -q` en un entorno con requirements.txt. Incluye regresión de sesiones, aislamiento, ventas, caja, inventario, clientes, descuentos, anulaciones, CSRF, configuración Railway y pruebas de precios, aprobación, reintentos, cancelación, cuotas, exportación y migración con copia previa.

Pruebas de interfaz: `npm ci` y, con el entorno Python activado, `npm run test:ui`. El ejecutor inicia un servidor HTTP aislado con una base temporal, crea cuentas y ventas de prueba y lo detiene al terminar. Las pruebas DOM verifican comportamiento; no sustituyen una impresión física ni pruebas en Windows.

## Pendiente antes de 1.0

El cobro bancario recurrente de suscripciones NO está integrado. BAC HIT permanece desconectado y `/api/payments/bac-hit/charge` devuelve 501; las tarjetas de caja son simulaciones. Consulta BAC-HIT.md.

Faltan instalador y actualizador firmado Windows, funcionamiento offline, facturación fiscal, devoluciones parciales y caja por usuario, empleados/sucursales, recuperación de cuenta, MFA, PostgreSQL, almacenamiento separado de imágenes, paginación de historiales grandes, monitoreo, copias externas programadas y restauración operativa probada. La API limita cada solicitud de catálogo a 8 MB; fotos grandes pueden alcanzar ese límite antes que el número de productos del plan. Esta actualización no se despliega automáticamente desde el ZIP.
