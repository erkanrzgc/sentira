# OCR development stress addendum

The clean-page development run recovered sixteen of sixteen fields on each OCR
representation, alongside majority six of sixteen and seeded random seven of
sixteen. These calculated counts motivate a harder development check, not an
accuracy claim about unseen source documents.

Before running another comparison, fix the second configuration to 72 dots per
inch and 10-point type. The four authored families, field values, parser,
baselines, engine, recognition data and engine options remain the same. Both
parameters change together; the experiment cannot attribute any difference to
resolution or type size individually. These are deliberately clean computer
renderings, not a model of real scanner noise, stamps, rotation or handwriting.

Use `experiments/ocr/fixtures-stress.toml`. Prepare eight new pages in another
directory, inspect all eight, lock their registration and run once without
changing matching rules in response to observed errors. Retain all errors and
the earlier clean-page result. The author-provided answers and repeated families
remain development-only, not independent references or a held-out set.

Do not repair OCR strings using expected answers. Any further change to engine
options or matching would require a separately identified development run.
