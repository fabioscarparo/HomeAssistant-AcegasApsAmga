"""Calendar platform: self-reading windows and unpaid bill due dates."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import letture as lt
from .const import DOMAIN, NOME_INTEGRAZIONE, PORTALE_ORIGIN
from .coordinator import AcegasCoordinator, DatiContratto
from .sensor import PAGINE_CONSUMI
from .testi import testo


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: AcegasCoordinator = entry.runtime_data
    async_add_entities(
        AcegasCalendarioEntity(coordinator, contratto) for contratto in coordinator.contratti
    )


class AcegasCalendarioEntity(CoordinatorEntity[AcegasCoordinator], CalendarEntity):
    """Calendar of self-reading windows and open bill due dates for a contract."""

    _attr_has_entity_name = True
    _attr_translation_key = "calendario"

    def __init__(self, coordinator: AcegasCoordinator, contratto: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._contratto = contratto
        self._servizio = contratto["servizio"]
        numero = contratto["contratto"]
        self._attr_unique_id = f"{numero}_calendario"
        lingua = coordinator.lingua
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, numero)},
            name=f"{testo(lingua, f'servizio_{self._servizio}')} {coordinator.codice(contratto)}",
            manufacturer=NOME_INTEGRAZIONE,
            model=testo(lingua, f"modello_{self._servizio}"),
            model_id=contratto.get("modello"),
            serial_number=contratto.get("contatore"),
            configuration_url=f"{PORTALE_ORIGIN}/{PAGINE_CONSUMI.get(self._servizio, '')}",
        )

    @property
    def _dati(self) -> DatiContratto | None:
        return (self.coordinator.data or {}).get(self._contratto["contratto"])

    @property
    def available(self) -> bool:
        return self._dati is not None

    def _eventi(self) -> list[CalendarEvent]:
        dati = self._dati
        if dati is None:
            return []
        lingua = self.coordinator.lingua
        servizio = testo(lingua, f"servizio_{self._servizio}")
        codice = self.coordinator.codice(self._contratto)
        numero = self._contratto["contratto"]

        eventi: list[CalendarEvent] = []
        visti: set[tuple[str, date, date]] = set()

        finestre = list(dati.calendario_autoletture)
        if dati.finestra and dati.finestra.get("inizio"):
            finestre.append(dati.finestra)
        for finestra in finestre:
            inizio_iso = finestra.get("inizio")
            if not inizio_iso:
                continue
            try:
                inizio = date.fromisoformat(inizio_iso)
                fine_incluso = (
                    date.fromisoformat(finestra["fine"]) if finestra.get("fine") else inizio
                )
            except ValueError:
                continue
            if fine_incluso < inizio:
                fine_incluso = inizio
            fine_escluso = fine_incluso + timedelta(days=1)
            chiave = ("autolettura", inizio, fine_escluso)
            if chiave in visti:
                continue
            visti.add(chiave)
            eventi.append(
                CalendarEvent(
                    start=inizio,
                    end=fine_escluso,
                    summary=testo(lingua, "evento_autolettura", servizio=servizio, codice=codice),
                    description=testo(lingua, "evento_autolettura_desc", contratto=numero),
                )
            )

        for bolletta in dati.bollette:
            if not bolletta.da_pagare or bolletta.scadenza is None:
                continue
            inizio = bolletta.scadenza
            fine_escluso = inizio + timedelta(days=1)
            chiave = (f"bolletta_{bolletta.numero}", inizio, fine_escluso)
            if chiave in visti:
                continue
            visti.add(chiave)
            importo = f"{bolletta.residuo:.2f}"
            eventi.append(
                CalendarEvent(
                    start=inizio,
                    end=fine_escluso,
                    summary=testo(lingua, "evento_bolletta", servizio=servizio, importo=importo),
                    description=testo(
                        lingua,
                        "evento_bolletta_desc",
                        numero=bolletta.numero,
                        importo=importo,
                    ),
                )
            )

        eventi.sort(key=lambda e: (e.start, e.end, e.summary))
        return eventi

    @property
    def event(self) -> CalendarEvent | None:
        oggi = dt_util.now(lt.FUSO).date()
        for evento in self._eventi():
            if isinstance(evento.end, date) and evento.end > oggi:
                return evento
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        inizio_req = start_date.astimezone(lt.FUSO).date()
        fine_req = end_date.astimezone(lt.FUSO).date()
        return [
            ev
            for ev in self._eventi()
            if isinstance(ev.start, date)
            and isinstance(ev.end, date)
            and ev.start <= fine_req
            and ev.end > inizio_req
        ]
