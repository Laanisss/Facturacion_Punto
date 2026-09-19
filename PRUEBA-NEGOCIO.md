# Revisión del piloto antes de usarlo en un negocio

Usa un negocio de prueba para no mezclar simulaciones con ventas reales. Esta lista no sustituye pruebas fiscales, bancarias, Windows ni de impresión física.

1. Entra con un negocio existente y comprueba sus productos, fotos, logo y ventas antiguas.
2. Crea un producto de L 55 con 10 unidades y un cliente de prueba.
3. Abre una caja con L 100 de fondo.
4. Vende una unidad al cliente con descuento de L 5 y motivo. Recibe L 60. Resultado: total L 50, cambio L 10, stock 9, efectivo esperado L 150. Comprueba el recibo centrado.
5. Registra una salida de L 20 con motivo. Esperado: L 130.
6. Anula esa venta, confirma devolución física y reposición de todos los productos. Resultado: stock 10 y efectivo esperado L 80. La venta sigue visible como anulada.
7. Cierra contando L 80 con una nota. Debe quedar diferencia cero. Recarga: el cierre se conserva y no es editable.
8. Abre una caja nueva. Comprueba que el cierre anterior no cambia por operaciones posteriores.
9. Ajusta el producto a 15 unidades con motivo “Compra recibida”. Revisa el movimiento +5.
10. Activa apertura obligatoria y cierra caja. Intenta vender: debe pedir apertura sin descontar stock.
11. Revisa otro negocio: no debe ver clientes, movimientos, ventas ni cajas del primero.
12. Exporta JSON desde Personalizar y confirma que contiene clientes, cajas y movimientos.
13. Prueba búsqueda, filtros, navegación con Tab y uso a 1366×768. Verifica impresora y tamaño del papel con un recibo real de prueba.
14. En un entorno de prueba, reinicia el servidor conservando el volumen. Confirma persistencia.
15. Antes de lanzamiento, prueba una restauración real en un entorno separado y documenta tiempo y resultado.

El piloto no tiene devoluciones parciales, caja por cajero ni conciliación bancaria automática. El monto de una suscripción aprobada manualmente no es un saldo bancario.
