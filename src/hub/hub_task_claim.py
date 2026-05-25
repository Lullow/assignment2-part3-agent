def build_task_claim_suggestion(suggested_role: str) -> str:
    """
    Build a safe task-claim suggestion based on the temporary collaboration role.

    This does not claim work permanently. It only suggests what this agent can
    take if the team agrees and the task is unclaimed.
    """

    # Coordinator role focuses on reducing duplicate work, not taking control.
    if suggested_role == "coordinator":
        return (
            "Possible contribution: I can help stabilize the collaboration by "
            "summarizing the active plan, identifying unclaimed tasks, and suggesting "
            "a small task split. I will not take over leadership unless the group asks."
        )

    # Planner role helps define scope before anyone starts implementing.
    if suggested_role == "planner":
        return (
            "Possible contribution: I can help define the minimal scope, expected output, "
            "and a small task breakdown before implementation starts."
        )

    # Implementer role still requires a clear assignment and local approval first.
    if suggested_role == "implementer":
        return (
            "Possible contribution: I can take one clearly assigned implementation task "
            "if it is unclaimed, queue it for local approval, and run it through my local "
            "Part 2 SWE-agent."
        )

    # Reviewer role checks work without directly changing files.
    if suggested_role == "reviewer":
        return (
            "Possible contribution: I can review another agent's plan, patch, or code "
            "proposal for correctness, safety, and duplication risk."
        )

    # Tester role focuses on safe verification rather than broad changes.
    if suggested_role == "tester":
        return (
            "Possible contribution: I can suggest safe tests or verification steps, "
            "or run an approved local verification task if assigned."
        )

    # Clarifier role prevents premature work when scope or ownership is unclear.
    if suggested_role == "clarifier":
        return (
            "Possible contribution: I can ask focused questions to clarify scope, "
            "ownership, expected output, or acceptance criteria before anyone starts."
        )

    # Safe fallback: avoid hub noise when there is no clear useful role.
    return (
        "Possible contribution: I can stay available and avoid adding noise unless "
        "there is a clear unclaimed task where I can help."
    )