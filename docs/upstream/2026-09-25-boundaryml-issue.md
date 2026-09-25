<!-- DRAFT, not posted. Target: github.com/BoundaryML/feelings/issues. Post only after the owner approves. -->

# Offer: a pre-CI code-change check with `.fill<T>()`, plus measured results

Hi! We forked `feelings` and used it to test whether Jev can act as a fast check on
code changes before the slow checks (tests, lint, CI) run. It worked well, and the
result is a small, idiomatic example we'd like to offer back, if it's useful to you.

**The example (3 files, 87 lines, on top of your `main`):** `baml_src/code_review.baml`
turns four questions into one `.fill<Review>()` request, piped from `git diff` through your
`read_stdin_lines()`:

```sh
git diff HEAD~1 | baml run code_review -- --message "$(git log -1 --format=%B)"
{"scope_creep":0.1,"unused_abstraction":0.08,"duplication":0.05,"weakened_tests":0.05}
```

It adds offline tests in the style of `vibes_test.baml` (all 6 pass) and a short README
section 8. The diff against your `main`: https://github.com/BoundaryML/feelings/compare/main...qte77:feelings:contrib/code-review-example

**What we measured** (184 labelled changes from four public Apache-2.0 repos; the same four
questions, asked of a pinned `jev-1.13.0`):
- Jev separates problem changes from good ones at 0.89–0.99 AUC per question.
- At a 0.7 cut-off it catches 78% of problem changes and flags 1 of 59 good ones.
- Answers agree 97–100% across five repeats, in ~0.3 s and ~$0.0001 per check.
- The results are the same through BAML and through the Python SDK.
- Method, data and caveats: https://qte77.github.io/feelings/

**One lesson that might belong in the README either way:** ask about what's *in the input*.
"Is this abstraction used only once?" needs the whole codebase, which Jev can't see.
Rewording it to "…that nothing else in the diff uses?" took false flags on good changes from
6.7% to 0% on the same examples.

Would you like this as a PR? Happy to adjust it, trim it to just the README tip, or leave it here.

(Related: your issue #1 asks for a LICENSE. We'd contribute under whatever licence you pick.)
