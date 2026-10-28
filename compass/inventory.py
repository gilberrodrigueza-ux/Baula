"""Resumen del inventario y detección de VMs apagadas y SO fuera de soporte."""
from __future__ import annotations

from collections import Counter
from datetime import date

from .rvtools import Inventory

MIB_PER_GIB = 1024


def os_support(os_name: str, os_eol: dict, today: date) -> dict | None:
    """Devuelve la entrada de fin de soporte si el SO ya venció o vence en 12 meses."""
    lowered = os_name.lower()
    for entry in os_eol["entries"]:
        if entry["match"] in lowered:
            eos = date.fromisoformat(entry["end_of_support"])
            days = (eos - today).days
            if days < 0:
                return {**entry, "state": "expired"}
            if days <= 365:
                return {**entry, "state": "expiring"}
            return None
    return None


def summarize(inv: Inventory, os_eol: dict, today: date | None = None) -> dict:
    today = today or date.today()
    vms = [v for v in inv.vms if not v.template]
    on = [v for v in vms if v.powered_on]
    off = [v for v in vms if not v.powered_on]

    unsupported = []
    for v in vms:
        hit = os_support(v.os, os_eol, today)
        if hit:
            unsupported.append({"vm": v.name, "os": v.os, "label": hit["label"],
                                "end_of_support": hit["end_of_support"], "state": hit["state"],
                                "powered_on": v.powered_on})

    return {
        "source": inv.source,
        "vms_total": len(vms),
        "vms_powered_on": len(on),
        "vms_powered_off": len(off),
        "templates": sum(1 for v in inv.vms if v.template),
        "vcpus_total": sum(v.vcpus for v in vms),
        "vcpus_powered_on": sum(v.vcpus for v in on),
        "memory_gib_total": round(sum(v.memory_mib for v in vms) / MIB_PER_GIB, 1),
        "memory_gib_powered_on": round(sum(v.memory_mib for v in on) / MIB_PER_GIB, 1),
        "disk_gib_provisioned": round(sum(v.disk_total_mib for v in vms) / MIB_PER_GIB, 1),
        "disk_gib_in_use": round(sum((v.in_use_mib or 0) for v in vms) / MIB_PER_GIB, 1),
        "hosts": len(inv.hosts),
        "sockets": sum(h.sockets for h in inv.hosts),
        "physical_cores": sum(h.sockets * h.cores_per_cpu for h in inv.hosts),
        "host_list": [{"name": h.name, "cluster": h.cluster, "sockets": h.sockets,
                       "cores_per_cpu": h.cores_per_cpu, "esx_version": h.esx_version} for h in inv.hosts],
        "os_breakdown": dict(Counter(v.os or "Desconocido" for v in vms).most_common()),
        "powered_off_vms": sorted(v.name for v in off),
        "unsupported_os": unsupported,
        "warnings": list(inv.warnings),
    }
