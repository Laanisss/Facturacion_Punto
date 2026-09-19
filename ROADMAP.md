# Camino de Punto hacia 1.0

## Entregado en 0.5.1 beta

- Promociones de porcentaje, monto fijo, 2×1, 3×2 y combinaciones personalizadas, vigencia, compra mínima y selección de productos.

## Conservado de 0.5 beta

- Diseño del inicio, navegación y pantallas de trabajo renovado.
- Clientes, descuentos con motivo, apertura/cierre de caja, entradas/salidas y anulaciones completas.
- Inventario con ajustes e historial; búsqueda y filtros; exportación ampliada.
- Suscripciones manuales Básico/Pro de 0.4, permisos, aislamiento por negocio y auditoría.
- Migración v1/v2 → v3 con copia previa. SQLite con una sola réplica.

Esta entrega adelanta funciones del antiguo hito de caja. No significa que PostgreSQL, recuperación de cuenta o integración bancaria del roadmap anterior estén terminados.

| Etapa | Trabajo pendiente | Cómo se acepta |
|---|---|---|
| 0.6 · datos y acceso | Recuperación de cuenta, MFA del administrador, roles cajero/gerente, paginación, imágenes separadas, PostgreSQL y migraciones | Dos negocios y varios usuarios sin cruce de datos; copia externa y restauración real verificadas |
| 0.7 · operación avanzada | Apertura por caja/usuario, devoluciones parciales, compras/proveedores, costos, márgenes e impuestos configurables | Ventas, existencias, efectivo, devoluciones y costos conciliados en escenarios reales |
| 0.8 · Windows | Instalador firmado, actualización firmada, recuperación ante fallo, impresión y estrategia offline | Instalación y actualización en Windows, pruebas de desconexión y sincronización sin duplicar ventas |
| Integración BAC | Confirmar posibilidad oficial de conexión HIT desde Windows, contrato, documentación y sandbox | No anunciar integración hasta verificar un pago real por el mecanismo autorizado; si no existe, acordar otra modalidad |
| Suscripciones automáticas | Proveedor, eventos verificados, renovación, fallos, cancelación, facturas y conciliación | No duplicar cobros ni activar planes solo por una respuesta del navegador |
| 0.9 · piloto supervisado | Monitoreo, soporte, carga, seguridad, impresoras, formación y requisitos fiscales aplicables | Negocios piloto completan operación y recuperación; diferencias resueltas |
| 1.0 · lanzamiento | Cerrar los pendientes necesarios para el alcance comercial pactado | Instalación, cobros anunciados, facturación aplicable, datos, soporte y recuperación demostrados |

Los hitos son condiciones de aceptación, no fechas prometidas. Los tickets actuales no tienen validez fiscal y las tarjetas de caja siguen siendo simuladas.
