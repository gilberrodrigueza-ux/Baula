# Empresas simuladas (DATOS FICTICIOS)

Cinco exports de RVTools inventados para probar Compass con inventarios parecidos a los de medianas de Costa Rica y Centroamérica. **Ninguna de estas empresas existe**; nombres, hosts, VMs, IPs y números de serie son inventados. Cada archivo trae la hoja `LEEME-FICTICIO` y la marca en la columna Annotation.

| Archivo | Empresa ficticia | VMs | Hosts | Casos raros que prueba |
|---|---|---|---|---|
| `coopeandina-rvtools.xlsx` | Coopeandina R.L. (cooperativa) | 132 | 8 | 87% Windows, 2008 R2 y 2012 R2, ESXi 7.0.3, DR con CPUs de 12 núcleos, réplicas apagadas, vCLS |
| `sanrafael-rvtools.xlsx` | Hospital Metropolitano San Rafael de Occidente | 139 | 10 | PACS con discos de 8 TiB, Windows XP y 7 de equipos médicos, ESXi 6.7, VM de 128 vCPU / 1 TiB |
| `laceiba-rvtools.xlsx` | Supermercados La Ceiba S.A. | 87 | 16 | 12 tiendas con 1 host de 1 socket y 8 núcleos (relleno a 16), SUSE 12 en POS |
| `conecta-rvtools.xlsx` | Conecta Servicios Globales S.A. (BPO) | 278 | 10 | 220 escritorios VDI Windows 10/11, CentOS 7, VMs apagadas con "2016 or later" |
| `utvalle-rvtools.xlsx` | Universidad Técnica del Valle Central | 190 | 10 | dos vCenters con nombres de VM repetidos, AMD EPYC de 64 núcleos, laboratorios apagados |

Se regeneran con `python scripts/make_simulated_companies.py` (semilla fija, mismo resultado). Las columnas siguen los encabezados de RVTools 4.x; la forma exacta en que VMware Tools reporta el nombre del SO (genérico o de la distribución) se mezcla a propósito y se confirma con los exports reales de la fase 0.
