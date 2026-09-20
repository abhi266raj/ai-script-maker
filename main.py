"""CLI runner for Hindi Short Reel Generation with 4-Step Verification."""

import sys
import argparse
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from workflow import reel_workflow
from core.fm_engine import fm_engine

console = Console()


def run_cli(news: str, scenario: str, batch: int = 10, target_sec: int = 30):
    console.print(
        Panel(
            f"[bold magenta]Hindi Reel Generator[/bold magenta] — Powered by [bold cyan]Apple Foundation Models (`fm`)[/bold cyan]\n"
            f"[dim]News: {news}\nScenario: {scenario}\nTarget Duration: {target_sec}s | Batch: {batch} Scripts (Multiple of 10)[/dim]",
            title="🎬 Reel Creator Studio",
            border_style="magenta",
        )
    )

    available, msg = fm_engine.is_available()
    if not available:
        console.print(f"[bold red]Error:[/bold red] Apple Foundation Model not ready: {msg}")
        sys.exit(1)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Initializing verification & script pipeline...", total=None)

        pipeline = reel_workflow.run_stream(
            news_input=news,
            scenario=scenario,
            batch_size=batch,
            target_seconds=target_sec,
        )

        batch_result = None
        for step in pipeline:
            progress.update(
                task,
                description=f"{step['icon']} [bold]{step['agent']}[/bold]: {step['status']}",
            )
            if step.get("completed"):
                batch_result = step["data"]["batch_result"]

    if batch_result:
        # Step 1 Summary
        console.print("\n")
        console.print(
            Panel(
                f"[bold]Step 1: News Verification (Antigravity Check)[/bold]\n"
                f"Confidence Score: [bold green]{batch_result.verification.confidence_score}%[/bold green]\n"
                f"Summary: {batch_result.verification.verification_summary}\n\n"
                f"[dim]Verified Facts:[/dim]\n" + "\n".join([f"  • {f}" for f in batch_result.verification.verified_facts]),
                title="🔍 Step 1: Verification",
                border_style="green",
            )
        )

        # Multiple of 10 Scripts Summary Table
        table = Table(title=f"🎬 Generated Hindi Reel Scripts ({len(batch_result.scripts)} Variations)")
        table.add_column("#", style="dim", width=4)
        table.add_column("Angle", style="cyan", width=24)
        table.add_column("Hook (0-3s)", style="bold yellow", width=30)
        table.add_column("Words", style="blue", width=10)
        table.add_column("Duration", style="purple", width=12)
        table.add_column("Timeline Fit", style="green", width=16)

        for s in batch_result.scripts:
            table.add_row(
                str(s.id),
                s.angle.split("(")[0],
                s.hook_hindi[:30] + "...",
                f"{s.word_count} w",
                f"{s.estimated_duration_sec}s",
                s.timeline_fit_status,
            )

        console.print(table)

        # Print detailed first script as example
        first = batch_result.scripts[0]
        console.print(
            Panel(
                f"[bold red]🔥 HOOK (0-3s):[/bold red] {first.hook_hindi}\n\n"
                f"[bold cyan]📜 HINDI NARRATION:[/bold cyan]\n{first.narration_hindi}\n\n"
                f"[bold green]📣 CALL TO ACTION:[/bold green] {first.call_to_action}\n\n"
                f"[dim]Word Count: {first.word_count} ({first.word_count_status}) | Est Duration: {first.estimated_duration_sec}s (Target: {first.target_duration_sec}s)[/dim]",
                title=f"Sample: {first.title}",
                border_style="blue",
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Hindi Short Reel Script Studio with 4-Step Verification")
    parser.add_argument("news", nargs="?", default="ISRO announces next lunar mission with international collaboration", help="News story or headline")
    parser.add_argument("--scenario", default="Youth and tech-enthusiast audience, high-energy dramatic revelation", help="Scenario/context/angle")
    parser.add_argument("--batch", type=int, default=10, help="Output count in multiple of 10 (10, 20, 30)")
    parser.add_argument("--duration", type=int, default=30, help="Target reel duration in seconds (15, 30, 60)")

    args = parser.parse_args()
    run_cli(args.news, scenario=args.scenario, batch=args.batch, target_sec=args.duration)
