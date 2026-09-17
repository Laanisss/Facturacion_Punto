# BAC HIT: alcance confirmado y trabajo pendiente

Revisión de fuentes públicas: 17 de septiembre de 2026.

## Confirmado por BAC Honduras

BAC describe HIT como una solución que convierte un Android con NFC en un punto de venta para pagos sin contacto, sin un lector adicional. La misma página presenta MiPOS por separado, con conexión Bluetooth. Por tanto, no son nombres intercambiables para diseñar esta integración.

Fuentes oficiales:
- [Puntos de venta BAC Honduras](https://www.baccredomatic.com/es-hn/pymes/puntos-de-venta)
- [Solicitud de afiliación HIT](https://www.baccredomatic.com/es-hn/personas/solicitud-de-afiliacion-hit/solicitud)

Las páginas revisadas explican el producto y la afiliación, pero no proporcionan un contrato técnico de integración Windows → servidor → HIT. No se confirmó una API pública, un SDK, un esquema de apertura de la app o un mecanismo de confirmación para terceros. La ausencia en estas páginas no demuestra que BAC no ofrezca una integración privada.

## Qué pedir a BAC

- Confirmación escrita de si HIT Honduras admite integración con un software de caja externo para Windows.
- Si existe una API servidor a servidor, SDK Android, enlace oficial entre apps o puente autorizado; compatibilidad y requisitos de certificación.
- Documentación, ambiente de pruebas, credenciales de sandbox y contacto técnico.
- Cómo identificar comercio y terminal, emparejarlo y revocar el acceso.
- Monedas, importes, referencias e idempotencia admitidas.
- Mecanismo verificable de confirmación, consultas de estado, tiempos de espera y recuperación tras pérdida de conexión.
- Anulaciones, reembolsos, conciliación, comisiones y contrato aplicable a cada comercio.

No se envió ninguna solicitud ni se contactó a BAC desde esta tarea.

## Arquitectura propuesta, condicionada a soporte oficial

Punto Windows crea un pedido en su servidor. El servidor calcula el total y crea una intención de pago. Solo un mecanismo autorizado por BAC enviaría el importe al dispositivo HIT emparejado. El teléfono procesa la tarjeta y el servidor verifica el resultado con BAC antes de confirmar la venta.

Si BAC solo ofrece un SDK Android, podría requerirse una aplicación compañera autorizada; no se asume que un HTML en Windows pueda invocar directamente una app de Android. Si no existe integración externa, el registro manual de un cobro hecho en HIT es una alternativa distinta y debe identificarse como tal.

## Estado del código

- `/api/payments/bac-hit/status`: informa que BAC no está conectado.
- `/api/payments/bac-hit/charge`: devuelve 501 sin efectuar cargos.
- `/api/sales` con `method: card_simulated`: simulación propia, sin contacto con BAC. Aprueba, rechaza o devuelve error según el escenario seleccionado.
- No hay datos bancarios ni credenciales en el paquete.

Estos endpoints pertenecen a Punto; NO son endpoints de BAC. El bloqueo explícito evita que se confunda la preparación de la integración con una conexión bancaria funcional.
