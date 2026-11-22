"""Config flow: email and password, then the contracts to follow.

Reauth asks for credentials again; options change the tracked contracts.
"""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.update_coordinator import UpdateFailed

from .api import ApiClient, ApiError, contratto_da_api
from .auth import (
    AuthClient,
    AuthError,
    CredenzialiNonValide,
    ErroreRete,
    PassaggioInatteso,
    nuovo_cookie_jar,
)
from .const import (
    CONF_CONTRATTI,
    CONF_ID_UTENTE,
    DOMAIN,
    SERVIZI_SUPPORTATI,
)
from .testi import testo

_LOGGER = logging.getLogger(__name__)

SCHEMA_EMAIL = TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username"))
SCHEMA_PASSWORD = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
)


class Accesso:
    """Result of a successful login: account id and contracts."""

    def __init__(self, id_utente: str | None, contratti: list[dict[str, Any]]) -> None:
        self.id_utente = id_utente
        self.contratti = contratti

    @property
    def supportati(self) -> list[dict[str, Any]]:
        return [c for c in self.contratti if c["servizio"] in SERVIZI_SUPPORTATI]

    @property
    def non_supportati(self) -> list[dict[str, Any]]:
        return [c for c in self.contratti if c["servizio"] not in SERVIZI_SUPPORTATI]


async def async_accedi(
    hass, email: str, password: str, *, solo_login: bool = False
) -> Accesso:
    """Log in and list the account's contracts. Raises AuthError or ApiError."""
    session = async_create_clientsession(hass, auto_cleanup=False, cookie_jar=nuovo_cookie_jar())
    try:
        token = await AuthClient(session).async_login(email, password)
        if solo_login:
            contratti: list[dict[str, Any]] = []
        else:
            api = ApiClient(session, token.access_token)
            contratti = [contratto_da_api(p, c) for p, c in await api.async_contratti_account()]
    finally:
        session.detach()
    return Accesso(token.id_utente, contratti)


def errore_accesso(err: Exception) -> str:
    """Form error key for a failed login."""
    if isinstance(err, CredenzialiNonValide):
        return "credenziali_non_valide"
    if isinstance(err, PassaggioInatteso):
        return "passaggio_inatteso"
    if isinstance(err, ErroreRete) or (isinstance(err, ApiError) and err.rete):
        return "impossibile_connettersi"
    return "risposta_inattesa"


def etichetta(lingua: str | None, contratto: dict[str, Any]) -> str:
    servizio = contratto["servizio"]
    parti = [
        testo(lingua, f"servizio_{servizio}")
        if servizio in SERVIZI_SUPPORTATI
        else str(servizio),
        contratto["contratto"],
    ]
    if contratto.get("indirizzo"):
        parti.append(contratto["indirizzo"])
    if contratto.get("stato") not in (None, "ACTIVE"):
        parti.append(str(contratto["stato"]).lower())
    return " - ".join(parti)


def schema_contratti(
    lingua: str | None, contratti: list[dict[str, Any]], scelti: list[str]
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_CONTRATTI, default=scelti): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=c["contratto"], label=etichetta(lingua, c))
                        for c in contratti
                    ],
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                )
            )
        }
    )


class AcegasConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._email = ""
        self._password = ""
        self._accesso: Accesso | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AcegasOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        segnaposto = {"messaggio": ""}
        if user_input is not None:
            self._email = user_input[CONF_EMAIL].strip()
            self._password = user_input[CONF_PASSWORD]
            try:
                self._accesso = await async_accedi(self.hass, self._email, self._password)
            except (AuthError, ApiError) as err:
                _LOGGER.debug("Accesso non riuscito: %r", err)
                errors["base"] = errore_accesso(err)
                segnaposto["messaggio"] = str(err)
            else:
                await self.async_set_unique_id(self._accesso.id_utente or self._email.lower())
                self._abort_if_unique_id_configured()
                supportati = self._accesso.supportati
                if not supportati:
                    return self.async_abort(
                        reason="nessun_contratto",
                        description_placeholders={
                            "servizi": ", ".join(
                                sorted({str(c["servizio"]) for c in self._accesso.non_supportati})
                            )
                            or "-"
                        },
                    )
                if len(supportati) == 1:
                    return self._crea_entry(supportati)
                return await self.async_step_contratti()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_EMAIL): SCHEMA_EMAIL,
                        vol.Required(CONF_PASSWORD): SCHEMA_PASSWORD,
                    }
                ),
                {CONF_EMAIL: self._email},
            ),
            errors=errors,
            description_placeholders=segnaposto,
        )

    async def async_step_contratti(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._accesso is not None
        supportati = self._accesso.supportati
        errors: dict[str, str] = {}
        if user_input is not None:
            scelti = set(user_input[CONF_CONTRATTI])
            if scelti:
                return self._crea_entry([c for c in supportati if c["contratto"] in scelti])
            errors["base"] = "nessuna_scelta"
        attivi = [c["contratto"] for c in supportati if c.get("stato") == "ACTIVE"]
        return self.async_show_form(
            step_id="contratti",
            data_schema=schema_contratti(
                self.hass.config.language,
                supportati,
                attivi or [c["contratto"] for c in supportati],
            ),
            errors=errors,
        )

    def _crea_entry(self, contratti: list[dict[str, Any]]) -> ConfigFlowResult:
        assert self._accesso is not None
        return self.async_create_entry(
            title=self._email,
            data={
                CONF_EMAIL: self._email,
                CONF_PASSWORD: self._password,
                CONF_ID_UTENTE: self._accesso.id_utente,
                CONF_CONTRATTI: contratti,
            },
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        email_corrente = entry.data[CONF_EMAIL]
        errors: dict[str, str] = {}
        segnaposto = {"email": email_corrente, "messaggio": ""}
        if user_input is not None:
            email = (user_input.get(CONF_EMAIL) or email_corrente).strip()
            segnaposto["email"] = email
            try:
                accesso = await async_accedi(
                    self.hass, email, user_input[CONF_PASSWORD], solo_login=True
                )
            except (AuthError, ApiError) as err:
                errors["base"] = errore_accesso(err)
                segnaposto["messaggio"] = str(err)
            else:
                await self.async_set_unique_id(accesso.id_utente or email.lower())
                self._abort_if_unique_id_mismatch(reason="account_diverso")
                aggiornamenti = {CONF_EMAIL: email, CONF_PASSWORD: user_input[CONF_PASSWORD]}
                return self.async_update_reload_and_abort(
                    entry, title=email, data_updates=aggiornamenti
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Optional(CONF_EMAIL, default=email_corrente): SCHEMA_EMAIL,
                        vol.Required(CONF_PASSWORD): SCHEMA_PASSWORD,
                    }
                ),
                {CONF_EMAIL: segnaposto["email"]},
            ),
            errors=errors,
            description_placeholders=segnaposto,
        )


class AcegasOptionsFlow(OptionsFlow):
    """Change the contracts, reading the list again from the account."""

    def __init__(self) -> None:
        self._accesso: Accesso | None = None

    async def _async_leggi_contratti(self, entry: ConfigEntry) -> Accesso:
        coordinator = getattr(entry, "runtime_data", None)
        if (
            coordinator is not None
            and entry.state is ConfigEntryState.LOADED
            and coordinator.ha_token_valido
        ):
            try:
                contratti = await coordinator.async_contratti_account()
            except (AuthError, ApiError, UpdateFailed, ConfigEntryAuthFailed):
                _LOGGER.debug("Elenco contratti dal coordinator non riuscito, provo nuovo accesso")
            else:
                return Accesso(entry.data.get(CONF_ID_UTENTE), contratti)
        return await async_accedi(self.hass, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self.config_entry
        if self._accesso is None:
            try:
                self._accesso = await self._async_leggi_contratti(entry)
            except (AuthError, ApiError) as err:
                return self.async_abort(
                    reason=errore_accesso(err), description_placeholders={"messaggio": str(err)}
                )

        configurati = {c["contratto"]: c for c in entry.data.get(CONF_CONTRATTI) or []}
        # Contracts no longer on the account stay in the list, so they can be removed.
        disponibili = self._accesso.supportati + [
            c
            for numero, c in configurati.items()
            if numero not in {d["contratto"] for d in self._accesso.supportati}
        ]
        errors: dict[str, str] = {}
        if user_input is not None:
            scelti = set(user_input[CONF_CONTRATTI])
            if scelti:
                rimossi = set(configurati) - scelti
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={
                        **entry.data,
                        CONF_CONTRATTI: [c for c in disponibili if c["contratto"] in scelti],
                    },
                )
                if rimossi:
                    self._rimuovi_dispositivi(entry, rimossi)
                self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_create_entry(data=dict(entry.options))
            errors["base"] = "nessuna_scelta"
        return self.async_show_form(
            step_id="init",
            data_schema=schema_contratti(
                self.hass.config.language, disponibili, list(configurati)
            ),
            errors=errors,
        )

    def _rimuovi_dispositivi(self, entry: ConfigEntry, rimossi: set[str]) -> None:
        registro_dispositivi = dr.async_get(self.hass)
        registro_entita = er.async_get(self.hass)
        identificatori = {(DOMAIN, numero) for numero in rimossi}
        for dispositivo in list(
            dr.async_entries_for_config_entry(registro_dispositivi, entry.entry_id)
        ):
            if not (dispositivo.identifiers & identificatori):
                continue
            for entita in er.async_entries_for_device(
                registro_entita, dispositivo.id, include_disabled_entities=True
            ):
                if entita.config_entry_id == entry.entry_id:
                    registro_entita.async_remove(entita.entity_id)
            registro_dispositivi.async_remove_device(dispositivo.id)
