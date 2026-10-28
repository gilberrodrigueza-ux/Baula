"""Genera el catálogo de precios de GCP para Compass desde la Cloud Billing Catalog API.

Uso: GCP_API_KEY=... python scripts/fetch_gcp_prices.py --region us-east1 --out prices/gcp-us-east1.json

Arma los tamaños n2-standard, n2-highmem y n2-highcpu con el precio por vCPU y por GiB de N2.
La licencia de Windows Server se suma por vCPU-hora. El disco es Balanced PD.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timezone

COMPUTE_SERVICE = "services/6F81-5844-456A"
API = f"https://cloudbilling.googleapis.com/v1/{COMPUTE_SERVICE}/skus"
SHAPES = {"standard": 4, "highmem": 8, "highcpu": 1}  # GiB por vCPU
VCPUS = (2, 4, 8, 16, 32, 48, 64, 80, 96, 128)


def fetch_skus(key: str) -> list[dict]:
    skus, token = [], ""
    while True:
        q = {"key": key, "pageSize": 5000, "currencyCode": "USD"}
        if token:
            q["pageToken"] = token
        with urllib.request.urlopen(f"{API}?{urllib.parse.urlencode(q)}", timeout=120) as r:
            page = json.load(r)
        skus += page.get("skus", [])
        token = page.get("nextPageToken")
        if not token:
            return skus


def unit_price(sku: dict) -> float:
    rate = sku["pricingInfo"][0]["pricingExpression"]["tieredRates"][-1]["unitPrice"]
    return int(rate.get("units", 0)) + rate.get("nanos", 0) / 1e9


def find(skus, region, *, contains, usage="OnDemand", exclude=()):
    for s in skus:
        d = s["description"]
        if (region in s.get("serviceRegions", []) and s["category"].get("usageType") == usage
                and all(c in d for c in contains) and not any(e in d for e in exclude)):
            return s
    raise SystemExit(f"No se encontró SKU con {contains} ({usage}) en {region}.")


def build(region: str, key: str) -> dict:
    skus = fetch_skus(key)
    core = unit_price(find(skus, region, contains=("N2 Instance Core",), exclude=("Custom", "Sole Tenancy")))
    ram = unit_price(find(skus, region, contains=("N2 Instance Ram",), exclude=("Custom", "Sole Tenancy")))
    cud_core = unit_price(find(skus, region, contains=("Commitment", "N2 Cpu", "3 Year"), usage="Commit3Yr"))
    win = unit_price(find(skus, region, contains=("Licensing Fee for Windows Server", "CPU cost")))
    disk = unit_price(find(skus, region, contains=("Balanced PD Capacity",), exclude=("Regional",)))

    instances = []
    for shape, gib in SHAPES.items():
        for n in VCPUS:
            linux = n * core + n * gib * ram
            instances.append({"name": f"n2-{shape}-{n}", "vcpus": n, "memory_gib": n * gib,
                              "linux_hour": round(linux, 5), "windows_hour": round(linux + n * win, 5)})
    return {
        "provider": "gcp",
        "region": region,
        "currency": "USD",
        "fetched": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": API,
        "sample": False,
        "hours_per_month": 730,
        # el compromiso de 3 años se aproxima con la relación de precio de vCPU
        "commit_discount_3yr": round(1 - cud_core / core, 3),
        "storage": {"name": "Balanced PD", "usd_per_gib_month": round(disk, 5)},
        "instances": sorted(instances, key=lambda i: (i["vcpus"], i["memory_gib"])),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="us-east1")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    key = os.environ.get("GCP_API_KEY")
    if not key:
        raise SystemExit("Falta la variable GCP_API_KEY (clave de API con Cloud Billing API habilitada).")
    cat = build(a.region, key)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(cat, f, indent=2)
    print(f"{len(cat['instances'])} tamaños, descuento 3 años {cat['commit_discount_3yr']:.0%}, guardado en {a.out}")
