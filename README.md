# Baula

Herramienta open core para planificar la salida de VMware. *Cruza océanos. Llega a casa.*

Este repo contiene, por ahora, solo el prototipo del motor de **Baula Compass**. Baula Tide (descubrimiento y olas) y Baula Nest (runbooks y modo evento) son fase 3 y no existen todavía.

## Baula Compass (prototipo)

Prototipo en Python del motor de Baula Compass: toma un export de RVTools y compara el costo de renovar VMware (VCF y VVF) contra salir a Azure, GCP o Proxmox. Sirve para validar las fórmulas con exports reales antes de pasar el motor al navegador (TypeScript).

**Estado (28-oct-2026):** prototipo de fase 1, adelantado mientras corre la fase 0. Probado solo con exports sintéticos y con un catálogo de precios de muestra. Los precios reales de Azure y GCP todavía no se descargaron.

### Uso

```bash
pip install -r requirements.txt
python -m compass mi-export.xlsx --catalog prices/azure-eastus.json
python -m compass mi-export.xlsx --json          # resultado completo
python -m compass mi-export.xlsx --late --years 3 # con recargo por renovación tardía
python -m compass mi-export.xlsx --catalog prices/azure-eastus.json --client "Cliente S.A." --pdf reporte.pdf
python -m pytest -q
```

`--html` y `--pdf` generan el reporte para el cliente. El PDF se imprime con Chrome, Chromium o Edge en modo headless; si no lo encuentra, indicá la ruta en `BAULA_CHROME`. El reporte se marca como "datos de ejemplo" con `--example` o cuando algún catálogo de precios es de muestra.

Opciones: `--order-minimum` aplica el mínimo de 72 núcleos por pedido (en disputa, apagado por defecto); `--proxmox-tier` elige el nivel de soporte.

### Qué hay

| Pieza | Archivo | Notas |
|---|---|---|
| Lector de RVTools | `compass/rvtools.py` | Hojas vInfo, vHost y vDisk. Busca columnas por nombre y acepta variantes (MiB/MB). |
| Resumen de inventario | `compass/inventory.py` | VMs, vCPU, RAM, disco, núcleos; VMs apagadas; SO vencidos o que vencen en 12 meses. |
| Renovación VCF/VVF | `compass/licensing.py` | Mínimo de 16 núcleos por CPU, vSAN incluido, rango de lista y negociado, recargo opcional. |
| Nube | `compass/cloud.py` | Instancia más barata que cubre vCPU y RAM asignadas; rango entre pago por uso y compromiso de 3 años. |
| Proxmox | `compass/proxmox.py` | Suscripción por socket sobre el mismo hardware. |
| Reglas | `rules/*.json` | Cada regla con fuente, fecha y estado (`official`, `reported`, `disputed`, `to_verify`). |
| Precios | `scripts/fetch_*_prices.py` | Azure Retail Prices API (sin clave) y Cloud Billing Catalog de GCP (pide `GCP_API_KEY`). Se corren cada semana en GitHub Actions. |
| Reporte | `compass/report.py` | HTML autocontenido y PDF: resumen, inventario, escenarios, supuestos con fuente y fecha, próximos pasos. |
| Reporte de ejemplo | `examples/demo/` | Empresa ficticia (182 VMs, 8 hosts) con precios de nube ilustrativos, para mostrar en entrevistas. Se regenera con `scripts/make_demo_rvtools.py`. |
| Exports de prueba | `scripts/make_sample_rvtools.py` | Datos inventados, en dos formas de columnas distintas. |

### Límites conocidos

- Dimensiona por recursos asignados, no por uso real.
- La capacidad cruda de vSAN no viene en RVTools: se informa lo incluido, no el excedente.
- Las fechas de fin de soporte de SO están marcadas `to_verify`.
- Licencias de Windows en Azure se calculan a pago por uso, sin Azure Hybrid Benefit.
- Las diferencias reales entre RVTools 4.7 y 4.8 se confirman con los exports de la fase 0.

El reporte no es asesoría legal ni contractual.
