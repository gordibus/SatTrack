from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

# Polynomes generateurs NASA/CCSDS pour un code convolutionnel de rendement 1/2, longueur
# de contrainte K=7 (171, 133 en octal). Valeurs confirmees pour Meteor-M LRPT (recherche
# du 16/08/2026, recoupees sur deux sources independantes) : G1=0x79, G2=0x5B = (171, 133) octal.
DEFAULT_POLYNOMIALS = (0o171, 0o133)
DEFAULT_CONSTRAINT_LENGTH = 7


def convolutional_encode(
    bits: list[int],
    polynomials: tuple[int, ...] = DEFAULT_POLYNOMIALS,
    constraint_length: int = DEFAULT_CONSTRAINT_LENGTH,
) -> list[int]:
    if constraint_length < 2:
        raise ValueError(f"constraint_length doit etre >= 2, recu {constraint_length}")
    if not polynomials:
        raise ValueError("polynomials ne doit pas etre vide")
    if any(bit not in (0, 1) for bit in bits):
        raise ValueError("bits doit contenir uniquement des 0 et des 1")

    history = [0] * (constraint_length - 1)
    encoded: list[int] = []
    for bit in bits:
        window = [bit] + history
        for poly in polynomials:
            parity = 0
            for i, tap in enumerate(window):
                if (poly >> (constraint_length - 1 - i)) & 1:
                    parity ^= tap
            encoded.append(parity)
        history = window[:-1]
    return encoded


def _state_to_bits(state: int, n_bits: int) -> list[int]:
    return [(state >> (n_bits - 1 - i)) & 1 for i in range(n_bits)]


def _bits_to_state(bits: list[int]) -> int:
    state = 0
    for bit in bits:
        state = (state << 1) | bit
    return state


def _build_transition_table(
    polynomials: tuple[int, ...], constraint_length: int
) -> dict[int, dict[int, tuple[int, list[int]]]]:
    n_memory = constraint_length - 1
    num_states = 1 << n_memory
    table: dict[int, dict[int, tuple[int, list[int]]]] = {}

    for state in range(num_states):
        history = _state_to_bits(state, n_memory)
        table[state] = {}
        for input_bit in (0, 1):
            window = [input_bit] + history
            outputs = []
            for poly in polynomials:
                parity = 0
                for i, tap in enumerate(window):
                    if (poly >> (constraint_length - 1 - i)) & 1:
                        parity ^= tap
                outputs.append(parity)
            next_state = _bits_to_state(window[:-1])
            table[state][input_bit] = (next_state, outputs)
    return table


def _build_trellis_arrays(
    polynomials: tuple[int, ...], constraint_length: int
) -> tuple[NDArray[np.int64], NDArray[np.int64], NDArray[np.int64]]:
    # Un treillis binaire convolutionnel rendement 1/n a exactement 2 predecesseurs par
    # etat (l'etat suivant est forme du bit d'entree suivi des (n_memory-1) premiers bits
    # de l'historique precedent, donc pour un etat suivant donne, seul le dernier bit de
    # l'historique precedent varie). Precalculer cette relation "par etat suivant" permet
    # de vectoriser tout le pas de mise a jour du treillis avec numpy (plus de boucle
    # Python sur les etats), ce qui est necessaire pour decoder un enregistrement reel de
    # plusieurs minutes (des millions de symboles).
    n_memory = constraint_length - 1
    num_states = 1 << n_memory
    rate = len(polynomials)
    table = _build_transition_table(polynomials, constraint_length)

    pred_state = np.zeros((num_states, 2), dtype=np.int64)
    pred_input = np.zeros((num_states, 2), dtype=np.int64)
    pred_output = np.zeros((num_states, 2, rate), dtype=np.int64)
    fill_count = [0] * num_states

    for state in range(num_states):
        for input_bit in (0, 1):
            next_state, outputs = table[state][input_bit]
            slot = fill_count[next_state]
            pred_state[next_state, slot] = state
            pred_input[next_state, slot] = input_bit
            pred_output[next_state, slot] = outputs
            fill_count[next_state] += 1

    return pred_state, pred_input, pred_output


def viterbi_decode(
    received_bits: list[int],
    polynomials: tuple[int, ...] = DEFAULT_POLYNOMIALS,
    constraint_length: int = DEFAULT_CONSTRAINT_LENGTH,
) -> list[int]:
    if constraint_length < 2:
        raise ValueError(f"constraint_length doit etre >= 2, recu {constraint_length}")
    if not polynomials:
        raise ValueError("polynomials ne doit pas etre vide")
    rate = len(polynomials)
    if len(received_bits) % rate != 0:
        raise ValueError(
            f"received_bits doit avoir une longueur multiple de {rate} (rendement 1/{rate}), "
            f"recu {len(received_bits)}"
        )
    if not received_bits:
        raise ValueError("received_bits ne doit pas etre vide")

    n_memory = constraint_length - 1
    num_states = 1 << n_memory
    pred_state, pred_input, pred_output = _build_trellis_arrays(polynomials, constraint_length)

    received = np.array(received_bits, dtype=np.int64).reshape(-1, rate)
    n_symbols = received.shape[0]

    path_metric = np.full(num_states, np.inf)
    path_metric[0] = 0.0

    backtrack_prev = np.zeros((n_symbols, num_states), dtype=np.int64)
    backtrack_input = np.zeros((n_symbols, num_states), dtype=np.int64)

    for t in range(n_symbols):
        symbol = received[t]
        branch_metric = np.count_nonzero(pred_output != symbol, axis=2)
        candidates = path_metric[pred_state] + branch_metric
        choose_first = candidates[:, 0] <= candidates[:, 1]

        path_metric = np.where(choose_first, candidates[:, 0], candidates[:, 1])
        backtrack_prev[t] = np.where(choose_first, pred_state[:, 0], pred_state[:, 1])
        backtrack_input[t] = np.where(choose_first, pred_input[:, 0], pred_input[:, 1])

    best_final_state = int(np.argmin(path_metric))
    if np.isinf(path_metric[best_final_state]):
        raise ValueError("aucun chemin valide trouve dans le treillis (flux recu incoherent)")

    decoded = [0] * n_symbols
    state = best_final_state
    for t in range(n_symbols - 1, -1, -1):
        decoded[t] = int(backtrack_input[t, state])
        state = int(backtrack_prev[t, state])

    return decoded
