# Administración de Solicitudes de Compra

## Análisis y alcance

Compras está implementado en `upcv_app/scompras_app`: `models.py`, `views.py`, `form.py`, `urls.py` y `templates/scompras/`. `SolicitudCompra` guarda `codigo_correlativo` (cadena única), `fecha_solicitud` (DateTimeField), `estado`, solicitante, sección, prioridad y descripción. Departamento se obtiene mediante la sección; los detalles están en `InsumoSolicitud` y `ServicioSolicitud`. No existen fechas independientes de creación y modificación en la solicitud, por lo que no se inventan ni se muestran esas fechas.

El receptor `generar_codigo_correlativo` de `views.py` produce dos formatos:

- Institución-departamento-sección-número-año, cuando ambas abreviaturas difieren.
- Institución-departamento-número-año, cuando no corresponde un componente separado de sección.

No se modificó ese receptor ni el flujo normal. Las abreviaturas del correlativo almacenado son la fuente de búsqueda: no se sustituyen por las abreviaturas actuales de los catálogos. La base local estaba vacía antes de las pruebas; no se afirma haber inspeccionado los datos de producción. Se cubren mediante pruebas formatos de cuatro y cinco componentes, códigos históricos irregulares y registros ambiguos.

## Archivos

- `solicitud_admin.py`: consultas progresivas, detalle, edición transaccional y lectura de auditoría.
- `form.py`: `SolicitudAdministracionForm`, exclusivamente fecha, estado y versión firmada.
- `urls.py`: cinco rutas nuevas, sin modificar las anteriores.
- `templates/scompras/base.html`: entrada Configuración → Administración de Solicitudes, sólo para `es_admin`, con selección activa.
- `templates/scompras/administracion_solicitudes.html`: búsqueda, información, historial y modal Bootstrap.
- `static/scompras/administracion_solicitudes.css`: diseño adaptable, menú compacto y efectos limitados a esta pantalla.
- `static/scompras/administracion_solicitudes.js`: Fetch, cancelación de consultas, actualización de tarjetas y confirmación SweetAlert2.
- `test_solicitud_admin.py`: 24 pruebas de comportamiento y seguridad, incluida concurrencia real con dos conexiones PostgreSQL.

Todas esas rutas de archivo corresponden a `upcv_app/scompras_app/`. No se modifican modelos ni otras aplicaciones. No se requieren migraciones ni tablas adicionales.

## Rutas y permisos

Prefijo `/scompras/administracion-solicitudes/`:

| Método | Sufijo | Nombre Django (`scompras:`) |
|---|---|---|
| GET | vacío | administracion_solicitudes |
| GET | opciones/ | administracion_solicitudes_opciones |
| GET | detalle/ | administracion_solicitudes_detalle |
| POST | `<pk>/actualizar/` | administracion_solicitudes_actualizar |
| GET | `<pk>/historial/` | administracion_solicitudes_historial |

Cada petición verifica pertenencia exacta al grupo **Administrador**. No basta ser superusuario ni pertenecer a COMPRAS, PRESUPUESTO o Departamento. Los administradores tienen alcance global en la arquitectura actual; no se omiten restricciones departamentales aplicables a otros roles porque éstos no acceden a esta pantalla. Los endpoints retornan JSON con `success`, y `error`/`code` en errores. La página devuelve 403 para usuarios ajenos al grupo. La edición conserva la protección CSRF; no hay `csrf_exempt`.

## Consultas y formatos históricos

`opciones/?nivel=institucion` obtiene los valores distintos encontrados. Los niveles siguientes son `departamento`, `seccion`, `numero` y `anio`; requieren todos los componentes anteriores como parámetros. El ORM valida el formato mediante regex antes de aplicar `split_part` de PostgreSQL. Aplica filtros progresivos y DISTINCT en la base; ordena números/años por su valor numérico conservando el texto original y sus ceros.

Los códigos de cuatro componentes tienen una opción generada por el servidor: «Sin componente de sección». No se inserta ese texto en ningún correlativo. Los formatos diferentes se contabilizan y pueden consultarse mediante `detalle/?historico=<código exacto>`. No se intenta interpretar códigos con separadores ambiguos o renumerarlos.

El detalle filtra por los cinco componentes y obtiene el código almacenado; no construye una cadena ficticia. Comprueba cero, una o varias coincidencias antes de seleccionar el ID. Incluso si una base antigua careciera de la restricción única, una ambigüedad devuelve 409. El resto de operaciones usa la clave primaria.

El detalle usa `select_related` y `prefetch_related`, incluyendo los catálogos de insumos y servicios, sin consultas por cada fila. La tabla sólo permite lectura. Los datos se insertan en el DOM mediante `textContent` y `Option`, sin interpretar HTML procedente de la base.

Cada cambio de selector borra y deshabilita los posteriores e invalida el detalle anterior. `AbortController` y un contador de versiones descartan respuestas antiguas. Historial usa una cancelación independiente. Hay indicadores, mensajes de ausencia/error y botones de reintento o limpieza. Después de guardar se conserva la selección y se vuelve a consultar el detalle y el historial.

## Edición y reglas de estado

Los estados se obtienen de `SolicitudCompra.ESTADOS`: **Creada, Rechazada, Finalizada**. La corrección administrativa permite seleccionar cualquiera de los estados del modelo, incluido volver a **Creada** desde Finalizada o Rechazada. Esta ampliación se limita a la nueva pantalla administrativa y no cambia las transiciones del flujo operativo habitual.

Las transiciones se bloquean si hay CDP reservados/ejecutados o pasos completados, y se indica que deben gestionarse desde el flujo operativo. Se sigue permitiendo corregir únicamente la fecha. Se conservan el estado actual y las opciones realmente autorizadas; no se inventan estados ni se ejecutan reservas, liberaciones, notificaciones, aprobaciones o movimientos de almacén. Las operaciones de CDP tienen sus propios métodos de negocio y no se invocan desde esta vista.

El servidor valida la fecha ISO y las opciones del formulario. Conserva la hora y microsegundos en la zona configurada y nunca cambia el correlativo, aunque el año de fecha deje de coincidir con el código. Usa `transaction.atomic`, `select_for_update` y una versión firmada (ID, fecha/hora completa, estado, correlativo y última auditoría administrativa), con vencimiento de una hora. Una versión ajena, alterada, vencida o desactualizada devuelve 409; el navegador consulta de nuevo sin sobrescribir cambios ajenos. Dos peticiones simultáneas con la misma versión producen un guardado y un conflicto.

Un UPDATE acotado modifica sólo los campos realmente cambiados. No se llama a la generación de correlativos ni a señales operativas. Una petición sin cambios no realiza UPDATE ni crea auditoría. Si falla la auditoría, la transacción revierte la actualización.

## Auditoría

Se reutiliza `gestion_empleados.models.RegistroAuditoria`, que ya admite cualquier objeto mediante ContentType y cuya administración Django es de sólo lectura. No se modifica esa aplicación.

La acción `scompras_edicion_administrativa` registra FK del administrador, fecha/hora automática, ContentType e ID de solicitud y JSON con correlativo, fecha anterior/nueva y estado anterior/nuevo. Cada operación produce una entrada; la pantalla presenta una fila por campo alterado, ordenada desde la modificación más reciente. Pagina de diez operaciones por página, con hasta veinte filas si cambian ambos campos. No existen endpoints para editar o eliminar entradas. Las operaciones quedan dentro de la misma transacción que el cambio.

## Validación

En la base PostgreSQL local preparada durante el onboarding:

```bash
source /workspace/.upcv/activate.sh
bash /workspace/.upcv/prepare-tests.sh
cd /workspace/Upcv-Tickets/upcv_app
python manage.py test scompras_app.test_solicitud_admin --keepdb --noinput
python manage.py test scompras_app --keepdb --noinput
```

Las 24 pruebas nuevas pasan. Incluyen acceso estricto, CSRF, aislamiento de campos, correlativos históricos, duplicados, detalle real, reglas de estado, presupuesto, pasos, preservación de código/hora/insumos, auditoría/paginación, rollback, versiones obsoletas y dos POST simultáneos. El flujo normal de generación y detalle también se verifica.

La regresión de Compras tiene dos fallos de aserción preexistentes en los mensajes de reversión de transferencias (`test_no_permite_reversa_doble` y `test_reversa_sin_stock_en_destino_hace_rollback`), ya observados antes de esta implementación. No se cambiaron sus tests ni su lógica.

Chromium verificó en escritorio y móvil: habilitación y limpieza de selectores, ceros y opciones reales, detalle, escape de HTML, modal, operación sin cambios, edición de fecha/estado con CSRF, SweetAlert2, historial, selección conservada, cambio rápido con respuesta demorada, fallo/reintento de red y consulta histórica válida/inexistente. El cuerpo del CDN de SweetAlert2 se obtuvo por HTTPS verificado y se sirvió al navegador de pruebas sin alterar la dependencia usada por la aplicación. También se comprobó el fallback de confirmación nativa cuando el CDN no está disponible.

Persisten incidencias generales de la plantilla compartida, ajenas a esta función: inicialización de `sidebar-pin.js` sin `.pin-title`, inicialización de DataTables sin su tabla y referencias a algunos archivos estáticos inexistentes. No se corrigieron globalmente para evitar alterar el resto del sistema. No se observaron errores en el JavaScript nuevo.

`manage.py check` conserva sólo la advertencia previa de namespace `empleados` duplicado. El análisis de migraciones con el historial habilitado no detecta cambios en scompras_app. Los dos historiales de migración defectuosos ya documentados en el onboarding siguen requiriendo su propia corrección; las pruebas locales usan el ajuste de esquema existente para Compras/Tickets. No se valida con ello la aplicación de sus migraciones originales a una base nueva.

## Verificación desde el navegador

1. Arrancar el proyecto con su configuración habitual, PostgreSQL y las migraciones existentes ya aplicadas. En este entorno local: activar `/workspace/.upcv/activate.sh`, ejecutar `/workspace/.upcv/start-db.sh` y arrancar `python manage.py runserver` desde `upcv_app`.
2. Iniciar sesión con un usuario del grupo exacto Administrador. Abrir **Configuración → Administración de Solicitudes**, o la ruta descrita en esta documentación.
3. Seleccionar los componentes de un correlativo existente, o consultar un histórico completo. Si la base está vacía, primero crear una solicitud mediante el flujo habitual; no hay datos de ejemplo incorporados.
4. Revisar los insumos y abrir **Editar fecha y estado**. Corregir la fecha o elegir una transición disponible, confirmar y comprobar que se mantienen el correlativo y los insumos, y que aparece el historial.
5. Abrir la misma solicitud en dos pestañas, guardar en una e intentar guardar la otra: debe aparecer el conflicto y recargarse el detalle.
6. Repetir con un usuario sin ese grupo: no debe ver el menú y las URLs directas deben responder 403, incluidos los endpoints de lectura y POST.

## Diseño y navegación adaptable

La opción se encuentra dentro de **Configuración**, visible sólo para Administrador. El CSS `static/scompras/administracion_solicitudes.css` está limitado a la clase de esta pantalla: mantiene una barra lateral de 240 px en escritorio, con un botón para ocultarla, y un menú deslizable cerrado inicialmente en móvil/tablet. Un fondo permite cerrar el menú y Escape devuelve el foco al botón. La barra lateral cerrada es inerte en dispositivos pequeños para que no reciba foco fuera de pantalla.

Las tarjetas distinguen búsqueda, detalle e historial; los estados tienen badges por color, los controles conservan su altura táctil y las tablas se desplazan horizontalmente dentro de sus tarjetas. Las animaciones respetan la preferencia de movimiento reducido. Las demás pantallas conservan su diseño.
