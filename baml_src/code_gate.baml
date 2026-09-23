// code_gate.baml — BAML half of the Jev code-gate comparison
// (docs/plans/2026-09-23-0001-jev-coding-gate-pilot.md).
//   baml run eval_gate < eval/fixtures.jsonl > eval/run-baml.jsonl
// The questions must match eval/jev_gate.py; eval/test_jev_gate.py enforces it.

// Pinned, unlike the shared `Jev` client: thresholds get tuned against this version.
client JevPinned = typesafeai.Client.new(model = "jev-1.13.0", api_key = env.TYPESAFE_API_KEY);

/// "Yes" always means a problem. Each float field is one Noul; its value is the probability.
class Concerns {
    scope_creep: float @description("Does this change add functionality beyond what its commit message describes?"),
    single_use_abstraction: float @description("Does this change introduce an abstraction (class, interface, helper function, or config parameter) that is used only once?"),
    duplication: float @description("Does this change duplicate logic that already appears elsewhere in the same diff?"),
    weakened_tests: float @description("Does this change weaken, skip, or delete tests or assertions?"),
}

class Fixture {
    id: string,
    message: string,
    diff: string,
}

class Sample {
    runner: string,
    id: string,
    sample: int,
    concerns: Concerns,
}

// No instructions: each field's @description is its question, the prompt is the state.
function CheckDiff(state: string) -> Concerns {
    client: JevPinned
    prompt: `${state}`
}

function state_for(f: Fixture) -> string {
    `Commit message:\n${f.message}\n\nDiff:\n${f.diff}`
}

function eval_gate(k: int = 5) -> void {
    //# One fixture per stdin line (JSONL)
    for (let line in read_stdin_lines()) {
        let f = baml.json.from_string<Fixture>(line);
        let state = state_for(f);
        //# k repeats, one at a time so the Python runner's per-request timings stay comparable
        let i = 0;
        while (i < k) {
            let rec = Sample { runner: "baml", id: f.id, sample: i, concerns: CheckDiff(state) };
            baml.io.println(baml.json.to_string(rec));
            i += 1;
        }
    }
}
