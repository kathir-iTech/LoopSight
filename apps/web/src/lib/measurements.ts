/** Demo and live responses share this explicit image-space scope. */
export const MEASUREMENT_CONTRACT = {
  version: "image-space-v1",
  physical_units_available: false as const,
  water_unit: "dimensionless",
  crack_width_unit: "analysis_image_pixels",
  limitations: [
    "Pattern visibility is an image score, not a calibrated NTU measurement.",
    "Image-space feature widths do not establish physical width or structural safety.",
  ],
};
