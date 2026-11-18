"""Constants of the AcegasApsAmga integration.

AcegasApsAmga runs on Gruppo Hera's "Servizi Online" platform: login through
Azure AD B2C, data from a JSON API on the portal's own host.
"""
from __future__ import annotations

DOMAIN = "acegasapsamga"
NOME_INTEGRAZIONE = "AcegasApsAmga"

# --- Login (Azure AD B2C) -----------------------------------------------------
# Public values of the portal's web app. It is a single-page app: no client
# secret, PKCE, and the token endpoint wants the portal's Origin header.
B2C_HOST = "login.acegasapsamga.it"
B2C_TENANT = "myheraapp.onmicrosoft.com"
B2C_POLICY = "B2C_1A_SIGNIN_WEB"
B2C_AUTHORITY = f"https://{B2C_HOST}/{B2C_TENANT}/{B2C_POLICY}"
B2C_AUTHORIZE_URL = f"{B2C_AUTHORITY}/oauth2/v2.0/authorize"
B2C_TOKEN_URL = f"{B2C_AUTHORITY}/oauth2/v2.0/token"
B2C_CLIENT_ID = "40c94bb1-2d83-4ccc-8c72-fde8ad15ed24"
B2C_SCOPE = f"openid offline_access https://{B2C_TENANT}/{B2C_CLIENT_ID}/read"
B2C_REFERRER = "acegas"

# --- Data (Servizi Online API) ------------------------------------------------
PORTALE_ORIGIN = "https://servizionline.acegasapsamga.it"
B2C_REDIRECT_URI = f"{PORTALE_ORIGIN}/auth/acegas/login"
API_BASE_URL = f"{PORTALE_ORIGIN}/api"

# Headers the web app sends on every call: without the referer the API
# answers 417.
API_PLATFORM_ID = "web"
API_REFERER = "ACEGAS"

# The web app asks for 6 items per page; 100 works and covers years of
# monthly readings in a single call.
DIMENSIONE_PAGINA = 100
MAX_PAGINE = 20

# --- Services -------------------------------------------------------------------
SERVIZIO_ACQUA = "WATER"
SERVIZIO_GAS = "GAS"

# Gas is ready in the code but disabled until there is an account to test it.
SERVIZI_SUPPORTATI = (SERVIZIO_ACQUA,)

# Estimated readings are billing estimates, not meter values.
TIPO_LETTURA_STIMATA = "ESTIMATED"

FUSO_ITALIA = "Europe/Rome"

# --- Config entry -----------------------------------------------------------------
CONF_CONTRATTI = "contratti"
CONF_ID_UTENTE = "id_utente"

# --- Updates ----------------------------------------------------------------------
# Readings arrive about once a month: four checks a day are plenty.
INTERVALLO_AGGIORNAMENTO_ORE = 6

# Readings and reading periods listed in the sensors' attributes, for the card:
# about three years of monthly readings, two years of periods.
MAX_LETTURE_ATTRIBUTO = 36
MAX_PERIODI_ATTRIBUTO = 24
# Bills listed in the last bill sensor: about four years.
MAX_BOLLETTE_ATTRIBUTO = 12
