"""Pruebas con los exports de 5 empresas FICTICIAS (tests/fixtures/empresas, ver scripts/make_simulated_companies.py).

Las pruebas marcadas xfail documentan comportamientos del motor que salieron raros en estas
pruebas y que todavía no se corrigieron. Cuando se corrija uno, su prueba pasa y hay que
quitarle la marca (strict=True la hace fallar para que no se olvide).
"""
from datetime import date
from pathlib import Path

import pytest

from compass import rvtools
from compass.analyze import analyze
from compass.cloud import load_catalog
from compass.inventory import summarize
from compass.rules import load_rules

EMPRESAS = Path(__file__).parent / "fixtures" / "empresas"
CATALOG = Path(__file__).parent / "fixtures" / "catalog_sample.json"
TODAY = date(2026, 11, 4)

# empresa -> (VMs sin plantillas, hosts, núcleos físicos, núcleos de relleno VCF)
ESPERADO = {
    "coopeandina": (132, 8, 240, 16),
    "sanrafael": (139, 10, 416, 48),
    "laceiba": (87, 16, 256, 96),
    "conecta": (278, 10, 416, 0),
    "utvalle": (190, 10, 704, 0),
}


def path(key):
    return EMPRESAS / f"{key}-rvtools.xlsx"


@pytest.mark.parametrize("key", ESPERADO)
def test_carga_y_licenciamiento(key):
    vms, hosts, cores, padding = ESPERADO[key]
    r = analyze(path(key), [CATALOG], today=TODAY)
    inv = r["inventory"]
    assert (inv["vms_total"], inv["hosts"], inv["physical_cores"]) == (vms, hosts, cores)
    assert r["scenarios"]["VCF"]["padding_cores"] == padding
    assert r["scenarios"]["VCF"]["licensed_cores"] == cores + padding


@pytest.mark.parametrize("key", ESPERADO)
def test_todo_marcado_como_ficticio(key):
    from openpyxl import load_workbook
    wb = load_workbook(path(key), read_only=True)
    assert "LEEME-FICTICIO" in wb.sheetnames
    assert "FICTICIOS" in next(wb["LEEME-FICTICIO"].iter_rows(values_only=True))[0]


def test_vm_monstruo_queda_sin_instancia():
    # 128 vCPU y 1 TiB: no cabe ni en la instancia más grande del catálogo de Azure del repo
    azure = Path(__file__).parent.parent / "prices" / "azure-eastus.json"
    r = analyze(path("sanrafael"), [azure], today=TODAY)
    assert r["scenarios"]["AZURE"]["vms_unplaced"] == ["ia-imagenes-01"]


def test_tiendas_de_un_socket_pagan_relleno():
    inv = rvtools.load(path("laceiba"))
    robo = [h for h in inv.hosts if h.sockets == 1]
    assert len(robo) == 12 and all(h.cores_per_cpu == 8 for h in robo)


# --- comportamientos raros detectados, pendientes de decisión ---

def _unsupported(key):
    inv = rvtools.load(path(key))
    return summarize(inv, load_rules("os_eol"), TODAY)


@pytest.mark.xfail(strict=True, reason="os_eol solo reconoce 'CentOS 7', no 'CentOS Linux 7 (Core)' ni 'Red Hat Enterprise Linux Server 7.9'")
def test_detecta_centos_y_rhel_7_con_nombre_de_distribucion():
    s = _unsupported("sanrafael")
    flagged = {u["os"] for u in s["unsupported_os"]}
    assert "CentOS Linux 7 (Core)" in flagged
    assert "Red Hat Enterprise Linux Server 7.9 (Maipo)" in flagged


@pytest.mark.xfail(strict=True, reason="os_eol no tiene Windows de escritorio (XP, 7, 10)")
def test_detecta_windows_de_escritorio_sin_soporte():
    s = _unsupported("conecta")
    assert any("Windows 10" in u["os"] for u in s["unsupported_os"])


@pytest.mark.xfail(strict=True, reason="el lector usa el nombre de VM como clave y descarta la segunda VM con el mismo nombre en otro vCenter")
def test_no_descarta_vms_con_el_mismo_nombre_en_otro_vcenter():
    inv = rvtools.load(path("utvalle"))
    assert sum(1 for v in inv.vms if v.name == "web01") == 2


@pytest.mark.xfail(strict=True, reason="las VMs de sistema (vCLS, vCenter) se cotizan en la nube como cualquier otra")
def test_no_cotiza_vcls_en_la_nube():
    from compass.cloud import cloud_cost
    inv = rvtools.load(path("coopeandina"))
    lines = cloud_cost(inv.vms, load_catalog(CATALOG))["lines"]
    assert not any(l["vm"].startswith("vCLS-") for l in lines)
