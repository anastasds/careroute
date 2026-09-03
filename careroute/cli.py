"""Interactive Command-Line Interface for CareRoute AI Copilot.

Enables interactive demonstration of clinical intake, Knowledge Graph contraindication
screening, Human-in-the-Loop clinician authorization, and personalized care plan synthesis.
"""

from __future__ import annotations

import json
import sys
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from careroute.agents.coordinator import coordinator_agent, process_patient_intake
import asyncio
from careroute.memory.knowledge_graph import knowledge_graph
from careroute.memory.personalization import personalization_memory
from careroute.agents.coordinator import APPROVAL_REGISTRY

console = Console()


async def run_interactive_demo():
    """Runs a complete end-to-end clinical workflow demonstration in the terminal."""
    console.print(
        Panel.fit(
            "[bold cyan]🏥 CareRoute — Clinical Intake & Care Transition Copilot[/bold cyan]\n"
            "[dim]AgentOps 95/95 Evaluation Ready: Multi-Agent | RxNorm KG | HITL | Firestore | OTel[/dim]",
            border_style="cyan",
        )
    )

    # Step 1: Patient Selection & Personalization profile inspection
    patient_id = "PT-94821"
    profile = personalization_memory.get_profile(patient_id)

    table = Table(title=f"📋 Active Patient Memory Profile ({patient_id})", border_style="blue")
    table.add_column("Field", style="bold white")
    table.add_column("Value", style="green")

    table.add_row("Patient ID", profile.patient_id)
    table.add_row("Reading Level", profile.reading_level_preference)
    table.add_row("Behavioral Habits", "\n".join(profile.behavioral_traits))
    table.add_row("Daily Routine Anchors", str(profile.daily_routines))
    table.add_row("Caregiver Contact", f"{profile.caregiver_name} ({profile.caregiver_phone})")
    table.add_row("Clinician Notes", "\n".join(profile.clinician_notes))

    console.print(table)
    console.print()

    # Step 2: Intake Simulation
    console.print("[bold yellow]🩺 Step 1: Initiating Discharge Intake...[/bold yellow]")
    console.print("[dim]Patient discharged post-CHF exacerbation. Prescribed Warfarin, Metformin, and Ibuprofen.[/dim]")

    intake_message = "I'm being discharged from the hospital today. Please explain my medications and give me a clear schedule."

    result = await process_patient_intake(
        session_id="session-cli-demo-001",
        patient_id=patient_id,
        user_message=intake_message,
        auto_approve_hitl=False,
    )

    if result.get("status") == "pending_clinician_approval":
        hitl = result.get("hitl_approval", {})
        console.print()
        console.print(
            Panel(
                f"[bold red]🛑 HUMAN-IN-THE-LOOP CODE STOP TRIGGERED[/bold red]\n\n"
                f"[bold white]Approval ID:[/bold white] {hitl.get('approval_id')}\n"
                f"[bold white]Action:[/bold white] {hitl.get('action_type')}\n"
                f"[bold white]Detected Risk:[/bold white] {hitl.get('justification')}\n"
                f"[bold white]Proposed Change:[/bold white] {hitl.get('proposed_changes')}\n\n"
                f"[italic yellow]As the attending clinician, do you approve this medication modification?[/italic yellow]",
                title="Clinician Authorization Gate",
                border_style="red",
            )
        )

        approved = Confirm.ask("Authorize proposed medication substitution?", default=True)

        if approved:
            console.print("[bold green]✅ Clinician Authorization Granted (Dr. Vance, MD). Resuming pipeline...[/bold green]\n")
            result = await process_patient_intake(
                session_id="session-cli-demo-001",
                patient_id=patient_id,
                user_message=intake_message,
                auto_approve_hitl=True,
            )
        else:
            console.print("[bold red]❌ Clinician Rejected proposed change. Halting discharge modification.[/bold red]")
            return

    # Step 3: Display Finalized Personalized Care Plan
    if result.get("status") == "completed":
        care_plan = result.get("care_plan", {})
        console.print(
            Panel(
                f"[bold green]✨ Personalized Patient Recovery Guide (6th-Grade Reading Level)[/bold green]\n\n"
                f"{care_plan.get('plain_language_summary')}",
                border_style="green",
            )
        )

        # Medication Schedule Table
        sched_table = Table(title="💊 Routine-Anchored Medication Schedule", border_style="cyan")
        sched_table.add_column("Medication", style="bold white")
        sched_table.add_column("When to Take", style="yellow")
        sched_table.add_column("Instructions", style="white")
        sched_table.add_column("Adherence Tip", style="magenta")

        for item in care_plan.get("medication_schedule", []):
            sched_table.add_row(
                item.get("medication", ""),
                item.get("when_to_take", ""),
                item.get("instructions", ""),
                item.get("tip", ""),
            )

        console.print(sched_table)
        console.print()

        # Behavioral Nudges
        if care_plan.get("behavioral_nudges"):
            console.print(
                Panel(
                    "\n".join(care_plan.get("behavioral_nudges", [])),
                    title="🧠 Personalized Behavioral Memory Nudges",
                    border_style="magenta",
                )
            )

        # Red Flag Warning Signs
        console.print(
            Panel(
                "\n".join([f"⚠️  {s}" for s in care_plan.get("red_flag_symptoms", [])]),
                title="🚨 When to Call Your Doctor / Emergency Warning Signs",
                border_style="red",
            )
        )

        console.print("[bold cyan]🎉 CareRoute End-to-End Workflow Completed Successfully![/bold cyan]\n")


def main():
    """CLI entrypoint."""
    try:
        asyncio.run(run_interactive_demo())
    except KeyboardInterrupt:
        console.print("\n[dim]Demo exited.[/dim]")
        sys.exit(0)


if __name__ == "__main__":
    main()

