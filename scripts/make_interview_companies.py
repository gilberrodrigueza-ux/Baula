"""Genera los exports de RVTools de 3 empresas FICTICIAS más, para las entrevistas simuladas de la fase 0.

Uso: python scripts/make_interview_companies.py [carpeta]   (por defecto tests/fixtures/empresas)

Ninguna de estas empresas existe. Completan la mezcla de las 10 entrevistas simuladas (6 clientes
finales, 2 que ya migraron, 2 integradores) con empresas fuera de Costa Rica. Reusan el formato y
el escritor de scripts/make_simulated_companies.py.

- istmo:    aseguradora en Panamá. Oracle Database en 2 VMs grandes, sitio de DR en David con
            hosts de 1 socket, ESXi 8.0.2, Windows 2012 R2 en el sistema de reclamos.
- quetzal:  manufactura textil en Guatemala. Export de antes de pasarse a Hyper-V: 6 hosts ESXi 7.0,
            92 % Windows, SCADA en Windows 2008 R2 y 7, ya tenían Windows Server Datacenter.
- copan:    financiera en Honduras. Export de antes de pasarse a Azure: VMs sobredimensionadas
            (los recursos asignados están muy por encima del uso), que es lo que infló su factura.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from make_simulated_companies import Company, HostSpec, VMSpec, hosts, vcls, write  # noqa: E402


def _roles(c: Company, rnd: random.Random, roles, pool_of, off_prob=0.45):
    for role, os, count, (cpu, mem), disks in roles:
        pool = pool_of(role)
        for i in range(1, count + 1):
            on = not (role in ("test", "dev", "qa") and rnd.random() < off_prob)
            c.vms.append(VMSpec(f"{role}-{i:02d}", os, cpu, mem, list(disks), pool[i % len(pool)], on))


def istmo(rnd: random.Random) -> Company:
    c = Company("istmo", "Istmo Seguros S.A.", "Aseguradora", "Ciudad de Panamá, Panamá", "istmoseguros.local", "4.7.1")
    vc = "vcsa.istmoseguros.local"
    prd = hosts("esx-pty", 5, 1, "PTY-PROD", "DC-PANAMA", 2, 16, 768, "8.0.2", vc, vendor="HPE", model="ProLiant DL360 Gen10 Plus")
    dr = hosts("esx-dav", 3, 1, "DAV-DR", "DC-DAVID", 1, 12, 384, "8.0.2", vc, vendor="HPE", model="ProLiant DL20 Gen10 Plus")
    c.hosts = prd + dr
    c.datastores = [("DS-PTY-PRIMERA01", "VMFS", 40960), ("DS-PTY-PRIMERA02", "VMFS", 40960), ("DS-DAV-MSA01", "VMFS", 30720)]
    roles = [("core-polizas-db", "ol8", 2, (16, 256), [150, 3000, 1000]),
             ("core-polizas-app", "rhel8", 6, (8, 32), [100]),
             ("reclamos", "w2012r2", 4, (4, 16), [100, 400]),
             ("portal-corredores", "ubu2204", 4, (4, 8), [60]),
             ("cotizador-web", "ubu2204", 3, (2, 8), [60]),
             ("sql", "w2019", 3, (8, 64), [120, 1000]),
             ("bi", "w2022", 2, (8, 64), [120, 800]),
             ("documentos", "w2016", 3, (4, 16), [100, 5000]),
             ("dc", "w2019", 3, (2, 8), [80]),
             ("exchange-hibrido", "w2019", 1, (4, 16), [120]),
             ("integracion-bus", "rhel7", 4, (4, 16), [80]),
             ("antifraude", "rocky9", 2, (8, 32), [100]),
             ("rpa", "w2019", 6, (4, 8), [80]),
             ("mon", "ubu2004", 2, (2, 8), [60]),
             ("veeam", "w2022", 2, (8, 32), [120]),
             ("qa", "rhel8", 12, (4, 16), [80]),
             ("test", "w2019", 14, (4, 8), [80])]
    _roles(c, rnd, roles, lambda r: prd)
    for i in range(1, 7):
        c.vms.append(VMSpec(f"dr-core-{i:02d}", "rhel8" if i < 4 else "ol8", 8, 32, [100, 500], dr[i % 3], on=False,
                            annotation="Réplica de DR en David, apagada"))
    c.vms.append(VMSpec("vcsa", "photon", 4, 19, [700], prd[0]))
    vcls(c, rnd)
    return c


def quetzal(rnd: random.Random) -> Company:
    c = Company("quetzal", "Textiles Quetzal S.A.", "Manufactura textil (migró a Hyper-V en 2025)",
                "Villa Nueva, Guatemala", "tquetzal.local", "4.6.1")
    vc = "vcenter.tquetzal.local"
    c.hosts = hosts("esx", 6, 1, "PLANTA", "DC-VILLANUEVA", 2, 12, 384, "7.0", vc, model="PowerEdge R640")
    c.datastores = [("DS-UNITY-01", "VMFS", 30720), ("DS-UNITY-02", "VMFS", 30720)]
    roles = [("erp-dynamics", "w2016", 4, (8, 32), [120, 300]),
             ("sql-erp", "w2016", 2, (16, 128), [120, 2000]),
             ("mes-planta", "w2012r2", 4, (4, 16), [100, 200]),
             ("scada-hist", "w2008r2", 2, (4, 16), [80, 1000]),
             ("scada-hmi", "w7", 6, (2, 4), [60]),
             ("calidad-lab", "w2012r2", 2, (2, 8), [80]),
             ("nomina", "w2016", 2, (4, 16), [100]),
             ("dc", "w2016", 3, (2, 8), [80]),
             ("file", "w2016", 2, (4, 16), [100, 4000]),
             ("print", "w2012r2", 2, (2, 4), [60]),
             ("rdp-gw", "w2019", 3, (8, 32), [100]),
             ("wsus", "w2016", 1, (2, 8), [80, 500]),
             ("edi-proveedores", "centos7", 2, (2, 8), [60]),
             ("bi", "w2019", 2, (8, 32), [120, 500]),
             ("test", "w2016", 10, (4, 8), [80])]
    _roles(c, rnd, roles, lambda r: c.hosts)
    c.vms.append(VMSpec("vcenter", "photon", 4, 19, [700], c.hosts[0]))
    vcls(c, rnd)
    return c


def copan(rnd: random.Random) -> Company:
    c = Company("copan", "Financiera Copán S.A.", "Financiera (migró a Azure en 2025)",
                "San Pedro Sula, Honduras", "fcopan.local", "4.6.1")
    vc = "vc.fcopan.local"
    c.hosts = hosts("esx-sps", 4, 1, "SPS-PROD", "DC-SPS", 2, 16, 512, "7.0", vc, model="PowerEdge R650")
    c.datastores = [("DS-SPS-01", "VMFS", 30720), ("DS-SPS-02", "VMFS", 20480)]
    # todo pedido "por las dudas": 8-16 vCPU y 32-64 GiB para apps que usan 10 %
    roles = [("core-fin-app", "w2019", 4, (16, 64), [150]),
             ("core-fin-db", "w2019", 2, (32, 256), [150, 2000]),
             ("originacion", "w2019", 4, (8, 32), [120]),
             ("cobranza", "w2016", 3, (8, 32), [120, 300]),
             ("app-movil-api", "ubu2004", 6, (8, 32), [80]),
             ("web", "w2019", 4, (8, 16), [80]),
             ("dc", "w2019", 2, (4, 16), [80]),
             ("file", "w2019", 1, (8, 32), [120, 3000]),
             ("sql-rpt", "w2019", 2, (16, 128), [150, 1000]),
             ("buro-int", "w2016", 2, (8, 16), [80]),
             ("siem", "ubu2004", 2, (16, 64), [100, 2000]),
             ("dev", "w2019", 12, (8, 32), [100]),
             ("test", "w2019", 10, (8, 32), [100])]
    _roles(c, rnd, roles, lambda r: c.hosts, off_prob=0.2)
    c.vms.append(VMSpec("vc", "photon", 4, 19, [700], c.hosts[0]))
    vcls(c, rnd)
    return c


PROFILES = [istmo, quetzal, copan]


def build(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    done = []
    for i, profile in enumerate(PROFILES):
        rnd = random.Random(2026_11_05 + i)
        company = profile(rnd)
        path = out_dir / f"{company.key}-rvtools.xlsx"
        write(company, path, rnd)
        done.append((company, path))
    return done


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/empresas")
    for company, path in build(out):
        print(f"{path}  {company.name}: {len(company.vms)} VMs, {len(company.hosts)} hosts")
