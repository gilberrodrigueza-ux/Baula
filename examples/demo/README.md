# Reporte de ejemplo

Todo lo de esta carpeta es ficticio y sirve para mostrar el reporte de Compass en entrevistas.

- `empresa-ejemplo.xlsx`: export de RVTools inventado (Empresa Ejemplo S.A., 182 VMs, 8 hosts). Se regenera con `python scripts/make_demo_rvtools.py examples/demo/empresa-ejemplo.xlsx`.
- `azure-eastus-ilustrativo.json`, `gcp-us-east1-ilustrativo.json`: precios aproximados a mano, no descargados de las APIs. Están marcados `"sample": true`, así que el reporte sale con la marca de datos de ejemplo.
- `reporte-ejemplo.html` y `reporte-ejemplo.pdf`: el resultado.

Las reglas de Broadcom y Proxmox sí son las reales de `rules/`, a la fecha de esas reglas.

```bash
python -m compass examples/demo/empresa-ejemplo.xlsx \
  --catalog examples/demo/azure-eastus-ilustrativo.json \
  --catalog examples/demo/gcp-us-east1-ilustrativo.json \
  --client "Empresa Ejemplo S.A." --example \
  --html examples/demo/reporte-ejemplo.html --pdf examples/demo/reporte-ejemplo.pdf
```
