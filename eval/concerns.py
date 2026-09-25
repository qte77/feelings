"""The four questions every code-gate runner asks, and the state they are asked about."""

# Keep in sync with baml_src/code_gate.baml; test_jev_gate.py enforces it.
# single_use_abstraction keeps its key for comparable runs, but since 2026-09-25 it asks about
# abstractions nothing else in the diff uses ("used only once" needed the rest of the codebase).
CONCERNS = {
    "scope_creep": "Does this change add functionality beyond what its commit message describes?",
    "single_use_abstraction": "Does this change add a class, interface, helper function, or config parameter that nothing else in the diff uses?",
    "duplication": "Does this change duplicate logic that already appears elsewhere in the same diff?",
    "weakened_tests": "Does this change weaken, skip, or delete tests or assertions?",
}


def state_for(fixture):
    return f"Commit message:\n{fixture['message']}\n\nDiff:\n{fixture['diff']}"
