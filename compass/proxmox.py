"""Costo de suscripción de Proxmox VE sobre el mismo hardware (se cobra por socket)."""
from __future__ import annotations

from .rvtools import Host


def proxmox_cost(hosts: list[Host], proxmox: dict, tier: str | None = None) -> dict:
    tier = tier or proxmox["default_tier"]
    sockets = sum(h.sockets for h in hosts)
    eur = proxmox["tiers"][tier]["eur_per_socket_year"] * sockets
    fx = proxmox["eur_to_usd"]["value"]
    # rango: el nivel elegido contra el siguiente más caro, para mostrar sensibilidad al soporte
    order = list(proxmox["tiers"])
    upper = order[min(order.index(tier) + 1, len(order) - 1)]
    eur_high = proxmox["tiers"][upper]["eur_per_socket_year"] * sockets
    return {
        "tier": tier,
        "upper_tier": upper,
        "sockets": sockets,
        "annual_eur": eur,
        "annual_usd": {"low": round(eur * fx), "high": round(eur_high * fx)},
        "eur_to_usd": fx,
        "rules_version": proxmox["rules_version"],
        "note": "Solo suscripción de software. No incluye hardware nuevo, backup ni horas de migración.",
    }
