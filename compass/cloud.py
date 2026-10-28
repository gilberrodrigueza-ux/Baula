"""Costo estimado en nube pública (Azure, GCP) a partir de un catálogo de precios.

El catálogo lo generan scripts/fetch_azure_prices.py y scripts/fetch_gcp_prices.py.
Cada VM encendida se asigna a la instancia más barata que cubre sus vCPU y su RAM
asignadas (no las consumidas: eso es dimensionamiento por uso real, fuera del MVP).
"""
from __future__ import annotations

import json
from pathlib import Path

from .rvtools import VM

MIB_PER_GIB = 1024


def load_catalog(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_windows(vm: VM) -> bool:
    return "windows" in vm.os.lower()


def pick_instance(vm: VM, catalog: dict) -> dict | None:
    mem_gib = vm.memory_mib / MIB_PER_GIB
    price_key = "windows_hour" if is_windows(vm) else "linux_hour"
    fits = [i for i in catalog["instances"]
            if i["vcpus"] >= vm.vcpus and i["memory_gib"] >= mem_gib and i.get(price_key) is not None]
    if not fits:
        return None
    return min(fits, key=lambda i: (i[price_key], i["vcpus"], i["memory_gib"]))


def cloud_cost(vms: list[VM], catalog: dict, *, include_powered_off: bool = False) -> dict:
    hours = catalog.get("hours_per_month", 730)
    storage_rate = catalog["storage"]["usd_per_gib_month"]
    commit = catalog.get("commit_discount_3yr", 0.0)

    lines, unplaced = [], []
    compute_month = storage_month = 0.0
    for vm in vms:
        if vm.template or (not vm.powered_on and not include_powered_off):
            continue
        disk_gib = vm.disk_total_mib / MIB_PER_GIB
        storage = disk_gib * storage_rate
        inst = pick_instance(vm, catalog)
        if inst is None:
            unplaced.append(vm.name)
            continue
        hourly = inst["windows_hour"] if is_windows(vm) else inst["linux_hour"]
        compute = hourly * hours
        compute_month += compute
        storage_month += storage
        lines.append({"vm": vm.name, "instance": inst["name"], "windows": is_windows(vm),
                      "compute_usd_month": round(compute, 2), "storage_usd_month": round(storage, 2)})

    on_demand_year = (compute_month + storage_month) * 12
    committed_year = (compute_month * (1 - commit) + storage_month) * 12
    return {
        "provider": catalog["provider"],
        "region": catalog["region"],
        "catalog_fetched": catalog.get("fetched"),
        "catalog_is_sample": catalog.get("sample", False),
        "vms_placed": len(lines),
        "vms_unplaced": unplaced,
        "annual_usd": {"low": round(committed_year), "high": round(on_demand_year)},
        "compute_usd_month": round(compute_month, 2),
        "storage_usd_month": round(storage_month, 2),
        "lines": lines,
    }
