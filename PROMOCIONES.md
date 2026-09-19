# Crear y usar promociones — Punto 0.5.1 beta

Disponible para propietarios de negocios en Básico, Pro y prueba vigente.

## Crear

1. Abre **Promociones → Crear promoción**.
2. Escribe un nombre, por ejemplo “Semana del café”.
3. Elige porcentaje (entero de 1 a 100), monto fijo en la moneda del negocio, 2×1, 3×2, 4×3 o “Lleva X, paga Y”. En la opción personalizada indica unidades que se llevan (2 a 100) y las que se pagan (al menos 1 y menos de las que se llevan).
4. Define la compra mínima total. Cero significa sin mínimo.
5. Elige fecha inicial y, si quieres, final. Las fechas son de Honduras e incluyen ambos días completos. Deja el final vacío para no fijar vencimiento.
6. Selecciona todo el catálogo o marca productos específicos.
7. Guarda. Puedes programarla, pausarla, activarla y editarla después.

Ejemplos:

- 10% en café: el porcentaje se aplica al importe de los cafés elegibles del pedido.
- L 50 en pedidos desde L 300: selecciona monto fijo 50, compra mínima 300 y todo el catálogo.
- L 20 en productos seleccionados: se descuenta una sola vez del conjunto elegible de la venta, no L 20 por unidad. Nunca supera el importe de los productos elegibles.

## Ofertas 2×1, 3×2 y personalizadas

Se calculan por grupos completos del MISMO producto, sin mezclar artículos diferentes. Puedes seleccionar varios productos elegibles; cada uno forma sus propios grupos.

| Oferta | Unidades del mismo producto | Unidades cobradas |
|---|---|---|
| 2×1 | 2 | 1 |
| 2×1 | 3 | 2 |
| 2×1 | 4 | 2 |
| 3×2 | 7 | 5 |
| 4×3 | 9 | 7 |
| Lleva 5, paga 2 | 12 | 6 |

Los sobrantes se cobran a precio normal. Una unidad de café y una de pan NO completan un 2×1. No hace falta agregar manualmente un producto gratis: pon en el pedido todas las unidades entregadas y selecciona la promoción. El inventario descuenta todas, incluidas las gratuitas. El recibo muestra la oferta y el ahorro.

## Aplicar al cobrar

Agrega productos y pulsa **Cobrar**. En **Promoción** elige la oferta. Solo aparecen promociones vigentes, activas y aplicables al pedido y su compra mínima. Revisa el total antes de confirmar. Puedes dejar “Sin promoción” para no aplicar ninguna.

Una promoción por venta. No se combina con el descuento manual. El servidor vuelve a validar productos, vigencia y compra mínima; no confía en el importe que muestre el navegador. Si otro equipo editó la promoción, se rechaza la operación para revisar las condiciones nuevas antes de cobrar: actualiza los datos y reconstruye el pedido.

El recibo muestra nombre e importe del descuento. La venta guarda una copia de la promoción aplicada: editarla o pausarla después no cambia ventas ni recibos anteriores. Los reintentos de una venta ya guardada devuelven el mismo resultado. Anular una venta promocional devuelve su total neto, no el precio sin descuento, y mantiene el flujo normal de reposición de inventario.

## Reglas y límites

- Porcentajes redondeados al centavo más próximo; medios centavos hacia arriba. Si el resultado fuera cero, no se ofrece la promoción.
- La compra mínima se evalúa sobre todo el pedido antes de descuentos. El descuento se calcula exclusivamente sobre productos elegibles.
- Todo el catálogo incluye productos que agregues después. La selección específica conserva identificadores; un producto eliminado no es elegible.
- Los nombres no son cupones: no hay códigos públicos ni límites de usos en esta versión. Los 2×1 y similares sí están incluidos, por producto.
- Hasta 500 promociones guardadas por negocio; se pausan en lugar de borrarse y puedes reutilizarlas editándolas.
- No se puede cambiar la moneda después de crear promociones, para evitar reinterpretar montos fijos y mínimos.
- Requiere suscripción vigente para crear o modificar. Se pueden consultar y exportar con el acceso vencido.
- Las simulaciones de tarjeta pueden usar promociones, pero siguen sin hacer cargos bancarios.

## Actualización y datos

Esquema v4: migración desde v1, v2 o v3 con copia previa. No cambia promociones antiguas porque esta es la primera versión del módulo. Se conservan los datos de negocio y las suscripciones. La exportación JSON agrega la tabla de promociones, y cada venta nueva puede incluir su instantánea `promotion`.

Consulta ACTUALIZAR.md para reemplazar los archivos de GitHub conservando el servicio y el volumen de Railway.
