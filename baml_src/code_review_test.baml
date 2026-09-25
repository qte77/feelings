// Offline: no request is sent (no API key needed). Reuses the pattern in vibes_test.baml:
// generic calls are type-checked with @spec, and the state Jev receives is checked directly.

test "code_review sends the commit message and the diff as the state" {
    let change = Change { message: "Add retry to fetch", diff: "+    retry(fetch)" };
    assert.equal(state_of(change), `{"message":"Add retry to fetch","diff":"+    retry(fetch)"}`)
}

test "a Review is four questions in one fill<T>() request" {
    // Only type-checks the dispatch: Review's four float fields become four Jev questions.
    let spec = Matches<Review>@spec(state_of(Change { message: "m", diff: "d" }));
    assert.not_null(spec)
}
