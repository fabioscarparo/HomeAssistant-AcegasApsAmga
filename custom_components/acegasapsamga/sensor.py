"""Sensors, one device per contract.

Consumption for the Energy Dashboard lives in the external statistics. These
sensors have no state_class on purpose: otherwise Home Assistant would build a
second series, with a whole month on the hour the reading was downloaded.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import letture as lt
from .const import (
    DOMAIN,
    MAX_LETTURE_ATTRIBUTO,
    MAX_PERIODI_ATTRIBUTO,
    NOME_INTEGRAZIONE,
    PORTALE_ORIGIN,
    SERVIZIO_ACQUA,
)
from .coordinator import AcegasCoordinator, DatiContratto
from .testi import testo

PAGINE_CONSUMI = {SERVIZIO_ACQUA: "usage/water/", "GAS": "usage/gas/"}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: AcegasCoordinator = entry.runtime_data
    async_add_entities(
        classe(coordinator, contratto)
        for contratto in coordinator.contratti
        for classe in (
            LetturaSensor,
            DataLetturaSensor,
            ConsumoPeriodoSensor,
            MediaGiornalieraSensor,
            AutoletturaSensor,
        )
    )


class _SensoreContratto(CoordinatorEntity[AcegasCoordinator], SensorEntity):
    """Base sensor of a contract.

    It stays available while there is data, even saved data: a failed update
    keeps the last values instead of making them unknown.
    """

    _attr_has_entity_name = True
    chiave: str

    def __init__(self, coordinator: AcegasCoordinator, contratto: dict[str, Any]) -> None:
        super().__init__(coordinator)
        self._contratto = contratto
        self._servizio = contratto["servizio"]
        numero = contratto["contratto"]
        self._attr_unique_id = f"{numero}_{self.chiave}"
        self._attr_translation_key = self.chiave
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

    def _volume(self) -> None:
        acqua = self._servizio == SERVIZIO_ACQUA
        self._attr_device_class = SensorDeviceClass.WATER if acqua else SensorDeviceClass.GAS
        self._attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
        # Water meters are read in whole cubic metres.
        if acqua:
            self._attr_suggested_display_precision = 0


class LetturaSensor(_SensoreContratto):
    """Last real reading. 'statistic_id' and 'pod' tell the card which series
    to read; 'letture' lists the latest readings for the card and is not
    recorded."""

    chiave = "lettura"
    _unrecorded_attributes = frozenset({"letture"})

    def __init__(self, coordinator: AcegasCoordinator, contratto: dict[str, Any]) -> None:
        super().__init__(coordinator, contratto)
        self._volume()

    @property
    def _ultima(self) -> lt.Lettura | None:
        return lt.ultima_reale(self._dati.letture) if self._dati else None

    @property
    def native_value(self) -> float | None:
        return self._ultima.valore if self._ultima else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        ultima = self._ultima
        recenti = list(reversed(self._dati.letture))[:MAX_LETTURE_ATTRIBUTO] if self._dati else []
        return {
            "giorno": ultima.giorno.isoformat() if ultima else None,
            "canale": ultima.canale if ultima else None,
            "contatore": ultima.contatore if ultima else None,
            "pod": self.coordinator.codice(self._contratto),
            "statistic_id": self.coordinator.statistic_id(self._contratto),
            "letture": [
                {"giorno": l.giorno.isoformat(), "valore": l.valore, "tipo": l.tipo}
                for l in recenti
            ],
        }


class DataLetturaSensor(_SensoreContratto):
    """Day of the last real reading: the Energy Dashboard has data up to here."""

    chiave = "data_lettura"
    _attr_device_class = SensorDeviceClass.DATE

    @property
    def native_value(self) -> date | None:
        ultima = lt.ultima_reale(self._dati.letture) if self._dati else None
        return ultima.giorno if ultima else None


class ConsumoPeriodoSensor(_SensoreContratto):
    """Consumption between the last two real readings. The 'periodi'
    attribute (every period between real readings) is for the card and is not
    recorded."""

    chiave = "consumo_periodo"
    _unrecorded_attributes = frozenset({"periodi"})

    def __init__(self, coordinator: AcegasCoordinator, contratto: dict[str, Any]) -> None:
        super().__init__(coordinator, contratto)
        self._volume()

    @property
    def _periodo(self) -> dict[str, Any] | None:
        return lt.ultimo_periodo(self._dati.letture) if self._dati else None

    @property
    def native_value(self) -> float | None:
        periodo = self._periodo
        return round(periodo["consumo"], 3) if periodo else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        periodo = self._periodo
        tutti = lt.periodi(self._dati.letture) if self._dati else []
        return {
            "dal": periodo["dal"].isoformat() if periodo else None,
            "al": periodo["al"].isoformat() if periodo else None,
            "giorni": periodo["giorni"] if periodo else None,
            "periodi": [
                {
                    "dal": p["dal"].isoformat(),
                    "al": p["al"].isoformat(),
                    "giorni": p["giorni"],
                    "consumo": round(p["consumo"], 3),
                }
                for p in tutti[-MAX_PERIODI_ATTRIBUTO:]
            ],
        }


class MediaGiornalieraSensor(_SensoreContratto):
    """Daily average of the last period: litres for water, m³ for gas."""

    chiave = "media_giornaliera"

    def __init__(self, coordinator: AcegasCoordinator, contratto: dict[str, Any]) -> None:
        super().__init__(coordinator, contratto)
        self._litri = self._servizio == SERVIZIO_ACQUA
        self._attr_native_unit_of_measurement = "L/d" if self._litri else "m³/d"
        self._attr_suggested_display_precision = 0 if self._litri else 2

    @property
    def native_value(self) -> float | None:
        periodo = lt.ultimo_periodo(self._dati.letture) if self._dati else None
        if periodo is None:
            return None
        media = periodo["media_giornaliera"]
        return round(media * 1000, 1) if self._litri else round(media, 4)


class AutoletturaSensor(_SensoreContratto):
    """First day of the current or next self-reading window."""

    chiave = "autolettura"
    _attr_device_class = SensorDeviceClass.DATE

    @property
    def _finestra(self) -> dict[str, Any] | None:
        return self._dati.finestra if self._dati else None

    @property
    def native_value(self) -> date | None:
        finestra = self._finestra
        return date.fromisoformat(finestra["inizio"]) if finestra else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        finestra = self._finestra or {}
        return {"fine": finestra.get("fine"), "aperta": finestra.get("aperta")}
