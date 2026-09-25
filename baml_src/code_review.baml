// code_review.baml — a fast check on a code change, before the slow ones.
//   git diff HEAD~1 | baml run code_review -- --message "$(git log -1 --format=%B)"
//
// One .fill<T>() call: every field is a question, all answered in one Jev request.
// Each question asks about what is *in* the change (message + diff), not the rest of
// the codebase; that wording is what made them reliable (see the README).

class Change {
    message: string,
    diff: string,
}

class Review {
    scope_creep: float @description(
        "Does this change add functionality beyond what its commit message describes?",
    ),
    unused_abstraction: float @description(
        "Does this change add a class, interface, helper function, or config parameter that nothing else in the diff uses?",
    ),
    duplication: float @description(
        "Does this change duplicate logic that already appears elsewhere in the same diff?",
    ),
    weakened_tests: float @description("Does this change weaken, skip, or delete tests or assertions?"),
}

function code_review(message: string) -> void {
    let change = Change { message: message, diff: read_stdin_lines().join("\n") };
    let review = change.fill<Review>();
    baml.io.println(baml.json.to_string(review));
    //# Flag the change if any concern is likely; tune the threshold on your own history
    if (
        review.scope_creep >= 0.7
            || review.unused_abstraction >= 0.7
            || review.duplication >= 0.7
            || review.weakened_tests >= 0.7
    ) {
        baml.io.println("worth a closer look before merging");
    }
}
