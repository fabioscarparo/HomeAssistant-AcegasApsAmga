"""Sensors: one device per contract plus one account device.

Consumption for the Energy Dashboard lives in the external statistics. Meter
sensors have no state_class on purpose: otherwise Home Assistant would build a
second series, with a whole month on the hour the reading was downloaded.

Bill sensors show the whole bill, plus service-specific amounts from
companyServices when a bill groups multiple contracts.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import bollette as bl
from . import letture as lt
from . import rifiuti as rf
from .const import (
    DOMAIN,
    MAX_AUTOLETTURE_ATTRIBUTO,
    MAX_BOLLETTE_ATTRIBUTO,
    MAX_LETTURE_ATTRIBUTO,
    MAX_NOTIFICHE_ATTRIBUTO,
    MAX_PERIODI_ATTRIBUTO,
    MAX_SVUOTAMENTI_ATTRIBUTO,
    NOME_INTEGRAZIONE,
    PORTALE_ORIGIN,
    SERVIZIO_ACQUA,
    SERVIZIO_AMBIENTE,
    SERVIZIO_GAS,
    SERVIZIO_LUCE,
    SERVIZIO_TLR,
)
from .coordinator import AcegasCoordinator, DatiAccount, DatiContratto
from .statistics import unita_servizio
from .testi import testo

PAGINE_CONSUMI = {
    SERVIZIO_ACQUA: "usage/water/",
    SERVIZIO_GAS: "usage/gas/",
    SERVIZIO_LUCE: "usage/energy/",
    SERVIZIO_TLR: "usage/tlr/",
    SERVIZIO_AMBIENTE: "tcp/",
}

_ICONE_MEDIA = {
    SERVIZIO_GAS: "mdi:fire",
    SERVIZIO_LUCE: "mdi:lightning-bolt",
    SERVIZIO_TLR: "mdi:radiator",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: AcegasCoordinator = entry.runtime_data
    entita: list[SensorEntity] = []
    for contratto in coordinator.contratti:
        if contratto["servizio"] == SERVIZIO_AMBIENTE:
            classi: tuple[type[_SensoreContratto], ...] = (
                SvuotamentiRifiutiSensor,
                VolumeRifiutiSensor,
                DotazioniRifiutiSensor,
                BollettaSensor,
                DaPagareSensor,
                ScadenzaBollettaSensor,
                StatoBollettaSensor,
            )
        else:
            classi = (
                LetturaSensor,
                DataLetturaSensor,
                ConsumoPeriodoSensor,
                MediaGiornalieraSensor,
                AutoletturaSensor,
                BollettaSensor,
                DaPagareSensor,
                ScadenzaBollettaSensor,
                StatoBollettaSensor,
            )
        entita.extend(classe(coordinator, contratto) for classe in classi)

    entita.extend(
        [
            ScadenzaPasswordSensor(coordinator),
            NotificheSensor(coordinator),
        ]
    )
    async_add_entities(entita)


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

    def _configura_misura(self) -> None:
        unita, _ = unita_servizio(self._servizio, self._contratto.get("unita"))
        if self._servizio == SERVIZIO_ACQUA:
            self._attr_device_class = SensorDeviceClass.WATER
            self._attr_suggested_display_precision = 0
        elif self._servizio == SERVIZIO_GAS:
            self._attr_device_class = SensorDeviceClass.GAS
        else:
            self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_native_unit_of_measurement = unita


class LetturaSensor(_SensoreContratto):
    """Last real reading. 'statistic_id' and 'pod' tell the cards which series
    to read; 'letture' lists the latest readings for the cards and is not
    recorded."""

    chiave = "lettura"
    _unrecorded_attributes = frozenset({"letture", "vas"})

    def __init__(self, coordinator: AcegasCoordinator, contratto: dict[str, Any]) -> None:
        super().__init__(coordinator, contratto)
        self._configura_misura()

    @property
    def _ultima(self) -> lt.Lettura | None:
        return self._dati.ultima_reale if self._dati else None

    @property
    def native_value(self) -> float | None:
        return self._ultima.valore if self._ultima else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        ultima = self._ultima
        recenti = list(reversed(self._dati.letture))[:MAX_LETTURE_ATTRIBUTO] if self._dati else []
        vas = self._dati.vas if self._dati else []
        letture_attr = []
        for l in recenti:
            voce: dict[str, Any] = {
                "giorno": l.giorno.isoformat(),
                "valore": l.valore,
                "tipo": l.tipo,
            }
            if l.stato is not None:
                voce["stato"] = l.stato
            if l.fasce:
                voce["fasce"] = dict(l.fasce)
            letture_attr.append(voce)

        attributi: dict[str, Any] = {
            "giorno": ultima.giorno.isoformat() if ultima else None,
            "canale": ultima.canale if ultima else None,
            "contatore": ultima.contatore if ultima else None,
            "pod": self.coordinator.codice(self._contratto),
            "statistic_id": self.coordinator.statistic_id(self._contratto),
            "servizio": self._servizio,
            "letture": letture_attr,
        }
        if ultima and ultima.fasce:
            attributi["fasce"] = dict(ultima.fasce)
        for campo in (
            "attivazione",
            "uso",
            "mercato",
            "installazione",
            "calibro",
            "distributore",
            "tipo_contatore",
            "potenza",
            "teleletto",
            "autolettura_disponibile",
            "domiciliato",
            "bolletta_web",
        ):
            if campo in self._contratto:
                attributi[campo] = self._contratto[campo]
        if vas:
            attributi["vas"] = vas
            attributi["diario_consumi"] = any(
                str(v.get("id") or "").upper() == "AC"
                and str(v.get("stato") or "").lower() == "active"
                for v in vas
            )
        return attributi


class DataLetturaSensor(_SensoreContratto):
    """Day of the last real reading: the Energy Dashboard has data up to here."""

    chiave = "data_lettura"
    _attr_device_class = SensorDeviceClass.DATE

    @property
    def native_value(self) -> date | None:
        ultima = self._dati.ultima_reale if self._dati else None
        return ultima.giorno if ultima else None


class ConsumoPeriodoSensor(_SensoreContratto):
    """Consumption between the last two real readings. The 'periodi'
    attribute (every period between real readings) is for the cards and is not
    recorded."""

    chiave = "consumo_periodo"
    _unrecorded_attributes = frozenset({"periodi", "consumi_giornalieri"})

    def __init__(self, coordinator: AcegasCoordinator, contratto: dict[str, Any]) -> None:
        super().__init__(coordinator, contratto)
        self._configura_misura()

    @property
    def _periodo(self) -> dict[str, Any] | None:
        return self._dati.ultimo_periodo if self._dati else None

    @property
    def native_value(self) -> float | None:
        periodo = self._periodo
        return round(periodo["consumo"], 3) if periodo else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        periodo = self._periodo
        tutti = self._dati.periodi if self._dati else []
        periodi_attr = []
        for p in tutti[-MAX_PERIODI_ATTRIBUTO:]:
            voce: dict[str, Any] = {
                "dal": p["dal"].isoformat(),
                "al": p["al"].isoformat(),
                "giorni": p["giorni"],
                "consumo": round(p["consumo"], 3),
            }
            if p.get("fasce"):
                voce["fasce"] = dict(p["fasce"])
            periodi_attr.append(voce)

        attributi: dict[str, Any] = {
            "dal": periodo["dal"].isoformat() if periodo else None,
            "al": periodo["al"].isoformat() if periodo else None,
            "giorni": periodo["giorni"] if periodo else None,
            "periodi": periodi_attr,
        }
        if periodo and periodo.get("fasce"):
            attributi["fasce"] = dict(periodo["fasce"])
        if self._dati and self._dati.consumi_giornalieri:
            attributi["consumi_giornalieri"] = self._dati.consumi_giornalieri
        return attributi


class MediaGiornalieraSensor(_SensoreContratto):
    """Daily average of the last period: L/d (water), m³/d (gas), kWh/d or MWh/d."""

    chiave = "media_giornaliera"

    def __init__(self, coordinator: AcegasCoordinator, contratto: dict[str, Any]) -> None:
        super().__init__(coordinator, contratto)
        self._litri = self._servizio == SERVIZIO_ACQUA
        if self._litri:
            self._attr_native_unit_of_measurement = "L/d"
            self._attr_suggested_display_precision = 0
        else:
            unita, _ = unita_servizio(self._servizio, contratto.get("unita"))
            self._attr_native_unit_of_measurement = f"{unita}/d"
            self._attr_suggested_display_precision = 2
            if icona := _ICONE_MEDIA.get(self._servizio):
                self._attr_icon = icona

    @property
    def native_value(self) -> float | None:
        periodo = self._dati.ultimo_periodo if self._dati else None
        if periodo is None:
            return None
        media = periodo["media_giornaliera"]
        return round(media * 1000, 1) if self._litri else round(media, 4)


class AutoletturaSensor(_SensoreContratto):
    """First day of the current or next self-reading window."""

    chiave = "autolettura"
    _attr_device_class = SensorDeviceClass.DATE
    _unrecorded_attributes = frozenset({"autoletture"})

    def __init__(self, coordinator: AcegasCoordinator, contratto: dict[str, Any]) -> None:
        super().__init__(coordinator, contratto)
        if contratto.get("autolettura_disponibile") is False or contratto.get("teleletto") is True:
            self._attr_entity_registry_enabled_default = False

    @property
    def _finestra(self) -> dict[str, Any] | None:
        return self._dati.finestra if self._dati else None

    @property
    def native_value(self) -> date | None:
        finestra = self._finestra
        return date.fromisoformat(finestra["inizio"]) if finestra else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        finestra = self._finestra
        autoletture = self._dati.autoletture if self._dati else []
        ultima_auto = autoletture[-1] if autoletture else None

        if not finestra:
            attributi: dict[str, Any] = {"fine": None, "aperta": None, "giorni_mancanti": None}
        else:
            inizio = finestra.get("inizio")
            fine = finestra.get("fine")
            oggi = dt_util.now(lt.FUSO).date()
            if inizio and fine:
                d_inizio = date.fromisoformat(inizio)
                d_fine = date.fromisoformat(fine)
                aperta: bool | None = d_inizio <= oggi <= d_fine
                if aperta:
                    giorni_mancanti: int | None = 0
                elif d_inizio > oggi:
                    giorni_mancanti = (d_inizio - oggi).days
                else:
                    giorni_mancanti = finestra.get("giorni_mancanti")
            else:
                aperta = finestra.get("aperta")
                giorni_mancanti = finestra.get("giorni_mancanti")
            attributi = {
                "fine": fine,
                "aperta": aperta,
                "giorni_mancanti": giorni_mancanti,
            }

        if ultima_auto is not None:
            attributi["ultima_autolettura"] = ultima_auto.giorno.isoformat()
            attributi["stato_ultima_autolettura"] = ultima_auto.stato
            attributi["autoletture"] = [
                a.come_dict() for a in reversed(autoletture[-MAX_AUTOLETTURE_ATTRIBUTO:])
            ]
        return attributi


# --- Waste / TARI (ENVIRONMENT / TCP) sensors ---------------------------------


class _SensoreRifiuti(_SensoreContratto):
    @property
    def _rifiuti(self) -> rf.DatiRifiuti | None:
        return self._dati.rifiuti if self._dati else None


class SvuotamentiRifiutiSensor(_SensoreRifiuti):
    """Number of waste disposals in the current year."""

    chiave = "svuotamenti_rifiuti"
    _unrecorded_attributes = frozenset({"svuotamenti", "per_mese", "vantaggi"})

    @property
    def native_value(self) -> int | None:
        if self._rifiuti is None:
            return None
        return len(self._rifiuti.svuotamenti_anno_corrente)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rifiuti = self._rifiuti
        if rifiuti is None:
            return {"pod": self.coordinator.codice(self._contratto), "servizio": self._servizio}
        return {
            "pod": self.coordinator.codice(self._contratto),
            "servizio": self._servizio,
            "anno_precedente": len(rifiuti.svuotamenti_anno_precedente),
            "per_tipo": rifiuti.per_tipo(),
            "per_mese": rifiuti.per_mese(),
            "vantaggi": rifiuti.vantaggi,
            "svuotamenti": [
                s.come_dict() for s in rifiuti.svuotamenti_anno_corrente[:MAX_SVUOTAMENTI_ATTRIBUTO]
            ],
        }


class VolumeRifiutiSensor(_SensoreRifiuti):
    """Total waste volume conferred in the current year (litres)."""

    chiave = "volume_rifiuti"
    _attr_device_class = SensorDeviceClass.VOLUME
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_suggested_display_precision = 0

    @property
    def native_value(self) -> float | None:
        if self._rifiuti is None:
            return None
        return self._rifiuti.volume_totale_corrente

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rifiuti = self._rifiuti
        if rifiuti is None:
            return {}
        return {
            "anno_precedente": rifiuti.volume_totale_precedente,
            "per_tipo": rifiuti.per_tipo(),
        }


class DotazioniRifiutiSensor(_SensoreRifiuti):
    """Active waste equipment (bins, RFID cards, keys) assigned to the contract."""

    chiave = "dotazioni_rifiuti"
    _unrecorded_attributes = frozenset({"dotazioni"})

    @property
    def native_value(self) -> int | None:
        if self._rifiuti is None:
            return None
        return len(self._rifiuti.dotazioni_attive)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        rifiuti = self._rifiuti
        if rifiuti is None:
            return {}
        return {
            "totale": len(rifiuti.dotazioni),
            "dotazioni": [d.come_dict() for d in rifiuti.dotazioni],
        }


# --- Bill sensors -------------------------------------------------------------


class _SensoreBollette(_SensoreContratto):
    @property
    def _bollette(self) -> list[bl.Bolletta]:
        return self._dati.bollette if self._dati else []

    @property
    def _ultima(self) -> bl.Bolletta | None:
        return self._bollette[0] if self._bollette else None


class BollettaSensor(_SensoreBollette):
    """Amount of the newest bill. 'bollette' lists the latest bills and is
    not recorded."""

    chiave = "bolletta"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "EUR"
    _attr_suggested_display_precision = 2
    _unrecorded_attributes = frozenset({"bollette"})

    @property
    def native_value(self) -> float | None:
        return self._ultima.importo if self._ultima else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        ultima = self._ultima
        bollette_attr = []
        for b in self._bollette[:MAX_BOLLETTE_ATTRIBUTO]:
            voce: dict[str, Any] = {
                "numero": b.numero,
                "emissione": b.emissione.isoformat(),
                "scadenza": b.scadenza.isoformat() if b.scadenza else None,
                "importo": b.importo,
                "residuo": b.residuo,
                "stato": b.stato,
                "domiciliata": b.domiciliata,
            }
            if b.stato_dettaglio is not None:
                voce["stato_dettaglio"] = b.stato_dettaglio
            if b.bolletta_web is not None:
                voce["bolletta_web"] = b.bolletta_web
            if b.pdf_disponibile:
                voce["pdf_disponibile"] = True
            if b.data_pagamento is not None:
                voce["data_pagamento"] = b.data_pagamento.isoformat()
            if b.importi_servizi:
                voce["importi_servizi"] = dict(b.importi_servizi)
                voce["importo_servizio"] = b.importo_servizio(self._servizio)
            bollette_attr.append(voce)

        attributi: dict[str, Any] = {
            "servizio": self._servizio,
            "numero": ultima.numero if ultima else None,
            "emissione": ultima.emissione.isoformat() if ultima else None,
            "scadenza": ultima.scadenza.isoformat() if ultima and ultima.scadenza else None,
            "residuo": ultima.residuo if ultima else None,
            "domiciliata": ultima.domiciliata if ultima else None,
            "stato_dettaglio": ultima.stato_dettaglio if ultima else None,
            "bolletta_web": ultima.bolletta_web if ultima else None,
            "pdf_disponibile": ultima.pdf_disponibile if ultima else None,
            "data_pagamento": (
                ultima.data_pagamento.isoformat() if ultima and ultima.data_pagamento else None
            ),
            "importo_servizio": (
                ultima.importo_servizio(self._servizio) if ultima else None
            ),
            "bollette": bollette_attr,
        }
        return attributi


class DaPagareSensor(_SensoreBollette):
    """What is left to pay on the bills not paid yet, direct debits included."""

    chiave = "da_pagare"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "EUR"
    _attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        return bl.totale_da_pagare(self._bollette) if self._bollette else None


class ScadenzaBollettaSensor(_SensoreBollette):
    """Earliest due date of the bills still to pay; unknown when nothing is due."""

    chiave = "scadenza_bolletta"
    _attr_device_class = SensorDeviceClass.DATE

    @property
    def native_value(self) -> date | None:
        return bl.prossima_scadenza(self._bollette)


class StatoBollettaSensor(_SensoreBollette):
    """Payment status of the newest bill."""

    chiave = "stato_bolletta"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = bl.OPZIONI_STATO

    @property
    def native_value(self) -> str | None:
        return self._ultima.stato if self._ultima else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"stato_dettaglio": self._ultima.stato_dettaglio if self._ultima else None}


# --- Account-level sensors ----------------------------------------------------


class _SensoreAccount(CoordinatorEntity[AcegasCoordinator], SensorEntity):
    _attr_has_entity_name = True
    chiave: str

    def __init__(self, coordinator: AcegasCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.entry
        self._attr_unique_id = f"account_{entry.entry_id}_{self.chiave}"
        self._attr_translation_key = self.chiave
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"account_{entry.entry_id}")},
            name=f"{NOME_INTEGRAZIONE} ({entry.title})",
            manufacturer=NOME_INTEGRAZIONE,
            model=testo(coordinator.lingua, "modello_account"),
            configuration_url=PORTALE_ORIGIN,
        )

    @property
    def _account(self) -> DatiAccount:
        return self.coordinator.dati_account


class ScadenzaPasswordSensor(_SensoreAccount):
    """Password expiration date on the Servizi Online portal (180-day cycle)."""

    chiave = "scadenza_password"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> date | None:
        scadenza = self._account.scadenza_password
        return date.fromisoformat(scadenza) if scadenza else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        scadenza = self.native_value
        giorni = (scadenza - dt_util.now(lt.FUSO).date()).days if scadenza else None
        return {
            "giorni_rimanenti": giorni,
            "ultimo_cambio": self._account.cambio_password,
            "rinnovo_richiesto": self._account.rinnovo_password,
            "nuove_condizioni_accettate": self._account.nuove_condizioni_accettate,
        }


class NotificheSensor(_SensoreAccount):
    """Unread portal notifications and active service alerts (including water outages)."""

    chiave = "notifiche"
    _unrecorded_attributes = frozenset({"notifiche", "avvisi_configurati"})

    @property
    def native_value(self) -> int:
        return self._account.notifiche_non_lette

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        notifiche = self._account.notifiche[:MAX_NOTIFICHE_ATTRIBUTO]
        ultima = notifiche[0] if notifiche else None
        return {
            "totale": self._account.notifiche_totali,
            "ultima_notifica": ultima.get("titolo") if ultima else None,
            "data_ultima_notifica": ultima.get("data") if ultima else None,
            "avvisi_idrici_attivi": self._account.avvisi_idrici_attivi,
            "notifiche": notifiche,
            "avvisi_configurati": self._account.avvisi_configurati,
        }
