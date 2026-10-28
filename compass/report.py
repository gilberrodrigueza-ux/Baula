"""Reporte de Compass en HTML imprimible y en PDF (vía Chrome, Chromium o Edge headless).

El HTML es autocontenido: sin fuentes, scripts ni imágenes externas, para que el
mismo archivo se pueda abrir en el navegador o convertir a PDF sin red.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from datetime import date
from html import escape
from pathlib import Path

from .rules import load_rules

STATUS_LABEL = {
    "official": "Oficial",
    "reported": "Reportado",
    "disputed": "En disputa",
    "assumption": "Supuesto",
    "to_verify": "Por verificar",
}
SCENARIO_LABEL = {
    "VCF": "Renovar VMware Cloud Foundation",
    "VVF": "Renovar vSphere Foundation",
    "AZURE": "Migrar a Azure",
    "GCP": "Migrar a Google Cloud",
    "PROXMOX": "Migrar a Proxmox VE",
}


def _usd(n: float) -> str:
    return f"US$ {n:,.0f}"


def _k(n: float) -> str:
    return f"{n / 1000:,.0f} k" if n >= 10_000 else f"{n:,.0f}"


def _range(r: dict) -> str:
    return f"{r['low']:,.0f} a {r['high']:,.0f}"


def term_ranges(result: dict, years: int) -> list[dict]:
    """Rango de costo de software en el plazo, en el mismo orden para el gráfico y la tabla."""
    rows = []
    for key, s in result["scenarios"].items():
        if key in ("VCF", "VVF"):
            n = s["term_negotiated_usd"]
            low, high = n["prepared"]["low"], n["unprepared"]["high"]
            basis = "Negociado: con preparación a sin preparación"
        elif key == "PROXMOX":
            low, high = s["annual_usd"]["low"] * years, s["annual_usd"]["high"] * years
            basis = f"Suscripción {s['tier']} a {s['upper_tier']}, {s['sockets']} sockets"
        else:
            low, high = s["annual_usd"]["low"] * years, s["annual_usd"]["high"] * years
            basis = f"{s['region']}: compromiso 3 años a pago por uso"
        rows.append({"key": key, "label": SCENARIO_LABEL.get(key, key), "low": low, "high": high,
                     "basis": basis, "sample": s.get("catalog_is_sample", False)})
    return rows


def range_chart(rows: list[dict]) -> str:
    """Barras de rango horizontales en una sola escala. Una sola serie: el nombre de la fila da la identidad."""
    width, label_w, value_w, row_h, top = 680, 240, 120, 32, 8
    plot_w = width - label_w - value_w
    vmax = max(r["high"] for r in rows) or 1
    height = top + row_h * len(rows) + 26
    x = lambda v: label_w + plot_w * v / vmax
    out = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" '
           f'aria-label="Costo de software en el plazo por escenario">']
    for i in range(5):  # grilla recesiva
        v = vmax * i / 4
        out.append(f'<line x1="{x(v):.1f}" x2="{x(v):.1f}" y1="{top}" y2="{height - 22}" class="grid"/>')
        out.append(f'<text x="{x(v):.1f}" y="{height - 6}" class="axis" text-anchor="middle">{_k(v)}</text>')
    for i, r in enumerate(rows):
        cy = top + row_h * i + row_h / 2
        x0, x1 = x(r["low"]), max(x(r["high"]), x(r["low"]) + 6)
        out.append(f'<text x="{label_w - 12}" y="{cy + 4:.1f}" class="label" text-anchor="end">{escape(r["label"])}</text>')
        out.append(f'<rect x="{x0:.1f}" y="{cy - 7:.1f}" width="{x1 - x0:.1f}" height="14" rx="4" class="bar"/>')
        out.append(f'<text x="{x1 + 8:.1f}" y="{cy + 4:.1f}" class="value">{_k(r["low"])} a {_k(r["high"])}</text>')
    out.append("</svg>")
    return "".join(out)


def findings(result: dict, rows: list[dict], broadcom: dict, today: date) -> list[str]:
    inv, vcf = result["inventory"], result["scenarios"]["VCF"]
    out = []
    cheapest = min(rows, key=lambda r: r["low"])
    renew = [r for r in rows if r["key"] in ("VCF", "VVF")]
    if cheapest["key"] not in ("VCF", "VVF") and renew:
        best = min(renew, key=lambda r: r["low"])
        out.append(f"<b>{escape(cheapest['label'])}</b> es el escenario de menor costo de software: "
                   f"{_k(cheapest['low'])} a {_k(cheapest['high'])} en el plazo, contra "
                   f"{_k(best['low'])} a {_k(best['high'])} para {escape(best['label'][0].lower() + best['label'][1:])}.")
    if vcf["padding_cores"]:
        out.append(f"Se pagan <b>{vcf['padding_cores']} núcleos que no existen</b>: de {vcf['licensed_cores']} "
                   f"licenciados, {vcf['padding_cores']} son relleno por el mínimo de 16 núcleos por CPU "
                   f"en hosts con CPUs más chicas. Consolidar esos hosts baja la renovación.")
    if inv["vms_powered_off"]:
        out.append(f"<b>{inv['vms_powered_off']} VMs apagadas</b> de {inv['vms_total']}. No se cuentan en la nube; "
                   f"son candidatas a retiro antes de migrar o de renovar.")
    expired = [u for u in inv["unsupported_os"] if u["state"] == "expired"]
    expiring = [u for u in inv["unsupported_os"] if u["state"] == "expiring"]
    if expired or expiring:
        out.append(f"<b>{len(expired)} VMs con sistema operativo sin soporte</b> y {len(expiring)} que pierden "
                   f"soporte en los próximos 12 meses. Cualquier destino exige resolverlas: actualizar, "
                   f"aislar o pagar soporte extendido.")
    eogs = broadcom["rules"]["vsphere8_end_of_general_support"]["value"]
    v8 = [h for h in inv["host_list"] if "8.0" in h["esx_version"]]
    if v8:
        months = (date.fromisoformat(eogs).year - today.year) * 12 + date.fromisoformat(eogs).month - today.month
        out.append(f"{len(v8)} de {inv['hosts']} hosts corren ESXi 8. El soporte general de vSphere 8 termina el "
                   f"<b>{_fecha(eogs)}</b>, en unos {months} meses.")
    return out


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def _fecha(iso: str | None) -> str:
    if not iso:
        return "sin fecha"
    parts = iso[:10].split("-")
    if len(parts) == 2:
        return f"{MESES[int(parts[1]) - 1]} {parts[0]}"
    if len(parts) == 1:
        return parts[0]
    return f"{int(parts[2])} {MESES[int(parts[1]) - 1][:3]} {parts[0]}"


def _sources_rows(broadcom: dict, proxmox: dict, catalogs: list[dict]) -> str:
    names = {
        "min_cores_per_cpu": "Mínimo de 16 núcleos por CPU",
        "min_cores_per_order": "Mínimo de 72 núcleos por pedido",
        "vsan_tib_per_core": "vSAN incluido por núcleo",
        "list_price_usd_per_core_year": "Precio de lista por núcleo y año",
        "negotiated_discount": "Descuento negociado",
        "late_renewal_surcharge": "Recargo por renovación tardía",
        "vvf_availability": "Disponibilidad de VVF en América",
        "vsphere8_end_of_general_support": "Fin de soporte general de vSphere 8",
    }
    rows = []
    for key, label in names.items():
        r = broadcom["rules"][key]
        src = "<br>".join(f'{escape(s["title"])} <span class="muted">({_fecha(s["source_date"])}, '
                          f'revisado {_fecha(s["checked"])})</span>' for s in r["sources"])
        used = "" if r.get("default_enabled", True) else '<br><span class="muted">No aplicado en este reporte</span>'
        rows.append(f'<tr><td>{label}{used}</td><td><span class="tag tag-{r["status"]}">'
                    f'{STATUS_LABEL[r["status"]]}</span></td><td>{src}</td></tr>')
    p = proxmox["sources"][0]
    rows.append(f'<tr><td>Suscripción Proxmox VE por socket</td><td><span class="tag tag-official">Oficial</span></td>'
                f'<td>{escape(p["title"])} <span class="muted">(revisado {_fecha(p["checked"])})</span></td></tr>')
    fx = proxmox["eur_to_usd"]
    rows.append(f'<tr><td>Tipo de cambio EUR a USD: {fx["value"]}</td><td><span class="tag tag-assumption">Supuesto</span></td>'
                f'<td>{escape(fx["note"])}</td></tr>')
    for c in catalogs:
        status = "assumption" if c["sample"] else "official"
        text = ("Precios ilustrativos, no descargados de la API ni cotizados" if c["sample"]
                else f"API pública de precios, descargada {_fecha(c['fetched'])}")
        rows.append(f'<tr><td>Precios de {escape(c["provider"].upper())} {escape(c["region"])}</td>'
                    f'<td><span class="tag tag-{status}">{STATUS_LABEL[status]}</span></td><td>{text}</td></tr>')
    return "".join(rows)


def render_html(result: dict, *, client: str = "", example: bool = False,
                today: date | None = None, years: int | None = None) -> str:
    today = today or date.today()
    inv, sc = result["inventory"], result["scenarios"]
    years = years or sc["VCF"]["term_years"]
    broadcom, proxmox = load_rules("broadcom"), load_rules("proxmox")
    min_cpu = broadcom["rules"]["min_cores_per_cpu"]["value"]
    rows = term_ranges(result, years)
    clouds = [s for k, s in sc.items() if k not in ("VCF", "VVF", "PROXMOX")]
    catalogs = [{"provider": s["provider"], "region": s["region"], "sample": s["catalog_is_sample"],
                 "fetched": s["catalog_fetched"]} for s in clouds]
    example = example or any(c["sample"] for c in catalogs)

    banner = ('<div class="banner">Datos de ejemplo. Empresa, inventario y precios de nube ficticios. '
              'Las reglas de Broadcom y Proxmox son las reales del motor al día de hoy.</div>') if example else ""

    hosts = "".join(
        f'<tr><td>{escape(h["name"])}</td><td>{escape(h["cluster"])}</td><td class="n">{h["sockets"]}</td>'
        f'<td class="n">{h["cores_per_cpu"]}</td><td class="n">{h["sockets"] * max(h["cores_per_cpu"], min_cpu)}</td>'
        f'<td>{escape(h["esx_version"])}</td></tr>' for h in inv["host_list"])

    risk = {}
    for u in inv["unsupported_os"]:
        r = risk.setdefault(u["label"], {"n": 0, "on": 0, "eos": u["end_of_support"], "state": u["state"]})
        r["n"] += 1
        r["on"] += u["powered_on"]
    risk_rows = "".join(
        f'<tr><td>{escape(label)}</td><td class="n">{r["n"]}</td><td class="n">{r["on"]}</td>'
        f'<td>{_fecha(r["eos"])}</td><td>{"Vencido" if r["state"] == "expired" else "Vence en 12 meses"}</td></tr>'
        for label, r in sorted(risk.items(), key=lambda kv: kv[1]["eos"]))

    detail = []
    for edition in ("VCF", "VVF"):
        s = sc[edition]
        detail.append(
            f'<tr><td><b>{edition}</b><br><span class="muted">{s["licensed_cores"]} núcleos licenciados, '
            f'{s["vsan_tib_included"]:g} TiB de vSAN incluidos</span></td>'
            f'<td class="n">{_range(s["annual_list_usd"])}</td><td class="n">{_range(s["annual_negotiated_usd"]["unprepared"])}</td>'
            f'<td class="n">{_range(s["annual_negotiated_usd"]["prepared"])}</td></tr>')
    cloud_rows = "".join(
        f'<tr><td><b>{escape(s["provider"].upper())}</b> {escape(s["region"])}</td><td class="n">{s["vms_placed"]}</td>'
        f'<td class="n">{len(s["vms_unplaced"])}</td><td class="n">{_usd(s["compute_usd_month"])}</td>'
        f'<td class="n">{_usd(s["storage_usd_month"])}</td><td class="n">{_range(s["annual_usd"])}</td></tr>' for s in clouds)
    px = sc["PROXMOX"]

    findings_html = "".join(f"<li>{f}</li>" for f in findings(result, rows, broadcom, today))
    term_rows = "".join(
        f'<tr><td>{escape(r["label"])}</td><td class="n">{_usd(r["low"])}</td><td class="n">{_usd(r["high"])}</td>'
        f'<td class="muted">{escape(r["basis"])}</td></tr>' for r in rows)
    client_line = escape(client) if client else escape(inv["source"])

    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Baula Compass: {client_line}</title>
<style>{CSS}</style></head>
<body>
<section class="page">
  <header class="cover">
    <div class="brand">{LOGO}<span>Baula Compass</span></div>
    <h1>Renovar VMware o salir</h1>
    <p class="sub">Evaluación preliminar para <b>{client_line}</b></p>
    <p class="meta">Generado el {_fecha(today.isoformat())} · Export de RVTools: {escape(inv["source"])} ·
      Reglas de Broadcom al {_fecha(broadcom["rules_version"])} · Plazo: {years} años</p>
  </header>
  {banner}
  <h2>Resumen</h2>
  <ul class="findings">{findings_html}</ul>
  <h3>Costo de software en {years} años, en USD</h3>
  {range_chart(rows)}
  <p class="note">Solo software y nube. No incluye hardware, centro de datos, energía, personal, backup ni horas de
  migración. Renovar y Proxmox siguen sobre el hardware actual; la nube lo reemplaza. Comparar los totales
  sin ese ajuste favorece a quedarse en sitio.</p>
</section>

<section class="page">
  <h2>Inventario</h2>
  <div class="kpis">
    <div><b>{inv["vms_total"]}</b><span>VMs ({inv["vms_powered_on"]} encendidas)</span></div>
    <div><b>{inv["vcpus_total"]:,}</b><span>vCPU asignadas</span></div>
    <div><b>{inv["memory_gib_total"]:,.0f}</b><span>GiB de RAM asignada</span></div>
    <div><b>{inv["disk_gib_provisioned"] / 1024:,.1f}</b><span>TiB de disco aprovisionado</span></div>
    <div><b>{inv["hosts"]}</b><span>hosts, {inv["sockets"]} sockets</span></div>
    <div><b>{inv["physical_cores"]}</b><span>núcleos físicos</span></div>
  </div>
  <h3>Hosts y núcleos licenciables</h3>
  <table><thead><tr><th>Host</th><th>Cluster</th><th class="n">Sockets</th><th class="n">Núcleos por CPU</th>
  <th class="n">Núcleos a licenciar</th><th>Versión</th></tr></thead><tbody>{hosts}</tbody></table>
  <h3>Sistemas operativos sin soporte o por vencer</h3>
  <table><thead><tr><th>Sistema operativo</th><th class="n">VMs</th><th class="n">Encendidas</th><th>Fin de soporte</th>
  <th>Estado</th></tr></thead><tbody>{risk_rows}</tbody></table>
  <p class="note">Fechas de fin de soporte estándar del fabricante, pendientes de verificar contra cada página de ciclo de vida.</p>
</section>

<section class="page">
  <h2>Detalle por escenario</h2>
  <h3>Costo de software en {years} años</h3>
  <table><thead><tr><th>Escenario</th><th class="n">Desde</th><th class="n">Hasta</th><th>Base del rango</th></tr></thead>
  <tbody>{term_rows}</tbody></table>
  <h3>Renovar VMware, costo anual en USD</h3>
  <table><thead><tr><th>Edición</th><th class="n">Lista</th><th class="n">Negociado sin preparación</th><th class="n">Negociado con preparación</th></tr></thead>
  <tbody>{"".join(detail)}</tbody></table>
  <p class="note">"Con preparación" supone llegar a la negociación con inventario limpio, alternativa cotizada y
  fecha de renovación bajo control. El mínimo de 72 núcleos por pedido está en disputa y no se aplicó.</p>
  <h3>Nube pública</h3>
  <table><thead><tr><th>Destino</th><th class="n">VMs ubicadas</th><th class="n">Sin instancia</th>
  <th class="n">Cómputo / mes</th><th class="n">Disco / mes</th><th class="n">Anual (USD)</th></tr></thead><tbody>{cloud_rows}</tbody></table>
  <p class="note">Cada VM encendida va a la instancia más barata que cubre sus vCPU y RAM asignadas, no las usadas.
  Windows a pago por uso, sin Azure Hybrid Benefit ni licencias propias. El rango va de compromiso a 3 años a pago por uso.</p>
  <h3>Proxmox VE</h3>
  <table><thead><tr><th>Suscripción</th><th class="n">Sockets</th><th class="n">Anual (USD)</th></tr></thead>
  <tbody><tr><td>{escape(px["tier"])} a {escape(px["upper_tier"])}</td><td class="n">{px["sockets"]}</td><td class="n">{_range(px["annual_usd"])}</td></tr></tbody></table>
  <p class="note">{escape(px["note"])}</p>
</section>

<section class="page">
  <h2>Supuestos y fuentes</h2>
  <p>Broadcom no publica lista de precios y cambia las reglas seguido. Cada cifra de licenciamiento sale de una
  regla versionada con fuente y fecha. Si una regla cambia, el reporte se regenera.</p>
  <table class="sources"><thead><tr><th>Regla</th><th>Estado</th><th>Fuente</th></tr></thead>
  <tbody>{_sources_rows(broadcom, proxmox, catalogs)}</tbody></table>
</section>

<section class="page">
  <h2>Qué no mide este reporte</h2>
  <ul>
    <li>Uso real de CPU y RAM: dimensiona por lo asignado, así que la nube sale cara. El ajuste por uso real suele bajarla bastante.</li>
    <li>Excedente de vSAN: RVTools no trae la capacidad cruda.</li>
    <li>Dependencias entre aplicaciones, firewall, cambio de IPs y olas de migración.</li>
    <li>Hardware, centro de datos, personal y costo de la migración en sí.</li>
  </ul>
  <h2>Próximos pasos</h2>
  <ol class="steps">
    <li><b>Confirmar la fecha de renovación</b> y el estado del contrato con el partner: define cuánto margen hay para negociar.</li>
    <li><b>Evaluación formal de Baula</b>: dimensionamiento por uso real, precios del día y cotización de cada destino,
      licencias propias de Windows y SQL, y un plan de olas para las VMs críticas.</li>
    <li><b>Resolver los sistemas operativos vencidos</b> antes de elegir destino.</li>
    <li><b>Retirar las VMs apagadas</b> que nadie reclama, para no licenciarlas ni migrarlas.</li>
  </ol>
  <footer>Baula Compass · baulashift.com · Estimación orientativa, no es asesoría legal ni contractual
  ni una cotización de Broadcom, Microsoft, Google o Proxmox.</footer>
</section>
</body></html>
"""


CHROME_CANDIDATES = [
    "chromium", "chromium-browser", "google-chrome", "chrome", "msedge",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def find_chrome() -> str | None:
    for c in [os.environ.get("BAULA_CHROME"), *CHROME_CANDIDATES]:
        if c and (shutil.which(c) or Path(c).is_file()):
            return shutil.which(c) or c
    return None


def write_pdf(html: str, path: str | Path) -> None:
    """Imprime el HTML a PDF con Chrome, Chromium o Edge en modo headless (BAULA_CHROME fuerza la ruta)."""
    chrome = find_chrome()
    if chrome is None:
        raise RuntimeError("No se encontró Chrome, Chromium ni Edge. Indicá la ruta en BAULA_CHROME.")
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "reporte.html"
        src.write_text(html, encoding="utf-8")
        subprocess.run([chrome, "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                        f"--user-data-dir={tmp}", f"--print-to-pdf={Path(path).resolve()}", src.as_uri()],
                       check=True, capture_output=True, timeout=120)


LOGO = ('<svg viewBox="0 0 64 64" width="28" height="28" aria-hidden="true"><circle cx="32" cy="32" r="30" fill="#2fb5a3"/>'
        '<ellipse cx="32" cy="34" rx="13" ry="17" fill="#0b2a3a"/><path d="M32 18v32M22 27h20M21 37h22" stroke="#2fb5a3" '
        'stroke-width="2.4" stroke-linecap="round"/><circle cx="32" cy="13" r="5" fill="#0b2a3a"/></svg>')

CSS = """
:root { --deep:#0b2a3a; --sea:#12465f; --teal:#2fb5a3; --teal-ink:#1d7f72; --sand:#f4efe6; --ink:#10222c;
  --muted:#5b6b73; --line:#dfe5e8; --warn:#8a5a00; --warn-bg:#fff4dc; }
* { box-sizing:border-box; }
body { margin:0; background:#fff; color:var(--ink); font:10.5pt/1.5 system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif; }
.page { max-width:760px; margin:0 auto; padding:16px; break-after:page; }
@media print { .page { padding:0; } }
.page:last-child { break-after:auto; }
.cover { background:var(--deep); color:#fff; border-radius:12px; padding:16px 22px; }
.brand { display:flex; align-items:center; gap:10px; font-weight:700; letter-spacing:.02em; color:var(--teal); }
h1 { font-size:22pt; margin:6px 0 2px; line-height:1.15; }
.sub { margin:0; font-size:12pt; }
.meta { margin:8px 0 0; font-size:8.5pt; color:#b8c9d1; }
.banner { margin:12px 0 0; padding:8px 12px; border-radius:8px; background:var(--warn-bg); color:var(--warn);
  font-weight:600; font-size:9pt; border:1px solid #f0d9a6; }
h2 { font-size:15pt; color:var(--sea); margin:18px 0 6px; }
h3 { font-size:11pt; margin:14px 0 6px; }
.findings { padding-left:18px; margin:0; }
.findings li { margin:4px 0; }
.chart { width:100%; height:auto; display:block; margin:4px 0 8px; }
.chart .grid { stroke:var(--line); stroke-width:1; }
.chart .axis { fill:var(--muted); font-size:10px; }
.chart .label { fill:var(--ink); font-size:12px; }
.chart .value { fill:var(--muted); font-size:11px; }
.chart .bar { fill:var(--teal); }
table { width:100%; border-collapse:collapse; font-size:9pt; margin:4px 0; }
th { text-align:left; color:var(--muted); font-weight:600; border-bottom:1.5px solid var(--line); padding:4px 6px; }
td { border-bottom:1px solid var(--line); padding:4px 6px; vertical-align:top; }
tr { break-inside:avoid; }
.n { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
.muted { color:var(--muted); }
.note { font-size:8.5pt; color:var(--muted); margin:4px 0 10px; }
.kpis { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin:6px 0 10px; }
.kpis div { background:var(--sand); border-radius:10px; padding:10px 12px; }
.kpis b { display:block; font-size:17pt; color:var(--deep); font-variant-numeric:tabular-nums; }
.kpis span { font-size:8.5pt; color:var(--muted); }
.tag { display:inline-block; padding:1px 7px; border-radius:99px; font-size:8pt; font-weight:600; white-space:nowrap;
  border:1px solid currentColor; }
.tag-official { color:var(--teal-ink); } .tag-reported { color:var(--sea); }
.tag-disputed, .tag-to_verify, .tag-assumption { color:var(--warn); }
.sources td:first-child { width:30%; } .sources td:nth-child(2) { width:13%; }
.steps li { margin:4px 0; }
footer { margin-top:18px; padding-top:8px; border-top:1px solid var(--line); font-size:8pt; color:var(--muted); }
@media (max-width:600px) { .kpis { grid-template-columns:repeat(2,1fr); } }
@page { size:Letter; margin:14mm; }
"""
