"""The four questions every code-gate runner asks, and the state they are asked about."""

# Keep in sync with baml_src/code_gate.baml; test_jev_gate.py enforces it.
CONCERNS = {
    "scope_creep": "Does this change add functionality beyond what its commit message describes?",
    "single_use_abstraction": "Does this change introduce an abstraction (class, interface, helper function, or config parameter) that is used only once?",
    "duplication": "Does this change duplicate logic that already appears elsewhere in the same diff?",
    "weakened_tests": "Does this change weaken, skip, or delete tests or assertions?",
}


def state_for(fixture):
    return f"Commit message:\n{fixture['message']}\n\nDiff:\n{fixture['diff']}"
