# Changelog

## 0.4.1

- Waste card: this year is compared with last year up to the same day, not
  with the whole of last year; without that figure it shows last year's totals
  without a percentage. New `anno_precedente_ad_oggi` attribute on the waste
  disposals and volume sensors.
- Bills card: the header lists the utilities it covers instead of flags taken
  from the latest bill only; bills covering several utilities are grouped by
  name ("Water and gas"); rows no longer repeat a single-service amount.
- Meter card: an electricity meter shows as electricity; an open self-reading
  window is marked with a dot instead of light text.
- Electricity card: the band bar has a title and softer shades.
- Italian dates use the elided article ("l'1 dic", "l'8 dic", "all'11 nov").
- On narrow cards, three columns become two; filter chips have a 40px touch
  area; tints no longer need `color-mix()`, so older companion apps show them.
- Electricity and waste cards without a matching contract link to the
  integration page instead of starting a new setup.

## 0.4.0

- Added full multi-service support for Water, Gas, Electricity (with F1/F2/F3
  time-of-use bands and Energy Dashboard grid source), District Heating
  (kWh/MWh) and Waste / TARI (TCP disposals, volumes, fractions, equipment and
  discounts).
- Enriched bill and contract data with detailed portal statuses (including
  partial reversals, under-threshold bills and installment plans), per-service
  splits on combined bills, actual payment dates, paperless and PDF availability
  flags, self-reading history and remaining-days countdown, optional daily reads
  and VAS / Diario dei Consumi flags.
- Added account-level diagnostic sensors and Repair Issues for 180-day portal
  password expiration and new terms acceptance, plus unread portal notifications
  and active water outage alert status.
- Added a native Calendar platform exposing upcoming self-reading windows and
  unpaid bill due dates.
- Added Home Assistant actions to submit meter self-readings
  (`acegasapsamga.invia_autolettura`) and download bill PDFs
  (`acegasapsamga.scarica_bolletta`).
- Added three new built-in Lovelace cards (`acegasapsamga-luce-card`,
  `acegasapsamga-rifiuti-card`, `acegasapsamga-bollette-card`) alongside the
  redesigned `acegasapsamga-contatore-card`: hidden-by-default bill summaries on
  consumption cards (optional `show_bills` toggle), interactive stacked band and
  waste-fraction charts, utility-grouped bills overview, keyboard/touch tooltips
  and native Home Assistant empty and error states.
- Hardened authentication, coordinator and diagnostics: resilient B2C sign-in
  and session handling, non-blocking cached startup, incremental Recorder
  statistics, normalized statistic IDs, clean device/entity removal when
  updating contracts, email update during reauth, meter serial sync and complete
  diagnostics anonymization.
- Updated integration brand icons (`icon.svg`, `brand/icon.png` and
  `brand/icon@2x.png`) for crisp dark-mode contrast, added a light/dark 6-card
  README wall and added `ruff` and `pytest` checks to CI.

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
