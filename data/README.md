# data/ — Self-captured dataset

## Structure (expected)

```
data/self_captured/
  clear/        # pattern sharp through clear water
  turbid/       # same pattern obscured through visibly cloudy water
  borderline/   # genuinely ambiguous middle case
```

Water photos: place a printed checkerboard (or grid) behind/under a clear glass,
photograph it with and without water. Capture each sample under two lightings
(backlight vs ambient or phone flash) so `track_across_frames` has a real second observation.

For `fdm_print_surface_v1` legacy photos (if needed):
```
data/self_captured_fdm/
  clean/
  layer_shift/
  ...
```

## Consent

If you photograph water samples in shared spaces or with other people visible,
obtain explicit oral consent before shooting and do not include faces,
names, or private property identifiers in the dataset. Store only the
glass+pattern crop. If a bystander appears inadvertently, crop or discard.

- No faces required for this task — frame tightly on the glass + pattern.
- Do not photograph private documents, addresses, or other sensitive backgrounds.
- By contributing, you confirm you have permission to share these images
  under MIT (self-captured code/dataset licensing per `LICENSE` and
  `services/reports/technical_report.md` §7).

## Licensing

Self-captured images you create and place here are contributed under MIT
and may be published as part of the submission. Do not add MVTec AD or
other CC BY-NC-SA 4.0 data here — that is internal-validation-only and
never redistributed.

## Next steps

```bash
python services/inference/scripts/calibrate_thresholds.py data/self_captured
python services/inference/scripts/run_experiments.py data/self_captured --profile water_turbidity_v1
```
