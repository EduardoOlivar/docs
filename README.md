# docs

Herramientas para recopilar y documentar información pública.

## Proyecto Mercado Público (MVP)

La primera versión consulta **licitaciones** mediante la API oficial v1, identifica registros relacionados con modernización, migraciones, digitalización, integraciones, mantenimiento, desarrollo y datos; guarda el histórico JSON y sincroniza datos descriptivos con Google Sheets.

**No genera puntajes, encajes, recomendaciones de postulación ni análisis inventados.**

> Pendientes: Compra Ágil v2, descarga de bases y análisis del contenido de los adjuntos. Esta versión **no** realiza esas funciones todavía.

Fuente oficial: https://www.chilecompra.cl/api/

### Estructura

```text
.github/workflows/mercado-publico.yml   Workflow manual
config/keywords.json                     Temas que buscamos
scripts/mercado_publico.py               Consulta API v1
scripts/run.py                            Histórico sin duplicados
scripts/google_sheets.py                  Actualiza la hoja
data/licitaciones.json                   Histórico público
tests/test_pipeline.py                   Pruebas unitarias
```

### Probar localmente

Requiere Python 3.12+ y un ticket API de ChileCompra. No subas las credenciales al repositorio público.

```bash
python -m venv venv
# Activa el entorno virtual correspondiente a tu terminal.
pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Configura `MERCADO_PUBLICO_TICKET` en tu entorno y ejecuta:

```bash
python -m scripts.run --days 7 --max-details 70
```

El ticket se solicita en https://www.chilecompra.cl/api/.

### Workflow manual

En GitHub: **Actions → Actualizar Mercado Publico → Run workflow**. No hay horarios ni triggers periódicos.

**Importante:** GitHub exige que un workflow con `workflow_dispatch` exista en la rama predeterminada. Esta implementación está en **master**, por lo que debes cambiar la rama predeterminada a `master` en los ajustes del repositorio (actualmente es `main`).

Agrega estos secretos en **Settings → Secrets and variables → Actions**:

| Secret | Valor |
|---|---|
| `MERCADO_PUBLICO_TICKET` | Ticket de la API |
| `GOOGLE_SHEET_ID` | ID de Google Sheets |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | JSON completo de la cuenta de servicio |

Si GitHub Actions no puede publicar el JSON, habilita permiso de escritura para Actions en **Settings → Actions → General → Workflow permissions**.

### Preparar Google Sheets

La hoja debe ser un Google Sheets nativo, ubicado preferentemente en `docs/mercado-publico` de tu Google Drive personal.

1. Utiliza una pestaña llamada **Licitaciones** (vacía o con encabezados correctos).
2. Habilita **Google Sheets API** en un proyecto de Google Cloud.
3. Crea una cuenta de servicio y comparte **solo esa hoja** con el correo de la cuenta como Editor.
4. Agrega los tres secretos a GitHub. Nunca publiques la clave JSON.
5. Ejecuta el workflow en master.

El script escribe únicamente A:O. Las columnas **P:U** son para observaciones manuales sobre qué solicita el organismo, situación actual, requisitos, reutilización, mejoras y notas. Estas columnas no son sobrescritas.

Si los encabezados existentes son distintos, la sincronización falla sin alterarlos para proteger los análisis.

### Alcance y límites

- La búsqueda usa fechas de publicación en la API v1 y consulta en detalle solo registros cuyo título/resumen tiene términos configurados.
- El máximo de detalles consultados se limita por ejecución.
- La coincidencia de palabras clave no es exhaustiva y puede omitir licitaciones relevantes.
- Los enlaces no incluidos en la API se dejan vacíos.
- No se descargan bases ni se rellena artificialmente información no verificada.
- El histórico JSON y su descripción son **públicos**. No incluyas datos privados.
