"""Costo estimado en nube pública (Azure, GCP) a partir de un catálogo de precios.

El catálogo lo generan scripts/fetch_azure_prices.py y scripts/fetch_gcp_prices.py.
Cada VM encendida se asigna a la instancia más barata que cubre sus vCPU y su RAM
asignadas (no las consumidas: eso es dimensionamiento por uso real, fuera del MVP).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .rvtools import VM

MIB_PER_GIB = 1024


def load_catalog(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_windows(vm: VM) -> bool:
    return "windows" in vm.os.lower()


# VMs de la propia plataforma VMware que no se migran: vCLS (vSphere Cluster Services) y el vCenter
_VCENTER_NAME = re.compile(r"(^|[-_.])(vc|vcsa|vcenter)\d*($|[-_.])")


def is_vmware_system(vm: VM) -> bool:
    name = vm.name.lower()
    if name.startswith("vcls-") or name.startswith("vcls ("):
        return True
    photon = "photon" in (vm.os or vm.os_config).lower()
    return photon and _VCENTER_NAME.search(name) is not None


_DESKTOP = re.compile(r"windows (xp|vista|7|8|8\.1|10|11)\b")


def is_windows_desktop(vm: VM) -> bool:
    """Windows de escritorio (VDI o equipos heredados): no se cotiza como VM de servidor en IaaS."""
    return any(_DESKTOP.search(n.lower()) for n in (vm.os_detail, vm.os, vm.os_config) if n)


def disk_in_use_mib(vm: VM) -> float:
    """Espacio usado en disco: "In Use MiB" de vInfo sin el archivo de swap de la VM encendida, tope en lo aprovisionado."""
    total = vm.disk_total_mib
    if vm.in_use_mib is None:
        return total
    used = vm.in_use_mib - (vm.memory_mib if vm.powered_on else 0)
    return min(max(used, 0.0), total)


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

    lines, unplaced, system, desktops, unplaced_detail = [], [], [], [], []
    # el compromiso (reserva o plan de ahorro) descuenta solo el cómputo; la licencia de Windows
    # se paga aparte a precio de lista, así que se separa: cómputo base = precio Linux
    compute_month = license_month = storage_month = storage_used_month = 0.0
    for vm in vms:
        if vm.template or (not vm.powered_on and not include_powered_off):
            continue
        if is_vmware_system(vm):
            system.append(vm.name)
            continue
        if is_windows_desktop(vm):
            desktops.append(vm.name)
            continue
        disk_gib = vm.disk_total_mib / MIB_PER_GIB
        storage = disk_gib * storage_rate
        storage_used = disk_in_use_mib(vm) / MIB_PER_GIB * storage_rate
        inst = pick_instance(vm, catalog)
        if inst is None:
            unplaced.append(vm.name)
            unplaced_detail.append({"vm": vm.name, "vcpus": vm.vcpus,
                                    "memory_gib": round(vm.memory_mib / MIB_PER_GIB, 1)})
            continue
        hourly = inst["windows_hour"] if is_windows(vm) else inst["linux_hour"]
        compute = hourly * hours
        license_ = (inst["windows_hour"] - inst["linux_hour"]) * hours if is_windows(vm) else 0.0
        compute_month += compute
        license_month += license_
        storage_month += storage
        storage_used_month += storage_used
        lines.append({"vm": vm.name, "instance": inst["name"], "windows": is_windows(vm),
                      "compute_usd_month": round(compute, 2), "windows_license_usd_month": round(license_, 2),
                      "storage_usd_month": round(storage, 2)})

    # alto: pago por uso y disco aprovisionado; bajo: compromiso y solo el espacio usado
    on_demand_year = (compute_month + storage_month) * 12
    committed_year = ((compute_month - license_month) * (1 - commit) + license_month + storage_used_month) * 12
    return {
        "provider": catalog["provider"],
        "region": catalog["region"],
        "catalog_fetched": catalog.get("fetched"),
        "catalog_is_sample": catalog.get("sample", False),
        "vms_placed": len(lines),
        "vms_unplaced": unplaced,
        "vms_vmware_system": system,
        "vms_windows_desktop": desktops,
        "unplaced_detail": unplaced_detail,
        "annual_usd": {"low": round(committed_year), "high": round(on_demand_year)},
        "compute_usd_month": round(compute_month, 2),
        "windows_license_usd_month": round(license_month, 2),
        "storage_usd_month": round(storage_month, 2),
        "storage_in_use_usd_month": round(storage_used_month, 2),
        "lines": lines,
    }
