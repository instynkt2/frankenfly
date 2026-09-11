"""Small deterministic circuits exercise direction, summation and state."""
import numpy as np
import scipy.sparse as sp
from frankenfly.brain import Brain


def circuit(edges, n=3):
    brain = Brain.__new__(Brain)
    brain.n = n
    # entries are (presynaptic, postsynaptic, weight)
    matrix = sp.csc_matrix(([e[2] for e in edges], ([e[1] for e in edges], [e[0] for e in edges])), shape=(n, n))
    brain.data, brain.indices, brain.indptr = matrix.data, matrix.indices, matrix.indptr
    brain.v = np.full(n, brain.rest, dtype=np.float32)
    brain.refr = np.zeros(n, np.int16)
    brain.rng = np.random.default_rng(99)
    brain.decay = np.float32(np.exp(-brain.dt_ms / brain.tau_ms))
    brain.refr_steps = 11
    brain.total_steps = 0
    brain.motor = {"readout": np.array([1])}
    return brain


def test_spikes_flow_from_source_to_target_and_sum():
    brain = circuit([(0, 1, 4), (2, 1, 4)])
    counts, _, _ = brain.advance(np.array([0, 2]), np.array([5000., 5000.]), steps=2)
    assert counts.tolist() == [1, 1, 1]
    assert brain.total_steps == 2


def test_inhibition_suppresses_target():
    excited = circuit([(0, 1, 9)])
    inhibited = circuit([(0, 1, 9), (2, 1, -12)])
    assert excited.advance([0], [5000], 2)[0][1] == 1
    assert inhibited.advance([0, 2], [5000, 5000], 2)[0][1] == 0


def test_state_persists_across_integrator_chunks_and_refractory_period():
    whole = circuit([(0, 1, 9)])
    chunks = circuit([(0, 1, 9)])
    c1 = whole.advance([0], [5000], 24)[0]
    c2 = chunks.advance([0], [5000], 12)[0] + chunks.advance([0], [5000], 12)[0]
    np.testing.assert_array_equal(c1, c2)
    np.testing.assert_allclose(whole.v, chunks.v)
    assert c1[0] <= 3  # repeated drive cannot bypass refractory behavior
