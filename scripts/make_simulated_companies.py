"""Genera los exports de RVTools de 5 empresas FICTICIAS para probar Compass. No son datos reales.

Uso: python scripts/make_simulated_companies.py [carpeta]   (por defecto tests/fixtures/empresas)

Ninguna de estas empresas existe. Los nombres, hosts, VMs, IPs y números de serie son inventados.
Cada perfil imita una mediana típica de Costa Rica y Centroamérica y mete a propósito los casos
raros que aparecen en exports reales:

- coopeandina:  cooperativa de ahorro y crédito. Windows pesado, 2008 R2 y 2012 R2, ESXi 7.0.3
                (fuera de soporte general), hosts de DR con CPUs de 12 núcleos (relleno a 16), vCLS.
- sanrafael:    hospital. PACS con discos enormes, Windows XP y 7 de equipos médicos, ESXi 6.7
                y 8.0, una VM de analítica de 128 vCPU y 1 TiB que no cabe en ninguna instancia.
- laceiba:      cadena de supermercados. 4 hosts centrales y 12 tiendas con 1 host de 1 socket
                y 8 núcleos cada una (mucho relleno, Nutanix pide 3 nodos), SUSE 12 en POS.
- conecta:      BPO/contact center. 220 escritorios VDI Windows 10/11, telefonía en CentOS 7,
                VMs apagadas con el nombre de SO del archivo de configuración ("2016 or later").
- utvalle:      universidad. Dos vCenters en un mismo archivo con nombres de VM repetidos,
                hosts AMD EPYC de 64 núcleos, laboratorios apagados, Debian 9/10, CentOS 8.

Las columnas siguen los encabezados de RVTools 4.x (vInfo, vCPU, vMemory, vDisk, vPartition,
vNetwork, vHost, vCluster, vDatastore, vSource, vMetaData). Las hojas que Compass no lee
llevan un subconjunto de columnas.
"""
from __future__ import annotations

import random
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import Workbook

NOTICE = "DATOS FICTICIOS - generado por Baula para pruebas, no corresponde a ninguna empresa real"

# nombres de SO como aparecen en RVTools: (archivo de configuración, VMware Tools, prettyName del
# "Guest Detailed Data"). VMware Tools a veces reporta el nombre genérico del tipo de SO y a veces el
# nombre de la distribución; el generador mezcla las dos formas porque no sabemos cuál domina en
# exports reales (se confirma con los exports de la fase 0).
OS = {
    "w2008r2": ("Microsoft Windows Server 2008 R2 (64-bit)", "Microsoft Windows Server 2008 R2 (64-bit)", "Microsoft Windows Server 2008 R2 Standard"),
    "w2012r2": ("Microsoft Windows Server 2012 (64-bit)", "Microsoft Windows Server 2012 (64-bit)", "Microsoft Windows Server 2012 R2 Standard"),
    "w2016": ("Microsoft Windows Server 2016 or later (64-bit)", "Microsoft Windows Server 2016 (64-bit)", "Microsoft Windows Server 2016 Standard"),
    "w2019": ("Microsoft Windows Server 2016 or later (64-bit)", "Microsoft Windows Server 2019 (64-bit)", "Microsoft Windows Server 2019 Standard"),
    "w2022": ("Microsoft Windows Server 2022 (64-bit)", "Microsoft Windows Server 2022 (64-bit)", "Microsoft Windows Server 2022 Standard"),
    "wxp": ("Microsoft Windows XP Professional (32-bit)", "Microsoft Windows XP Professional (32-bit)", "Microsoft Windows XP Professional"),
    "w7": ("Microsoft Windows 7 (64-bit)", "Microsoft Windows 7 (64-bit)", "Microsoft Windows 7 Professional"),
    "w10": ("Microsoft Windows 10 (64-bit)", "Microsoft Windows 10 (64-bit)", "Microsoft Windows 10 Enterprise"),
    "w11": ("Microsoft Windows 11 (64-bit)", "Microsoft Windows 11 (64-bit)", "Microsoft Windows 11 Enterprise"),
    "rhel7": ("Red Hat Enterprise Linux 7 (64-bit)", "Red Hat Enterprise Linux 7 (64-bit)", "Red Hat Enterprise Linux Server 7.9 (Maipo)"),
    "rhel8": ("Red Hat Enterprise Linux 8 (64-bit)", "Red Hat Enterprise Linux 8 (64-bit)", "Red Hat Enterprise Linux 8.10 (Ootpa)"),
    "rhel9": ("Red Hat Enterprise Linux 9 (64-bit)", "Red Hat Enterprise Linux 9 (64-bit)", "Red Hat Enterprise Linux 9.4 (Plow)"),
    "ol7": ("Oracle Linux 7 (64-bit)", "Oracle Linux 7 (64-bit)", "Oracle Linux Server 7.9"),
    "ol8": ("Oracle Linux 8 (64-bit)", "Oracle Linux 8 (64-bit)", "Oracle Linux Server 8.10"),
    "centos7": ("CentOS 7 (64-bit)", "CentOS 7 (64-bit)", "CentOS Linux 7 (Core)"),
    "centos8": ("CentOS 8 (64-bit)", "CentOS 8 (64-bit)", "CentOS Linux 8"),
    "rocky9": ("Rocky Linux (64-bit)", "Rocky Linux (64-bit)", "Rocky Linux 9.4 (Blue Onyx)"),
    "ubu1804": ("Ubuntu Linux (64-bit)", "Ubuntu Linux (64-bit)", "Ubuntu 18.04.6 LTS"),
    "ubu2004": ("Ubuntu Linux (64-bit)", "Ubuntu Linux (64-bit)", "Ubuntu 20.04.6 LTS"),
    "ubu2204": ("Ubuntu Linux (64-bit)", "Ubuntu Linux (64-bit)", "Ubuntu 22.04.4 LTS"),
    "deb9": ("Debian GNU/Linux 9 (64-bit)", "Debian GNU/Linux 9 (64-bit)", "Debian GNU/Linux 9 (stretch)"),
    "deb10": ("Debian GNU/Linux 10 (64-bit)", "Debian GNU/Linux 10 (64-bit)", "Debian GNU/Linux 10 (buster)"),
    "deb12": ("Debian GNU/Linux 12 (64-bit)", "Debian GNU/Linux 12 (64-bit)", "Debian GNU/Linux 12 (bookworm)"),
    "sles12": ("SUSE Linux Enterprise 12 (64-bit)", "SUSE Linux Enterprise 12 (64-bit)", "SUSE Linux Enterprise Server 12 SP5"),
    "sles15": ("SUSE Linux Enterprise 15 (64-bit)", "SUSE Linux Enterprise 15 (64-bit)", "SUSE Linux Enterprise Server 15 SP5"),
    "photon": ("VMware Photon OS (64-bit)", "VMware Photon OS (64-bit)", "VMware Photon OS 4.0"),
}

ESX = {
    "6.7": "VMware ESXi 6.7.0 build-20497097",
    "7.0": "VMware ESXi 7.0.3 build-24411414",
    "8.0.2": "VMware ESXi 8.0.2 build-23305546",
    "8.0.3": "VMware ESXi 8.0.3 build-24585383",
}

CPU_MODELS = {
    12: "Intel(R) Xeon(R) Silver 4214 CPU @ 2.20GHz",
    10: "Intel(R) Xeon(R) Silver 4210R CPU @ 2.40GHz",
    16: "Intel(R) Xeon(R) Gold 6326 CPU @ 2.90GHz",
    20: "Intel(R) Xeon(R) Gold 5218R CPU @ 2.10GHz",
    24: "Intel(R) Xeon(R) Gold 6342 CPU @ 2.80GHz",
    28: "Intel(R) Xeon(R) Gold 6330 CPU @ 2.00GHz",
    8: "Intel(R) Xeon(R) E-2388G CPU @ 3.20GHz",
    32: "AMD EPYC 9354 32-Core Processor",
    64: "AMD EPYC 9554 64-Core Processor",
}


@dataclass
class HostSpec:
    name: str
    cluster: str
    datacenter: str
    sockets: int
    cores: int
    ram_gib: int
    esx: str
    vcenter: str
    vendor: str = "Dell Inc."
    model: str = "PowerEdge R650"


@dataclass
class VMSpec:
    name: str
    os: str
    cpus: int
    mem_gib: float
    disks_gib: list[float]
    host: HostSpec
    on: bool = True
    template: bool = False
    annotation: str = ""
    tools_reports_os: bool = True


@dataclass
class Company:
    key: str
    name: str
    sector: str
    city: str
    domain: str
    rvtools_version: str
    hosts: list[HostSpec] = field(default_factory=list)
    vms: list[VMSpec] = field(default_factory=list)
    datastores: list[tuple[str, str, int]] = field(default_factory=list)  # nombre, tipo, capacidad GiB


def pick(rnd: random.Random, weighted: list[tuple[object, int]]):
    items = [o for o, w in weighted for _ in range(w)]
    return rnd.choice(items)


def hosts(prefix, n, start, cluster, dc, sockets, cores, ram, esx, vcenter, **kw):
    return [HostSpec(f"{prefix}{i:02d}", cluster, dc, sockets, cores, ram, ESX[esx], vcenter, **kw)
            for i in range(start, start + n)]


def vcls(company: Company, rnd: random.Random):
    """vSphere Cluster Services: 1 a 3 VMs chicas por clúster en vSphere 7.0 U1 y 8.0 hasta U2."""
    by_cluster: dict[str, list[HostSpec]] = {}
    for h in company.hosts:
        if not h.esx.startswith("VMware ESXi 8.0.3"):
            by_cluster.setdefault(h.cluster, []).append(h)
    for cluster, hs in by_cluster.items():
        for i in range(min(3, len(hs))):
            company.vms.append(VMSpec(f"vCLS-{uuid.UUID(int=rnd.getrandbits(128))}"[:44], "photon", 1, 0.125,
                                      [2], hs[i], annotation="vSphere Cluster Service VM"))


# --------------------------------------------------------------------- perfiles

def coopeandina(rnd: random.Random) -> Company:
    c = Company("coopeandina", "Coopeandina R.L.", "Cooperativa de ahorro y crédito", "San José, Costa Rica",
                "coopeandina.local", "4.7.1")
    vc = "vcsa01.coopeandina.local"
    c.hosts = (hosts("esxprd", 6, 1, "CL-PRODUCCION", "DC-SABANA", 2, 16, 768, "7.0", vc)
               + hosts("esxdr", 2, 1, "CL-DR", "DC-ALAJUELA", 2, 12, 512, "7.0", vc, model="PowerEdge R640"))
    prd, dr = c.hosts[:6], c.hosts[6:]
    c.datastores = [("DS-PRD-PURE01", "VMFS", 40960), ("DS-PRD-PURE02", "VMFS", 40960), ("DS-DR-UNITY01", "VMFS", 30720)]
    roles = [("core-bancario", "w2008r2", 3, (16, 64), [120, 800]),
             ("sql", "w2016", 6, (16, 128), [120, 1500]),
             ("sql-cobros", "w2019", 4, (8, 64), [120, 750]),
             ("app-creditos", "w2012r2", 8, (4, 16), [100]),
             ("app-ahorros", "w2019", 8, (4, 16), [100, 200]),
             ("web-banca", "w2022", 6, (4, 8), [80]),
             ("dc", "w2019", 4, (2, 8), [80]),
             ("file", "w2016", 3, (4, 16), [100, 4000]),
             ("rpt", "w2012r2", 6, (4, 32), [100, 300]),
             ("bi", "w2022", 3, (16, 128), [120, 1000]),
             ("kiosko", "w2016", 12, (2, 4), [60]),
             ("rhel-api", "rhel8", 10, (4, 16), [80]),
             ("oracle-cobros", "ol7", 2, (8, 96), [100, 2000]),
             ("mon", "ubu2004", 3, (2, 8), [60]),
             ("veeam-proxy", "w2019", 4, (8, 16), [80]),
             ("test", "w2019", 20, (4, 16), [100]),
             ("dev", "rhel8", 16, (4, 16), [80])]
    n = 0
    for role, os, count, (cpu, mem), disks in roles:
        for i in range(1, count + 1):
            n += 1
            h = dr[n % 2] if role in ("test",) and i % 3 == 0 else prd[n % len(prd)]
            on = not (role in ("test", "dev") and rnd.random() < 0.45)
            c.vms.append(VMSpec(f"{role}-{i:02d}", os, cpu, mem, list(disks), h, on))
    # réplicas de DR (Zerto/SRM), apagadas
    for i in range(1, 9):
        c.vms.append(VMSpec(f"dr-replica-app-{i:02d}", "w2019", 4, 16, [100, 200], dr[i % 2], on=False,
                            annotation="Réplica de DR, se enciende solo en contingencia"))
    c.vms.append(VMSpec("tpl-w2022", "w2022", 2, 4, [80], prd[0], on=False, template=True))
    c.vms.append(VMSpec("tpl-rhel8", "rhel8", 2, 4, [60], prd[1], on=False, template=True))
    c.vms.append(VMSpec("vcsa01", "photon", 4, 19, [700], prd[0], annotation="VMware vCenter Server Appliance"))
    vcls(c, rnd)
    return c


def sanrafael(rnd: random.Random) -> Company:
    c = Company("sanrafael", "Hospital Metropolitano San Rafael de Occidente", "Hospital privado",
                "Santa Ana, Costa Rica", "hmsro.local", "4.7.1")
    vc = "vcenter.hmsro.local"
    c.hosts = (hosts("esx-n", 6, 1, "Clinico", "HMSRO-DC1", 2, 28, 1536, "8.0.2", vc, vendor="HPE", model="ProLiant DL380 Gen11")
               + hosts("esx-old", 4, 1, "Legado", "HMSRO-DC1", 2, 10, 384, "6.7", vc, vendor="HPE", model="ProLiant DL380 Gen9"))
    new, old = c.hosts[:6], c.hosts[6:]
    c.datastores = [("VSAN-Clinico", "vsan", 184320), ("LEG-3PAR-01", "VMFS", 51200), ("NFS-PACS", "NFS", 163840)]
    roles = [("his-app", "w2019", 10, (8, 32), [150], new),
             ("his-db", "ol8", 2, (24, 384), [200, 4000, 2000], new),
             ("pacs-arch", "w2016", 4, (8, 64), [150, 8192, 8192, 8192], new),
             ("pacs-view", "w2019", 6, (8, 32), [120], new),
             ("ris", "w2012r2", 3, (4, 16), [100, 500], old),
             ("lis-lab", "w2008r2", 2, (4, 8), [80, 200], old),
             ("ecg-gw", "wxp", 3, (1, 2), [40], old),
             ("tomo-wks", "w7", 4, (2, 8), [120], old),
             ("ultra-sw", "w7", 2, (2, 4), [80], old),
             ("farmacia", "w2016", 3, (4, 16), [100, 300], new),
             ("erp-fin", "w2019", 4, (8, 64), [120, 600], new),
             ("citrix-vda", "w2019", 24, (8, 32), [100], new),
             ("citrix-ctl", "w2016", 3, (4, 8), [80], new),
             ("dc", "w2016", 3, (2, 8), [80], new),
             ("web-citas", "ubu1804", 4, (2, 8), [60], new),
             ("hl7-mirth", "centos7", 3, (4, 16), [100], new),
             ("integ", "rhel7", 6, (4, 16), [80], new),
             ("k8s-node", "ubu2204", 12, (8, 32), [150], new),
             ("backup", "w2019", 2, (16, 64), [120], new),
             ("mon", "rocky9", 3, (4, 8), [80], new),
             ("test-his", "w2019", 16, (4, 16), [100], new),
             ("app-legado", "w2008r2", 12, (2, 8), [80], old)]
    for role, os, count, (cpu, mem), disks, pool in roles:
        for i in range(1, count + 1):
            h = pool[i % len(pool)]
            on = not (role.startswith("test") and rnd.random() < 0.5) and not (role == "app-legado" and i % 3 == 0)
            # VMs sobredimensionadas típicas: alguien pidió "lo máximo"
            if role == "his-app" and i in (3, 7):
                cpu, mem = 32, 256
            c.vms.append(VMSpec(f"{role}-{i:02d}", os, cpu, mem, list(disks), h, on))
            if role == "his-app" and i in (3, 7):
                cpu, mem = 8, 32
    # VM monstruo: analítica de imágenes, no cabe en ninguna instancia del catálogo
    c.vms.append(VMSpec("ia-imagenes-01", "ubu2204", 128, 1024, [500, 4000], new[0],
                        annotation="Piloto de IA para radiología"))
    c.vms.append(VMSpec("vcenter", "photon", 4, 21, [700], new[1]))
    vcls(c, rnd)
    return c


def laceiba(rnd: random.Random) -> Company:
    c = Company("laceiba", "Supermercados La Ceiba S.A.", "Retail: cadena de supermercados",
                "Heredia, Costa Rica", "laceiba.local", "4.6.1")
    vc = "vc.laceiba.local"
    central = hosts("esx-cen", 4, 1, "CENTRAL", "CEDI-HEREDIA", 2, 20, 768, "8.0.3", vc, model="PowerEdge R750")
    tiendas = ["HEREDIA", "ALAJUELA", "CARTAGO", "LIBERIA", "PEREZ-ZELEDON", "LIMON", "SAN-CARLOS",
               "PUNTARENAS", "ESCAZU", "DESAMPARADOS", "GRECIA", "TURRIALBA"]
    robo = [HostSpec(f"esx-t{i:02d}-{t.lower()}", f"TIENDA-{t}", f"TIENDA-{t}", 1, 8, 128, ESX["8.0.3"], vc,
                     model="PowerEdge T350") for i, t in enumerate(tiendas, 1)]
    c.hosts = central + robo
    c.datastores = [("DS-CENTRAL-01", "VMFS", 30720), ("DS-CENTRAL-02", "VMFS", 30720),
                    *[(f"local-{h.name}", "VMFS", 3584) for h in robo]]
    roles = [("erp-sap-app", "sles15", 4, (8, 64), [100, 200]),
             ("erp-sap-db", "sles15", 1, (32, 512), [200, 3000, 1000]),
             ("pos-central", "sles12", 4, (4, 16), [80, 200]),
             ("ecommerce", "ubu2204", 6, (4, 8), [60]),
             ("ecommerce-db", "rhel8", 2, (8, 64), [100, 800]),
             ("wms-cedi", "w2016", 3, (4, 16), [100, 300]),
             ("dc", "w2019", 2, (2, 8), [80]),
             ("file", "w2016", 2, (4, 16), [100, 3000]),
             ("bi-powerbi-gw", "w2022", 2, (8, 32), [100]),
             ("lealtad-api", "ubu2004", 4, (4, 8), [60]),
             ("camaras-nvr", "w2019", 3, (8, 16), [80, 6000]),
             ("print", "w2012r2", 2, (2, 4), [60]),
             ("rpa", "w2019", 4, (4, 16), [100]),
             ("dev", "ubu2204", 10, (2, 8), [60]),
             ("test", "w2019", 8, (4, 8), [80])]
    for role, os, count, (cpu, mem), disks in roles:
        for i in range(1, count + 1):
            on = not (role in ("dev", "test") and rnd.random() < 0.4)
            c.vms.append(VMSpec(f"{role}-{i:02d}", os, cpu, mem, list(disks), central[i % 4], on))
    for h in robo:
        t = h.cluster.split("-", 1)[1].lower()
        c.vms.append(VMSpec(f"pos-srv-{t}", "sles12", 4, 16, [120], h))
        c.vms.append(VMSpec(f"dc-{t}", "w2016", 2, 4, [60], h))
        if rnd.random() < 0.6:
            c.vms.append(VMSpec(f"balanzas-{t}", "w7", 2, 4, [60], h, annotation="Software de balanzas, solo corre en Windows 7"))
    c.vms.append(VMSpec("vc", "photon", 4, 19, [700], central[0]))
    vcls(c, rnd)  # 8.0.3 usa vCLS embebido: no agrega VMs
    return c


def conecta(rnd: random.Random) -> Company:
    c = Company("conecta", "Conecta Servicios Globales S.A.", "BPO y contact center",
                "Zona Franca, Heredia, Costa Rica", "conectags.local", "4.7.1")
    vc = "vcsa.conectags.local"
    c.hosts = (hosts("esx-vdi", 6, 1, "VDI", "ZF-HEREDIA", 2, 24, 1024, "8.0.2", vc, vendor="Lenovo", model="ThinkSystem SR650 V3")
               + hosts("esx-srv", 4, 1, "SERVIDORES", "ZF-HEREDIA", 2, 16, 768, "8.0.2", vc, vendor="Lenovo", model="ThinkSystem SR650 V2"))
    vdi, srv = c.hosts[:6], c.hosts[6:]
    c.datastores = [("vsanDatastore-VDI", "vsan", 92160), ("DS-SRV-NIMBLE01", "VMFS", 40960)]
    for i in range(1, 221):
        os = "w10" if i <= 150 else "w11"
        on = rnd.random() > 0.12
        c.vms.append(VMSpec(f"VDI-AG-{i:03d}", os, 2, 8, [80], vdi[i % 6], on))
    for i in range(1, 4):
        c.vms.append(VMSpec(f"tpl-vdi-gold-w{10 if i < 3 else 11}-v{i}", "w10" if i < 3 else "w11", 2, 8, [80],
                            vdi[0], on=False, template=True))
    roles = [("horizon-cs", "w2019", 3, (4, 16)), ("uag", "photon", 2, (4, 8)), ("app-vol", "w2019", 2, (4, 8)),
             ("telefonia-sbc", "centos7", 4, (8, 16)), ("telefonia-media", "centos7", 6, (8, 16)),
             ("grabacion", "w2016", 3, (8, 32)), ("crm-app", "w2019", 6, (4, 16)), ("crm-db", "w2019", 2, (16, 128)),
             ("wfm", "w2022", 2, (8, 32)), ("dc", "w2022", 3, (2, 8)), ("file", "w2019", 2, (4, 16)),
             ("bot-ia", "ubu2204", 4, (8, 32)), ("sftp-clientes", "rhel9", 2, (2, 4)),
             ("pbx-vieja", "centos7", 2, (4, 8)), ("test", "w2019", 8, (4, 8))]
    for role, os, count, (cpu, mem) in roles:
        for i in range(1, count + 1):
            disks = [100, 2000] if role == "grabacion" else ([150, 500] if role == "crm-db" else [80])
            on = not (role in ("test", "pbx-vieja") and rnd.random() < 0.6)
            # las apagadas no reportan SO por VMware Tools: queda el del archivo de configuración
            c.vms.append(VMSpec(f"{role}-{i:02d}", os, cpu, mem, disks, srv[i % 4], on, tools_reports_os=on))
    c.vms.append(VMSpec("vcsa", "photon", 4, 21, [700], srv[0]))
    vcls(c, rnd)
    return c


def utvalle(rnd: random.Random) -> Company:
    c = Company("utvalle", "Universidad Técnica del Valle Central", "Universidad privada",
                "Cartago, Costa Rica", "utvc.ac.cr", "4.7.1")
    vc1, vc2 = "vcenter-campus.utvc.ac.cr", "vcenter-investigacion.utvc.ac.cr"
    c.hosts = (hosts("esx-campus", 6, 1, "Campus", "DC-Campus", 2, 16, 512, "7.0", vc1, vendor="Supermicro", model="SYS-1029U")
               + hosts("esx-hpc", 4, 1, "Investigacion-HPC", "DC-Investigacion", 2, 64, 2048, "8.0.3", vc2,
                       vendor="Dell Inc.", model="PowerEdge R7625"))
    campus, hpc = c.hosts[:6], c.hosts[6:]
    c.datastores = [("campus-nfs01", "NFS", 61440), ("hpc-vsan", "vsan", 245760)]
    roles = [("moodle-web", "ubu2004", 6, (4, 8), [60], campus), ("moodle-db", "ubu2004", 2, (8, 64), [100, 1000], campus),
             ("matricula", "w2012r2", 3, (4, 16), [100], campus), ("erp-u", "w2016", 4, (4, 16), [100, 300], campus),
             ("biblioteca", "deb9", 2, (2, 4), [60], campus), ("portal", "deb10", 4, (2, 4), [60], campus),
             ("ldap", "centos7", 2, (2, 4), [40], campus), ("dc", "w2019", 3, (2, 8), [80], campus),
             ("correo-relay", "deb12", 2, (2, 4), [40], campus), ("lab-redes", "ubu1804", 30, (2, 4), [40], campus),
             ("lab-so", "centos8", 25, (2, 4), [40], campus), ("lab-win", "w2016", 20, (2, 4), [60], campus),
             ("proyecto-est", "ubu2204", 40, (4, 8), [60], campus),
             ("hpc-compute", "rocky9", 24, (32, 256), [200], hpc), ("gpu-ml", "ubu2204", 6, (48, 384), [500, 2000], hpc),
             ("jupyter", "ubu2204", 8, (16, 64), [200], hpc), ("datos-inv", "rocky9", 3, (16, 128), [100, 8000], hpc),
             ("web01", "deb10", 1, (2, 4), [40], campus), ("web01", "ubu2204", 1, (4, 8), [60], hpc),
             ("ubuntu-2204-tpl", "ubu2204", 1, (2, 4), [40], campus), ("ubuntu-2204-tpl", "ubu2204", 1, (2, 4), [40], hpc)]
    for role, os, count, (cpu, mem), disks, pool in roles:
        for i in range(1, count + 1):
            name = role if count == 1 else f"{role}-{i:02d}"
            lab = role.startswith(("lab-", "proyecto"))
            on = not (lab and rnd.random() < 0.55)
            tpl = role.endswith("-tpl")
            # los laboratorios casi nunca usan lo que se les asignó
            c.vms.append(VMSpec(name, os, cpu, mem, list(disks), pool[i % len(pool)], on and not tpl, template=tpl))
    c.vms.append(VMSpec("vcenter-campus", "photon", 4, 19, [700], campus[0]))
    c.vms.append(VMSpec("vcenter-investigacion", "photon", 4, 21, [700], hpc[0]))
    vcls(c, rnd)
    return c


PROFILES = [coopeandina, sanrafael, laceiba, conecta, utvalle]

# --------------------------------------------------------------------- escritura

VINFO = ["VM", "Powerstate", "Template", "SRM Placeholder", "Config status", "DNS Name", "Connection state",
         "Guest state", "Heartbeat", "Consolidation Needed", "PowerOn", "Creation date", "CPUs", "Memory",
         "Active Memory", "NICs", "Disks", "Total disk capacity MiB", "Primary IP Address", "Network #1",
         "Resource pool", "Folder", "Provisioned MiB", "In Use MiB", "Unshared MiB", "Firmware", "HW version",
         "Path", "Annotation", "Datacenter", "Cluster", "Host", "OS according to the configuration file",
         "OS according to the VMware Tools", "Guest Detailed Data", "VM ID", "VM UUID", "VI SDK Server type", "VI SDK API Version",
         "VI SDK Server"]

VHOST = ["Host", "Datacenter", "Cluster", "Config status", "in Maintenance Mode", "CPU Model", "Speed",
         "HT Available", "HT Active", "# CPU", "Cores per CPU", "# Cores", "CPU usage %", "# Memory",
         "Memory usage %", "# NICs", "# HBAs", "# VMs total", "# VMs", "VMs per Core", "# vCPUs",
         "vCPUs per Core", "vRAM", "ESX Version", "Vendor", "Model", "Serial number", "VI SDK Server"]


def write(company: Company, path: Path, rnd: random.Random) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "vInfo"
    ws.append(VINFO)
    base = datetime(2026, 10, 30, 22, 15)
    ip = 10
    by_host: dict[str, list[VMSpec]] = {}
    for n, v in enumerate(company.vms, 1):
        by_host.setdefault(v.host.name, []).append(v)
        cfg, generic, pretty = OS[v.os]
        # las distribuciones Linux a veces llegan con el nombre de la distribución en vez del genérico
        tools = pretty if (not v.os.startswith("w") and v.os != "photon" and rnd.random() < 0.5) else generic
        detail = f"architecture='X86' bitness='64' distroName='{pretty}' prettyName='{pretty}'" if v.on else ""
        disks_mib = [round(d * 1024) for d in v.disks_gib]
        mem_mib = round(v.mem_gib * 1024)
        total = sum(disks_mib)
        in_use = round(total * rnd.uniform(0.25, 0.75)) + (mem_mib if v.on else 0)
        ip += 1
        ws.append([
            v.name, "poweredOn" if v.on else "poweredOff", v.template, False, "green",
            f"{v.name}.{company.domain}" if v.on else "", "connected",
            "running" if v.on else "notRunning", "green" if v.on else "gray", False,
            (base - timedelta(days=rnd.randint(1, 120))).strftime("%Y/%m/%d %H:%M:%S") if v.on else "",
            (base - timedelta(days=rnd.randint(200, 3000))).strftime("%Y/%m/%d %H:%M:%S"),
            v.cpus, mem_mib, round(mem_mib * rnd.uniform(0.05, 0.4)) if v.on else 0, 1, len(disks_mib), total,
            f"10.{20 + ip // 250}.{ip % 250}.{10 + n % 200}" if v.on else "", "VLAN-SERVIDORES",
            "Resources", "Discovered virtual machine" if v.name.startswith("vCLS") else "Servidores",
            total + mem_mib, in_use, in_use, "efi" if v.os not in ("wxp", "w7", "w2008r2") else "bios",
            "vmx-19" if "8.0" in v.host.esx else ("vmx-13" if "6.7" in v.host.esx else "vmx-17"),
            f"[{company.datastores[0][0]}] {v.name}/{v.name}.vmx",
            " | ".join(x for x in (v.annotation, NOTICE) if x),
            v.host.datacenter, v.host.cluster, v.host.name, cfg,
            tools if (v.on and v.tools_reports_os) else "", detail,
            f"vm-{1000 + n}", str(uuid.UUID(int=rnd.getrandbits(128))), "VirtualCenter",
            "8.0.3.0" if "8.0" in v.host.esx else "7.0.3.0", v.host.vcenter,
        ])

    wc = wb.create_sheet("vCPU")
    wc.append(["VM", "Powerstate", "Template", "CPUs", "Sockets", "Cores p/s", "Max", "Overall", "Level",
               "Shares", "Reservation", "Limit", "Hot Add", "Hot Remove", "Annotation", "Datacenter", "Cluster", "Host",
               "VI SDK Server"])
    wm = wb.create_sheet("vMemory")
    wm.append(["VM", "Powerstate", "Template", "Size MiB", "Overhead", "Max", "Consumed", "Consumed Overhead",
               "Private", "Shared", "Swapped", "Ballooned", "Active", "Entitlement", "Reservation", "Limit",
               "Hot Add", "Annotation", "Datacenter", "Cluster", "Host", "VI SDK Server"])
    wd = wb.create_sheet("vDisk")
    wd.append(["VM", "Powerstate", "Template", "Disk", "Disk Key", "Capacity MiB", "Raw", "Disk Mode", "Thin",
               "Eagerly Scrub", "Controller", "Unit #", "Path", "Annotation", "Datacenter", "Cluster", "Host",
               "VI SDK Server"])
    wp = wb.create_sheet("vPartition")
    wp.append(["VM", "Powerstate", "Template", "Disk", "Capacity MiB", "Consumed MiB", "Free MiB", "Free %",
               "Annotation", "Datacenter", "Cluster", "Host", "VI SDK Server"])
    wn = wb.create_sheet("vNetwork")
    wn.append(["VM", "Powerstate", "Template", "NIC label", "Adapter", "Network", "Switch", "Connected",
               "Starts Connected", "Mac Address", "Type", "IPv4 Address", "Datacenter", "Cluster", "Host", "VI SDK Server"])
    for v in company.vms:
        pw = "poweredOn" if v.on else "poweredOff"
        loc = [v.host.datacenter, v.host.cluster, v.host.name, v.host.vcenter]
        mem_mib = round(v.mem_gib * 1024)
        cps = 1 if v.cpus <= 8 else 2
        wc.append([v.name, pw, v.template, v.cpus, cps, max(1, v.cpus // cps), v.cpus * 2900 if v.on else 0,
                   round(v.cpus * 2900 * rnd.uniform(0.02, 0.3)) if v.on else 0, "normal", v.cpus * 1000, 0, -1,
                   False, False, NOTICE, *loc])
        wm.append([v.name, pw, v.template, mem_mib, 60, mem_mib, round(mem_mib * rnd.uniform(0.3, 0.95)) if v.on else 0,
                   55 if v.on else 0, 0, 0, 0, 0, round(mem_mib * rnd.uniform(0.05, 0.4)) if v.on else 0,
                   mem_mib if v.on else 0, 0, -1, False, NOTICE, *loc])
        for k, d in enumerate(v.disks_gib, 1):
            cap = round(d * 1024)
            wd.append([v.name, pw, v.template, f"Hard disk {k}", 2000 + k, cap, False, "persistent",
                       rnd.random() < 0.7, False, "SCSI controller 0", k - 1,
                       f"[{company.datastores[0][0]}] {v.name}/{v.name}_{k}.vmdk", NOTICE, *loc])
            if v.on:
                used = round(cap * rnd.uniform(0.2, 0.85))
                label = "C:\\" if v.os.startswith("w") and k == 1 else ("D:\\" if v.os.startswith("w") else ("/" if k == 1 else f"/data{k}"))
                wp.append([v.name, pw, v.template, label, cap - 512, used, cap - 512 - used,
                           round((cap - 512 - used) * 100 / (cap - 512)), NOTICE, *loc])
        mac = ":".join(f"{rnd.randint(0, 255):02x}" for _ in range(3))
        wn.append([v.name, pw, v.template, "Network adapter 1", "Vmxnet3", "VLAN-SERVIDORES", "dvs-principal",
                   v.on, True, f"00:50:56:{mac}", "assigned", "" if not v.on else f"10.30.{rnd.randint(1, 250)}.{rnd.randint(2, 250)}",
                   *loc])

    wh = wb.create_sheet("vHost")
    wh.append(VHOST)
    for h in company.hosts:
        vms = by_host.get(h.name, [])
        on = [v for v in vms if v.on]
        cores = h.sockets * h.cores
        vcpus = sum(v.cpus for v in on)
        vram = round(sum(v.mem_gib for v in on) * 1024)
        wh.append([h.name, h.datacenter, h.cluster, "green", False, CPU_MODELS.get(h.cores, "Intel(R) Xeon(R)"),
                   2900, True, True, h.sockets, h.cores, cores, rnd.randint(8, 55), h.ram_gib * 1024,
                   min(95, round(vram * 100 / (h.ram_gib * 1024))) if h.ram_gib else 0, 4, 2, len(vms), len(on),
                   round(len(on) / cores, 2), vcpus, round(vcpus / cores, 2), vram, h.esx, h.vendor, h.model,
                   f"FICT{rnd.randint(100000, 999999)}", h.vcenter])

    wcl = wb.create_sheet("vCluster")
    wcl.append(["Name", "Config status", "OverallStatus", "NumHosts", "numEffectiveHosts", "TotalCpu", "NumCpuCores",
                "NumCpuThreads", "Effective Cpu", "TotalMemory", "Effective Memory", "HA enabled", "DRS enabled",
                "VI SDK Server"])
    clusters: dict[str, list[HostSpec]] = {}
    for h in company.hosts:
        clusters.setdefault(h.cluster, []).append(h)
    for name, hs in clusters.items():
        cores = sum(h.sockets * h.cores for h in hs)
        mem = sum(h.ram_gib for h in hs) * 1024 ** 3
        wcl.append([name, "green", "green", len(hs), len(hs), cores * 2900, cores, cores * 2, round(cores * 2900 * 0.95),
                    mem, round(mem * 0.95 / 1024 ** 2), len(hs) > 1, len(hs) > 1, hs[0].vcenter])

    wds = wb.create_sheet("vDatastore")
    wds.append(["Name", "Config status", "Accessible", "Type", "# VMs", "Capacity MiB", "Provisioned MiB",
                "In Use MiB", "Free MiB", "Free %", "VI SDK Server"])
    for name, kind, cap_gib in company.datastores:
        cap = cap_gib * 1024
        used = round(cap * rnd.uniform(0.45, 0.85))
        wds.append([name, "green", True, kind, "", cap, round(used * 1.4), used, cap - used,
                    round((cap - used) * 100 / cap), company.hosts[0].vcenter])

    wsrc = wb.create_sheet("vSource")
    wsrc.append(["Name", "OS type", "API type", "API version", "Version", "Patch level", "Build", "Fullname",
                 "Product name", "Product version", "Product line", "Vendor", "VI SDK Server"])
    for vc in sorted({h.vcenter for h in company.hosts}):
        v8 = any("8.0" in h.esx for h in company.hosts if h.vcenter == vc)
        ver, build = ("8.0.3", "24322831") if v8 else ("7.0.3", "24322018")
        wsrc.append([vc, "linux-x64", "VirtualCenter", ver + ".0", ver, "", build,
                     f"VMware vCenter Server {ver} build-{build}", "VMware vCenter Server", ver, "vpx",
                     "VMware, Inc.", vc])

    wmeta = wb.create_sheet("vMetaData")
    wmeta.append(["RVTools major version", "RVTools version", "xlsx creation datetime", "Server"])
    for vc in sorted({h.vcenter for h in company.hosts}):
        wmeta.append([company.rvtools_version.split(".")[0], company.rvtools_version,
                      base.strftime("%Y/%m/%d %H:%M:%S"), vc])
    wnote = wb.create_sheet("LEEME-FICTICIO")
    wnote.append([NOTICE])
    wnote.append([f"Empresa ficticia: {company.name} ({company.sector}, {company.city})."])
    wnote.append(["Generado con scripts/make_simulated_companies.py del repo de Baula."])
    wb.save(path)


def build(out_dir: Path) -> list[tuple[Company, Path]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    done = []
    for i, profile in enumerate(PROFILES):
        rnd = random.Random(2026_11_04 + i)
        company = profile(rnd)
        path = out_dir / f"{company.key}-rvtools.xlsx"
        write(company, path, rnd)
        done.append((company, path))
    return done


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/empresas")
    for company, path in build(out):
        print(f"{path}  {company.name}: {len(company.vms)} VMs, {len(company.hosts)} hosts")
