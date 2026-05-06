#!/usr/bin/env python3
"""
NHAI Tender Intelligence CLI

Commands:
  fetch           Pull latest tender list from NHAI API → Supabase
  detail <id>     Fetch full detail for one tender (API fields only)
  analyze <id>    Download docs + run full AI analysis → Supabase
  analyze-all     Analyze all tenders not yet analyzed
  show <id>       Print analysis for a tender (formatted)
  list            List all tenders in Supabase
  docs <id>       List documents for a tender with download links
"""
import json
import logging
import sys
from datetime import datetime, timezone

import click
from rich.console import Console
from rich.table import Table
from rich import box
from rich.panel import Panel
from rich.text import Text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
log = logging.getLogger(__name__)
console = Console()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _normalize_tender(raw: dict, detail: dict = None) -> dict:
    """Flatten list API + detail API into one row for Supabase."""
    dates = {}
    if detail:
        imp = (detail.get("important_dates") or [{}])[0]
        dates = {
            "date_published":               imp.get("Date Published", ""),
            "bid_submission_start":         imp.get("Bid Submission Start Date", ""),
            "submission_deadline":          imp.get("Bid Submission End Date", ""),
            "bid_opening_date":             imp.get("Bid Opening Date Time", ""),
            "priced_bid_opening":           imp.get("Priced Bid Opening Date", ""),
            "pre_bid_meeting":              imp.get("Pre Bid Meeting Date", ""),
            "doc_sales_start":              imp.get("Tender Document Sales Start Date", ""),
            "doc_sales_end":                imp.get("Tender Document Sales End Date", ""),
        }
        basic = (detail.get("basic_information") or [{}])[0]
        dates.update({
            "tender_type":      basic.get("Tender Type", ""),
            "procurement_cat":  basic.get("Procurement Category", ""),
            "evaluation_type":  basic.get("Evaluation Type", ""),
            "application_fee":  basic.get("Application Fee", ""),
            "emd_value":        basic.get("EMD Value", ""),
        })

    return {
        "tender_id":         str(raw.get("id", "")),
        "tender_no":         raw.get("tender_no", ""),
        "title":             raw.get("title", ""),
        "publish_date":      raw.get("publish_date", ""),
        "submission_deadline": raw.get("bid_submission_end_date", ""),
        "bid_opening_date":  raw.get("bid_opening_date", ""),
        "source_url":        "https://nhai.gov.in/#/tenders",
        "status":            "active",
        "fetched_at":        datetime.now(timezone.utc).isoformat(),
        "raw_detail":        detail or {},
        **dates,
    }


# ── Commands ─────────────────────────────────────────────────────────────────

@click.group()
def cli():
    """NHAI Tender Intelligence System"""


@cli.command()
@click.option("--page-size", default=10000, help="Max tenders to fetch")
@click.option("--no-db", is_flag=True, help="Skip Supabase, just print count")
def fetch(page_size, no_db):
    """Fetch tender list from NHAI API and store in Supabase."""
    from api.nhai import fetch_tender_list

    console.print("[bold cyan]Fetching tender list from NHAI...[/]")
    tenders = fetch_tender_list(page_size=page_size)
    console.print(f"[green]Got {len(tenders)} tenders[/]")

    if no_db:
        console.print(json.dumps(tenders[:3], indent=2))
        return

    from db.supabase import get_client, upsert_tenders_bulk
    client = get_client()
    rows = [_normalize_tender(t) for t in tenders]
    upsert_tenders_bulk(client, rows)
    console.print(f"[green]✓ {len(rows)} tenders saved to Supabase[/]")


@cli.command()
@click.argument("tender_id")
def detail(tender_id):
    """Fetch full API detail for one tender and print it."""
    from api.nhai import fetch_tender_detail
    d = fetch_tender_detail(tender_id)
    console.print_json(json.dumps(d, indent=2))


@cli.command()
@click.argument("tender_id")
@click.option("--no-upload", is_flag=True, help="Skip uploading docs to Supabase Storage")
def analyze(tender_id, no_upload):
    """Download documents + run full AI analysis for one tender."""
    from api.nhai import fetch_tender_list, fetch_tender_detail
    from api.documents import download_all_documents
    from analysis.engine import analyze_tender
    from db.supabase import get_client, upsert_analysis, upload_document, upsert_document_metadata

    # Get tender info
    console.print(f"[cyan]Fetching detail for tender {tender_id}...[/]")
    detail_data = fetch_tender_detail(tender_id)

    # Get title/no from list (detail doesn't duplicate these)
    tenders = fetch_tender_list(page_size=10000)
    raw = next((t for t in tenders if str(t["id"]) == str(tender_id)), {})
    title = raw.get("title", detail_data.get("title", "Unknown"))
    tender_no = raw.get("tender_no", "")

    # Download documents
    other_docs = detail_data.get("other_documents", [])
    console.print(f"[cyan]Downloading {len(other_docs)} document(s)...[/]")
    downloaded = download_all_documents(tender_id, other_docs)

    for d in downloaded:
        status = f"[green]✓[/] {d['filename']} ({d['filesize']})"
        if d.get("error"):
            status = f"[red]✗[/] {d['filename']}: {d['error']}"
        console.print(f"  {status}")

    # Run AI analysis
    console.print("[cyan]Running AI analysis (this takes ~60-120s)...[/]")
    analysis = analyze_tender(
        tender_id=tender_id,
        tender_no=tender_no,
        title=title,
        downloaded_docs=downloaded,
        api_detail=detail_data,
    )

    analysis_dict = analysis.model_dump()
    console.print(f"[green]✓ Analysis complete — confidence: {analysis.confidence}[/]")
    console.print(f"  Tender type: {analysis.tender_type}")
    console.print(f"  Submission deadline: {analysis.key_dates.proposal_submission_deadline}")

    # Save to Supabase
    client = get_client()
    upsert_analysis(client, tender_id, analysis_dict)
    console.print("[green]✓ Analysis saved to Supabase[/]")

    # Upload documents to Supabase Storage
    if not no_upload:
        from pathlib import Path
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
                    console.print(f"  [red]Upload failed {d['filename']}: {e}[/]")


@cli.command(name="analyze-all")
@click.option("--limit", default=0, help="Max tenders to process (0 = all)")
@click.option("--skip-analyzed", is_flag=True, default=True,
              help="Skip tenders already analyzed")
def analyze_all(limit, skip_analyzed):
    """Analyze all tenders in Supabase that have not been analyzed yet."""
    from db.supabase import get_client, list_tenders, get_analysis
    import subprocess, sys

    client = get_client()
    tenders = list_tenders(client, status="active")
    console.print(f"[cyan]{len(tenders)} active tenders in DB[/]")

    to_process = []
    for t in tenders:
        if skip_analyzed and get_analysis(client, t["tender_id"]):
            continue
        to_process.append(t)
        if limit and len(to_process) >= limit:
            break

    console.print(f"[cyan]Processing {len(to_process)} tenders[/]")

    for i, t in enumerate(to_process, 1):
        tid = t["tender_id"]
        console.print(f"\n[bold]({i}/{len(to_process)}) Tender {tid}[/] — {t['title'][:70]}")
        try:
            # Run as subprocess so one failure doesn't kill the batch
            result = subprocess.run(
                [sys.executable, "cli.py", "analyze", tid],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                console.print(f"  [green]✓ Done[/]")
            else:
                console.print(f"  [red]✗ Failed:[/] {result.stderr[-200:]}")
        except subprocess.TimeoutExpired:
            console.print(f"  [red]✗ Timed out[/]")
        except Exception as e:
            console.print(f"  [red]✗ Error: {e}[/]")


@cli.command()
@click.argument("tender_id")
@click.option("--section", default=None,
              help="Show one section: dates|fees|eligibility|evaluation|scope|submission|contacts|risk")
@click.option("--json", "as_json", is_flag=True, help="Raw JSON output")
def show(tender_id, section, as_json):
    """Display analysis for a tender in formatted view."""
    from db.supabase import get_client, get_analysis

    client = get_client()
    analysis = get_analysis(client, tender_id)
    if not analysis:
        console.print(f"[red]No analysis found for tender {tender_id}[/]")
        sys.exit(1)

    if as_json:
        console.print_json(json.dumps(analysis, indent=2))
        return

    _print_analysis(analysis, section)


@cli.command(name="list")
@click.option("--status", default=None, help="Filter: active | closed")
@click.option("--analyzed", is_flag=True, help="Show only analyzed tenders")
def list_cmd(status, analyzed):
    """List all tenders."""
    from db.supabase import get_client, list_tenders, get_analysis

    client = get_client()
    tenders = list_tenders(client, status=status)

    table = Table(box=box.SIMPLE_HEAD, show_lines=False)
    table.add_column("ID", style="dim", width=8)
    table.add_column("Tender No", width=35)
    table.add_column("Title", width=50)
    table.add_column("Deadline", width=12)
    table.add_column("Analyzed", width=8)

    for t in tenders:
        has_analysis = bool(get_analysis(client, t["tender_id"]))
        if analyzed and not has_analysis:
            continue
        table.add_row(
            t["tender_id"],
            t.get("tender_no", "")[:35],
            t.get("title", "")[:50],
            (t.get("submission_deadline") or "")[:10],
            "[green]Yes[/]" if has_analysis else "[dim]No[/]",
        )

    console.print(table)


@cli.command()
@click.argument("tender_id")
def docs(tender_id):
    """List all documents for a tender with download links."""
    from db.supabase import get_client, get_document_url
    from supabase import create_client
    from config import SUPABASE_URL, SUPABASE_KEY

    client = get_client()
    rows = (client.table("tender_documents")
            .select("*")
            .eq("tender_id", tender_id)
            .execute().data or [])

    if not rows:
        console.print(f"[yellow]No documents found for tender {tender_id}[/]")
        return

    table = Table(title=f"Documents — Tender {tender_id}", box=box.ROUNDED)
    table.add_column("Filename", style="cyan")
    table.add_column("Description")
    table.add_column("Size")
    table.add_column("Public URL")

    for r in rows:
        url = get_document_url(client, r["supabase_path"]) if r.get("supabase_path") else r.get("url", "N/A")
        table.add_row(r["filename"], r.get("description", ""), r.get("filesize", ""), url)

    console.print(table)


# ── Pretty printer ───────────────────────────────────────────────────────────

def _val(v) -> str:
    if v is None or v == "N/A" or v == "":
        return "[dim]N/A[/]"
    return str(v)


def _src(citations: list) -> str:
    if not citations:
        return ""
    parts = [f"p.{c['page']}" for c in citations[:3]]
    return f" [dim]({', '.join(parts)})[/]"


def _print_analysis(a: dict, section: str = None):
    console.print(Panel(
        f"[bold]{a['title']}[/]\n"
        f"[dim]Tender No:[/] {a['tender_no']}  "
        f"[dim]Type:[/] {a.get('tender_type','?')}  "
        f"[dim]Confidence:[/] {a.get('confidence','?')}",
        title="NHAI Tender Analysis", border_style="blue"
    ))

    def show(s): return section is None or section.lower() in s.lower()

    if show("dates"):
        kd = a.get("key_dates", {})
        console.print("\n[bold yellow]KEY DATES[/]")
        for label, key in [
            ("Pre-bid Meeting",            "pre_bid_meeting"),
            ("Last Date for Clarification","last_date_clarification"),
            ("Submission Deadline",        "proposal_submission_deadline"),
            ("Technical Bid Opening",      "technical_bid_opening"),
            ("Financial Bid Opening",      "financial_bid_opening"),
            ("Bid Validity",               "bid_validity_period"),
            ("Doc Download Period",        "document_download_period"),
        ]:
            console.print(f"  {label:30s} {_val(kd.get(key))}{_src(kd.get(key+'_source',[]))}")

    if show("fees"):
        f = a.get("rfp_fees", {})
        console.print("\n[bold yellow]RFP FEES & PAYMENT[/]")
        console.print(f"  RFP Fee:             {_val(f.get('rfp_fee_amount'))}{_src(f.get('rfp_fee_source',[]))}")
        console.print(f"  Payment Mode:        {_val(f.get('payment_mode'))}")
        console.print(f"  EMD:                 {_val(f.get('emd_amount'))}{_src(f.get('emd_source',[]))}")
        console.print(f"  Performance Security:{_val(f.get('performance_security'))}{_src(f.get('performance_security_source',[]))}")
        bd = f.get("bank_details", {})
        if bd and bd.get("account_number") not in (None, "N/A", ""):
            console.print(f"  Bank: {bd.get('bank_name')} | A/C: {bd.get('account_number')} | IFSC: {bd.get('ifsc_code')}")

    if show("elig"):
        e = a.get("eligibility", {})
        t = e.get("technical", {})
        fi = e.get("financial", {})
        console.print("\n[bold yellow]ELIGIBILITY CRITERIA[/]")
        console.print("[cyan]  Technical:[/]")
        console.print(f"    Annual Turnover:     {_val(t.get('min_annual_turnover'))}{_src(t.get('min_annual_turnover_source',[]))}")
        console.print(f"    Similar Experience:  {_val(t.get('similar_project_experience'))}{_src(t.get('similar_project_experience_source',[]))}")
        console.print(f"    JV Conditions:       {_val(t.get('jv_conditions'))}{_src(t.get('jv_conditions_source',[]))}")
        console.print(f"    Assignment Cap:      {_val(t.get('ongoing_assignment_cap'))}{_src(t.get('ongoing_assignment_cap_source',[]))}")
        for p in (t.get("key_personnel_requirements") or []):
            console.print(f"    Personnel:           {p}")
        console.print("[cyan]  Financial:[/]")
        console.print(f"    Annual Turnover:     {_val(fi.get('min_annual_turnover'))}{_src(fi.get('min_annual_turnover_source',[]))}")
        console.print(f"    Net Worth:           {_val(fi.get('net_worth_requirement'))}{_src(fi.get('net_worth_requirement_source',[]))}")
        console.print(f"    Years Considered:    {_val(fi.get('financial_years_considered'))}{_src(fi.get('financial_years_considered_source',[]))}")

    if show("eval"):
        ev = a.get("evaluation", {})
        console.print("\n[bold yellow]EVALUATION & SELECTION CRITERIA[/]")
        console.print(f"  Method:              {_val(ev.get('selection_method'))}{_src(ev.get('selection_method_source',[]))}")
        console.print(f"  Technical Weightage: {_val(ev.get('technical_weightage'))}")
        console.print(f"  Financial Weightage: {_val(ev.get('financial_weightage'))}{_src(ev.get('weightage_source',[]))}")
        console.print(f"  Tech Min Score:      {_val(ev.get('technical_min_qualifying_score'))}{_src(ev.get('qualifying_score_source',[]))}")
        console.print(f"  Financial > Tech:    {'Yes' if ev.get('financial_higher_wins') else 'No'}")
        for c in (ev.get("technical_evaluation_criteria") or []):
            console.print(f"    {c.get('criterion','')}: {c.get('max_marks','')} marks")
        for pf in (ev.get("pass_fail_criteria") or []):
            console.print(f"    Pass/Fail: {pf}")

    if show("scope"):
        sc = a.get("scope", {})
        console.print("\n[bold yellow]SCOPE OF RFP[/]")
        console.print(f"  {_val(sc.get('summary'))}")
        console.print(f"  Location:            {_val(sc.get('project_location'))}{_src(sc.get('project_location_source',[]))}")
        console.print(f"  Contract Duration:   {_val(sc.get('contract_duration'))}{_src(sc.get('contract_duration_source',[]))}")
        if sc.get("in_scope"):
            console.print("[cyan]  In-Scope:[/]")
            for item in sc["in_scope"]:
                console.print(f"    • {item['description']}{_src(item.get('source',[]))}")
        if sc.get("out_of_scope"):
            console.print("[cyan]  Out-of-Scope / Client Provides:[/]")
            for item in sc["out_of_scope"]:
                console.print(f"    • {item['description']}{_src(item.get('source',[]))}")
        if sc.get("deliverables"):
            console.print("[cyan]  Deliverables:[/]")
            for d in sc["deliverables"]:
                console.print(f"    • {d['description']}{_src(d.get('source',[]))}")
        if sc.get("milestones"):
            console.print("[cyan]  Milestones:[/]")
            for m in sc["milestones"]:
                console.print(f"    • {m['name']} | {m['timeline']} | {m['deliverable']}{_src(m.get('source',[]))}")

    if show("sub"):
        sub = a.get("submission", {})
        console.print("\n[bold yellow]SUBMISSION MECHANISMS[/]")
        console.print(f"  Mode:   {_val(sub.get('submission_mode'))}{_src(sub.get('submission_mode_source',[]))}")
        console.print(f"  Portal: {_val(sub.get('portal'))}{_src(sub.get('portal_source',[]))}")
        console.print(f"  Language: {_val(sub.get('language'))}  Copies: {_val(sub.get('number_of_copies'))}")
        if sub.get("required_forms"):
            console.print("[cyan]  Required Forms:[/]")
            for f in sub["required_forms"]:
                sign = f"  [signed by: {f['signing_authority']}]" if f.get("signing_authority") not in (None, "N/A", "") else ""
                console.print(f"    • {f['form_name']}: {f.get('description','')}{sign}  [dim](p.{f.get('source_page',0)})[/]")
        if sub.get("annexures_required"):
            console.print("[cyan]  Annexures:[/]")
            for ann in sub["annexures_required"]:
                console.print(f"    • {ann}")

    if show("contact"):
        console.print("\n[bold yellow]CONTACT / SPOC[/]")
        for c in (a.get("contacts") or []):
            console.print(f"  [cyan]{c.get('name','?')}[/] — {c.get('designation','')} | {c.get('department','')}")
            console.print(f"    Address: {_val(c.get('address'))}")
            console.print(f"    Phone:   {_val(c.get('phone'))}  Email: {_val(c.get('email'))}")

    if show("pay"):
        console.print("\n[bold yellow]PAYMENT TERMS[/]")
        for p in (a.get("payment_terms") or []):
            console.print(f"  • {p.get('milestone')}: {_val(p.get('percentage'))} — {p.get('condition','')}{_src(p.get('source',[]))}")

    if show("risk"):
        r = a.get("risk", {})
        console.print("\n[bold yellow]RISK & REGULATORY[/]")
        console.print(f"  Liquidated Damages:  {_val(r.get('liquidated_damages'))}{_src(r.get('liquidated_damages_source',[]))}")
        console.print(f"  Force Majeure:       {_val(r.get('force_majeure'))}{_src(r.get('force_majeure_source',[]))}")
        console.print(f"  Dispute Resolution:  {_val(r.get('dispute_resolution'))}{_src(r.get('dispute_resolution_source',[]))}")
        console.print(f"  Integrity Pact:      {_val(r.get('integrity_pact'))}{_src(r.get('integrity_pact_source',[]))}")
        if r.get("penalty_clauses"):
            console.print("[cyan]  Penalty Clauses:[/]")
            for p in r["penalty_clauses"]:
                console.print(f"    • [{p.get('category','')}] {p.get('risk','')}{_src(p.get('source',[]))}")
        if r.get("termination_conditions"):
            console.print("[cyan]  Termination Conditions:[/]")
            for tc in r["termination_conditions"]:
                console.print(f"    • {tc}")
        if r.get("insurance_requirements"):
            console.print("[cyan]  Insurance:[/]")
            for ins in r["insurance_requirements"]:
                console.print(f"    • {ins}")

    if show("doc"):
        console.print("\n[bold yellow]DOCUMENTS & FORMS[/]")
        for d in (a.get("documents") or []):
            icon = "[red]✗[/]" if d.get("download_error") else "[green]✓[/]"
            console.print(f"  {icon} {d['filename']} ({d.get('filesize','?')}) — {d.get('description','')}")
            console.print(f"      URL: {d.get('url','')}")
            if d.get("supabase_path"):
                console.print(f"      Supabase: {d['supabase_path']}")


if __name__ == "__main__":
    cli()
