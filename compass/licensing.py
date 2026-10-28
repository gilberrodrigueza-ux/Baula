"""Costo de renovar VMware en VCF o VVF, por núcleo, con las reglas de rules/broadcom.json."""
from __future__ import annotations

import math

from .rules import rule
from .rvtools import Host

EDITIONS = ("VCF", "VVF")


def licensed_cores(hosts: list[Host], min_per_cpu: int) -> int:
    return sum(h.sockets * max(h.cores_per_cpu, min_per_cpu) for h in hosts)


def renewal_cost(hosts: list[Host], broadcom: dict, edition: str, *,
                 apply_order_minimum: bool | None = None,
                 late_renewal: bool = False,
                 term_years: int = 1) -> dict:
    if edition not in EDITIONS:
        raise ValueError(f"Edición desconocida: {edition}")
    rules = broadcom["rules"]
    min_cpu = rule(broadcom, "min_cores_per_cpu")
    cores = licensed_cores(hosts, min_cpu)
    physical = sum(h.sockets * h.cores_per_cpu for h in hosts)

    if apply_order_minimum is None:
        apply_order_minimum = rules["min_cores_per_order"].get("default_enabled", False)
    order_min = rule(broadcom, "min_cores_per_order")
    if apply_order_minimum and cores < order_min:
        cores = order_min

    price = rule(broadcom, "list_price_usd_per_core_year")[edition]
    list_low, list_high = cores * price["low"], cores * price["high"]

    disc = rule(broadcom, "negotiated_discount")
    def band(d):
        # el escenario más barato usa el precio bajo con el descuento alto, y viceversa
        return {"low": round(list_low * (1 - d["high"])), "high": round(list_high * (1 - d["low"]))}

    surcharge = rule(broadcom, "late_renewal_surcharge") if late_renewal else 0.0

    def term(b):
        # el recargo aplica solo al primer año
        return {k: round(v * term_years + v * surcharge) for k, v in b.items()}

    per_core = rule(broadcom, "vsan_tib_per_core")[edition]
    vsan_tib = cores * per_core
    if edition == "VVF":
        vsan_tib = math.ceil(vsan_tib)

    annual_list = {"low": round(list_low), "high": round(list_high)}
    return {
        "edition": edition,
        "physical_cores": physical,
        "licensed_cores": cores,
        "padding_cores": cores - physical,
        "order_minimum_applied": bool(apply_order_minimum),
        "late_renewal_surcharge": surcharge,
        "term_years": term_years,
        "annual_list_usd": annual_list,
        "annual_negotiated_usd": {"unprepared": band(disc["unprepared"]), "prepared": band(disc["prepared"])},
        "term_list_usd": term(annual_list),
        "term_negotiated_usd": {"unprepared": term(band(disc["unprepared"])), "prepared": term(band(disc["prepared"]))},
        "vsan_tib_included": vsan_tib,
        "rules_version": broadcom["rules_version"],
        "rules_status": {k: rules[k]["status"] for k in
                         ("min_cores_per_cpu", "min_cores_per_order", "list_price_usd_per_core_year",
                          "negotiated_discount", "late_renewal_surcharge")},
    }
