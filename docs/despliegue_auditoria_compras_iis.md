# Auditoría independiente de Compras y despliegue en IIS

## Causa y corrección

`urls.py` carga `solicitud_admin.py` durante las comprobaciones que preceden a `migrate`. La importación directa de `gestion_empleados.models.RegistroAuditoria` hacía fallar incluso ese comando si la aplicación no estaba copiada en el servidor.

Compras ahora usa únicamente `scompras_app.models.AuditoriaSolicitudCompra`. No se importa Gestión de Empleados desde el módulo, sus pruebas ni su administración Django. No hace falta instalarla, añadirla a INSTALLED_APPS ni copiar su carpeta para esta auditoría.

La tabla propia incluye solicitud, usuario, fecha/hora de modificación, fechas y estados anterior/nuevo y observación opcional. Conserva además correlativo e ID original de la solicitud para identificar el evento aunque se elimine la solicitud por un flujo existente. La FK usa SET_NULL y conserva ambos valores, sin impedir esas eliminaciones ni borrar el historial. `registro_origen_id` identifica las copias del sistema anterior y evita duplicarlas.

El registro y la actualización siguen dentro del mismo `transaction.atomic()`, en la misma base. Los permisos del grupo Administrador, CSRF, bloqueos presupuestarios, consultas por correlativo, control de concurrencia y formato JSON del historial se mantienen. La administración Django de la auditoría permite consultar, pero no crear, editar ni eliminar entradas.

## Archivos modificados

Dentro de `upcv_app/scompras_app/`:

- `models.py`: modelo propio de auditoría.
- `solicitud_admin.py`: guardado, lectura del historial y versión de concurrencia basados en ese modelo.
- `admin.py`: consulta de auditoría de sólo lectura.
- `test_solicitud_admin.py`: pruebas existentes adaptadas a la auditoría propia.

También se actualizó `docs/administracion_solicitudes_compra.md` para sustituir la descripción anterior.

## Archivos nuevos

Dentro de `upcv_app/scompras_app/`:

- `migrations/0029_auditoriasolicitudcompra.py`.
- `management/commands/importar_auditoria_solicitudes.py`.
- `test_auditoria_independiente.py`.
- `standalone_test_settings.py` y `standalone_test_urls.py`, únicamente para pruebas aisladas; **no son configuración de producción**.

Este documento: `docs/despliegue_auditoria_compras_iis.md`.

## Migración

`0029_auditoriasolicitudcompra` depende de `scompras_app.0028_alter_insumo_codigo_presentacion` y del usuario configurado mediante AUTH_USER_MODEL. Contiene exclusivamente `CreateModel` con sus relaciones e índice; no actualiza ni borra solicitudes, correlativos, insumos o auditorías anteriores. No depende de migraciones de Gestión de Empleados.

No se han cambiado los historiales de migración anteriores ni se han aplicado migraciones destructivas. En el entorno cloud, esos historiales contienen defectos previos ya documentados; no se debe usar `--fake`, eliminar filas de django_migrations ni renumerar migraciones para ocultarlos.

## Qué copiar al servidor

1. Respaldar la base PostgreSQL y la carpeta actual antes de sustituir archivos.
2. Copiar **la carpeta completa `upcv_app/scompras_app/` actualizada**, incluidas `migrations`, `management`, `templates` y `static`, a la ubicación de esa aplicación junto al `manage.py` existente. Evitar mezclar archivos de versiones diferentes.
3. No copiar `__pycache__`, entornos virtuales ni configuraciones locales del cloud. Los archivos de pruebas aisladas no son necesarios para ejecutar IIS y pueden omitirse del despliegue; no cambiar DJANGO_SETTINGS_MODULE para apuntar a ellos.
4. No copiar Gestión de Empleados. Los documentos de `docs/` son instrucciones y no son necesarios en el directorio servido por IIS.

**No se requiere modificar `settings.py`, el `urls.py` raíz, `requirements.txt`, `web.config`, WSGI ni la configuración de FastCGI para esta corrección.** `scompras_app` debe seguir incluida en el INSTALLED_APPS existente, con las rutas habituales del servidor.

Si el `settings.py` o el `urls.py` raíz del servidor ya contienen referencias a Gestión de Empleados aunque esa aplicación no existe allí, esas referencias son otro problema de configuración: revisar INSTALLED_APPS, includes de URLs, context processors, middleware o routers que la mencionen. Esta corrección no requiere añadirlas. No sustituir los archivos de configuración del servidor por los del proyecto completo para desplegar una sola aplicación.

## Comandos en Windows Server

Usar una terminal con el entorno virtual que utiliza IIS activado y cambiar al directorio que contiene el `manage.py` del servidor. Ejecutar con los ajustes habituales de producción, **sin `--settings=...standalone...`**.

```powershell
python -m pip check
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py showmigrations scompras_app
python manage.py migrate --plan
```

`makemigrations --check --dry-run` sólo comprueba; **no es necesario generar nuevas migraciones en IIS**. La `0029` ya se entrega en el repositorio.

Revisar el plan. Si Compras ya está al día hasta la `0028`, la única migración nueva de esa aplicación debe ser crear `AuditoriaSolicitudCompra`. Si aparecen migraciones anteriores pendientes o errores de otras aplicaciones, investigarlos antes de continuar; no asumir que el plan prueba que esos historiales antiguos pueden ejecutarse sin errores.

Durante la ventana de actualización, detener temporalmente el grupo de aplicaciones de IIS correspondiente para que no se escriban solicitudes mientras falta la nueva tabla. Después:

```powershell
python manage.py migrate scompras_app
python manage.py importar_auditoria_solicitudes
python manage.py collectstatic --noinput
python manage.py check
```

Si la base usa otro alias, pasar `--database=ALIAS` tanto a migrate como al comando de importación, según la configuración existente. Finalmente, iniciar o reciclar **ese grupo de aplicaciones** desde IIS Manager. No es necesario reiniciar todos los sitios del servidor. Recargar el navegador y verificar una solicitud como Administrador, cambiar fecha/estado y consultar su historial.

## Auditorías anteriores

El comando `importar_auditoria_solicitudes` es opcional si nunca existieron registros con el sistema anterior. Puede ejecutarse de todos modos:

- Si la tabla antigua no existe, informa de ello y termina correctamente. No intenta importar la aplicación ni crear sus tablas.
- Si existe, lee sólo las entradas de ContentType `scompras_app.solicitudcompra` y acción `scompras_edicion_administrativa`. Utiliza introspección y lectura SQL parametrizada de esa tabla, sin importar modelos externos.
- Copia usuario, fecha/hora original, correlativo y valores anteriores/nuevos. Conserva incluso registros cuya solicitud ya no existe, identificados por el ID y correlativo originales.
- No modifica ni elimina registros de origen. `registro_origen_id` único hace que sea seguro repetir el comando.
- Si un registro tiene JSON, fechas o valores inválidos, aborta y revierte esa importación completa; informa del ID a revisar sin alterar el origen. Una restricción de base de datos también revierte la transacción. No borra filas inválidas para continuar.

Si los registros anteriores están en una base distinta a la de Compras, no se copian automáticamente entre bases: el comando opera dentro del alias indicado y conserva el origen intacto. Esa transferencia debe prepararse por separado; no se debe apuntar el comando a una base que no contenga el esquema de Compras actualizado.

## Dependencias revisadas

La auditoría nueva sólo utiliza Django y la base de datos existente; **no añade paquetes Python ni bibliotecas nativas**. Las dependencias que las vistas actuales de Compras ya cargaban son:

- Django y el controlador PostgreSQL (`psycopg2`).
- `openpyxl`, `pandas`, `reportlab`, `xhtml2pdf`, `weasyprint`, `certifi`; Pillow respalda los ImageField. Sus dependencias transitivas siguen en el requirements.txt existente.
- WeasyPrint requiere sus bibliotecas nativas (incluido Pango) en Windows. Debe conservarse la instalación y las rutas de DLL que el servidor usa para sus PDF. La eliminación de la dependencia de auditoría no instala ni cambia esas bibliotecas.
- Bootstrap, iconos y demás recursos estáticos de la plantilla ya existente. SweetAlert2 se carga por el CDN existente y tiene confirmación nativa de respaldo; no se ha añadido dependencia JavaScript.

No se encontraron otros imports Python obligatorios hacia las aplicaciones del proyecto dentro de Compras. Sí existen integraciones previas: `models_empleados.py` es un modelo local no administrado que consulta la tabla externa `empleados_app_empleado`; algunas pantallas/context processors utilizan `tickets_db` y MEDIA_SERVER_TICKETS. Esas pantallas necesitan su conexión/esquema/configuración habitual, pero no requieren copiar el paquete Python de Gestión de Empleados y no participan en la nueva auditoría.

## Validación ejecutada y límites

- `check` con configuración aislada, que sólo instala Django y `scompras_app`: sin incidencias.
- `makemigrations --check --dry-run` en esa configuración: `No changes detected`.
- `migrate --plan` con esa configuración: carga completa y reconoce `0029` sin importar otras aplicaciones.
- La operación real de `0029` se aplicó en una base PostgreSQL local nueva preparada con el esquema previo, y una solicitud existente conservó todos sus valores. Se insertó una auditoría después de crear la tabla. No se fingió la aplicación de los historiales antiguos.
- 30 pruebas nuevas/adaptadas aprobadas: permisos, búsqueda, fecha/estado, historial, CSRF, rollback, concurrencia real, importación ausente/idempotente/inválida, preservación de origen y registros huérfanos. Una prueba bloquea explícitamente los imports de Gestión de Empleados y las demás aplicaciones y carga las URLs/vistas reales de Compras en otro proceso.
- Regresión aislada de toda Compras: 39 de 41 pruebas pasan; persisten únicamente los dos fallos previos de mensajes de reversión de transferencias, sin modificar sus pruebas ni su lógica.
- En la configuración completa del repositorio, `check` mantiene la advertencia previa `urls.W005`, y el chequeo global de migraciones detecta la diferencia previa de Meta options en Gestión de Empleados. No se generó ni modificó esa migración ajena a Compras.

Las pruebas funcionales usan una base desechable con esquema actual porque los historiales originales tienen defectos anteriores. Esto no afirma que todo ese historial pueda aplicarse desde cero. Las pruebas se ejecutaron en Linux/PostgreSQL; no se dispone de acceso al IIS real. La compatibilidad de los imports nuevos se comprobó por aislamiento, y no se introdujo código dependiente de rutas o ejecutables Linux.
