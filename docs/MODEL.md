# Model and provenance

## Data

Source: FlyEM male CNS v1.0, the public `flat-connectome` files in
`https://storage.googleapis.com/flyem-male-cns/`.

The source graph is real anatomical reconstruction data. Frankenfly retains
neurons marked `Traced`, excludes glia, retains pairs with at least three
synapses, and derives each presynaptic sign from predicted neurotransmitter.
Acetylcholine is excitatory. GABA, glutamate and histamine are inhibitory.
Monoamines and unknown neurotransmitters have zero fast weight in this model.
This simplified sign convention is not a receptor-specific physiological model.

The graph has 165,122 neurons and 10,228,000 **nonzero directed weighted edges**.
Edges aggregate synapse counts; this number is not the total number of
individual anatomical synapses. Connectivity is represented as CSC: columns
are presynaptic sources, rows are postsynaptic targets.

The importer uses sorted body-ID lookup and streams Arrow record batches.
It does not allocate arrays indexed by the largest EM segment identifier.
Each source object is checked against its expected MD5, and the processed
graph is SHA-256 checked against the local build manifest when the app loads.
The source checksums are pinned to the publicly listed bucket objects
inspected on 2026-09-11. They check file integrity, not scientific correctness.

## Observation windows

Each observation starts all numerical neurons at -52 mV. It runs 60 steps of
0.2 ms each: 12 ms of simulated neural time. Threshold is -45 mV, membrane
time constant is 20 ms, refractory period is 2.2 ms, and each presynaptic spike
adds `0.275 mV × anatomical synapse count × presynaptic sign` to its targets.
Sensory events are sampled as Poisson inputs, as in the upstream model.

The integrator preserves state within a window, and the RNG evolves between
windows. Membrane and refractory state reset at the next observation. This
matches the upstream per-frame integration pattern. A continuously integrated
variant was tried locally, but in this arena it often silenced or saturated
the selected motor readouts. v0.1 therefore explicitly uses observation windows.
This choice is disclosed in the interface and telemetry. It does not represent
continuous cognition, memory or learning.

## Sensory interface

L1 and L2 input neurons use their measured retinotopic hex coordinates. An
engineered egocentric ground-plane view maps these into arena luminance:
bright increments feed L1, complementary luminance feeds L2. These are simple
static luminance channels rather than a complete fly visual system. The cat
mascot, labels, decorative grid and neural panel are not fed into the eye.

Light raises luminance locally. Shadow creates a pulsating dark region.
The synthetic scent control injects a distance-dependent pulse into neurons
whose type is annotated `ORN…`. It is neither a validated banana odor nor a
receptor-specific chemical encoding. Its concentration-to-rate mapping is an
engineering choice. No direct movement command comes from stimulus location.

## Body adapter

| Neural population | Engineered output |
| --- | --- |
| DNa02 right minus left | Angular velocity |
| Mean DNa01 firing | Forward drive |
| Mean MDN firing | Reverse drive |
| Mean DNp09 firing | Reduces translation |

The body is a 2D kinematic avatar with circle-versus-obstacle collision checks.
It does not model cat anatomy, gait, muscles, fly biomechanics or an actual
robot. The sprite points in the body's heading; wing/gait animation is not
additional neural output.

Movement is determined by the measured model output followed by this fixed
adapter. There is no target-seeking rule, hidden AI agent, random-walk fallback,
or scripted escape from walls. Awkward, reverse or stationary behavior is a
valid outcome, not proof of failure or intelligence. No success at learning,
navigation or biological replication is claimed.

At the default eight world steps per target wall second, each world step is
0.125 world seconds but only 0.012 neural seconds. If compute is slower than
the target rate, the world runs slower; the UI independently reports neural
time and computation time. Rendering interpolates measured body positions.

## Telemetry and persistence

Neuron counts and spikes are computed across the full graph. The scatter plot
shows a deterministic sample of up to 1,800 neurons at their measured soma
positions, projected into two dimensions. The sample positions are not random
decorative dots, and the plotted firing values come from the same model window
that drives movement. Rates refer to simulated time.

World position, stimuli, traces, RNG state, last-window arrays and accumulated
step count are checkpointed atomically every 60 seconds and on graceful exit.
The graph fingerprint must match before restoring. No learned weights are
saved because v0.1 does not implement learning. A restart between checkpoints
can lose up to approximately one minute of session progress.

## Upstream relationship

Frankenfly adapts the graph construction, numerical LIF approach and retina /
descending-neuron mapping from `fruitflydev/flycoinrh`. It does not use its
wallet, browser, token-launch automation or novelty-based learning module.
Retain LICENSE and NOTICE when redistributing code or processed data.
