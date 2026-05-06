#!/usr/bin/env python3
"""
NHAI Tender Intelligence — Interactive CLI Dashboard
Full terminal UI: browse tenders, view analysis, trigger fetches.
"""
import json
import sys
import os
from datetime import datetime, timezone, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.live import Live
from rich.spinner import Spinner
from rich.rule import Rule
from rich import box

console = Console()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _days_left(deadline_str: str) -> int | None:
    if not deadline_str or deadline_str == "N/A":
        return None
    for fmt in ("%Y-%m-%d %I:%M %p", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            d = datetime.strptime(deadline_str[:len(fmt)], fmt)
            return (d.date() - date.today()).days
        except ValueError:
            continue
    return None


def _urgency_color(days: int | None) -> str:
    if days is None:
        return "dim"
    if days < 0:
        return "dim"
    if days <= 3:
        return "bold red"
    if days <= 7:
        return "bold yellow"
    return "green"


def _status_badge(days: int | None) -> str:
    if days is None:
        return "[dim]UNKNOWN[/]"
    if days < 0:
        return "[dim]CLOSED[/]"
    if days == 0:
        return "[bold red]TODAY[/]"
    if days <= 3:
        return f"[bold red]{days}d LEFT[/]"
    if days <= 7:
        return f"[bold yellow]{days}d LEFT[/]"
    return f"[green]{days}d[/]"


def _na(v) -> str:
    if not v or v == "N/A":
        return "[dim]N/A[/]"
    return str(v)


def _src(citations: list) -> str:
    if not citations:
        return ""
    pages = [str(c.get("page", "?")) for c in citations[:3] if isinstance(c, dict)]
    return f" [dim](p.{', '.join(pages)})[/]" if pages else ""


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_client():
    from db.supabase import get_client
    return get_client()


def _load_tenders(client, status_filter=None):
    q = client.table("tenders").select("*").order("submission_deadline", desc=False)
    if status_filter:
        q = q.eq("status", status_filter)
    return q.execute().data or []


def _load_analysis(client, tender_id):
    r = (client.table("tender_analysis")
         .select("analysis, analyzed_at")
         .eq("tender_id", tender_id)
         .execute())
    if r.data:
        return r.data[0]
    return None


def _get_date_range(tenders: list) -> tuple[str, str]:
    dates = [t.get("publish_date", "") or t.get("submission_deadline", "")
             for t in tenders if t.get("publish_date") or t.get("submission_deadline")]
    dates = sorted([d[:10] for d in dates if d])
    if not dates:
        return "N/A", "N/A"
    return dates[0], dates[-1]


# ── Screens ───────────────────────────────────────────────────────────────────

def screen_header():
    console.print()
    console.print(Panel(
        "[bold white]NHAI Tender Intelligence System[/]  |  "
        "[dim]EY AI Incubator[/]  |  "
        f"[dim]{datetime.now().strftime('%d %b %Y  %H:%M')}[/]",
        border_style="blue", padding=(0, 2)
    ))


def screen_dashboard(client):
    """Main dashboard: stats + tender list."""
    console.clear()
    screen_header()

    all_tenders = _load_tenders(client)
    today = date.today()

    live_tenders = []
    closed_tenders = []
    expiring_soon = []

    for t in all_tenders:
        days = _days_left(t.get("submission_deadline", ""))
        t["_days"] = days
        if days is None or days < 0:
            closed_tenders.append(t)
        else:
            live_tenders.append(t)
            if days <= 7:
                expiring_soon.append(t)

    earliest, latest = _get_date_range(all_tenders)

    # Stats row
    stats = Table.grid(padding=(0, 4))
    stats.add_column()
    stats.add_column()
    stats.add_column()
    stats.add_column()
    stats.add_column()
    stats.add_row(
        f"[bold cyan]{len(all_tenders)}[/]\n[dim]Total in DB[/]",
        f"[bold green]{len(live_tenders)}[/]\n[dim]Live / Active[/]",
        f"[bold red]{len(expiring_soon)}[/]\n[dim]Expiring ≤7d[/]",
        f"[bold dim]{len(closed_tenders)}[/]\n[dim]Closed[/]",
        f"[cyan]{earliest}[/] → [cyan]{latest}[/]\n[dim]Date range in DB[/]",
    )
    console.print(Panel(stats, title="Overview", border_style="cyan"))

    # Tender table
    table = Table(
        box=box.SIMPLE_HEAD,
        show_lines=True,
        title=f"[bold]All Tenders — sorted by deadline[/]",
        title_justify="left",
    )
    table.add_column("#", style="dim", width=4, no_wrap=True)
    table.add_column("ID", style="dim", width=7, no_wrap=True)
    table.add_column("Tender No", width=36, no_wrap=True)
    table.add_column("Title", width=52)
    table.add_column("Deadline", width=12, no_wrap=True)
    table.add_column("Status", width=11, no_wrap=True)
    table.add_column("✓", width=3, no_wrap=True)

    # Load analysis status for all
    analyzed_ids = set()
    r = client.table("tender_analysis").select("tender_id").execute()
    if r.data:
        analyzed_ids = {row["tender_id"] for row in r.data}

    # Live first, then closed
    sorted_tenders = live_tenders + sorted(closed_tenders, key=lambda t: t.get("submission_deadline", ""), reverse=True)

    for i, t in enumerate(sorted_tenders, 1):
        days = t["_days"]
        color = _urgency_color(days)
        deadline = (t.get("submission_deadline") or "")[:10]
        analyzed = "✓" if t["tender_id"] in analyzed_ids else ""
        table.add_row(
            str(i),
            t["tender_id"],
            Text(t.get("tender_no", "")[:36], style=color, overflow="ellipsis"),
            Text(t.get("title", "")[:52], overflow="ellipsis"),
            deadline,
            _status_badge(days),
            f"[green]{analyzed}[/]",
        )

    console.print(table)
    return sorted_tenders, analyzed_ids


def screen_tender_detail(client, tender: dict, analyzed_ids: set):
    """Show full detail + analysis for one tender."""
    console.clear()
    screen_header()

    tid = tender["tender_id"]
    days = tender.get("_days")

    console.print(Panel(
        f"[bold]{tender.get('title', 'Unknown')}[/]\n"
        f"[dim]Tender No:[/] {tender.get('tender_no', 'N/A')}  "
        f"[dim]ID:[/] {tid}  "
        f"[dim]Status:[/] {_status_badge(days)}  "
        f"[dim]Published:[/] {(tender.get('publish_date') or '')[:10]}",
        border_style="yellow",
        title="Tender Detail",
    ))

    # API fields panel
    api_table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    api_table.add_column("Field", style="dim", width=28)
    api_table.add_column("Value", width=50)
    for label, key in [
        ("Submission Deadline",  "submission_deadline"),
        ("Bid Opening Date",     "bid_opening_date"),
        ("Pre-Bid Meeting",      "pre_bid_meeting"),
        ("Tender Type",          "tender_type"),
        ("Procurement Category", "procurement_cat"),
        ("Evaluation Type",      "evaluation_type"),
        ("EMD Value",            "emd_value"),
        ("Application Fee",      "application_fee"),
        ("Doc Download Period",  "doc_sales_start"),
        ("Published",            "publish_date"),
    ]:
        val = (tender.get(key) or "")
        if val:
            api_table.add_row(label, val[:50])
    console.print(Panel(api_table, title="API Fields", border_style="dim"))

    # Analysis
    if tid in analyzed_ids:
        rec = _load_analysis(client, tid)
        if rec:
            console.print(f"[dim]Analyzed at: {rec.get('analyzed_at','?')[:19]}[/]")
            _print_full_analysis(rec["analysis"])
    else:
        console.print(Panel("[yellow]Not yet analyzed.[/] Run: [bold]python cli.py analyze " + tid + "[/]",
                            border_style="yellow"))


def _print_full_analysis(a: dict):
    """Print complete structured analysis with all citations."""
    def na(v): return _na(v)
    def src(c): return _src(c)

    # ── KEY DATES ─────────────────────────────────────────────────────────
    kd = a.get("key_dates", {})
    dt = Table(box=box.SIMPLE, show_header=False, padding=(0, 1), title="KEY DATES")
    dt.add_column("", style="dim", width=32)
    dt.add_column("", width=55)
    for label, key in [
        ("Pre-Bid Meeting",             "pre_bid_meeting"),
        ("Last Date — Clarification",   "last_date_clarification"),
        ("Submission Deadline",         "proposal_submission_deadline"),
        ("Technical Bid Opening",       "technical_bid_opening"),
        ("Financial Bid Opening",       "financial_bid_opening"),
        ("Bid Validity",                "bid_validity_period"),
        ("Doc Download Period",         "document_download_period"),
    ]:
        v = kd.get(key, "N/A")
        s = src(kd.get(key + "_source", []))
        dt.add_row(label, f"{na(v)}{s}")
    console.print(Panel(dt, border_style="yellow"))

    # ── RFP FEES ──────────────────────────────────────────────────────────
    f = a.get("rfp_fees", {})
    bd = f.get("bank_details", {})
    ft = Table(box=box.SIMPLE, show_header=False, padding=(0, 1), title="RFP FEES & PAYMENT")
    ft.add_column("", style="dim", width=32)
    ft.add_column("", width=55)
    ft.add_row("RFP Fee",              f"{na(f.get('rfp_fee_amount'))}{src(f.get('rfp_fee_source',[]))}")
    ft.add_row("Payment Mode",         na(f.get("payment_mode")))
    ft.add_row("EMD",                  f"{na(f.get('emd_amount'))}{src(f.get('emd_source',[]))}")
    ft.add_row("Performance Security", f"{na(f.get('performance_security'))}{src(f.get('performance_security_source',[]))}")
    if bd and bd.get("account_number") not in (None, "N/A", ""):
        ft.add_row("Bank",             f"{bd.get('bank_name','?')} | {bd.get('branch','')}")
        ft.add_row("Account No",       bd.get("account_number", ""))
        ft.add_row("IFSC",             bd.get("ifsc_code", ""))
        ft.add_row("Beneficiary",      bd.get("beneficiary_name", ""))
    console.print(Panel(ft, border_style="yellow"))

    # ── ELIGIBILITY ───────────────────────────────────────────────────────
    e = a.get("eligibility", {})
    te = e.get("technical", {})
    fe = e.get("financial", {})
    et = Table(box=box.SIMPLE, show_header=False, padding=(0, 1), title="ELIGIBILITY CRITERIA")
    et.add_column("", style="dim", width=32)
    et.add_column("", width=55)
    et.add_row("[cyan]TECHNICAL[/]", "")
    et.add_row("  Min Annual Turnover",       f"{na(te.get('min_annual_turnover'))}{src(te.get('min_annual_turnover_source',[]))}")
    et.add_row("  Similar Experience",        f"{na(te.get('similar_project_experience'))}{src(te.get('similar_project_experience_source',[]))}")
    et.add_row("  JV Conditions",             f"{na(te.get('jv_conditions'))}{src(te.get('jv_conditions_source',[]))}")
    et.add_row("  Assignment Cap",            f"{na(te.get('ongoing_assignment_cap'))}{src(te.get('ongoing_assignment_cap_source',[]))}")
    for p in (te.get("key_personnel_requirements") or []):
        et.add_row("  Key Personnel",         p)
    for o in (te.get("other_conditions") or []):
        et.add_row("  Other",                 o)
    et.add_row("[cyan]FINANCIAL[/]", "")
    et.add_row("  Min Annual Turnover",       f"{na(fe.get('min_annual_turnover'))}{src(fe.get('min_annual_turnover_source',[]))}")
    et.add_row("  Net Worth",                 f"{na(fe.get('net_worth_requirement'))}{src(fe.get('net_worth_requirement_source',[]))}")
    et.add_row("  Financial Years",           f"{na(fe.get('financial_years_considered'))}{src(fe.get('financial_years_considered_source',[]))}")
    console.print(Panel(et, border_style="yellow"))

    # ── EVALUATION ────────────────────────────────────────────────────────
    ev = a.get("evaluation", {})
    evt = Table(box=box.SIMPLE, show_header=False, padding=(0, 1), title="EVALUATION & SELECTION")
    evt.add_column("", style="dim", width=32)
    evt.add_column("", width=55)
    evt.add_row("Selection Method",       f"{na(ev.get('selection_method'))}{src(ev.get('selection_method_source',[]))}")
    evt.add_row("Technical Weightage",    na(ev.get("technical_weightage")))
    evt.add_row("Financial Weightage",    f"{na(ev.get('financial_weightage'))}{src(ev.get('weightage_source',[]))}")
    evt.add_row("Tech Min Score",         f"{na(ev.get('technical_min_qualifying_score'))}{src(ev.get('qualifying_score_source',[]))}")
    evt.add_row("Financial > Technical",  "[red]YES[/]" if ev.get("financial_higher_wins") else "[green]NO[/]")
    for c in (ev.get("technical_evaluation_criteria") or []):
        evt.add_row(f"  {c.get('criterion','')}", f"{c.get('max_marks','')} marks  {c.get('sub_criteria','')}")
    for pf in (ev.get("pass_fail_criteria") or []):
        evt.add_row("  Pass/Fail", pf[:80])
    console.print(Panel(evt, border_style="yellow"))

    # ── SCOPE ─────────────────────────────────────────────────────────────
    sc = a.get("scope", {})
    sct = Table(box=box.SIMPLE, show_header=False, padding=(0, 1), title="SCOPE OF RFP")
    sct.add_column("", style="dim", width=24)
    sct.add_column("", width=63)
    sct.add_row("Summary",         na(sc.get("summary")))
    sct.add_row("Location",        f"{na(sc.get('project_location'))}{src(sc.get('project_location_source',[]))}")
    sct.add_row("Duration",        f"{na(sc.get('contract_duration'))}{src(sc.get('contract_duration_source',[]))}")
    if sc.get("in_scope"):
        sct.add_row("[cyan]IN-SCOPE[/]", "")
        for item in sc["in_scope"]:
            sct.add_row("", f"• {item.get('description','')}{src(item.get('source',[]))}")
    if sc.get("out_of_scope"):
        sct.add_row("[cyan]OUT-OF-SCOPE[/]", "")
        for item in sc["out_of_scope"]:
            sct.add_row("", f"• {item.get('description','')}{src(item.get('source',[]))}")
    if sc.get("deliverables"):
        sct.add_row("[cyan]DELIVERABLES[/]", "")
        for d in sc["deliverables"]:
            sct.add_row("", f"• {d.get('description','')}{src(d.get('source',[]))}")
    if sc.get("milestones"):
        sct.add_row("[cyan]MILESTONES[/]", "")
        for m in sc["milestones"]:
            sct.add_row("", f"• {m.get('name','')} | {m.get('timeline','')} | {m.get('deliverable','')}")
    console.print(Panel(sct, border_style="yellow"))

    # ── SUBMISSION ────────────────────────────────────────────────────────
    sub = a.get("submission", {})
    subt = Table(box=box.SIMPLE, show_header=False, padding=(0, 1), title="SUBMISSION MECHANISMS")
    subt.add_column("", style="dim", width=24)
    subt.add_column("", width=63)
    subt.add_row("Mode",     f"{na(sub.get('submission_mode'))}{src(sub.get('submission_mode_source',[]))}")
    subt.add_row("Portal",   f"{na(sub.get('portal'))}{src(sub.get('portal_source',[]))}")
    subt.add_row("Language", na(sub.get("language")))
    subt.add_row("Copies",   na(sub.get("number_of_copies")))
    if sub.get("required_forms"):
        subt.add_row("[cyan]REQUIRED FORMS[/]", "")
        for fm in sub["required_forms"]:
            sign = f" [signed: {fm.get('signing_authority','')}]" if fm.get("signing_authority") not in (None,"N/A","") else ""
            subt.add_row("", f"• {fm.get('form_name','')}: {fm.get('description','')} {sign}  [dim](p.{fm.get('source_page','')})[/]")
    if sub.get("annexures_required"):
        subt.add_row("[cyan]ANNEXURES[/]", "")
        for ann in sub["annexures_required"]:
            subt.add_row("", f"• {ann}")
    if sub.get("certifications_required"):
        subt.add_row("[cyan]CERTIFICATIONS[/]", "")
        for cert in sub["certifications_required"]:
            subt.add_row("", f"• {cert}")
    console.print(Panel(subt, border_style="yellow"))

    # ── INSTRUCTIONS ──────────────────────────────────────────────────────
    inst = a.get("instructions", {})
    if inst.get("scope_of_work_summary") and inst.get("scope_of_work_summary") != "N/A":
        it = Table(box=box.SIMPLE, show_header=False, padding=(0, 1), title="INSTRUCTIONS TO BIDDERS")
        it.add_column("", style="dim", width=24)
        it.add_column("", width=63)
        it.add_row("Overview",             na(inst.get("overview")))
        it.add_row("Scope of Work",        f"{na(inst.get('scope_of_work_summary'))}{src(inst.get('scope_of_work_source',[]))}")
        it.add_row("Clarification",        f"{na(inst.get('clarification_process'))}{src(inst.get('clarification_source',[]))}")
        it.add_row("Conflict of Interest", f"{na(inst.get('conflict_of_interest'))}{src(inst.get('conflict_source',[]))}")
        for dc in (inst.get("disqualification_conditions") or []):
            it.add_row("Disqualification", dc[:70])
        console.print(Panel(it, border_style="yellow"))

    # ── CONTACTS ──────────────────────────────────────────────────────────
    contacts = a.get("contacts", [])
    if contacts:
        ct = Table(box=box.SIMPLE, show_header=False, padding=(0, 1), title="CONTACT / SPOC")
        ct.add_column("", style="dim", width=24)
        ct.add_column("", width=63)
        for c in contacts:
            ct.add_row("[cyan]Name[/]",        f"{na(c.get('name'))} — {na(c.get('designation'))}")
            ct.add_row("  Department",          na(c.get("department")))
            ct.add_row("  Address",             na(c.get("address")))
            ct.add_row("  Phone",               na(c.get("phone")))
            ct.add_row("  Email",               na(c.get("email")))
            ct.add_row("", "")
        console.print(Panel(ct, border_style="yellow"))

    # ── PAYMENT TERMS ─────────────────────────────────────────────────────
    pts = a.get("payment_terms", [])
    if pts:
        pt = Table(box=box.SIMPLE, show_header=False, padding=(0, 1), title="PAYMENT TERMS")
        pt.add_column("", style="dim", width=24)
        pt.add_column("", width=63)
        for p in pts:
            pt.add_row(p.get("milestone","")[:24], f"{na(p.get('percentage'))} — {p.get('condition','')}{src(p.get('source',[]))}")
        console.print(Panel(pt, border_style="yellow"))

    # ── RISK ──────────────────────────────────────────────────────────────
    r = a.get("risk", {})
    rt = Table(box=box.SIMPLE, show_header=False, padding=(0, 1), title="RISK & REGULATORY")
    rt.add_column("", style="dim", width=24)
    rt.add_column("", width=63)
    rt.add_row("Liquidated Damages",    f"{na(r.get('liquidated_damages'))}{src(r.get('liquidated_damages_source',[]))}")
    rt.add_row("Force Majeure",         f"{na(r.get('force_majeure'))}{src(r.get('force_majeure_source',[]))}")
    rt.add_row("Dispute Resolution",    f"{na(r.get('dispute_resolution'))}{src(r.get('dispute_resolution_source',[]))}")
    rt.add_row("Integrity Pact",        f"{na(r.get('integrity_pact'))}{src(r.get('integrity_pact_source',[]))}")
    if r.get("penalty_clauses"):
        rt.add_row("[cyan]PENALTIES[/]", "")
        for p in r["penalty_clauses"]:
            rt.add_row(f"  [{p.get('category','')}]", f"{p.get('risk','')}{src(p.get('source',[]))}")
    if r.get("termination_conditions"):
        rt.add_row("[cyan]TERMINATION[/]", "")
        for tc in r["termination_conditions"]:
            rt.add_row("", f"• {tc[:80]}")
    if r.get("insurance_requirements"):
        rt.add_row("[cyan]INSURANCE[/]", "")
        for ins in r["insurance_requirements"]:
            rt.add_row("", f"• {ins}")
    console.print(Panel(rt, border_style="yellow"))

    # ── DOCUMENTS ─────────────────────────────────────────────────────────
    docs = a.get("documents", [])
    if docs:
        doct = Table(box=box.SIMPLE, padding=(0, 1), title="DOCUMENTS & FORMS")
        doct.add_column("File", style="cyan", width=24)
        doct.add_column("Type", width=12)
        doct.add_column("Size", width=10)
        doct.add_column("URL / Storage", width=52)
        for d in docs:
            icon = "[red]✗[/]" if d.get("download_error") else "[green]✓[/]"
            url = d.get("supabase_path") or d.get("url", "")
            doct.add_row(
                f"{icon} {d.get('filename','')[:22]}",
                d.get("description","")[:12],
                d.get("filesize","")[:10],
                url[:52],
            )
        console.print(Panel(doct, border_style="yellow"))

    # Confidence footer
    conf = a.get("confidence", "?")
    color = {"high": "green", "medium": "yellow", "low": "red"}.get(conf, "dim")
    console.print(f"\n[{color}]Analysis confidence: {conf.upper()}[/]  "
                  f"[dim]Type: {a.get('tender_type','?')}  "
                  f"Docs analyzed: {', '.join(a.get('source_documents', []))}[/]")


# ── Main menu ─────────────────────────────────────────────────────────────────

def main():
    console.clear()
    screen_header()
    console.print("[dim]Connecting to Supabase...[/]")

    try:
        client = _get_client()
        # Quick ping
        client.table("tenders").select("count", count="exact").execute()
        console.print("[green]✓ Connected[/]\n")
    except Exception as e:
        console.print(f"[red]Connection failed: {e}[/]")
        sys.exit(1)

    while True:
        try:
            sorted_tenders, analyzed_ids = screen_dashboard(client)

            console.print()
            console.print(Rule(style="dim"))
            console.print(
                "[bold cyan]Commands:[/]  "
                "[white]<number>[/] view tender  "
                "[white]f[/] fetch latest  "
                "[white]a <id>[/] analyze tender  "
                "[white]aa[/] analyze all pending  "
                "[white]r[/] refresh  "
                "[white]q[/] quit"
            )

            cmd = Prompt.ask("\n[bold]>[/]", default="r").strip().lower()

            if cmd == "q":
                console.print("[dim]Bye.[/]")
                break

            elif cmd == "f":
                # Fetch latest tenders
                with console.status("[cyan]Fetching from NHAI API...[/]"):
                    from api.nhai import fetch_tender_list
                    from db.supabase import upsert_tenders_bulk
                    tenders = fetch_tender_list(page_size=10000)
                    rows = [_normalize_tender(t) for t in tenders]
                    upsert_tenders_bulk(client, rows)
                console.print(f"[green]✓ {len(rows)} tenders fetched and saved[/]")
                Prompt.ask("[dim]Press Enter to continue[/]", default="")

            elif cmd == "r":
                continue  # just redraw

            elif cmd.startswith("a "):
                parts = cmd.split()
                if len(parts) == 2:
                    tid = parts[1]
                    _run_analyze(client, tid, analyzed_ids, sorted_tenders)
                    Prompt.ask("[dim]Press Enter to continue[/]", default="")

            elif cmd == "aa":
                _run_analyze_all(client, sorted_tenders, analyzed_ids)
                Prompt.ask("[dim]Press Enter to continue[/]", default="")

            elif cmd.isdigit():
                idx = int(cmd) - 1
                if 0 <= idx < len(sorted_tenders):
                    t = sorted_tenders[idx]
                    screen_tender_detail(client, t, analyzed_ids)

                    console.print()
                    sub = Prompt.ask(
                        "[bold]>[/] [dim]a=analyze  r=re-analyze  q=back[/]",
                        default="q"
                    ).strip().lower()

                    if sub in ("a", "r"):
                        _run_analyze(client, t["tender_id"], analyzed_ids, sorted_tenders)
                    Prompt.ask("[dim]Press Enter to continue[/]", default="")
                else:
                    console.print(f"[red]Invalid number. Enter 1–{len(sorted_tenders)}[/]")
                    Prompt.ask("[dim]Press Enter[/]", default="")

        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted. Press q to quit.[/]")
            continue


def _run_analyze(client, tender_id: str, analyzed_ids: set, sorted_tenders: list):
    """Run analysis for one tender with live progress."""
    from api.nhai import fetch_tender_list, fetch_tender_detail
    from api.documents import download_all_documents
    from analysis.engine import analyze_tender
    from db.supabase import upsert_analysis, upload_document, upsert_document_metadata

    console.print(f"\n[cyan]Analyzing tender {tender_id}...[/]")

    try:
        detail_data = fetch_tender_detail(tender_id)
        raw = next((t for t in sorted_tenders if t["tender_id"] == tender_id), {})
        title = raw.get("title") or detail_data.get("title", "Unknown")
        tender_no = raw.get("tender_no", "")

        other_docs = detail_data.get("other_documents", [])
        console.print(f"  Downloading {len(other_docs)} document(s)...")
        downloaded = download_all_documents(tender_id, other_docs)
        for d in downloaded:
            icon = "[red]✗[/]" if d.get("error") else "[green]✓[/]"
            console.print(f"  {icon} {d['filename']} ({d.get('filesize','')})")

        with console.status(f"[cyan]Running AI analysis on {len(downloaded)} documents...[/]"):
            analysis = analyze_tender(
                tender_id=tender_id, tender_no=tender_no,
                title=title, downloaded_docs=downloaded,
                api_detail=detail_data,
            )

        upsert_analysis(client, tender_id, analysis.model_dump())
        console.print(f"[green]✓ Done — confidence: {analysis.confidence} | type: {analysis.tender_type}[/]")
        console.print(f"  Deadline: {analysis.key_dates.proposal_submission_deadline}")

        # Upload docs
        for d in downloaded:
            if d.get("local_path") and not d.get("error"):
                try:
                    path = Path(d["local_path"])
                    storage_path = upload_document(client, path, tender_id)
                    upsert_document_metadata(client, tender_id, {
                        "filename": d["filename"],
                        "description": d.get("description", ""),
                        "url": d["url"],
                        "filesize": d.get("filesize", ""),
                        "extension": d.get("extension", ""),
                        "supabase_path": storage_path,
                    })
                    console.print(f"  [green]↑[/] Uploaded {d['filename']}")
                except Exception as e:
                    console.print(f"  [yellow]Upload skipped {d['filename']}: {e}[/]")

    except Exception as e:
        console.print(f"[red]Analysis failed: {e}[/]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()[-500:]}[/]")


def _run_analyze_all(client, sorted_tenders: list, analyzed_ids: set):
    """Analyze all tenders not yet analyzed, with progress."""
    pending = [t for t in sorted_tenders if t["tender_id"] not in analyzed_ids]
    if not pending:
        console.print("[green]All tenders already analyzed.[/]")
        return

    console.print(f"\n[cyan]{len(pending)} tenders to analyze[/]")
    if not Confirm.ask(f"Analyze all {len(pending)}? (~{len(pending)*2} minutes)"):
        return

    for i, t in enumerate(pending, 1):
        console.print(f"\n[bold]({i}/{len(pending)})[/] {t['tender_id']} — {t.get('title','')[:60]}")
        _run_analyze(client, t["tender_id"], analyzed_ids, sorted_tenders)
        analyzed_ids.add(t["tender_id"])


def _normalize_tender(raw: dict) -> dict:
    """Normalize list API response to DB row (same as cli.py)."""
    from datetime import datetime, timezone
    return {
        "tender_id":          str(raw.get("id", "")),
        "tender_no":          raw.get("tender_no", ""),
        "title":              raw.get("title", ""),
        "publish_date":       raw.get("publish_date", ""),
        "submission_deadline": raw.get("bid_submission_end_date", ""),
        "bid_opening_date":   raw.get("bid_opening_date", ""),
        "source_url":         "https://nhai.gov.in/#/tenders",
        "status":             "active",
        "fetched_at":         datetime.now(timezone.utc).isoformat(),
        "raw_detail":         {},
    }


if __name__ == "__main__":
    main()
