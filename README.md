# feelings

**`.feels()` on anything.** A programming language for LLM workflows where the
"AI if statement" is a real, typed method — powered by [TypeSafe AI's Jev](https://docs.typesafe.ai/api)
and [BAML](https://boundaryml.com).

```baml
let email = baml.io.input("email: ");

if (email.feels("urgent")) {
    baml.io.println(email.ask("Draft a reply"));
}
```

This started as a reply to [@southpolesteve's Probably](https://probably-lang.southpolesteve.workers.dev/),
a toy language with `feels` baked in. The point of this repo: you don't need a new
language. `feels` is ~20 lines of BAML — an interface with a blanket implementation —
and because it's a real language, you get types, generics, loops, concurrency, tests,
and everything else for free.

> Jev makes the decisions, an LLM does the writing, and BAML ties it together.

## Try it

```sh
git clone https://github.com/boundaryml/feelings && cd feelings
baml toolchain use nightly && baml toolchain update   # latest nightly

cp .env.example .env             # TYPESAFE_API_KEY (Jev) + ANTHROPIC_API_KEY (for .ask)
set -a; source .env; set +a

echo "prod is down and customers can't log in" | baml run urgent
baml run inbox -- --email "any chance you have 30 min next week to chat?"
baml run demo                    # enums, literal unions, class fan-out, ints…
git log --format=%s | baml run grep_with_vibes -- --feeling "scary to revert"
git diff HEAD~1 | baml run code_review -- --message "$(git log -1 --format=%B)"
baml test                        # offline — inspects the Jev requests, no key needed
```

## The language, in a few minutes

Everything below is ordinary BAML. The only thing this repo adds is
[`baml_src/vibes.baml`](baml_src/vibes.baml).

### 1. Make a judgment with `.feels()`

`feels` compares any value with a quoted description and returns a `bool`
(Jev's probability, thresholded at 0.5).

```baml
if (message.feels("genuinely urgent")) {
    log.info("Drop everything.");
}
```

### 2. Keep the confidence with `.how()`

Same question, but you get the probability and pick the threshold yourself —
so "otherwise maybe" is just an `else if`.

```baml
let urgency = message.how("genuinely urgent");
if (urgency >= 0.8)      { log.info("Drop everything.") }
else if (urgency >= 0.5) { log.info("Ask a follow-up question.") }
else                     { log.info("It can wait.") }
```

### 3. Route between descriptions with `.matches<T>()` + `match`

`T` must be a finite set of choices: an enum, a literal union, or a union of
those (`Team?`, `Team | "hold"`). Jev picks one; BAML's `match` is exhaustive,
so forgetting a branch is a compile error. An enum's `@@description` is the
question; for a literal union, pass the question with `.judge<T>("…")`.

```baml
type Kind = "a bug report" | "a sales pitch" | "a meeting request" | "something else";

let strategy = match (email.judge<Kind>("What kind of email is this?")) {
    "a bug report"      => "Acknowledge the bug, ask for reproduction steps.",
    "a sales pitch"     => "Politely decline in two sentences.",
    "a meeting request" => "Propose two concrete time slots next week.",
    "something else"    => "Reply briefly and helpfully.",
};
```

### 4. Several judgments at once with `.fill<T>()`

`T extends reflect.AnyClass`: give it a class and every field becomes a question —
**one request**, one typed result. Enum descriptions are the criteria; field
descriptions are the questions. (`.matches<Triage>()` is rejected before any
HTTP call with a pointer to `.fill`; `.fill<Team>()` is a compile error.)

```baml
enum Team {
    Billing   @description("Payments, charges, refunds, or invoices"),
    Technical @description("Bugs, outages, or integrations"),
    Account   @description("Login, identity, or account access"),
    @@description("Which team should handle this ticket?")
}

class Triage {
    urgent: bool      @description("Does this ticket require immediate attention?"),
    route: Team,
    churn_risk: float @description("How likely is this customer to churn over this?"),
    mood: "calm" | "concerned" | "angry" @description("What is the customer's emotional state?"),
}

let tri = ticket.fill<Triage>();
// Triage { urgent: true, route: Technical, churn_risk: 0.56, mood: "angry" }
```

`ticket` here is a class, not a string. `.feels()` works on **any** value —
strings, ints, classes, arrays — because the implementation is a blanket impl:

```baml
1000000.feels("like a suspiciously round number")   // true
1337.feels("like a suspiciously round number")      // false
```

### 5. Generate text with `.ask()`

Jev only classifies. `.ask()` hands the value to a generative model.

```baml
let draft = email.ask("Draft a reply. Keep it under 80 words.");
```

### 6. Keep trying with `while … feels`

It's a normal `while`, so you bound it however you like.

```baml
let attempts = 0;
while (attempts < 5 && draft.feels("full of corporate jargon")) {
    draft = draft.ask("Rewrite this plainly, keeping the meaning.");
    attempts += 1;
}
```

### 7. Do it concurrently — and from the shell

Because it's a real language, judging a batch is `spawn` + `await`, and a
function that reads stdin is a shell tool. `grep_with_vibes` is grep where the
pattern is a feeling:

```baml
function grep_with_vibes(feeling: string) -> void {
    let lines = read_stdin_lines();
    let hits = await baml.future.all(lines.map((l) -> { spawn { l.feels(feeling) } }));
    // print lines[i] where hits[i]
}
```

```sh
$ git log --format=%s | baml run grep_with_vibes -- --feeling "like it would be scary to revert"
Prevent GC starvation across spawn handoffs (#4847)
Defer completion GC and reclaim idle native heaps (#4844)
Trigger full GC from reserved object-slot spending (#4840)
```

Forty commit subjects, judged in parallel, under a second.

### 8. Check a code change before CI runs

`.fill<T>()` turns a class into several questions in one request, so a pre-CI
review is a class and a pipe:

```baml
class Review {
    scope_creep: float        @description("Does this change add functionality beyond what its commit message describes?"),
    unused_abstraction: float @description("Does this change add a class, interface, helper function, or config parameter that nothing else in the diff uses?"),
    duplication: float        @description("Does this change duplicate logic that already appears elsewhere in the same diff?"),
    weakened_tests: float     @description("Does this change weaken, skip, or delete tests or assertions?"),
}

let review = Change { message: message, diff: read_stdin_lines().join("\n") }.fill<Review>();
```

```sh
$ git diff HEAD~1 | baml run code_review -- --message "$(git log -1 --format=%B)"
{"scope_creep":0.1,"unused_abstraction":0.08,"duplication":0.05,"weakened_tests":0.05}
```

Measured on 184 labelled changes from four public repos (the same four questions,
asked of a pinned `jev-1.13.0`; this example uses `jev-latest`), these questions separate
problem changes from good ones at 0.89–0.99 (AUC). At a 0.7 cut-off they catch 78%
of problem changes and flag 1 of 59 good ones, in ~0.3 s and ~$0.0001 per check;
the same through BAML and through the Python SDK. Full method and data:
[qte77.github.io/feelings](https://qte77.github.io/feelings/).

One thing that mattered: **ask about what's in the input.** "Is this abstraction
used only once?" needs the whole codebase, which Jev can't see; rewording it to
"…that nothing else in the diff uses?" took false flags on good changes from
6.7% to 0% on the same examples.

## How `.feels()` works

[`vibes.baml`](baml_src/vibes.baml), abridged:

```baml
interface Vibes {
    function feels(self, quality: string) -> bool throws unknown;
    function how(self, quality: string) -> float throws unknown;
    function matches<T>(self) -> T throws unknown;                      // enum / union
    function judge<T>(self, question: string) -> T throws unknown;      // …with a question
    function fill<T extends reflect.AnyClass>(self) -> T throws unknown; // class
    function ask(self, instruction: string) -> string throws unknown;
}

// Blanket implementation: every type S gets these methods.
implements<S> Vibes for S {
    function feels(self, quality: string) -> bool { Feels(state_of(self), quality) }
    function matches<T>(self) -> T { require_choice<T>(); Matches<T>(state_of(self)) }
    function fill<T extends reflect.AnyClass>(self) -> T { Matches<T>(state_of(self)) }
    // ...
}

// The return type IS the question. bool → Noul, float → probability,
// enum / literal union → Choice, class → one question per field.
function Feels(state: string, quality: string) -> bool {
    client: "typesafeai/jev-latest"
    prompt: `
        ${role("instructions")}
        Does this feel ${quality}?
        ${role("user")}
        ${state}
    `
}

function Matches<T>(state: string) -> T {
    client: "typesafeai/jev-latest"
    prompt: `${state}`
}
```

Strings are passed to Jev verbatim; everything else is serialized as JSON.
See [BAML's TypeSafe AI integration post](https://boundaryml.com/blog/typesafe-ai-jev)
for the full return-type → question mapping.

## What it doesn't do

Jev is a classifier. `.matches<T>()` needs an enum or union; `.fill<T>()` needs
a class whose fields are `bool`, `float`, enums, or literal unions. `string`,
`int`, arrays, and maps are rejected before any HTTP call — use `.ask()` for text.

## Files

| file | what |
| --- | --- |
| [`baml_src/vibes.baml`](baml_src/vibes.baml) | the `Vibes` interface, blanket impl, and Jev-backed functions |
| [`baml_src/urgent.baml`](baml_src/urgent.baml) | the tweet |
| [`baml_src/main.baml`](baml_src/main.baml) | same thing as a function with an `--email` arg |
| [`baml_src/inbox.baml`](baml_src/inbox.baml) | confidence gate → route → draft → rewrite loop → subject |
| [`baml_src/triage.baml`](baml_src/triage.baml) | enums, literal unions, class fan-out, ints, concurrency |
| [`baml_src/grep_with_vibes.baml`](baml_src/grep_with_vibes.baml) | grep, but the pattern is a feeling — a stdin-driven shell tool |
| [`baml_src/code_review.baml`](baml_src/code_review.baml) | a pre-CI code-change check: four questions, one `.fill<Review>()` request |
| [`baml_src/vibes_test.baml`](baml_src/vibes_test.baml) | offline tests that inspect the Jev request shape |
