# 📄 PDF Pipeline — Extracción · Clasificación · LLM

Pipeline end-to-end para procesar PDFs con **Azure Document Intelligence** (OCR) y **GPT-4.1-mini**, enfocado en detectar cotizaciones/proformas y extraer sus campos estructurados.

---

## ✨ Flujo del pipeline

```
PDFs en data/input/
       │
       ▼
[1] Azure Document Intelligence (prebuilt-read)
    → Extrae texto completo + páginas
       │
       ▼
[2] Clasificador por keywords
    → Filtra cotizaciones / proformas
       │
       ▼
[3] GPT-4.1-mini + prompt personalizable
    → Extrae campos estructurados como JSON
       │
       ├──▶ data/output/json/<nombre>.json   (uno por PDF)
       └──▶ data/output/tables/resumen.csv / .xlsx
```

---

## 🗂️ Estructura del proyecto

```
pdf_pipeline/
├── main.py                         # Punto de entrada CLI
├── config/
│   └── settings.py                 # Configuración centralizada (lee .env)
├── src/
│   ├── pipeline.py                 # Orquestador principal
│   ├── extraction/
│   │   └── azure_ocr.py            # Extracción con Azure Doc Intelligence
│   ├── classification/
│   │   └── document_classifier.py  # Detección de cotizaciones por keywords
│   ├── processing/
│   │   └── llm_processor.py        # Llamadas a GPT-4.1-mini + parsing JSON
│   ├── output/
│   │   └── json_exporter.py        # Exporta JSON individuales + tabla resumen
│   └── utils/
│       ├── file_utils.py           # Helpers de I/O
│       └── logger.py               # Logger con Rich + FileHandler
├── prompts/
│   └── cotizacion_prompt.txt       # Prompt del LLM (editable)
├── data/
│   ├── input/                      # ← Pon aquí tus PDFs
│   └── output/
│       ├── json/                   # JSON por PDF
│       ├── tables/                 # CSV y XLSX resumen
│       └── reports/                # (reservado para reportes futuros)
├── tests/                          # Pruebas unitarias (pytest)
├── logs/                           # pipeline.log
├── .env.example                    # Plantilla de variables de entorno
├── .gitignore
├── requirements.txt
├── pyproject.toml
└── Makefile
```

---

## 🚀 Inicio rápido

### 1. Clonar e instalar dependencias

```bash
git clone https://github.com/tu-usuario/pdf-pipeline.git
cd pdf-pipeline
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
make install                   # o: pip install -r requirements.txt
```

### 2. Configurar credenciales

```bash
cp .env.example .env
# Edita .env con tus credenciales de Azure y OpenAI
```

Variables obligatorias en `.env`:

| Variable | Descripción |
|---|---|
| `AZURE_DOC_INTELLIGENCE_ENDPOINT` | URL del recurso Azure AI |
| `AZURE_DOC_INTELLIGENCE_KEY` | API key de Azure |
| `OPENAI_API_KEY` | API key de OpenAI |

### 3. Agregar PDFs

Copia tus archivos PDF a `data/input/`:

```bash
cp /ruta/a/mis/*.pdf data/input/
```

### 4. Ejecutar

```bash
# Con defaults
python main.py

# Con opciones
python main.py --input /otra/carpeta --prompt mi_prompt.txt

# Con make
make run
```

---

## 🧠 Personalizar el prompt

Edita `prompts/cotizacion_prompt.txt` para definir qué campos extraer.

El modelo **debe devolver solo JSON válido** — el prompt ya está configurado para esto. Ejemplo del objeto esperado:

```json
{
  "numero_cotizacion": "COT-2024-001",
  "proveedor": { "nombre": "ACME SAC", "ruc_nit": "20123456789" },
  "total": 5950.00,
  "moneda": "PEN",
  "items": [
    { "descripcion": "Laptop Dell XPS", "cantidad": 2, "precio_unitario": 2500.0 }
  ]
}
```

Los campos del JSON se convierten automáticamente en columnas de la tabla resumen.

---

## 🔍 Lógica de clasificación

Un documento es considerado **cotización** si su texto contiene alguna de estas palabras clave (case-insensitive):

> proforma, cotización, cotizacion, cotizaciones, presupuesto, oferta, propuesta comercial, propuesta económica, quote, quotation, pro forma, precio referencial, lista de precios

Se pueden agregar más keywords en `config/settings.py` → `COTIZACION_KEYWORDS`.

---

## 📦 Outputs

### JSON individual por PDF (`data/output/json/<nombre>.json`)

```json
{
  "file_name": "cotizacion_proveedor_abc.pdf",
  "extraction": {
    "status": "success",
    "page_count": 3,
    "full_text": "...",
    "pages": [...]
  },
  "classification": {
    "is_cotizacion": true,
    "matched_keywords": ["proforma", "cotización"]
  },
  "llm_extraction": {
    "llm_status": "success",
    "extracted_fields": { ... }
  }
}
```

### Tabla resumen (`data/output/tables/resumen_cotizaciones.csv` / `.xlsx`)

| file_name | llm_status | numero_cotizacion | proveedor.nombre | total | moneda | ... |
|---|---|---|---|---|---|---|
| cot_001.pdf | success | COT-001 | ACME SAC | 5950.0 | PEN | ... |

---

## 🧪 Tests

```bash
make test           # Corre todos los tests
make test-cov       # Con reporte de cobertura HTML
```

Los tests **no requieren credenciales** — usan mocks para Azure y OpenAI.

---

## ⚙️ Variables de entorno (`.env.example`)

| Variable | Default | Descripción |
|---|---|---|
| `AZURE_DOC_INTELLIGENCE_MODEL` | `prebuilt-read` | Modelo de Azure |
| `OPENAI_MODEL` | `gpt-4.1-mini` | Modelo de OpenAI |
| `OPENAI_MAX_TOKENS` | `2000` | Tokens máximos en respuesta |
| `OPENAI_TEMPERATURE` | `0.0` | Temperatura (0 = determinista) |
| `MAX_WORKERS` | `4` | Workers para procesamiento paralelo |
| `MAX_PDF_SIZE_MB` | `50` | Tamaño máximo de PDF aceptado |
| `LOG_LEVEL` | `INFO` | Nivel de logs: DEBUG/INFO/WARNING/ERROR |

---

## 📋 Requisitos

- Python ≥ 3.10
- Cuenta Azure con recurso **Azure AI Document Intelligence** (F0 gratis disponible)
- API Key de **OpenAI** con acceso a `gpt-4.1-mini`
