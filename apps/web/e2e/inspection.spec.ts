import { expect, test } from "@playwright/test";
import path from "node:path";
import fs from "node:fs/promises";

const first = path.resolve(__dirname, "../../../data/self_captured/clear_dim_backlit/sample_backlit_01_ambient.png");
const second = path.resolve(__dirname, "../../../data/self_captured/clear_dim_backlit/sample_backlit_01_backlight.png");

async function firstUpload(page: import("@playwright/test").Page) {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Image analysis available", exact: true })).toBeVisible();
  await page.getByTestId("primary-image-input").setInputFiles(first);
  await page.getByRole("button", { name: "Run Active-Perception Inspection", exact: true }).click();
  await expect(page).toHaveURL(/\/job\/[0-9a-f]{32}$/);
  await expect(page.getByText("Supply Second Photo (Different Lighting)", { exact: true })).toBeVisible();
}

test("real upload, changed-lighting recapture, reload and evidence download", async ({ page }) => {
  await firstUpload(page);
  const parentUrl = page.url();
  await page.getByTestId("second-image-input").setInputFiles(second);
  await page.getByRole("button", { name: "Analyze new capture", exact: true }).click();
  await expect(page).not.toHaveURL(parentUrl);
  await expect(page.getByText("HIGH PATTERN VISIBILITY — NOT A WATER SAFETY TEST", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText("HIGH PATTERN VISIBILITY — NOT A WATER SAFETY TEST", { exact: true })).toBeVisible();
  const pending = page.waitForEvent("download");
  await page.getByRole("button", { name: "Evidence ZIP", exact: true }).click();
  const download = await pending;
  expect(download.suggestedFilename()).toMatch(/loopsight-.*-evidence\.zip/);
  const filename = await download.path();
  expect(filename).toBeTruthy();
  const bytes = await fs.readFile(filename!);
  expect(bytes.subarray(0, 2).toString()).toBe("PK");
  expect(bytes.length).toBeGreaterThan(1000);
});

test("duplicate follow-up remains an actionable error", async ({ page }) => {
  await firstUpload(page);
  const parentUrl = page.url();
  await page.getByTestId("second-image-input").setInputFiles(first);
  await page.getByRole("button", { name: "Analyze new capture", exact: true }).click();
  await expect(page.getByText(/the second image duplicates the first/)).toBeVisible();
  await expect(page).toHaveURL(parentUrl);
});

test("evaluation shows measured ties and unresolved cases", async ({ page }) => {
  await page.goto("/evaluation");
  await expect(page.getByRole("heading", { name: "What the current evidence shows" })).toBeVisible();
  await expect(page.getByRole("note")).toContainText("does not demonstrate an adaptive allocation advantage");
  await page.getByRole("combobox", { name: "Cases", exact: true }).selectOption("unresolved");
  await expect(page.getByText("Showing 12 of 34 cases.", { exact: false })).toBeVisible();
  const pending = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download full evaluation JSON" }).click();
  const download = await pending;
  expect(download.suggestedFilename()).toBe("loopsight-synthetic-capture-evaluation.json");
});

test("backend outage is shown without creating an inspection result", async ({ page }) => {
  await page.route("**/api/readiness", route => route.fulfill({ status: 503,
    contentType: "application/json", body: JSON.stringify({ available: false }) }));
  await page.route("**/api/inspect", route => route.fulfill({ status: 503,
    contentType: "application/json", body: JSON.stringify({ detail: "Evidence storage is unavailable. Retry the inspection." }) }));
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Analysis unavailable · Retry", exact: true })).toBeVisible();
  await page.getByTestId("primary-image-input").setInputFiles(first);
  await page.getByRole("button", { name: "Run Active-Perception Inspection", exact: true }).click();
  await expect(page.getByText("Evidence storage is unavailable. Retry the inspection.", { exact: true })).toBeVisible();
  await expect(page).toHaveURL("/");
});
