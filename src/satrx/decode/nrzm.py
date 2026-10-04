from __future__ import annotations

# Decodage differentiel NRZ-M (Non-Return-to-Zero Mark) applique au flux de bits
# LRPT Meteor-M apres decision QPSK et avant la recherche de l'ASM.
#
# Convention NRZ-M : un '1' produit une transition, un '0' ne produit pas de transition.
# Encodage (emetteur) : encoded[i] = encoded[i-1] XOR data[i]
# Decodage (recepteur) : decoded[i] = encoded[i] XOR encoded[i-1]
#
# Consequence pour la synchro de trame : le motif ASM 0x1ACFFC1D se trouve dans le flux
# APRES le decodage NRZ-M. Sans ce decodage, l'ASM n'est pas retrouvable.
# Reference : SatDump + artlav/meteor_decoder (session 16/08/2026).


def nrzm_decode(bits: list[int]) -> list[int]:
    """Decodage differentiel NRZ-M sur un flux de bits.

    Le premier bit est conserve tel quel (valeur de reference inconnue) ; tous
    les suivants sont calcules par XOR consecutif. Pour LRPT Meteor-M, ce premier
    bit est ambigu : la periodicite de l'ASM permet de detecter les bons frames
    independamment de cette valeur initiale.

    Args:
        bits: liste de bits (0 ou 1) issus de la decision QPSK.

    Returns:
        Liste de bits differentiellement decodes, meme longueur que l'entree.

    Raises:
        ValueError: si bits est vide.
    """
    if not bits:
        raise ValueError("bits ne doit pas etre vide")
    decoded = [0] * len(bits)
    decoded[0] = bits[0]
    for i in range(1, len(bits)):
        decoded[i] = bits[i] ^ bits[i - 1]
    return decoded


def nrzm_encode(data: list[int]) -> list[int]:
    """Encodage differentiel NRZ-M (inverse de nrzm_decode).

    Utile pour les tests de reversibilite et la generation de cas de test.

    Args:
        data: liste de bits de donnees (0 ou 1).

    Returns:
        Liste de bits encodes NRZ-M, meme longueur que l'entree.

    Raises:
        ValueError: si data est vide.
    """
    if not data:
        raise ValueError("data ne doit pas etre vide")
    encoded = [0] * len(data)
    encoded[0] = data[0]
    for i in range(1, len(data)):
        encoded[i] = encoded[i - 1] ^ data[i]
    return encoded
