# Camino de Punto 0.3 a 1.0

Actualizado: 17 de septiembre de 2026. El orden prioriza datos fiables, control comercial y después cobros reales. Los hitos no son fechas prometidas: la integración HIT depende de BAC.

| Versión | Objetivo | Condición para darla por terminada |
|---|---|---|
| 0.3 | Prototipo visual y ventas de prueba | Fotos, logo, plantillas, recibos centrados, perfiles locales y tarjetas simuladas. Entregado anteriormente. |
| 0.3.1 | Primera base de servidor | Cuentas, aislamiento por negocio, contraseñas con hash, sesiones, ventas transaccionales, administración de acceso y prueba de 14 días. Implementado en este paquete; sin hosting público. |
| 0.4 | Piloto conectado y datos recuperables | Servidor HTTPS persistente, PostgreSQL/migraciones, copias y restauración probadas, migración desde el HTML con verificación de ventas, recuperación de cuenta y MFA del administrador. Probar dos negocios desde dos equipos sin cruce de datos. |
| 0.5 | Aclarar y validar BAC HIT | Afiliación y documentación técnica oficial. Confirmar si HIT permite integración externa desde Windows. Si existe: sandbox, emparejamiento autorizado y cobro de prueba verificado por el servidor. Si no existe: elegir con el usuario registro manual o una solución BAC distinta; no anunciar conexión HIT. |
| 0.6 | Caja para operación diaria | Apertura/cierre, arqueo, descuentos autorizados, impuestos configurables validados, anulaciones y devoluciones auditadas, cajeros/gerentes y reportes. Ningún movimiento debe desaparecer del historial. |
| 0.7 | Suscripción comercial | Planes y funciones definidos, período de prueba, facturación de la plataforma, renovación/cancelación, cobros fallidos y período de gracia. Confirmar eventos con el proveedor y procesarlos una sola vez. No confundir cuotas de Punto con ventas del comercio. |
| 0.8 | Aplicación Windows | Instalador firmado, actualización firmada con recuperación ante fallos y conservación de datos. Diseño de operación offline, cola de ventas y resolución de conflictos; probar cortes de internet sin duplicar ventas. |
| 0.9 | Piloto con negocios reales | Pruebas con impresoras, devoluciones, cierres y cortes de red; monitoreo, soporte, restauración y revisión de seguridad. Validar los requisitos fiscales hondureños aplicables antes de emitir documentos fiscales. |
| 1.0 | Lanzamiento comercial | Piloto aceptado, cobros e inventario conciliados, recuperación probada, requisitos fiscales resueltos, términos/privacidad y soporte preparados. Publicar exactamente qué integración bancaria está certificada y disponible. |

## Decisiones de producto de esta entrega

- La plataforma tiene un administrador global. Cada comercio tiene su propietario; cajeros y sucursales se incorporarán después.
- El administrador gestiona acceso y planes, pero no puede leer contraseñas.
- Los datos del negocio deben poder exportarse aun con acceso suspendido. Suspender no equivale a borrar.
- La prueba dura 14 días como valor inicial; debe revisarse antes del lanzamiento.
- Los planes Basic/Pro no tienen todavía precios ni límites diferenciados. No se genera deuda ni un cargo al elegirlos.
- Los ingresos del comercio deberían liquidarse mediante su propia afiliación bancaria. Punto cobrará su suscripción por un flujo separado. Es una propuesta de arquitectura comercial, pendiente de contratación con los proveedores.
- Las credenciales del banco, cuando existan, se manejarán fuera del HTML y del instalador. No se pedirán PIN, CVV ni números completos de tarjeta en Punto.

## Criterios específicos de cobros antes de 1.0

1. El servidor calcula monto y moneda desde el pedido, y vincula usuario, negocio y terminal.
2. Una referencia única identifica cada intento; los reintentos no duplican el cargo.
3. No se marca una venta como cobrada por un botón del cliente, una captura o un enlace de retorno sin verificar.
4. Se verifica la respuesta mediante el mecanismo oficial de BAC (consulta firmada/evento/SDK, según lo que habiliten).
5. Se resuelven pagos pendientes, rechazos, pérdidas de conexión, reembolsos y conciliación con el estado bancario.
6. Se registran cambios de suscripción y acciones sensibles del administrador, con actor y motivo.

## Próxima entrega concreta: 0.4

Hosting elegido: Railway. Configurar el proyecto y el dominio; preparar el despliegue, persistencia, backups y recuperación. Reunir en paralelo la documentación oficial de integración HIT. El código local y las pruebas pueden avanzar sin credenciales bancarias, pero no se activarán cobros reales sin esa información.
