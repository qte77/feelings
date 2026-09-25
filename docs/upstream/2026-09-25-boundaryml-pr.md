<!-- DRAFT, not opened. Head: qte77/feelings:contrib/code-review-example, base: BoundaryML/feelings:main.
     Open only if the maintainers say yes on the issue, and after the owner approves. -->

# Add code_review: a pre-CI code-change check with one `.fill<Review>()` call

## What
- `baml_src/code_review.baml`: a `Review` class with four float fields, which are four Jev
  questions answered in one request. It reads the diff from stdin (`read_stdin_lines()`),
  takes the commit message as `--message`, prints the JSON, and says
  "worth a closer look before merging" when any score is ≥ 0.7.
- `baml_src/code_review_test.baml`: offline tests in the style of `vibes_test.baml`. They check
  the state Jev receives, and type-check the `fill<Review>` dispatch with `@spec`.
- README: section 8 (usage, measured results, the question-wording tip), a line in
  "Try it", and a row in "Files".

## Why
It shows `.fill<T>()` on a real task, with numbers. The measured results are on 184 labelled
changes; method and data are at https://qte77.github.io/feelings/.

## Checks
- `baml check` and `baml test`: 6 passed (4 existing, 2 new), offline.
- One live run on a real commit diff, which returned all four scores low, as expected for a clean change.

Nothing else in the repo changes.
