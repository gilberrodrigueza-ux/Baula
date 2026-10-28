"""Uso: python -m compass EXPORT.xlsx [--catalog azure.json] [--catalog gcp.json] [--json] [--html R.html] [--pdf R.pdf]"""
from __future__ import annotations

import argparse
import json
import sys

from .analyze import analyze
from .report import render_html, write_pdf
from .rvtools import RVToolsError


def _usd(r: dict) -> str:
    return f"US$ {r['low']:,} a {r['high']:,}"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="compass", description="Baula Compass: renovar VMware o salir.")
    p.add_argument("export", help="Export de RVTools (.xlsx)")
    p.add_argument("--catalog", action="append", default=[], help="Catálogo de precios de nube (JSON)")
    p.add_argument("--years", type=int, default=3, help="Plazo de la suscripción en años (3 por defecto)")
    p.add_argument("--late", action="store_true", help="Aplicar recargo por renovación tardía")
    p.add_argument("--order-minimum", action="store_true", help="Aplicar el mínimo de 72 núcleos por pedido (en disputa)")
    p.add_argument("--proxmox-tier", choices=["community", "basic", "standard", "premium"])
    p.add_argument("--json", action="store_true", help="Imprimir el resultado completo en JSON")
    p.add_argument("--html", help="Guardar el reporte en HTML")
    p.add_argument("--pdf", help="Guardar el reporte en PDF (usa Chrome, Chromium o Edge)")
    p.add_argument("--client", default="", help="Nombre del cliente para el reporte")
    p.add_argument("--example", action="store_true", help="Marcar el reporte como datos de ejemplo")
    a = p.parse_args(argv)

    try:
        r = analyze(a.export, a.catalog, term_years=a.years, late_renewal=a.late,
                    apply_order_minimum=a.order_minimum or None, proxmox_tier=a.proxmox_tier)
    except RVToolsError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    if a.html or a.pdf:
        html = render_html(r, client=a.client, example=a.example, years=a.years)
        if a.html:
            with open(a.html, "w", encoding="utf-8") as f:
                f.write(html)
        if a.pdf:
            try:
                write_pdf(html, a.pdf)
            except RuntimeError as e:
                print(f"Error: {e}", file=sys.stderr)
                return 3
    if a.json:
        print(json.dumps(r, indent=2, ensure_ascii=False))
        return 0

    inv = r["inventory"]
    print(f"Inventario de {inv['source']}")
    print(f"  VMs: {inv['vms_total']} ({inv['vms_powered_on']} encendidas, {inv['vms_powered_off']} apagadas)")
    print(f"  vCPU: {inv['vcpus_total']} · RAM: {inv['memory_gib_total']} GiB · Disco aprovisionado: {inv['disk_gib_provisioned']} GiB")
    print(f"  Hosts: {inv['hosts']} · Sockets: {inv['sockets']} · Núcleos físicos: {inv['physical_cores']}")
    print(f"  SO fuera de soporte o por vencer: {len(inv['unsupported_os'])}")
    for w in inv["warnings"]:
        print(f"  Aviso: {w}")
    print("\nCosto anual estimado")
    for name, s in r["scenarios"].items():
        if name in ("VCF", "VVF"):
            n = s["annual_negotiated_usd"]
            print(f"  {name}: {s['licensed_cores']} núcleos licenciados ({s['padding_cores']} de relleno por el mínimo)")
            print(f"    lista {_usd(s['annual_list_usd'])} · negociado sin preparación {_usd(n['unprepared'])} · con preparación {_usd(n['prepared'])}")
        elif name == "PROXMOX":
            print(f"  Proxmox ({s['tier']}/{s['upper_tier']}, {s['sockets']} sockets): {_usd(s['annual_usd'])}")
        elif name in ("HYPERV", "NUTANIX", "OLVM"):
            print(f"  {s['edition']}: {_usd(s['annual_usd'])} ({s['basis']})")
        else:
            tag = " [PRECIOS DE MUESTRA]" if s["catalog_is_sample"] else ""
            print(f"  {name} {s['region']}{tag}: {_usd(s['annual_usd'])} · {s['vms_placed']} VMs ubicadas, {len(s['vms_unplaced'])} sin instancia")
    print(f"\nReglas de Broadcom al {r['scenarios']['VCF']['rules_version']}. No es asesoría legal ni contractual.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
