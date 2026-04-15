# utils/ — Herramientas auxiliares

Scripts de apoyo que se corren **manualmente** cuando los necesitas,
antes o independientemente del pipeline principal.

| Script | Qué hace | Uso |
|---|---|---|
| `discovery.py` | Inventario JSON de todos los archivos de una carpeta | Diagnóstico previo |
| `descomprimir_rar_zip.py` | Extrae ZIP/RAR recursivamente | Antes del paso 0 si tienes comprimidos |
| `extract_eml_attachments.py` | Extrae adjuntos de .eml | Inspección manual de emails |
| `extract_msg_attachments.py` | Extrae adjuntos de .msg (Outlook) | Inspección manual de emails |
| `extract_docx_images.py` | Extrae imágenes de .docx | Si Azure no lee bien las imágenes |
| `extract_excel_images.py` | Extrae imágenes de .xlsx/.xlsm | Si Azure no lee bien las imágenes |

## Carpeta por defecto

Todos apuntan a `data/input/` por defecto y guardan resultados en `data/output/`.

## Carpeta personalizada

```bash
python utils/discovery.py              --carpeta data/procesables
python utils/descomprimir_rar_zip.py   --carpeta /ruta/mis_zips
python utils/extract_eml_attachments.py --carpeta data/input
python utils/extract_docx_images.py    --carpeta data/cotizaciones_encontradas
```
