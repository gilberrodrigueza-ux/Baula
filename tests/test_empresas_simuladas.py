"""Pruebas con los exports de 8 empresas FICTICIAS (tests/fixtures/empresas, ver scripts/make_simulated_companies.py
y scripts/make_interview_companies.py).

Las pruebas marcadas xfail (si hay) documentan comportamientos del motor que salieron raros en
estas pruebas y que todavía no se corrigieron. Cuando se corrija uno, su prueba pasa y hay que
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
    "utvalle": (191, 10, 704, 0),
    # entrevistas simuladas de la fase 0 (scripts/make_interview_companies.py)
    "istmo": (86, 8, 196, 12),
    "quetzal": (51, 6, 144, 48),
    "copan": (58, 4, 128, 0),
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


def test_detecta_centos_rhel_y_sles_con_nombre_de_distribucion():
    flagged = {u["os"] for u in _unsupported("sanrafael")["unsupported_os"]}
    assert "CentOS Linux 7 (Core)" in flagged
    assert "Red Hat Enterprise Linux Server 7.9 (Maipo)" in flagged
    flagged = {u["os"] for u in _unsupported("laceiba")["unsupported_os"]}
    assert "SUSE Linux Enterprise Server 12 SP5" in flagged
    assert "SUSE Linux Enterprise Server 15 SP5" not in flagged


def test_detecta_windows_de_escritorio_sin_soporte():
    labels = {u["label"] for u in _unsupported("conecta")["unsupported_os"]}
    assert "Windows 10" in labels
    labels = {u["label"] for u in _unsupported("sanrafael")["unsupported_os"]}
    assert {"Windows XP", "Windows 7"} <= labels


def test_2016_or_later_no_se_marca_como_2016():
    # apagadas: VMware Tools no reporta y queda el genérico "2016 or later" (puede ser 2019 o 2022)
    s = _unsupported("conecta")
    assert not any("or later" in u["os"] for u in s["unsupported_os"])
    # si tiene prettyName de Guest Detailed Data se usa; si no, queda como versión desconocida
    assert s["os_version_unknown"]


def test_ubuntu_generico_usa_guest_detailed_data():
    s = _unsupported("utvalle")
    assert "Ubuntu 18.04.6 LTS" in {u["os"] for u in s["unsupported_os"]}


def test_no_descarta_vms_con_el_mismo_nombre_en_otro_vcenter():
    inv = rvtools.load(path("utvalle"))
    web01 = [v for v in inv.vms if v.name == "web01"]
    assert len(web01) == 2 and {v.vcenter for v in web01} == {"vcenter-campus.utvc.ac.cr", "vcenter-investigacion.utvc.ac.cr"}
    assert all(v.disks_mib for v in web01)
    assert not inv.warnings


def test_avisa_esxi_sin_soporte_general():
    r = analyze(path("coopeandina"), [CATALOG], today=TODAY)
    hosts = r["inventory"]["unsupported_hosts"]
    assert len(hosts) == 8 and all(h["state"] == "expired" and h["end_of_general_support"] == "2025-10-02" for h in hosts)
    r = analyze(path("sanrafael"), [CATALOG], today=TODAY)
    states = {h["host"]: h for h in r["inventory"]["unsupported_hosts"]}
    assert states["esx-old01"]["end_of_general_support"] == "2022-10-15"
    # ESXi 8 pierde soporte general en octubre de 2027: a 11 meses de la fecha de prueba
    assert states["esx-n01"]["state"] == "expiring"


def test_descuento_de_compromiso_no_toca_la_licencia_windows():
    azure = Path(__file__).parent.parent / "prices" / "azure-eastus.json"
    c = analyze(path("coopeandina"), [azure], today=TODAY)["scenarios"]["AZURE"]
    cat = load_catalog(azure)
    base = c["compute_usd_month"] - c["windows_license_usd_month"]
    expected = (base * (1 - cat["commit_discount_3yr"]) + c["windows_license_usd_month"] + c["storage_in_use_usd_month"]) * 12
    assert abs(c["annual_usd"]["low"] - expected) <= 1
    assert c["windows_license_usd_month"] > 0.5 * base  # 87% Windows: la licencia pesa


def test_no_cotiza_vcls_ni_vcenter_en_la_nube():
    from compass.cloud import cloud_cost
    inv = rvtools.load(path("utvalle"))
    r = cloud_cost(inv.vms, load_catalog(CATALOG))
    names = {l["vm"] for l in r["lines"]} | set(r["vms_unplaced"])
    assert not any(n.startswith("vCLS-") for n in names)
    assert "vcenter-campus" in r["vms_vmware_system"] and "vcenter-investigacion" in r["vms_vmware_system"]
    assert sum(1 for n in r["vms_vmware_system"] if n.startswith("vCLS-")) == 3


def test_otras_vms_photon_si_se_cotizan():
    # el UAG de Horizon corre en Photon pero no es parte de vSphere: se cotiza
    from compass.cloud import cloud_cost
    inv = rvtools.load(path("conecta"))
    r = cloud_cost(inv.vms, load_catalog(CATALOG))
    assert not any(n.startswith("uag") for n in r["vms_vmware_system"])
    assert "vcsa" in r["vms_vmware_system"]


def test_fechas_de_fin_de_soporte_con_fuente():
    for e in load_rules("os_eol")["entries"]:
        assert e["status"] in ("official", "reported"), e["label"]
        assert e["sources"] and all(s["url"] and s["checked"] for s in e["sources"]), e["label"]


def test_escritorios_windows_no_se_cotizan_como_servidores():
    azure = Path(__file__).parent.parent / "prices" / "azure-eastus.json"
    c = analyze(path("conecta"), [azure], today=TODAY)["scenarios"]["AZURE"]
    assert len(c["vms_windows_desktop"]) >= 180  # los VDI encendidos (220, unos 12% apagados)
    assert not any(l["vm"].startswith("VDI-") for l in c["lines"])
    h = analyze(path("sanrafael"), [azure], today=TODAY)["scenarios"]["AZURE"]
    assert any(n.startswith("ecg-gw") for n in h["vms_windows_desktop"])  # Windows XP de equipos médicos


def test_vm_sin_instancia_sale_con_detalle_en_el_reporte():
    from compass.report import render_html
    azure = Path(__file__).parent.parent / "prices" / "azure-eastus.json"
    r = analyze(path("sanrafael"), [azure], today=TODAY)
    assert r["scenarios"]["AZURE"]["unplaced_detail"] == [{"vm": "ia-imagenes-01", "vcpus": 128, "memory_gib": 1024}]
    assert "ia-imagenes-01 (128 vCPU, 1024 GiB)" in render_html(r, today=TODAY)


def test_hyperv_sugiere_datacenter_ya_licenciado_con_mayoria_windows():
    s = analyze(path("coopeandina"), [CATALOG], today=TODAY)["scenarios"]["HYPERV"]
    assert s["windows_share"] >= 0.5 and "ya tengan Datacenter" in s["note"]
    assert s["annual_usd_if_owned"]["low"] == 0
    u = analyze(path("utvalle"), [CATALOG], today=TODAY)["scenarios"]["HYPERV"]
    assert u["windows_share"] < 0.5 and "ya tengan Datacenter" not in u["note"]


def test_disco_usado_baja_el_piso_de_la_nube():
    azure = Path(__file__).parent.parent / "prices" / "azure-eastus.json"
    c = analyze(path("sanrafael"), [azure], today=TODAY)["scenarios"]["AZURE"]
    assert 0 < c["storage_in_use_usd_month"] < c["storage_usd_month"]


def test_nutanix_avisa_clusteres_chicos():
    s = analyze(path("laceiba"), [CATALOG], today=TODAY)["scenarios"]["NUTANIX"]
    assert len(s["small_clusters"]) == 12 and "menos de 3 hosts" in s["note"]
    assert analyze(path("conecta"), [CATALOG], today=TODAY)["scenarios"]["NUTANIX"]["small_clusters"] == []
