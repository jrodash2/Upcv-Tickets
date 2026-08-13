# Arquitectura inicial: Gestión de Empleados

## Hallazgos y fuentes oficiales reutilizadas

La aplicación `empleados_app` continúa siendo dueña de la información maestra. La nueva app no reemplaza tablas ni URLs existentes.

| Modelo actual | Información reutilizada |
| --- | --- |
| `Empleado` | DPI, nombres, apellidos, fotografía, tipo/cargo, estado, usuario y QR. |
| `DatosBasicosEmpleado` | Fecha de nacimiento, sexo, estado civil, nacionalidad, grupo étnico, idiomas, dirección, teléfonos, contacto de emergencia y correo institucional. |
| `FormacionAcademicaEmpleado` | Historial de formación, título, centro y fecha. |
| `Contrato` | Historial completo, vigencia, tipo, renglón, sede, puesto, rescisión, motivo, observaciones, usuario y fecha de registro de rescisión. |
| `Sede` / `Puesto` | Catálogos y relaciones organizativas hoy disponibles. |
| `ConfiguracionGeneral` | Nombre, dirección y dos logotipos institucionales. |
| `User`, `Group`, `Permission` | Autenticación, grupos y autorización nativos de Django. |

La interfaz hereda `empleados/base.html`, por lo que conserva Riho, Bootstrap, recursos institucionales, tema claro/oscuro, breadcrumbs, cards y los paquetes existentes de DataTables y SweetAlert.

## Funciones existentes reutilizables

- `perfil_empleado`, `empleado_detalle`, `lista_empleados` y `buscar_empleado_dpi` para consulta y ficha.
- `crear_empleado` y `editar_empleado` para mantenimiento compatible del registro oficial.
- `crear_contrato`, `contratos` y `obtener_puestos_por_sede` para el flujo contractual.
- `Contrato.actualizar_estado_automatico`, `Empleado.tiene_contrato_activo` y `Empleado.contrato_activo` para estado/vigencia.
- `Contrato.rescindir`, `rescindir_contrato` y `usuario_puede_rescindir_contrato` para rescisión y auditoría.
- Exportaciones por vigencia y renglones 029/021, credenciales y fotografías existentes.
- `ConfiguracionGeneralForm` y `configuracion_general` para identidad institucional.

Los indicadores nuevos se concentran en `gestion_empleados/selectors.py`; consultan `Empleado` y `Contrato` directamente y no fuerzan escrituras ni modifican información histórica.

## Brechas detectadas

No se encontraron campos o entidades estructuradas para NIT, correo personal, departamento, sección, procesos de preselección/reclutamiento, lista documental del expediente, evaluaciones, casos judiciales o demandas. `dcargo` y `dcargo2` son texto libre y no sustituyen catálogos de departamento/sección. Tampoco se encontró una entidad denominada Riho: Riho es la plantilla visual instalada.

No se agregan estas entidades en profundidad en esta entrega. Antes de modelarlas se debe confirmar el flujo, los catálogos y las reglas de retención con RR. HH. para evitar duplicación.

## Relación complementaria propuesta e implementada

`ExpedienteEmpleado` usa `OneToOneField` con `Empleado`: agrega únicamente estado del expediente, observaciones y auditoría de actualización. No replica DPI, nombres, contactos ni contratos. Los futuros elementos documentales o etapas repetibles deberían usar `ForeignKey` hacia este expediente; cualquier dato contractual adicional debe relacionarse con `Contrato`.

## Seguridad y evolución

La app define permisos específicos para acceso general, preselección, expedientes, ficha, contratos, rescisión y consulta contractual. Superusuarios conservan acceso total. Para compatibilidad, los grupos administrativos existentes `Administrador` y `Admin_gafetes` acceden sin crear grupos duplicados; el resto debe recibir permisos explícitos.

Las seis áreas futuras tienen rutas, navegación y controles iniciales. Son pantallas deliberadamente informativas hasta implementar cada proceso, de forma incremental, sobre las fuentes oficiales.
