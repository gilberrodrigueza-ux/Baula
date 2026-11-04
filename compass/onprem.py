"""Costo de otros hipervisores sobre el mismo hardware: Hyper-V, Nutanix AHV y Oracle Linux KVM (OLVM).

Como Proxmox, solo cuentan licencias y soporte del software; no incluyen hardware
nuevo, backup ni horas de migración.
"""
from __future__ import annotations

import math

from .rvtools import VM, Host

NOTE = "Solo licencias y soporte del software. No incluye hardware nuevo, backup ni horas de migración."


def windows_share(vms: list[VM]) -> float:
    real = [v for v in vms if not v.template and not v.name.lower().startswith("vcls")]
    return sum("windows" in v.os.lower() for v in real) / len(real) if real else 0.0


def hyperv_cost(hosts: list[Host], rules: dict, term_years: int = 3, *, owns_datacenter: bool = False,
                vms: list[VM] | None = None) -> dict:
    per_cpu = rules["min_cores_per_cpu"]["value"]
    per_server = rules["min_cores_per_server"]["value"]
    cores = sum(max(h.sockets * max(h.cores_per_cpu, per_cpu), per_server) for h in hosts)
    per_core = rules["datacenter_usd_per_16_cores"]["value"] / 16
    license_usd = cores * per_core
    sa = rules["software_assurance_rate"]["value"]
    # la licencia es perpetua: se reparte en el plazo para compararla con las suscripciones
    owned = {"low": 0, "high": round(license_usd * sa)}
    share = windows_share(vms) if vms is not None else None
    hint = ""
    if owns_datacenter:
        # el cliente ya licencia Datacenter para sus VMs Windows sobre VMware: solo paga SA, si la mantiene
        low, high = 0.0, license_usd * sa
        basis = (f"Datacenter ya licenciado; el alto es Software Assurance de {sa:.0%} anual, "
                 f"que no es costo nuevo si ya se paga hoy")
    else:
        low = license_usd / term_years
        high = low + license_usd * sa
        basis = f"Licencia perpetua repartida en {term_years} años; el alto suma Software Assurance de {sa:.0%} anual"
        if share is not None and share >= 0.5:
            # con mayoría Windows es habitual tener Datacenter en los hosts de VMware para cubrir las VMs
            hint = (f"Con {share:.0%} de VMs Windows es probable que los hosts ya tengan Datacenter; "
                    f"si es así, el costo baja a US$ {owned['low']:,} a {owned['high']:,} al año. ")
    return {
        "edition": "Windows Server 2025 Datacenter",
        "licensed_cores": cores,
        "license_usd": round(license_usd),
        "term_years": term_years,
        "annual_usd": {"low": round(low), "high": round(high)},
        "owns_datacenter": owns_datacenter,
        "annual_usd_if_owned": owned,
        "windows_share": None if share is None else round(share, 2),
        "basis": basis,
        "note": hint + "Incluye VMs Windows Server ilimitadas en cada host. No incluye CALs ni System Center. " + NOTE,
        "rules_version": rules["rules_version"],
    }


def nutanix_cost(hosts: list[Host], rules: dict, edition: str | None = None) -> dict:
    edition = edition or rules["default_edition"]
    per_cpu = rules["min_cores_per_cpu"]["value"]
    cores = sum(h.sockets * max(h.cores_per_cpu, per_cpu) for h in hosts)
    price = rules["list_price_usd_per_core_year"]["value"][edition]
    disc = rules["negotiated_discount"]["value"]
    clusters: dict[str, int] = {}
    for h in hosts:
        clusters[h.cluster or h.name] = clusters.get(h.cluster or h.name, 0) + 1
    small = sorted(c for c, n in clusters.items() if n < 3)
    note = ("Requiere hardware certificado por Nutanix. El clúster estándar es de 3 nodos; los de 1 y 2 nodos "
            "solo van en modelos ROBO y NCI-Edge (hasta 5 nodos y 25 VMs por clúster) se licencia por VM. ")
    if small:
        note = (f"{len(small)} de {len(clusters)} clústeres tienen menos de 3 hosts: van a modelos ROBO de 1 o 2 nodos, "
                f"NCI-Edge o hardware adicional, y el precio puede no ser el de esta tabla. ") + note
    return {
        "edition": f"NCI {edition.capitalize()}",
        "licensed_cores": cores,
        "annual_list_usd": round(cores * price),
        "annual_usd": {"low": round(cores * price * (1 - disc["high"])),
                       "high": round(cores * price * (1 - disc["low"]))},
        "basis": f"Precio de revendedor de {price} USD por núcleo con descuento de {disc['low']:.0%} a {disc['high']:.0%}",
        "small_clusters": small,
        "note": note + NOTE,
        "rules_version": rules["rules_version"],
    }


def olvm_cost(hosts: list[Host], rules: dict) -> dict:
    pairs = sum(math.ceil(h.sockets / 2) for h in hosts)
    price = rules["support_usd_per_cpu_pair_year"]["value"]
    return {
        "edition": "Oracle Linux KVM + OLVM",
        "cpu_pairs": pairs,
        "annual_usd": {"low": pairs * price["premier"], "high": pairs * price["premier_plus"]},
        "basis": "Soporte Oracle Linux por par de CPUs: Premier en el bajo, Premier Plus (VMs ilimitadas) en el alto",
        "note": "El hipervisor y OLVM no tienen costo de licencia. " + NOTE,
        "rules_version": rules["rules_version"],
    }
