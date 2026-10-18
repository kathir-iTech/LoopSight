# Independent capture collection protocol

No physical captures are committed here. `../self_captured` contains generated
fixtures despite its historical directory name. Keep real originals separately;
never run the synthetic generator over this directory.

The current label scope is **relative image screening**, with PASS meaning high
checkerboard visibility and FAIL meaning low visibility. This is not a laboratory
turbidity measurement, water-safety classification or structural assessment.

1. Assign a preparation ID before capture. Record device, session, lighting,
   container, target, camera distance, original dimensions and capture timestamps.
   Document sample preparation and image rights; exclude people/private metadata.
2. Keep the target/sample in the same position for each pair. Take an ambient photo
   and a real follow-up under changed lighting. Preserve originals, including
   failures. Do not brighten/filter a photo and call it a new observation.
3. Capture follow-ups for both easy and ambiguous cases. If only ambiguous cases
   have a second image, fixed and adaptive acquisition may have identical budgets;
   such a dataset cannot establish an allocation advantage.
4. Set labels independently from model predictions, recording the assessor and
   justification. Use appropriate reference readings if claiming physical units.
   Exclude ambiguous labels from binary evaluation and report the exclusion count.
5. Freeze preparation/session groups into calibration, validation and blind test
   splits before tuning. All related devices, captures and companions from one
   preparation belong to one group/split. Do not reuse the blind test to tune.
6. Place the manifest alongside its images. Paths must remain inside that
   directory. The loader rejects group and decoded-image leakage across splits.
   It cannot detect every related preparation: group declarations need review.

Manifest shape (illustrative names; these files and physical samples do not exist):

```json
{
  "schema_version": 1,
  "label_scope": "relative_image_screening",
  "samples": [
    {
      "id": "preparation-01-phone-a-ambient",
      "group_id": "preparation-01",
      "split": "test",
      "source_kind": "physical",
      "expected_outcome": "PASS",
      "primary_image": "images/preparation-01-ambient.png",
      "secondary_image": "images/preparation-01-backlight.png"
    }
  ]
}
```

Run `python services/inference/scripts/evaluate_captures.py path/to/manifest.json
--json reports/physical-test.json` from the repository root. Current strategies
share one image policy and vary capture allocation. Report all abstentions,
false clears, rejected pairs, requested inputs and group counts. A source_kind
declaration is not proof of physical ground truth. Group-aware intervals, field
impact, costs and statistically supported comparisons remain additional work.
