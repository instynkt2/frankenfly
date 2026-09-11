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
- The native deployment on Hetzner started successfully, as recorded below.
  Public HTTPS/DNS and server-specific performance still need verification.
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
- The local build environment has no running systemd manager. Service startup
  was subsequently confirmed on the target host through operator-provided logs.
  Resource-limit enforcement has not been independently measured under load.

## Target-host deployment — operator-provided evidence

Console screenshots from 11 September 2026 confirm the native installation:

- Preflight passed with **3071 MiB available RAM** and a free localhost port 18080.
- The setup service completed successfully at **09:17:41 UTC**, after building
  the graph with the identical SHA-256 recorded above.
- systemd started the application on **127.0.0.1:18080**.
- At **09:17:45 UTC**, the readiness probe printed
  `Frankenfly health check passed`, followed by systemd's service-start confirmation.

This confirms model preparation and application readiness on the host. The
assistant did not have direct SSH access; these findings come from the
operator's console screenshots. The app is still bound to localhost. A public
URL, HTTPS, browser interaction and the impact on other workloads are not yet
verified. No token or wallet has been launched.

## Prepared subpath support

- Updated HTML and JavaScript URLs to stay within the page's mounted path.
- Two URL-resolution checks passed for `/` and `/frankenfly/`, using the real
  page references, static files and API routes. JavaScript syntax also passed.
- Three frontend-updater checks passed: backup and preservation of unrelated
  files, refusal to overwrite custom changes, and rollback after an I/O error.
- The updater's old/new SHA-256 values match the deployed baseline and the
  prepared frontend. It replaces only HTML/JavaScript and needs no app restart.
- Prepared a scoped Nginx location include. The target Nginx configuration has
  not yet been edited or reloaded; public path checks remain pending.

## Source repository

[instynkt2/frankenfly](https://github.com/instynkt2/frankenfly) contains the
application source, original mascot asset and deployment instructions.
Publishing source code does not deploy the application to Hetzner.
