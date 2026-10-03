from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

# Mapping APID -> canal spectral MSU-MR REELLEMENT diffuse en LRPT (recherche du
# 16/08/2026, recoupee sur plusieurs sources) : le LRPT ne diffuse que 3 des 6 canaux de
# l'instrument, et le choix varie SELON LE SATELLITE (le HRPT bande L, F6, diffuse le jeu
# complet). L'APID 70 est de la TELEMETRIE (position, etc.), PAS un canal image - corrige
# une premiere hypothese erronee (une source anterieure l'annoncait comme canal IR
# thermique, infirmee par recoupement, cf. `telemetry/onboard_time.py`).
# - METEOR-M2 3 (satellite cible pour la tentative de capture du 16/08/2026) : canaux
#   1,2,4 -> APID 64,65,67 (confirme explicitement).
# - METEOR-M2 / M2-2 : canaux 1,2,~5 -> APID 64,65,~66 ou ~68 selon les sources
#   (moins confirme, sources partiellement contradictoires sur le 3e canal).
METEOR_LRPT_APID_CHANNELS = {
    64: "canal 1 (0.5-0.7 um, visible) - actif sur tous les Meteor-M LRPT",
    65: "canal 2 (0.7-1.1 um, proche IR) - actif sur tous les Meteor-M LRPT",
    67: "canal 4 - actif sur METEOR-M2 3",
    66: "canal possible sur METEOR-M2/M2-2 (non confirme avec certitude)",
    68: "canal possible sur METEOR-M2/M2-2 (non confirme avec certitude)",
}


def align_channel_heights(
    channels: list[NDArray[np.uint16]],
) -> list[NDArray[np.uint16]]:
    if not channels:
        raise ValueError("channels ne doit pas etre vide")
    if any(channel.ndim != 2 for channel in channels):
        raise ValueError("chaque canal doit etre une image 2D (lignes x colonnes)")

    min_height = min(channel.shape[0] for channel in channels)
    if min_height == 0:
        raise ValueError("au moins un canal est vide (0 ligne)")
    return [channel[:min_height, :] for channel in channels]


def normalize_channel(
    channel: NDArray[np.uint16],
    low_percentile: float = 1.0,
    high_percentile: float = 99.0,
) -> NDArray[np.uint8]:
    if not 0.0 <= low_percentile < high_percentile <= 100.0:
        raise ValueError(f"percentiles invalides : low={low_percentile}, high={high_percentile}")

    low = np.percentile(channel, low_percentile)
    high = np.percentile(channel, high_percentile)
    if high <= low:
        return np.zeros(channel.shape, dtype=np.uint8)

    stretched = np.clip((channel.astype(np.float64) - low) / (high - low), 0.0, 1.0)
    result: NDArray[np.uint8] = (stretched * 255.0).astype(np.uint8)
    return result


def compose_rgb(
    red: NDArray[np.uint16],
    green: NDArray[np.uint16],
    blue: NDArray[np.uint16],
    normalize: bool = True,
) -> NDArray[np.uint8]:
    aligned_red, aligned_green, aligned_blue = align_channel_heights([red, green, blue])

    common_width = min(aligned_red.shape[1], aligned_green.shape[1], aligned_blue.shape[1])
    if common_width == 0:
        raise ValueError("largeur de canal nulle apres alignement")

    aligned_red = aligned_red[:, :common_width]
    aligned_green = aligned_green[:, :common_width]
    aligned_blue = aligned_blue[:, :common_width]

    if normalize:
        red_u8 = normalize_channel(aligned_red)
        green_u8 = normalize_channel(aligned_green)
        blue_u8 = normalize_channel(aligned_blue)
    else:
        red_u8 = aligned_red.astype(np.uint8)
        green_u8 = aligned_green.astype(np.uint8)
        blue_u8 = aligned_blue.astype(np.uint8)

    return np.dstack([red_u8, green_u8, blue_u8])


def compose_from_channel_map(
    channels: dict[int, NDArray[np.uint16]],
    red_apid: int,
    green_apid: int,
    blue_apid: int,
    normalize: bool = True,
) -> NDArray[np.uint8]:
    missing = [apid for apid in (red_apid, green_apid, blue_apid) if apid not in channels]
    if missing:
        raise ValueError(f"APID(s) manquant(s) dans channels : {missing}")

    return compose_rgb(
        channels[red_apid], channels[green_apid], channels[blue_apid], normalize=normalize
    )
