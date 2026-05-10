"""
SCRAPING REVIEW APP IN PLAY STORE
================================
Instalasi dependency:
  pip install google-play-scraper pandas openpyxl rich questionary
"""

import time
import sys
import copy
from datetime import date, datetime

import questionary
import pandas as pd
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text
from rich.rule import Rule
from rich.columns import Columns
from rich.prompt import Confirm
from google_play_scraper import reviews as gplay_reviews

console = Console()

# ─── Default config ───────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    'app_id':          'com.indomaret.klikindomaret',
    'start_date':      '2026-01-01',
    'target_version':  None,
    'total_batch':     20,
    'review_per_batch': 200,
}

DEFAULT_KEYWORDS = {
    'Keterlambatan': ['telat', 'terlambat', 'lama', 'belum sampai', 'pengiriman'],
    'Kurir':         ['kurir', 'driver'],
    'Refund':        ['refund', 'pengembalian', 'dana kembali'],
    'Aplikasi Error':['error', 'crash', 'force close', 'bug', 'login gagal'],
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

def stars(score: int) -> Text:
    t = Text()
    t.append("★" * score,       style="bold yellow")
    t.append("☆" * (5 - score), style="dim")
    return t

def tema_color(tema: str) -> str:
    return {
        'Keterlambatan': 'steel_blue1',
        'Kurir':         'green3',
        'Refund':        'orange3',
        'Aplikasi Error':'red1',
    }.get(tema, 'white')

def bar(value: int, total: int, width: int = 20) -> str:
    filled = round((value / total) * width) if total else 0
    return "█" * filled + "░" * (width - filled)

# ─── Screens ──────────────────────────────────────────────────────────────────

def print_header():
    console.clear()
    title = Text()
    title.append("🛒  Google", style="bold white")
    title.append("Play App", style="bold red")
    title.append("  Review Scraper", style="bold white")
    console.print(Panel(title, subtitle="[dim]Google Play Store · Analisis Sentimen & Tema[/dim]",
                        border_style="red", padding=(0, 2)))
    console.print()

def show_main_menu() -> str:
    print_header()
    return questionary.select(
        "Pilih menu:",
        choices=[
            questionary.Choice("▶   Mulai Scraping",             value="run"),
            questionary.Choice("⚙   Konfigurasi Scraping",       value="config"),
            questionary.Choice("🏷   Edit Kata Kunci Klasifikasi", value="keywords"),
            questionary.Choice("❌  Keluar",                      value="exit"),
        ],
        style=questionary.Style([
            ('selected',        'fg:red bold'),
            ('pointer',         'fg:red bold'),
            ('highlighted',     'fg:red bold'),
            ('answer',          'fg:red bold'),
        ])
    ).ask()

# ─── Config editor ────────────────────────────────────────────────────────────

def edit_config(cfg: dict) -> dict:
    cfg = copy.deepcopy(cfg)
    print_header()
    console.print(Rule("[bold red]Konfigurasi Scraping[/bold red]"))
    console.print()

    cfg['app_id'] = questionary.text(
        "App ID Google Play:",
        default=cfg['app_id']
    ).ask() or cfg['app_id']

    cfg['start_date'] = questionary.text(
        "Mulai tanggal (YYYY-MM-DD):",
        default=cfg['start_date'],
        validate=lambda v: True if _valid_date(v) else "Format harus YYYY-MM-DD"
    ).ask() or cfg['start_date']

    ver = questionary.text(
        "Filter versi aplikasi (kosongkan = semua):",
        default=cfg['target_version'] or ""
    ).ask()
    cfg['target_version'] = ver.strip() or None

    cfg['total_batch'] = int(questionary.text(
        "Jumlah batch:",
        default=str(cfg['total_batch']),
        validate=lambda v: v.isdigit() and int(v) > 0 or "Harus angka positif"
    ).ask())

    cfg['review_per_batch'] = int(questionary.text(
        "Review per batch:",
        default=str(cfg['review_per_batch']),
        validate=lambda v: v.isdigit() and int(v) > 0 or "Harus angka positif"
    ).ask())

    # Preview
    console.print()
    t = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    t.add_column(style="dim")
    t.add_column(style="bold white")
    t.add_row("App ID",        cfg['app_id'])
    t.add_row("Mulai tanggal", cfg['start_date'])
    t.add_row("Filter versi",  cfg['target_version'] or "[dim]semua[/dim]")
    t.add_row("Total batch",   str(cfg['total_batch']))
    t.add_row("Per batch",     str(cfg['review_per_batch']))
    console.print(Panel(t, title="[bold]Konfirmasi Konfigurasi[/bold]", border_style="dim"))

    if Confirm.ask("Simpan perubahan?", default=True):
        console.print("[green]✓ Konfigurasi disimpan.[/green]")
    else:
        console.print("[dim]Dibatalkan, konfigurasi tidak berubah.[/dim]")
        return DEFAULT_CONFIG  # rollback
    time.sleep(0.8)
    return cfg

def _valid_date(s: str) -> bool:
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except ValueError:
        return False

# ─── Keyword editor ───────────────────────────────────────────────────────────

def edit_keywords(kw: dict) -> dict:
    kw = copy.deepcopy(kw)
    while True:
        print_header()
        console.print(Rule("[bold red]Edit Kata Kunci Klasifikasi[/bold red]"))
        console.print()

        # Tampilkan semua kategori + tag
        for kat, tags in kw.items():
            color = tema_color(kat)
            tag_str = "  ".join(f"[{color}]{t}[/{color}]" for t in tags) or "[dim](kosong)[/dim]"
            console.print(f"  [bold]{kat}[/bold]")
            console.print(f"    {tag_str}")
            console.print()

        action = questionary.select(
            "Aksi:",
            choices=[
                questionary.Choice("➕  Tambah kata kunci", value="add"),
                questionary.Choice("➖  Hapus kata kunci",  value="remove"),
                questionary.Choice("↩   Kembali",           value="back"),
            ],
            style=questionary.Style([('selected', 'fg:red bold'), ('pointer', 'fg:red bold')])
        ).ask()

        if action == "back":
            break

        kat = questionary.select(
            "Pilih kategori:",
            choices=list(kw.keys()),
            style=questionary.Style([('selected', 'fg:red bold'), ('pointer', 'fg:red bold')])
        ).ask()

        if action == "add":
            new_tag = questionary.text(f"Kata kunci baru untuk '{kat}':").ask()
            if new_tag and new_tag.strip():
                tag = new_tag.strip().lower()
                if tag not in kw[kat]:
                    kw[kat].append(tag)
                    console.print(f"[green]✓ '{tag}' ditambahkan ke {kat}.[/green]")
                else:
                    console.print(f"[yellow]⚠ '{tag}' sudah ada.[/yellow]")
                time.sleep(0.6)

        elif action == "remove":
            if not kw[kat]:
                console.print("[yellow]Kategori ini kosong.[/yellow]")
                time.sleep(0.6)
                continue
            tag = questionary.select(
                "Pilih kata kunci yang dihapus:",
                choices=kw[kat],
                style=questionary.Style([('selected', 'fg:red bold'), ('pointer', 'fg:red bold')])
            ).ask()
            kw[kat].remove(tag)
            console.print(f"[red]✓ '{tag}' dihapus dari {kat}.[/red]")
            time.sleep(0.6)

    return kw

# ─── Scraping ─────────────────────────────────────────────────────────────────

def run_scraping(cfg: dict, kw: dict):
    print_header()
    console.print(Rule("[bold red]Memulai Scraping[/bold red]"))
    console.print()

    start_date = datetime.strptime(cfg['start_date'], "%Y-%m-%d").date()
    all_reviews = []
    token = None
    user_counter = 1
    stopped_early = False

    with Progress(
        SpinnerColumn(style="red"),
        TextColumn("[bold white]{task.description}"),
        BarColumn(bar_width=30, style="red", complete_style="bold red"),
        TextColumn("[dim]{task.completed}/{task.total} batch[/dim]"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("Scraping...", total=cfg['total_batch'])

        for i in range(cfg['total_batch']):
            progress.update(task, description=f"Batch {i+1}/{cfg['total_batch']} — {len(all_reviews)} review terkumpul")

            try:
                result, token = gplay_reviews(
                    cfg['app_id'],
                    lang='id',
                    country='id',
                    count=cfg['review_per_batch'],
                    continuation_token=token
                )
            except Exception as e:
                console.print(f"  [red][ERROR][/red] Batch {i+1} gagal: {e}")
                time.sleep(5)
                progress.advance(task)
                continue

            if not result:
                console.print("  [yellow]Tidak ada review lagi, scraping dihentikan lebih awal.[/yellow]")
                stopped_early = True
                break

            batch_added = 0
            for r in result:
                review_text = r['content'].lower()

                if r['at'].date() < start_date:
                    continue

                if cfg['target_version'] and r.get('reviewCreatedVersion') != cfg['target_version']:
                    continue

                tema = next(
                    (kat for kat, tags in kw.items() if any(t in review_text for t in tags)),
                    None
                )
                if not tema:
                    continue

                all_reviews.append({
                    'anonymous_user': f'USER_{user_counter:04d}',
                    'review':         r['content'],
                    'score':          r['score'],
                    'date':           r['at'].date(),
                    'app_version':    r.get('reviewCreatedVersion'),
                    'likes':          r['thumbsUpCount'],
                    'tema':           tema,
                })
                user_counter += 1
                batch_added += 1

            if token is None:
                stopped_early = True
                progress.advance(task)
                break

            progress.advance(task)
            time.sleep(2)

    console.print()

    # ── Validasi ──────────────────────────────────────────────────────────────
    if not all_reviews:
        console.print(Panel("[bold red]Tidak ada review yang berhasil dikumpulkan.[/bold red]\n"
                            "Coba periksa App ID atau koneksi internet.",
                            border_style="red"))
        questionary.press_any_key_to_continue().ask()
        return

    # ── DataFrame & dedup ─────────────────────────────────────────────────────
    df = pd.DataFrame(all_reviews)
    before = len(df)
    df = df.drop_duplicates(subset=['review'])
    dupes = before - len(df)

    # ── Statistik ─────────────────────────────────────────────────────────────
    show_results(df, dupes, stopped_early, cfg)

    # ── Export ────────────────────────────────────────────────────────────────
    export_excel(df)

    questionary.press_any_key_to_continue().ask()

# ─── Tampilan hasil ───────────────────────────────────────────────────────────

def show_results(df: pd.DataFrame, dupes: int, stopped_early: bool, cfg: dict):
    console.print(Rule("[bold red]Hasil Scraping[/bold red]"))
    console.print()

    # ── Kartu ringkasan ───────────────────────────────────────────────────────
    avg_score = df['score'].mean()
    total     = len(df)
    top_tema  = df['tema'].value_counts().idxmax()

    cards = [
        Panel(f"[bold red]{total}[/bold red]\n[dim]review bersih[/dim]",        border_style="dim", padding=(0, 3)),
        Panel(f"[bold yellow]{avg_score:.2f} ★[/bold yellow]\n[dim]rata-rata bintang[/dim]", border_style="dim", padding=(0, 3)),
        Panel(f"[bold white]{top_tema}[/bold white]\n[dim]tema dominan[/dim]",   border_style="dim", padding=(0, 3)),
        Panel(f"[bold]{dupes}[/bold]\n[dim]duplikat dihapus[/dim]",              border_style="dim", padding=(0, 3)),
    ]
    console.print(Columns(cards, equal=True))
    console.print()

    # ── Distribusi tema ───────────────────────────────────────────────────────
    tema_stats = df.groupby('tema').agg(
        jumlah=('tema', 'count'),
        rata_bintang=('score', 'mean')
    ).sort_values('jumlah', ascending=False)

    max_count = tema_stats['jumlah'].max()

    console.print("[bold]Distribusi Tema[/bold]")
    console.print()
    for tema, row in tema_stats.iterrows():
        color   = tema_color(tema)
        pct     = row['jumlah'] / total * 100
        b       = bar(row['jumlah'], max_count, 22)
        console.print(
            f"  [{color}]{tema:<18}[/{color}]"
            f"  [bold]{b}[/bold]"
            f"  [bold white]{row['jumlah']:>4}[/bold white] review"
            f"  [dim]({pct:.0f}%)[/dim]"
            f"  [yellow]★ {row['rata_bintang']:.1f}[/yellow]"
        )
    console.print()

    # ── Preview 5 review terbaru ──────────────────────────────────────────────
    console.print("[bold]Preview Review Terbaru[/bold]")
    console.print()

    t = Table(box=box.SIMPLE_HEAD, show_edge=False, padding=(0, 1), expand=True)
    t.add_column("ID",       style="dim",        no_wrap=True, width=10)
    t.add_column("Tema",                          no_wrap=True, width=16)
    t.add_column("★",                             no_wrap=True, width=7)
    t.add_column("Tanggal",  style="dim",         no_wrap=True, width=12)
    t.add_column("Review",                        ratio=1)

    for _, r in df.sort_values('date', ascending=False).head(5).iterrows():
        color = tema_color(r['tema'])
        t.add_row(
            r['anonymous_user'],
            f"[{color}]{r['tema']}[/{color}]",
            stars(r['score']),
            str(r['date']),
            r['review'][:120] + ("…" if len(r['review']) > 120 else ""),
        )

    console.print(t)
    console.print()

def export_excel(df: pd.DataFrame):
    output_file = 'hasil_penelitian_klik_indomaret.xlsx'

    stats      = df['tema'].value_counts()
    avg_score  = df.groupby('tema')['score'].mean().round(2)
    summary    = pd.DataFrame({'jumlah': stats, 'rata_rata_bintang': avg_score})

    try:
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            df.to_excel(writer,      sheet_name='Review',    index=False)
            summary.to_excel(writer, sheet_name='Statistik')

        console.print(Panel(
            f"[bold green]✓ File berhasil disimpan![/bold green]\n\n"
            f"  [dim]Lokasi :[/dim] [bold white]{output_file}[/bold white]\n"
            f"  [dim]Sheet   :[/dim] Review, Statistik\n"
            f"  [dim]Total   :[/dim] {len(df)} baris",
            border_style="green", padding=(0, 2)
        ))
    except Exception as e:
        console.print(Panel(f"[bold red][ERROR] Gagal menyimpan file:[/bold red]\n{e}", border_style="red"))

# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    kw  = copy.deepcopy(DEFAULT_KEYWORDS)

    while True:
        action = show_main_menu()

        if action == "exit" or action is None:
            console.print("\n[dim]Sampai jumpa! 👋[/dim]\n")
            sys.exit(0)

        elif action == "config":
            cfg = edit_config(cfg)

        elif action == "keywords":
            kw = edit_keywords(kw)

        elif action == "run":
            run_scraping(cfg, kw)

if __name__ == "__main__":
    main()
