# Punto 0.5 beta — Operación diaria

Una actualización del diseño y de las funciones del negocio, conservando las suscripciones de 0.4. No es todavía la versión comercial 1.0.

| Área | Qué cambia |
|---|---|
| Inicio | Ventas de hoy en efectivo, ticket promedio, productos, clientes, estado de caja y accesos rápidos. Fechas de Honduras. |
| Diseño | Navegación más clara, tarjetas de resumen, indicadores de estado, filtros, pantallas vacías, foco de teclado visible y adaptación a pantallas pequeñas. Se conservan las tres plantillas, colores, logo y fotos. |
| Caja | Apertura con fondo inicial, una caja compartida por negocio, entradas y salidas con motivo, cierre con efectivo contado, saldo esperado y diferencia. Los cierres son inmutables. |
| Clientes | Registro de nombre, teléfono y nota; búsqueda; historial reciente y total de ventas válidas en efectivo. La venta guarda una copia del nombre del cliente para conservar el recibo original. |
| Venta | Descuento por importe con motivo, selección de cliente, cálculo final en el servidor y recibo con subtotal, descuento y cambio. |
| Anulaciones | Anulación completa con motivo, reposición de todos los productos, registro permanente de la venta y devolución de efectivo registrada en la caja actual. No hace devoluciones bancarias. |
| Productos | Búsqueda por nombre/categoría y filtros por productos agotados o con pocas existencias. |
| Inventario | Ajuste de existencias con motivo y control de cambios concurrentes. Historial de altas/ediciones de stock, ventas, anulaciones y ajustes desde esta versión. |
| Historial | Búsqueda por referencia/cliente y filtros de efectivo, simulación o anuladas. Las anuladas no suman en los ingresos vigentes. |
| Exportación | Copia JSON ampliada: catálogo, ventas, clientes, cajas y movimientos. Sigue disponible con suscripción vencida. |
| Actualizar datos | Botón para recuperar datos del servidor; pide confirmar si hay un pedido en curso, ya que lo vaciará. |
| Migración | Esquema v3, actualización desde v1/v2 y copia SQLite previa. Conserva usuarios, hashes, ventas, productos y suscripciones. |

## Qué incluye cada plan

Todas las funciones operativas nuevas están incluidas tanto en Básico como en Pro. Básico mantiene 100 productos. Pro mantiene 1.000, reportes por fechas, más vendidos, CSV y alertas del reporte. La prueba dura 14 días y usa ventajas Pro. Los precios existentes no se cambian.

## Reglas que necesitas conocer

- La caja es compartida por el negocio, no una caja por empleado. Sigue existiendo una cuenta propietaria por negocio; roles de cajero/gerente vendrán después.
- La apertura obligatoria se activa en Personalizar. Por compatibilidad empieza desactivada: las ventas sin caja se guardan, pero NO se incorporan a una apertura posterior.
- Cerrar caja se permite incluso al vencer la suscripción para conciliar el efectivo. Vender, ajustar inventario, guardar clientes, abrir cajas y registrar entradas/salidas requieren suscripción vigente.
- Saldo esperado = fondo inicial + ventas en efectivo + entradas − salidas − devoluciones registradas en esa caja. El cambio al cliente ya está descontado porque se suma el importe neto de la venta.
- Las simulaciones afectan existencias como en la versión anterior, pero no suman efectivo. Usa un negocio separado para pruebas.
- Anular efectivo requiere una caja abierta, saldo esperado suficiente y confirmación de que devolviste el dinero manualmente. Si la venta era de una caja cerrada, la devolución se registra en la caja ACTUAL; no cambia el cierre anterior.
- La anulación siempre repone todos los productos. Úsala solo si vuelven al inventario. Devoluciones parciales, mermas de producto devuelto y reembolsos bancarios necesitan un flujo posterior.
- Un producto eliminado o cuyo stock excedería el límite impide la anulación completa, sin aplicar cambios parciales.
- El reporte de más vendidos muestra importes brutos de los artículos antes del descuento global. Ventas y ticket promedio usan el total neto después del descuento y excluyen anuladas.
- Reportes por fecha y el inicio descuentan anulaciones de la fecha original de venta; el flujo de caja registra el efectivo devuelto en el turno actual. Son perspectivas distintas y están identificadas en la interfaz.
- El historial de clientes usa ventas asociadas a su identificador; no vincula automáticamente compras antiguas.
- La exportación JSON ampliada no es un importador ni una restauración automática. Una copia completa SQLite sigue siendo necesaria para recuperar el servidor.

## Límites del piloto

Una réplica y un proceso SQLite; requiere internet hacia el servidor. El listado de clientes admite hasta 5.000 por negocio. La interfaz muestra los últimos 100 cierres y 300 movimientos de inventario; la exportación incluye todos los registros. El historial de ventas todavía se descarga completo.

Pendientes: fiscalidad, impuestos y numeración legal; instalador/actualizador Windows; operación offline; múltiples cajeros/sucursales; devoluciones parciales; compras/proveedores y costos/utilidad; recuperación de contraseña/MFA; conexión BAC; cobro recurrente automático; copias externas y pruebas de restauración operativa. No se afirma compatibilidad probada con una impresora física.
