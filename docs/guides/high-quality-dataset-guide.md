# Keys to a Good Benchmark Dataset

1. **Representative** — mirrors real inputs your app will actually see, not just easy/clean cases.
2. **Sufficient size** — enough examples per category/edge case for statistically meaningful results.
3. **Balanced** — avoid skew toward one class, topic, or difficulty level unless that reflects reality.
4. **Clear expected outputs** — unambiguous ground truth; define acceptable variation if multiple answers are valid.
5. **Covers edge cases** — ambiguous inputs, out-of-domain examples, long-context cases, adversarial/tricky prompts.
6. **Clean splits** — separate train/dev/test; never tune on test data.
7. **Consistent labeling** — same annotation guidelines/rubric across all examples; spot-check for errors.
8. **Versioned & documented** — track dataset version, source, and any changes over time for reproducibility.
9. **No leakage** — examples shouldn't overlap with model training data or across splits.
10. **Task-aligned** — format and difficulty match the actual deployment use case, not a generic benchmark.