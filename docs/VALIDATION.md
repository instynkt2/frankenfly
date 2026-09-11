# Validation — 11 September 2026

## Executed

- Downloaded all three pinned FlyEM input files from the actual public bucket
  and verified their checksums. The corrected source path includes
  `connectome-data/flat-connectome/`.
- Built the complete graph: **165,122 traced neurons; 10,228,000 signed edges**.
- Ran eight focused tests: presynaptic-to-postsynaptic propagation, summation,
  inhibition, refractory/chunk behavior, sensory inputs, collision boundaries,
  stimulus lifetime, API authorization/validation and offline behavior.
- Ran the actual full-graph runtime through the HTTP application's in-process
  client: healthy status, geometry for 1,800 measured neuron positions, operator
  scent placement, pause, and graceful checkpoint saving all succeeded.
- JavaScript passed `node --check`; static asset references were checked.
- A 120-step full-connectome run exercised light, shadow and synthetic odor.

## Full-model benchmark

| Measurement | Observed |
| --- | ---: |
| Neural observations | 120 |
| Elapsed wall time | 18.423 seconds |
| Observations per wall second | 6.51 |
| Median compute per observation | 149.7 ms |
| Peak process RSS | 207.1 MiB |
| Motor observations with nonzero output | 120 / 120 |
| Total body travel | 624.38 world units |

Graph SHA-256:
`7c926458f24ffbe89c67dfd5900215d089d6bada7570fe374a68c6d9b2dfdcb3`

These measurements are from the build environment, not from a Hetzner plan.
Memory is peak process RSS reported by `resource.getrusage`; it does not include
the separate data-import process or Docker's image/filesystem storage.

The benchmark proves that the full numerical path executes and moves the body.
It does not prove learning, intelligent navigation, biological fidelity or
capacity for a large public audience.

## Pending environment checks

- Docker Engine is not installed in the build environment, so the Docker
  image/Compose stack has not been executed here. Native Python and the real
  application runtime were tested.
- No Hetzner server was connected or changed. HTTPS/DNS and server-specific
  performance still need verification on the target host.
- Interactive browser/visual and WebMCP testing were not performed. The
  interface's HTML, local assets and JavaScript syntax were checked.

## Native shared-server installer

- Four additional focused checks passed: existing installation preservation,
  exclusive unit-file writes, archive traversal rejection and symlink rejection.
- Both generated service files passed systemd 255 syntax verification (the
  runtime interpreter path was substituted for the locally present Python).
  The exact setup service also passed verification without substitution.
- Downloaded and safely extracted the real pinned GitHub source archive.
- Created a fresh venv without ensurepip and successfully bootstrapped the
  SHA-256-verified pip 25.0.1 wheel inside it, without changing system Python.
- Rebuilt the full graph from the verified source data: **1301.8 MiB peak RSS**,
  with the identical graph SHA-256 recorded above. Peak RSS is not a measured
  cgroup memory limit.
- The environment has no running systemd manager, so actual DynamicUser,
  cgroup enforcement and native service startup remain target-host checks.

## Source repository

[instynkt2/frankenfly](https://github.com/instynkt2/frankenfly) contains the
application source, original mascot asset and deployment instructions.
Publishing source code does not deploy the application to Hetzner.
