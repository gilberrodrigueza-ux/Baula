"""Une las piezas: inventario, renovación VCF/VVF, nubes, Proxmox, Hyper-V, Nutanix y Oracle KVM."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from . import rvtools
from .cloud import cloud_cost, load_catalog
from .inventory import summarize
from .licensing import renewal_cost
from .onprem import hyperv_cost, nutanix_cost, olvm_cost
from .proxmox import proxmox_cost
from .rules import load_rules


def analyze(export_path: str | Path, catalogs: list[str | Path] = (), *,
            term_years: int = 3, late_renewal: bool = False,
            apply_order_minimum: bool | None = None,
            proxmox_tier: str | None = None, today: date | None = None) -> dict:
    inv = rvtools.load(export_path)
    broadcom = load_rules("broadcom")
    result = {
        "inventory": summarize(inv, load_rules("os_eol"), today),
        "scenarios": {},
    }
    for edition in ("VCF", "VVF"):
        result["scenarios"][edition] = renewal_cost(
            inv.hosts, broadcom, edition, term_years=term_years,
            late_renewal=late_renewal, apply_order_minimum=apply_order_minimum)
    for path in catalogs:
        catalog = load_catalog(path)
        result["scenarios"][catalog["provider"].upper()] = cloud_cost(inv.vms, catalog)
    result["scenarios"]["PROXMOX"] = proxmox_cost(inv.hosts, load_rules("proxmox"), proxmox_tier)
    result["scenarios"]["HYPERV"] = hyperv_cost(inv.hosts, load_rules("hyperv"), term_years)
    result["scenarios"]["NUTANIX"] = nutanix_cost(inv.hosts, load_rules("nutanix"))
    result["scenarios"]["OLVM"] = olvm_cost(inv.hosts, load_rules("oracle"))
    return result
