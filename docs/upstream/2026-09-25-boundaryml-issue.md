**Results page: https://qte77.github.io/feelings/**

We used `feelings` to test whether Jev can review code changes before CI runs. Four questions in one `.fill<Review>()` call flagged **78% of problem changes and 1 of 59 clean ones**. That is nearly as well as Claude Sonnet and Opus, about **70× faster** and about **80× cheaper**. We'd like to give back a small example and one README tip.

## What you'd get

1. **Measured evidence.** 184 labelled code changes from 4 public Apache-2.0 repos: 59 real commits as written, and 125 with one known problem (scope creep, an unused abstraction, duplicated code or a weakened test).
   - Jev separates problem changes from clean ones at **0.89–0.99 ROC-AUC** per question.
   - Its answers agree **97% or more** across five repeats.
   - About **0.3 s and $0.0001** per check.
2. **A fair comparison with Claude**, on the same examples and the same questions:

   | Setup | Tells good from bad (avg of 4) | Flags problem changes | Wrongly flags clean ones | p95 time | Cost per check |
   |---|---|---|---|---|---|
   | Jev | 0.94 | 78% | 1.7% | 0.28 s | $0.00012 |
   | Claude Haiku 4.5 | 0.90 | 79% | 11.9% | 27.9 s | $0.0092 |
   | Claude Sonnet 5 | 0.96 | 90% | 0% | 21.7 s | $0.022 |
   | Claude Opus 5.5 | 0.97 | 98% | 0% | 19.1 s | $0.042 |
3. **BAML matches the plain SDK.** Through BAML and through the Python SDK the requests are identical and the results agree within 0.02. That supports your "you don't need a new language" point.
4. **A tip for anyone writing `.feels()` or `.fill()` questions: ask about what's *in the input*.** "Is this abstraction used only once?" needs the whole codebase, which Jev never sees. Rewording it to "…that nothing else in the diff uses?" took wrongly flagged clean changes from **6.7% to 0%** on the same examples.
5. **A 25-line example on your own API.** `baml_src/code_review.baml` is a `Review` class answered by one `.fill<Review>()`, piped from `git diff` through your `read_stdin_lines()`:

   ```sh
   git diff HEAD~1 | baml run code_review -- --message "$(git log -1 --format=%B)"
   {"scope_creep":0.1,"unused_abstraction":0.08,"duplication":0.05,"weakened_tests":0.05}
   ```

   It comes with offline tests in the style of `vibes_test.baml` (all 6 pass) and a short README section 8. The diff against your `main` is 3 files, 87 lines, with no changes to existing code:
   https://github.com/BoundaryML/feelings/compare/main...qte77:feelings:contrib/code-review-example

Full method, data, caveats and the Claude comparison: **https://qte77.github.io/feelings/** (open "How we tested it"). The results were measured with a pinned `jev-1.13.0`; the example uses your `jev-latest` client.

## May we open a PR?

Reply with one:
- **(a)** the full example: `code_review.baml`, tests and README section 8;
- **(b)** just the README tip;
- **(c)** no thanks.

We'll adjust to whatever fits the repo.

(Related to your issue #1: we'd contribute under whatever licence you choose.)
