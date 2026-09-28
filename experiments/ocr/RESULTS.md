# Synthetic OCR development findings

Measured execution date: 2026-09-27. Two separately locked development runs used
the same four authored families. All sixteen rendered pages were visually
inspected by the assistant before their respective locks; this is not independent
human review. No retrieved source document was processed by OCR.

## Exact field recovery

Each cell has sixteen fields: four families multiplied by four labelled fields.
Counts below are **calculated** from retained local outputs. The same reference
inventory gives majority 6/16 and seeded random 7/16 for every row.

| Run | Method | Representation | Exact fields | Majority | Seeded random |
| --- | --- | --- | --- | --- | --- |
| Clean: 150 dpi, 16-point type | PDF extraction | Selectable text | 16/16 | 6/16 | 7/16 |
| Clean | PDF extraction | Image only | 0/16 | 6/16 | 7/16 |
| Clean | OCR | Raster of selectable text | 16/16 | 6/16 | 7/16 |
| Clean | OCR | Raster of image-only PDF | 16/16 | 6/16 | 7/16 |
| Stress: 72 dpi, 10-point type | PDF extraction | Selectable text | 16/16 | 6/16 | 7/16 |
| Stress | PDF extraction | Image only | 0/16 | 6/16 | 7/16 |
| Stress | OCR | Raster of selectable text | 6/16 | 6/16 | 7/16 |
| Stress | OCR | Raster of image-only PDF | 7/16 | 6/16 | 7/16 |

The stress conditions changed resolution and type size together; their individual
effects cannot be separated. The image-only route rasterises a PDF containing the
first raster, so paired rasters need not produce identical recognition. They are
repeated representations of the same families, not additional independent cases.

## Errors retained

| Synthetic example | Expected | Observed OCR | Consequence |
| --- | --- | --- | --- |
| First family, image-only decision | `004.018/0081` | `04.018/0081` | Leading zero lost |
| First family, image-only date | `2030-02-08` | `2090-02-08` | Wrong year still looks plausible |
| First family, selectable-text raster duration | `30 days` | `20 days` | Wrong explicit day count |
| Fourth family, selectable-text raster date | `2030-08-12` | `2090-00-12` | Invalid calendar month |

All eight stress OCR outputs missed the exact scale-labelled field. Some raw
lines changed the label or inserted leading punctuation; another also lost the
scale separator. This is a field-recovery failure under the registered parser,
not a claim that every scale value was wholly unreadable. Matching rules were
not relaxed after seeing these errors. No timeout or engine error occurred in
either measured run.

## Interpretation and next gate

Local OCR recovered the clean image-only template, where PDF text extraction
returned no fields. Under the registered stress conditions it failed to exceed
the seeded random baseline. This negative finding rules out automatic promotion
of recognised values into procedural evidence on the strength of this experiment.

Keep raw recognition separate from reviewed evidence. A future integration needs
explicit field review, source-page linkage and a measured abstention policy;
these controls are not implemented by this experiment. A later evaluation should
include independently reviewed varied layouts and representative degradation.
Do not tune against these four families and present the result as unseen-data
accuracy. No training or general analyst-model selection is justified here.

Native per-page elapsed times are retained in local JSON, separately from the
unmeasured human authoring, checking and correction time. No human time-saving
claim, production accuracy, legal effect or forecasting result follows.

## Reproduction records

| Item | Identity |
| --- | --- |
| Clean registration SHA-256 | `adbc3070365af4b963f3f85df22994c7f54cfe951c05b78e59aefd06734684dc` |
| Stress registration SHA-256 | `2074ce3be223b859d67dc17e184fc1c9fba5abd8f9f49918c9e88ccc21d48965` |
| Engine | Tesseract 5.5.2; mode 1; segmentation 6; timeout 30 seconds |
| Python for the native runs | 3.12.14 |
| PDF libraries | reportlab 4.4.9; pypdf 6.10.2 |
| Recognition data revision | `87416418657359cb625c412a48b6e1d6d41c29bd` |
| Recognition data SHA-256 | `7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2` |

The recognition data came from the official
[data repository](https://github.com/tesseract-ocr/tessdata_fast/tree/87416418657359cb625c412a48b6e1d6d41c29bd).
Its [licence text](https://github.com/tesseract-ocr/tessdata_fast/blob/87416418657359cb625c412a48b6e1d6d41c29bd/LICENSE)
was retrieved and identifies Apache-2.0. The downloaded bytes and licence digest
are recorded in local provenance. Data resides only in ignored experiment output;
there was no system-wide installation. Native runtimes were already present.

The local artefact directories are `out/ocr-development-v2`, `out/ocr-results-v2`,
`out/ocr-stress-v1` and `out/ocr-stress-results-v1` in the attached worktree.
An earlier `out/ocr-development-v1` contains only unscored fixture preparation
from before review fixes. Its rendered page hashes matched the clean run pages.

Source configuration and code are versioned; generated artefacts are local and
ignored. Input hashes, tool/library versions and raw output are retained there.
The lock is a drift guard, not a complete native environment image or protection
against an operator deliberately replacing both registration and digest.
