# English editing scenarios

Run the offline regression evaluation:

```sh
python eval/run_eval.py
python eval/run_eval.py --json eval/results.json
```

`data/english.jsonl` contains synthetic project-authored scenarios, with
`needs_edit` and `acceptable` labels. The same factual sentence appears with
and without formulaic wrappers across five contexts. Additional examples keep
precise terminology and deliberate punctuation. These fixtures are MIT licensed.

This evaluation checks intended editing behavior. It does not measure human
authorship, reader preference, voice matching quality, or accuracy on unseen
writing. Thresholds are provisional. The Japanese data, baselines and reported
accuracy from version 0.1.0 have been retired; they remain in Git history.

`tests/test_rewrite_and_hook.py` separately checks preservation, unsafe candidate
rejection, retries, deadlines and attachment handling. `tests/test_corpus.py`
checks source provenance, reading coverage and profile freshness. The five
`examples/rewrite` pairs are synthetic replies replayed through the actual
acceptance gates; they are not recordings of a live provider experiment.

Before making quality claims, collect licensed English writing from consenting
subjects across formats. Keep development and held-out subjects separate, use
independent readers, compare rewrites against their source facts, and report
voice fidelity and useful editing separately. Generated fixtures must remain
identified as synthetic.
