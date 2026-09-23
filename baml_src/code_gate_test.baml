// Offline tests for code_gate.baml: build the Jev request without sending it.

test "check_diff sends four noul questions to the pinned model" {
    let req = CheckDiff@build_request("Commit message:\nm\n\nDiff:\n+d");
    assert.equal(req.url, "https://api.typesafe.ai/v1/systemone");
    assert.contains(req.body ?? "", "\"model\":\"jev-1.13.0\"");
    let q = questions(req);
    assert.equal(q.keys().length(), 4);
    assert.contains(baml.json.to_string(q.get("weakened_tests")), "\"type\":\"noul\"");
    assert.contains(baml.json.to_string(q.get("weakened_tests")), "weaken, skip, or delete tests")
}

test "state_for puts the message before the diff, same as the Python runner" {
    assert.equal(
        state_for(Fixture { id: "a", message: "m", diff: "+d" }),
        "Commit message:\nm\n\nDiff:\n+d",
    )
}
