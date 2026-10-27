# HU que cubre el arquetipo (copiadas de 20261021_PB_Notificaciones)

## HU-NOT-01: Reportar stock bajo (flujo transaccional R2)
Yo como API de Inventario requiero reportar un nivel de stock bajo, para que el equipo destino (Inventario o Fabricación) se entere oportunamente de la necesidad de reabastecimiento.

1. **Registro.** La API de Inventario envía `POST /notificaciones` en JSON con una API Key válida de rol `inventario` en `X-API-Key`. Campos:
   - `tipo` (obligatorio): `STOCK_BAJO_INSUMO` para materias primas y artículos de terceros, `STOCK_BAJO_PRODUCTO` para cadenas y cuchillas.
   - `evento` (opcional): si no se envía, se toma `DETECTADA`.
   - `productoId` (obligatorio): entero o texto alfanumérico de 1 a 50 caracteres; solo letras, números y guion, sin espacios.
   - `nombre` (obligatorio): texto de 1 a 100 caracteres.
   - `stockActual` y `stockMinimo` (obligatorios): enteros de 0 a 1.000.000.

   Si no existe una alerta activa para ese tipo y productoId, se registra una notificación con:
   - `id`: UUID de 36 caracteres generado por la API.
   - `tipo`.
   - `destino`: `inventario` para STOCK_BAJO_INSUMO, `fabricacion` para STOCK_BAJO_PRODUCTO.
   - `mensaje`: máximo 200 caracteres, calculado a partir del tipo y los datos; **no se guarda**.
   - `fecha de registro`: UTC ISO 8601.
   - Los datos recibidos.

   Además queda activa la alerta de ese tipo y productoId.
2. **Respuesta de registro.** HTTP 201 con el `id` y el mensaje "Notificación registrada correctamente".
3. **Alerta ya activa.** Si ya existe una alerta activa para el mismo tipo y productoId (no resuelta y no expirada) y llega otra vez DETECTADA, no se registra nada. Respuesta: HTTP 200 con el id existente, `duplicada: true` y el mensaje "Ya existe una alerta activa para este artículo".
4. **Datos inválidos.** Se rechazan con HTTP 422, el mensaje "Los datos enviados no cumplen las reglas establecidas" y la lista de campos con su error. Son inválidos:
   - Que falte un campo obligatorio.
   - Tipos o formato incorrectos.
   - productoId con caracteres no permitidos, espacios o más de 50 caracteres.
   - nombre vacío o de más de 100 caracteres.
   - Números con decimales, negativos o mayores a 1.000.000.
   - tipo fuera del catálogo.
   - evento distinto de DETECTADA, REPUESTO o RESUELTA.
5. **Solo se valida la forma.** Aunque `stockActual` no sea menor que `stockMinimo`, el evento se procesa igual.
6. **Concurrencia.** Si llegan dos DETECTADA simultáneas sin alerta activa, se registra una sola notificación; la otra recibe 200 con el id existente.
7. **Falla interna.** HTTP 500 con "No fue posible registrar la notificación, intente de nuevo". No queda nada parcial (ni notificación ni alerta).
8. **Log.** Una línea por evento con:
   - resultado: `REGISTRADA`, `ALERTA_YA_ACTIVA`, `ALERTA_CERRADA` o `RECHAZADA`;
   - tipo;
   - destino;
   - clave de la alerta;
   - id de la notificación, si existe.

**En el Sprint 0:**
- REPUESTO y RESUELTA se aceptan en la validación, pero la resolución de alertas es HU-NOT-02 (Sprint 1). Por ahora responden 200 con "No había una alerta activa" solo si no hay alerta; resolverla de verdad llega en HU-NOT-02.
- Expiración: la alerta guarda `expira_en = creada_en + expiración del tipo` (24 h para stock bajo). Una alerta vencida se trata como no activa: la regla de HU-NOT-02 c5 es necesaria para que c3 sea correcta.

Lectura del flujo, como subconjunto de HU-NOT-09: `GET /notificaciones/estado/{id}` con API Key válida.
- Devuelve id, tipo, destino, mensaje, fechaRegistro y los datos.
- El id no es UUID → 422 "Solicitud inválida: verifique los parámetros enviados".
- El id no existe, o su destino no es el del rol → 404 "Notificación no encontrada". La llave `notificaciones` ve todo.

## HU-NOT-11: Generar API Key (solo lo necesario)
- **Alta.** El script recibe el rol (`inventario`, `fabricacion` o `notificaciones`). Genera una llave aleatoria de al menos 32 bytes y la muestra **una sola vez** junto con su id. Guarda solo el hash SHA-256, el rol, la fecha de creación (UTC) y el estado activa.
- **Rol inválido.** Mensaje "Rol no válido".
- **Límite.** Si el rol ya tiene 2 llaves activas: "Ya existen dos llaves activas para este rol".
- **Secretos.** El valor completo nunca queda en los logs ni en la BD.

## HU-NOT-12: Verificar la API Key (solo lo necesario)
- **Sin llave.** Sin `X-API-Key` o vacío → 401 "Acceso denegado". La documentación (`/docs`, `/openapi.json`) y `/health` no piden llave.
- **Llave inválida.** Si no coincide con ninguna llave activa → 401 "Acceso denegado".
- **Emisor equivocado.** En `POST /notificaciones`, si el emisor del tipo es otro rol → 403 "Acceso denegado". Por ejemplo, fabricacion enviando STOCK_BAJO_INSUMO: el emisor de los STOCK_BAJO_* es inventario.
- **Llave fuera del header.** Una llave en la URL o en el body se ignora → 401.
- **Log de rechazos.** Cada 401/403 deja en el log el motivo (sin llave, llave inválida, emisor no permitido), el endpoint y el rol si se conoce. **Nunca** la llave.
- **Swagger.** Tiene un campo para ingresar la API Key (security scheme APIKeyHeader).
