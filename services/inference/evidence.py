"""Public measurement contract: image evidence, not calibrated physical units."""

MEASUREMENT_CONTRACT = {
    "version": "image-space-v1",
    "physical_units_available": False,
    "confidence_basis": "heuristic_label_not_calibrated_probability",
    "water_metric": "pattern_visibility",
    "water_unit": "dimensionless",
    "crack_width_unit": "analysis_image_pixels",
    "limitations": [
        "Pattern visibility is an image heuristic, not a calibrated NTU measurement.",
        "Crack-like feature widths are measured in analysis pixels; physical scale is unavailable.",
        "Screening outcomes do not certify drinking-water potability or structural safety.",
    ],
}
