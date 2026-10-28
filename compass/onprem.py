"""Costo de otros hipervisores sobre el mismo hardware: Hyper-V, Nutanix AHV y Oracle Linux KVM (OLVM).

Como Proxmox, solo cuentan licencias y soporte del software; no incluyen hardware
nuevo, backup ni horas de migración.
"""
from __future__ import annotations

import math

from .rvtools import Host

NOTE = "Solo licencias y soporte del software. No incluye hardware nuevo, backup ni horas de migración."


def hyperv_cost(hosts: list[Host], rules: dict, term_years: int = 3) -> dict:
    per_cpu = rules["min_cores_per_cpu"]["value"]
    per_server = rules["min_cores_per_server"]["value"]
    cores = sum(max(h.sockets * max(h.cores_per_cpu, per_cpu), per_server) for h in hosts)
    per_core = rules["datacenter_usd_per_16_cores"]["value"] / 16
    license_usd = cores * per_core
    sa = rules["software_assurance_rate"]["value"]
    # la licencia es perpetua: se reparte en el plazo para compararla con las suscripciones
    low = license_usd / term_years
    high = low + license_usd * sa
    return {
        "edition": "Windows Server 2025 Datacenter",
        "licensed_cores": cores,
        "license_usd": round(license_usd),
        "term_years": term_years,
        "annual_usd": {"low": round(low), "high": round(high)},
        "basis": f"Licencia perpetua repartida en {term_years} años; el alto suma Software Assurance de {sa:.0%} anual",
        "note": "Incluye VMs Windows Server ilimitadas en cada host. No incluye CALs ni System Center. " + NOTE,
        "rules_version": rules["rules_version"],
    }


def nutanix_cost(hosts: list[Host], rules: dict, edition: str | None = None) -> dict:
    edition = edition or rules["default_edition"]
    per_cpu = rules["min_cores_per_cpu"]["value"]
    cores = sum(h.sockets * max(h.cores_per_cpu, per_cpu) for h in hosts)
    price = rules["list_price_usd_per_core_year"]["value"][edition]
    disc = rules["negotiated_discount"]["value"]
    return {
        "edition": f"NCI {edition.capitalize()}",
        "licensed_cores": cores,
        "annual_list_usd": round(cores * price),
        "annual_usd": {"low": round(cores * price * (1 - disc["high"])),
                       "high": round(cores * price * (1 - disc["low"]))},
        "basis": f"Precio de revendedor de {price} USD por núcleo con descuento de {disc['low']:.0%} a {disc['high']:.0%}",
        "note": "Requiere hardware certificado por Nutanix y al menos 3 nodos; confirmar si los hosts actuales califican. " + NOTE,
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
