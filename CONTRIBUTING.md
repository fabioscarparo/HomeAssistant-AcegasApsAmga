# Contributing

How the integration works inside, how to check it against a real account and
how to run the tests. For installing and using it, see the
[README](README.md).

## Architecture

```text
Azure AD B2C login (auth.py)
        ↓ access token
Servizi Online API (api.py)
        ↓ read archive
readings store (coordinator.py)
        ↓ real readings only
hourly series (letture.py)
        ↓
external statistics (statistics.py) → Energy Dashboard
```

### Login

The portal is Gruppo Hera's "Servizi Online". It signs in with MSAL against
the B2C tenant `myheraapp.onmicrosoft.com`, policy `B2C_1A_SIGNIN_WEB`, on
`login.acegasapsamga.it`. `auth.py` repeats the browser's steps: authorize
page, `SelfAsserted` with email and password, `confirmed`, token with PKCE.

The client is a single-page app: the token endpoint wants the portal's
`Origin` header, and refresh tokens last at most 24 hours. Tokens stay in
memory; the coordinator signs in again with the stored password when they
expire.

### API

Every call sends `Authorization: Bearer <token>`, `X-Bwb-PlatformId: web` and
`X-Bwb-Referer: ACEGAS` (without it the API answers 417). The endpoints used
are listed in `api.py`; anonymized real answers are in `tests/fixtures`.

Daily readings (`v2/.../usage` with `pdr`, `fromDate`, `toDate`) exist only
for profiles enabled to them: a household water profile gets "Profile Z001
not allowed for daily reads", so the integration uses the read archive.

### Bills

Bills come from `profile/{id}/bill/list`, with `groupBy` set to the profile's
`billGroupType` (read once from `profile/{id}`), as the portal's Bills page
does. The web app also calls a second host, `myhera.gruppohera.it`, with an
extra token: it is not needed. `bollette.py` keeps only number, dates,
amounts, status, direct debit and contracts, so the store holds no names,
addresses or bank details.

A bill has no billing period, and the `documentId` of the billing periods
always points to the latest bill: amounts cannot be spread over the
consumption, which is why there is no cost series.

### From readings to statistics

The rules are at the top of `letture.py`. In short: real readings only, a
reading closes its day, consumption spread evenly between readings, no
extrapolation after the last one. The whole series is rewritten when the
real readings change; a shorter series is cleared first.

Readings are kept in the integration's store (`.storage/acegasapsamga.<entry>`).
From the portal's oldest reading on, the portal wins; older stored readings
are kept, so the cumulative sum never restarts if the portal drops old
history.

### Gas

`SERVIZI_SUPPORTATI` in `const.py` lists the enabled services. Gas has its
statistic id (`<pod>_gas`), device class and Energy Dashboard source ready,
but the read archive of a gas contract has never been seen: before adding
`SERVIZIO_GAS`, check its answer with the script below.

## Checking against a real account

```bash
python3 -m venv .venv
.venv/bin/pip install aiohttp
.venv/bin/python scripts/verifica_accesso.py
```

The script asks for email and password, signs in like the integration and
prints contracts, readings, the series the Energy Dashboard would get and the
bills.
With `--salva` it also saves the raw answers to `verifica_*.json`: they
contain personal data, never commit them.

## Images

- `custom_components/acegasapsamga/brand/`: the integration's icon, 256 and
  512 px, shown by Home Assistant 2026.3+.
- `docs/images/header.svg`: the README header.
- `docs/images/icon.svg`: the icon as a vector.
- `docs/images/contatore-card-light.svg` and `-dark.svg`: the card in the
  README, rendered from the real card with simulated data, text drawn as
  paths. Render them again whenever the card changes look.

## Development

```bash
python3.14 -m venv .venv
.venv/bin/pip install -r requirements_test.txt ruff
.venv/bin/python -m pytest
.venv/bin/ruff check custom_components tests scripts
```
