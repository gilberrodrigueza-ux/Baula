"""Genera el catálogo de precios de Azure para Compass desde la Retail Prices API (pública, sin clave).

Uso: python scripts/fetch_azure_prices.py --region eastus --out prices/azure-eastus.json

La API no publica vCPU ni RAM por tamaño, por eso los tamaños soportados están en SIZES.
El almacenamiento se aproxima con el precio de un disco Premium SSD P30 (1 TiB) dividido por GiB.
"""
from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone

API = "https://prices.azure.com/api/retail/prices"

# armSkuName -> (vCPU, GiB de RAM). Fuente: documentación de tamaños de Azure (Dsv5, Esv5, Fsv2).
SIZES = {
    **{f"Standard_D{n}s_v5": (n, n * 4) for n in (2, 4, 8, 16, 32, 48, 64, 96)},
    **{f"Standard_E{n}s_v5": (n, n * 8) for n in (2, 4, 8, 16, 32, 48, 64)},
    "Standard_E20s_v5": (20, 160),
    "Standard_E96s_v5": (96, 672),
    **{f"Standard_F{n}s_v2": (n, n * 2) for n in (2, 4, 8, 16, 32, 48, 64, 72)},
}
HOURS_3Y = 3 * 8760


def fetch(filter_expr: str) -> list[dict]:
    url = f"{API}?{urllib.parse.urlencode({'$filter': filter_expr})}"
    items = []
    while url:
        with urllib.request.urlopen(url, timeout=60) as r:
            page = json.load(r)
        items += page.get("Items", [])
        url = page.get("NextPageLink")
    return items


def build(region: str) -> dict:
    base = f"serviceName eq 'Virtual Machines' and armRegionName eq '{region}'"
    consumption = fetch(base + " and priceType eq 'Consumption'")
    reservation = fetch(base + " and priceType eq 'Reservation'")

    instances = {}
    for it in consumption:
        sku = it.get("armSkuName")
        if sku not in SIZES or it.get("unitOfMeasure") != "1 Hour":
            continue
        if "Spot" in it["skuName"] or "Low Priority" in it["skuName"]:
            continue
        vcpus, mem = SIZES[sku]
        entry = instances.setdefault(sku, {"name": sku, "vcpus": vcpus, "memory_gib": mem,
                                           "linux_hour": None, "windows_hour": None})
        key = "windows_hour" if "Windows" in it["productName"] else "linux_hour"
        entry[key] = it["retailPrice"]

    ratios = []
    for it in reservation:
        sku = it.get("armSkuName")
        if sku in instances and it.get("reservationTerm") == "3 Years" and instances[sku]["linux_hour"]:
            ratios.append((it["retailPrice"] / HOURS_3Y) / instances[sku]["linux_hour"])
    commit = round(1 - sum(ratios) / len(ratios), 3) if ratios else 0.0

    disks = fetch(f"serviceName eq 'Storage' and armRegionName eq '{region}' and skuName eq 'P30 LRS'")
    p30 = next((d["retailPrice"] for d in disks if d.get("meterName", "").startswith("P30")), None)
    if p30 is None:
        raise SystemExit("No se encontró el precio del disco P30 LRS.")

    return {
        "provider": "azure",
        "region": region,
        "currency": "USD",
        "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": API,
        "sample": False,
        "hours_per_month": 730,
        "commit_discount_3yr": commit,
        "storage": {"name": "Premium SSD P30 LRS prorrateado", "usd_per_gib_month": round(p30 / 1024, 5)},
        "instances": sorted(instances.values(), key=lambda i: (i["vcpus"], i["memory_gib"])),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="eastus")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cat = build(a.region)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(cat, f, indent=2)
    print(f"{len(cat['instances'])} tamaños, descuento 3 años {cat['commit_discount_3yr']:.0%}, guardado en {a.out}")
