# Changelog

## 0.4.0-beta.1

- Excluded rejected (`KO`), pending (`IN_CHARGE`) and unknown readings from real
  readings, and guarded reading and bill parsing against invalid values.
- Added bill statuses for partial reversals, under-threshold bills and
  installment plans, deduplicated paginated bills and increased the bills
  attribute limit to 120.
- Made B2C sign-in resilient to transient server/OAuth errors, cleared all
  session cookies on login and preserved refresh tokens when not rotated.
- Loaded cached data without blocking Home Assistant startup, stopped polling on
  failed auth, parallelized portal API calls, removed unused usage API calls and
  appended Recorder statistics incrementally.
- Normalized statistic IDs, cleaned up devices and entities when removing
  contracts in options, allowed updating the email during reauth, kept device
  serial numbers in sync after meter replacements and closed anonymization gaps
  in diagnostics.
- Improved the meter card: direct-debit status per unpaid bill, accurate annual
  bill totals excluding reversed bills, missing device alert, theme redraws,
  semantic buttons, keyboard/touch tooltip handling and faster rendering/editor.
- Added `ruff` and `pytest` checks to CI.

## 0.3.0

- Meter card redesigned: one chart of the reading periods, year by year; the
  previous period and the bill to pay under the main number; the year's bills
  at the bottom. The `view` option is no longer used.
- The sensors' attributes list about ten years of reading periods and bills.

## 0.2.0

- Bill sensors: last bill, amount due, bill due date and last bill status.
- Bill numbers are anonymized in the diagnostics.
- The check script also lists the bills.

## 0.1.0

First version.

- Sign-in with the Servizi Online email and password.
- Water readings imported as statistics for the Energy Dashboard, with the
  whole history at setup.
- **Configure Energy dashboard** action.
- Sensors: meter reading, last reading date, last period consumption,
  average daily consumption, next self-reading.
- Meter card, served by the integration: litres a day of the last reading
  period with the change from the one before, charts by reading period and
  by month, year total and daily average.
- Italian and English.
