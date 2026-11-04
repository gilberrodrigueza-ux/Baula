"""Resumen del inventario y detección de VMs apagadas y SO fuera de soporte."""
from __future__ import annotations

import re
from collections import Counter
from datetime import date

from .rvtools import VM, Host, Inventory

MIB_PER_GIB = 1024


def _matches(entry: dict, lowered: str) -> bool:
    if "pattern" in entry:
        return re.search(entry["pattern"], lowered) is not None
    return entry["match"] in lowered


def os_names(vm: VM) -> list[str]:
    """Nombres del SO de una VM, del más específico al más genérico."""
    return [n for n in (vm.os_detail, vm.os, vm.os_config) if n]


def os_support(os_name: str | list[str], os_eol: dict, today: date) -> dict | None:
    """Devuelve la entrada de fin de soporte si el SO ya venció o vence en 12 meses.

    Acepta un nombre o varios (del más específico al más genérico): gana el primero que reconoce
    alguna entrada, para que el prettyName de Guest Detailed Data mande sobre un genérico.
    """
    names = [os_name] if isinstance(os_name, str) else os_name
    for name in names:
        lowered = name.lower()
        for entry in os_eol["entries"]:
            if _matches(entry, lowered):
                eos = date.fromisoformat(entry["end_of_support"])
                days = (eos - today).days
                if days < 0:
                    return {**entry, "state": "expired", "matched": name}
                if days <= 365:
                    return {**entry, "state": "expiring", "matched": name}
                return None
    return None


def os_version_unknown(vm: VM, os_eol: dict) -> bool:
    """True si ningún nombre del SO dice la versión (p. ej. "Ubuntu Linux (64-bit)", "2016 or later")."""
    patterns = os_eol.get("ambiguous", {}).get("patterns", [])
    names = os_names(vm)
    if not names:
        return False
    def known(n):
        low = n.lower()
        return not any(re.search(p, low) for p in patterns)
    return not any(known(n) for n in names)


ESXI_RULES = {"6": "vsphere6_end_of_general_support", "7": "vsphere7_end_of_general_support",
              "8": "vsphere8_end_of_general_support"}


def host_support(hosts: list[Host], broadcom: dict, today: date) -> list[dict]:
    """Hosts cuya versión de ESXi ya no tiene soporte general o lo pierde en 12 meses."""
    out = []
    for h in hosts:
        m = re.search(r"ESXi (\d+)\.", h.esx_version)
        key = ESXI_RULES.get(m.group(1)) if m else None
        if key is None or key not in broadcom["rules"]:
            continue
        eogs = date.fromisoformat(broadcom["rules"][key]["value"])
        days = (eogs - today).days
        if days <= 365:
            out.append({"host": h.name, "esx_version": h.esx_version, "end_of_general_support": eogs.isoformat(),
                        "state": "expired" if days < 0 else "expiring"})
    return out


def summarize(inv: Inventory, os_eol: dict, today: date | None = None, broadcom: dict | None = None) -> dict:
    today = today or date.today()
    vms = [v for v in inv.vms if not v.template]
    on = [v for v in vms if v.powered_on]
    off = [v for v in vms if not v.powered_on]

    unsupported = []
    for v in vms:
        hit = os_support(os_names(v), os_eol, today)
        if hit:
            unsupported.append({"vm": v.name, "os": hit["matched"], "label": hit["label"],
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
        "os_version_unknown": sorted(v.name for v in vms if os_version_unknown(v, os_eol)
                                     and not os_support(os_names(v), os_eol, today)),
        "unsupported_hosts": host_support(inv.hosts, broadcom, today) if broadcom else [],
        "warnings": list(inv.warnings),
    }
