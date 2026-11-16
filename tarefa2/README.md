# UAV Routing Simulation — Core + Satellite Topology

This GrADySim simulation collects sensor data using a core of 9 UAVs
and **4 satellites** shuttling data between the core and the sensor field.

The core can use one of two topologies (`--topology`):

- `random` (default): the 9 core UAVs move randomly inside the obstacle area.
- `star`: the 9 core UAVs form a rotating hub + 8 rim wheel (the original design).

Each run selects one routing protocol globally:

- `flooding`: broadcasts each routing message once within the core with a strict TTL (8).
- `dtn`: Epidemic Routing (Vahdat & Becker, 2000). Nodes conduct anti-entropy sessions with peers to exchange missing messages.
- `geocasting`: GPSR-based geocasting. Greedy geographic forwarding toward the destination dock point, falling back to Perimeter Mode (right-hand rule on a Relative Neighborhood Graph) at local minima, and flooding inside the region (`GEOCAST_REGION_RADIUS`).
- `swcore`: SWarm Core routing (see the course paper, Algorithms 1 and 2). Each core node keeps a routing table per satellite: `direct` (docked here), a next-hop core node, or `unreachable`. A satellite connecting to or leaving its hub triggers a `reachable` / `unreachable` RT-update that is flooded over the core (a hub-and-spoke tree in the star topology, radio neighbours in the random one), ordered by a version stamp. Messages follow the table, are delivered when the destination satellite is `direct`, and otherwise wait in the core buffer until a `reachable` update arrives. The hub of the sending satellite acknowledges each upload, and an unacknowledged upload is re-sent at the next docking.

## Architecture

### Star topology (`--topology star`)

```
                    Sat-N (shuttles N axis)
                       |
Sat-W ── [Rim0..7 rotating @ 6°/s around Hub] ── Sat-E
                       |
                    Sat-S (shuttles S axis)
```

### Random topology (`--topology random`, default)

The 9 core UAVs are identical. Each flies random waypoints (gradysim
`RandomMobilityPlugin`) inside the obstacle zone square at fixed `FLIGHT_ALT`.
Start positions and waypoints are seeded (`RANDOM_SEED`). Satellites keep the same
state machine and docking handshake as in the star topology.

### Rules shared by both topologies

- **Speed:** all moving UAVs (satellites, rim, random core nodes) fly at a shared `UAV_SPEED = 5.0 m/s` (except the hub which is stationary).
- **Dock alignment:** a core UAV counts as aligned with a dock point when it is within
  `DOCK_RANGE` (= `COMM_RANGE`, 2-D distance) of it. This applies to hub, rim and random UAVs.

### Core, star topology (9 UAVs)
- **Hub** (1): stationary at obstacle center, acts as follow-mobility leader.
  Broadcasts its position every `CORE_BROADCAST_INTERVAL = 0.1 s`.
- **Rim** (8): orbit the hub at `CORE_RADIUS = 29.25 m`, 45° apart.
  Follow-mobility followers; each updates its relative offset every `CORE_SPIN_DT = 0.05 s`.
  Formation rotates counter-clockwise at `ROT_RATE_DEG = 6°/s` (one full rotation per 60 s).
  Rim nodes near a dock point (within `DOCK_RANGE`) can serve that dock.

### Satellites (4 UAVs — N, E, S, W)
Each satellite follows a 4-state cycle:
1. **COLLECT_OUT** – fly to outer turnaround point (`SAT_OUTER_DIST = 90 m`), collecting sensor data.
2. **COLLECT_IN** – fly back to its dock point (`DOCK_RADIUS = 34.25 m` from center).
3. **WAIT_ALIGN** – hover at dock, broadcast `dock_hello` every 0.25 s until an aligned core node replies.
4. **EXCHANGE** – upload packet bundle to the aligned core node; it floods/forwards to the destination dock;
   destination satellite receives `dock_deliver`. Timeout = 1 s.

Messages can go from any face to any other face (N to S, W or E; W to N, S or E; and so on). With `MESSAGE_DEST_MODE = "any"` (default) each upload picks one of the other three faces at random (seeded by `RANDOM_SEED`); `"opposite"` restores the old N↔S, E↔W behaviour.

## Key Parameters

| Parameter | Value | Notes |
|---|---|---|
| `COMM_RANGE` | 30.0 m | Radio range |
| `CORE_RADIUS` | 29.25 m | Hub-to-rim (< 30 m) |
| `CORE_RIM_NODES` | 8 | 45° spacing |
| `ROT_RATE_DEG` | 6.0 °/s | CCW, 60 s/revolution |
| `DOCK_RADIUS` | 34.25 m | Face dock point distance |
| `DOCK_RANGE` | 30.0 m | Distance tolerance for dock alignment (all topologies) = `COMM_RANGE` |
| `NUM_RANDOM_UAVS` | 9 | Core UAVs in the random topology |
| `RANDOM_SEED` | 2056 | Seed for random starts and waypoints |
| `SAT_OUTER_DIST` | 90.0 m | Turnaround distance |
| `SIMULATION_DURATION` | 300 s | ~13 satellite cycles |
| `UAV_SPEED` | 5.0 m/s | Movement speed for all moving UAVs |
| `DTN_SESSION_COOLDOWN` | 3.0 s | Cooldown between DTN epidemic sessions |
| `DTN_MAX_HOPS` | 6 | Max replications for a message in Epidemic Routing |
| `GEOCAST_REGION_RADIUS` | 30.0 m | Radius for geocast region flooding (= `DOCK_RANGE`) |
| `SWCORE_MAX_HOPS` | 8 | Hop limit for swcore forwarding |
| `MESSAGE_DEST_MODE` | `"any"` | Destination face of each upload: `"any"` other face, or `"opposite"` face |

Derived values logged at startup:
- Rim adjacent chord ≈ 22.36 m (< 30 m ✓)
- Tangential speed ≈ 3.08 m/s (star)
- Alignment period = 7.5 s (star)

## Pub/Sub configuration in tarefa2

Run from `tarefa2`:

```bash
python -m src.main --pubsub --no-viz
```

`--pubsub` forces `--topology star` and `--routing-strategy swcore`, including
when conflicting values are explicitly supplied. Without Pub/Sub activation,
the original defaults and explicit CLI selections are preserved.

All new parameters live in `utils/common/config.py`:

| Parameter | Default | Meaning |
|---|---|---|
| `PUBSUB_ENABLED` | `False` | Default activation; the CLI flag enables this run without mutating the module |
| `PUBSUB_TOPICS` | `("T1", "T2")` | Pub/Sub topic names |
| `PSPEER_SLOTS` | `(0, 3, 6)` | Rim slots, not simulator IDs; gaps of 3, 3 and 2 slots around the eight-node rim |
| `PUBSUB_SEED` | `2056` | Seed for independent core publication generators |
| `PUBSUB_PUBLICATION_INTERVAL` | `5.0` | Core publication interval in simulated seconds; finite and positive |
| `PUBSUB_SUBSCRIPTION_INTERVAL` | `5.0` | Dynamic subscription interval; finite and positive |

The mode selects star/SwCore and hosts an independent local `PSPeerService`
on each rim selected by `PSPEER_SLOTS` (default: 0, 3, 6). Each peer logs its
node ID and slot at INFO and uses `PSPEER_COLOR` (green) in the visualization.
Exactly three distinct valid rim slots are required. Network requests, peer
synchronization, sensor publications, core publication timers and dynamic
subscription timers are implemented.
The original mobility and sensor seeds remain unchanged. Setting
`PUBSUB_ENABLED=True` enables the same selection without the CLI flag.

## Environment setup

### Core Pub/Sub transport

With `--pubsub`, hub and rim protocols expose `send_pubsub(destination, envelope)`
and the receive hook `handle_pubsub(envelope, source_id)`. The adapter reuses
SwCore's radio unicast and beacon-based neighbor discovery: direct neighbor
first, otherwise the known hub. It supports the star core, including two-hop
rim-to-rim delivery, with per-instance transport IDs and duplicate suppression.
`PUBSUB_TRANSPORT_MAX_HOPS` bounds forwarding. Sending to self dispatches locally.

The return value indicates local dispatch or submission to the next hop, not
confirmed delivery. Without a known next hop it returns `False`. DELIVER for a
known unavailable satellite is retained in the existing SwCore buffer, with
separate Pub/Sub entries. Connected satellites use the SwCore route table and
radio unicast; no periodic retry or transmission acknowledgment is added.
Existing SwCore satellite traffic keeps its original routing and buffers.

Core clients select a single simulator node ID with `select_pspeer(node_id)`, then
call `subscribe_pubsub(topic, accepted_regions)`, `publish_pubsub(publication)`
and `fetch_pubsub(topic)`. Without a selected peer these calls return `False`.
The adapter processes requests only at PSPeers. FETCH returns eligible history
over the same radio transport using DELIVER, including an empty result; clients
receive it through `on_pubsub_delivery(envelope)`. Successful receipt is recorded
locally and reported by subsequent FETCH requests. There is no automatic peer discovery.
Satellite sensor collections
generate publications as described below. Request/response logs are
INFO; per-hop paths are DEBUG. `tests/test_pubsub_adapter.py` exercises this path.

### Core publication timers

With `--pubsub`, each hub/rim generates one publication per
`PUBSUB_PUBLICATION_INTERVAL`, starting one interval after initialization.
`CorePublicationMixin` uses its own `random.Random` seeded from PUBSUB_SEED and
node ID with a core-specific prefix. Each event randomly selects T1/T2 and a
numeric payload value in [0, 1), with region C, current simulation time and an ID
`core:<node_id>:<sequence>`. Streams reproduce for the same seed and node IDs,
independently of inter-node event ordering, without using the global RNG.

PSPeers initially publish to themselves; other core nodes receive only the actual
ID of the first configured PSPeer during scenario construction. No recipient list
is exposed to the publisher. Generation continues after an unsuccessful submission,
without buffering or retrying that publication. True means first-hop submission,
not receipt. Outside Pub/Sub mode these timers are absent, and satellites retain
their separate sensor-driven publications. `test_core_publications.py` covers
reproducibility, intervals, opt-in behavior and TF04 over radio with regional filters.

### Dynamic subscriptions

In Pub/Sub mode every core node and satellite runs `DynamicSubscriptionMixin`.
Starting after one `PUBSUB_SUBSCRIPTION_INTERVAL`, each event randomly chooses a
topic and a nonempty subset of N/S/E/W/C. It replaces only that topic's filter,
so both T1 and T2 can remain subscribed simultaneously. The RNG uses PUBSUB_SEED,
node ID and a subscriptions-specific prefix, independent of publication/mobility
streams. No timers are installed outside Pub/Sub mode.

Core nodes send SUBSCRIBE followed by FETCH when submission succeeds. Satellites
do the same during EXCHANGE; while away they retain the latest local filter per
topic and send it on contact through the existing resume path. Intermediate
offline filters are superseded, not queued as separate network updates.

FETCH includes the current local subscription along with received IDs. The peer
validates its topic/subscriber, applies the filter and queries history in one
request. This handles FETCH arriving before SUBSCRIBE at the same simulated time
or after a lost SUBSCRIBE, without introducing an ACK. Older wire requests without
the optional filter retain their prior behavior. Historical delivery follows the
new filter and excludes confirmed IDs; changing one filter preserves consumption
and the other topic's subscription. `test_dynamic_subscriptions.py` covers TF05,
history, filter changes, reproducibility and offline contacts.

### Subscription synchronization

A changed client subscription triggers one SYNC broadcast containing only that
delta. PSPeers apply newer versions; other core nodes discard it. Receivers do
not forward or acknowledge it. Identical subscriptions at the same responsible
peer cause no new send; rebinding to a different peer creates a new version.
Per-subscription ordering uses `(Lamport version, sender ID)` to reject duplicates
and delayed older updates and break concurrent ties deterministically. It does
not establish wall-clock recency. Version zero is legacy data and is not applied.

In Pub/Sub mode, the local `PubSubCommunicationHandler` uses
`PUBSUB_SYNC_RANGE = CORE_DIAMETER + 1.0` (59.5 m) for SYNC and REPLICATE broadcasts,
implementing the specification's core-wide radio assumption. Ordinary traffic
retains `COMM_RANGE = 30.0`; configured radio loss and delay still apply to both.
The installed simulator is unchanged. Broadcasts may physically reach nearby
non-core nodes, which ignore this message type. No global application registry
or hub relay participates in synchronization.

Lost updates leave replicas stale: there is no retry or repair, including when
the same client filter is submitted again unchanged. Consumption is not
synchronized. `test_subscription_sync.py` and `test_pubsub_sync_radio.py`
cover ordering, three replicas, duplicate packets, losses and radio isolation.

### Publication replication

Under the policy confirmed for stage 15, a PSPeer accepting a new PUBLISH stores
it and sends one REPLICATE broadcast to the other peers, separate from SYNC.
`ReplicateEnvelope` identifies the sending peer while preserving the original
publication (ID, topic, origin, timestamp and payload). Peers store received
copies without re-broadcasting; other nodes discard them. Storage deduplicates
by `message_id`, retaining the first copy received at each peer, even if a later
copy contains different data. Repeated PUBLISH of an existing ID sends no replica.

Replication includes publications regardless of current subscription filters;
FETCH still applies those filters. Losses can leave different histories and are
not repaired by ACK, retry or repeated PUBLISH. This does not synchronize read
state. `test_pubsub_replication.py` exercises publication
through A and radio queries through B/C, duplicates, partial/total loss and delay.

### Live delivery to subscribers

On first storage of a PUBLISH or REPLICATE, each peer sends individual DELIVER
messages to eligible subscribers whose current subscription version originated
at that peer. This assigns one responsible peer per subscription when replicas
agree, without exposing subscribers to the publisher. Received replicas never
trigger another REPLICATE. Repeated publication IDs do not trigger another push.

`DeliverEnvelope.is_push` distinguishes live deliveries from FETCH replies.
Clients accept delivery from the selected peer, check their local topic/region
filter and suppress repeated publication IDs for both push and FETCH before
invoking `on_pubsub_delivery`. IDs enter the receipt ledger only after the callback
returns successfully. Empty FETCH results still invoke the callback.

With `--pubsub`, satellites also expose the client API. Requests go through the
current contact node only during the existing EXCHANGE state; incoming application
deliveries are accepted only in that state. The core uses SwCore's `direct`/`hop`
routes learned through its original connect/disconnect messages. Pub/Sub does not
change movement, sensor uploads, departure timing, or the original dock deliveries.
Existing subscriptions are resent and FETCH runs automatically upon contact.
Dynamic filters are generated separately; departure timing is unchanged.

Losses and stale subscription replicas can cause missed delivery. Selecting a
different peer resends known subscriptions and fetches unread history (satellites
retry this on contact if currently offline). The accepting peer takes responsibility
with a new subscription version, even for an unchanged filter. `test_pubsub_push.py`
covers TF01–TF03, three responsible peers, a satellite
reached in three radio hops, duplicate push, disconnection and delivery loss.

### Reconnection and incremental consumption

`FetchEnvelope.received_ids` carries the client's confirmed IDs for that topic.
The consulted peer merges this report before querying unread history, retaining
IDs even if the publication replica has not yet arrived. The client keeps its
ledger across contacts and peer changes. This is client-carried confirmation,
not peer-wide read-state replication or a standalone ACK protocol. A peer that
has not received a report may still send an old item; the client suppresses it.
Lost reports are included again in the next FETCH, without periodic retries.

Pending satellite DELIVER packets share `_core_buffer` with SwCore under separate
keys and without `dest_face`; original dock delivery excludes them. Connect and
reachable-route callbacks flush them through Pub/Sub radio transport. Transport
state distinguishes `pending` from `submitted`; only the client ledger proves
receipt. A send removes a pending entry without implying consumption. FETCH can
recover lost transmissions from peer history; it cannot recover a publication
missing from that peer due to replication loss. Unknown satellite routes are not
invented, and client state is in memory, not persistent across process restarts.

`test_pubsub_reconnection.py` tests TF06 with exact IDs across repeated contacts,
peer change, lost delivery/report, buffer flushing and callback failure. Receipt
reports grow with topic history; bounded summaries are not implemented.

### Integrated scenario validation (stage 22)

Run the fixed 300-second audit from `tarefa2`:

```powershell
../.venv/Scripts/python.exe -B tests/check_integrated_scenario.py
```

It runs the actual main scenario and inspects observations only after the run:
three peers with equal publication/subscription copies, both topics and all five
regions, eligible nonduplicate application receipts, historical delivery and
multiple completed cycles for every satellite. The observer never supplies data
to protocols. Its success marker is `INTEGRATED_SCENARIO_OK`; it also saves an
ignored diagnostic snapshot of original traffic in `.cache/stage22-traffic.json`.
This is a fixed integration check, not the later metric/seed-sweep runner.

The stage-22 run completed 13 cycles each for N/E/S and 14 for W. The three peers
held 1,211 publications and 26 subscriptions; 14,749 unique subscriber/publication
receipts were observed, including 7,044 historical receipts. These are diagnostic
counts for this run, not final performance metrics or delivery guarantees.

A separate baseline comparison found **55 original uploads / 53 deliveries without
Pub/Sub**, versus **53 / 47 with Pub/Sub**. The original movement/dock rules remain
unchanged, but numerical equivalence is not established. GrADyS-SIM compares event
timestamps without a tie-breaker; adding events can reorder equal-time legacy
events (confirmed with a small isolated event-loop check). This is a plausible
mechanism for the difference, not an attribution of every differing delivery.
No dependency or scheduler modifications were made.

### Logging

Set `LOG_LEVEL` in `utils/common/config.py` before starting a run:

Subscription requests/synchronization, peer storage and history requests use
human-readable INFO messages. Duplicate replica-storage and synchronization lines
are consolidated into one event each. Submission means acceptance by the transport,
not confirmed destination receipt; failed submissions are explicitly identified.
SUBSCRIBE processing includes the topic and accepted origin regions.
Subscription creation and submission share one message, including the submission
result. Generic PUBLISH and FETCH completion lines are omitted. Local clients are
identified as Core Node or Satellite; peers refer to remote clients as subscribers
when their role is not available. Versions and receipt-ID counts remain in the
structured events rather than the human-readable text.
Pub/Sub INFO messages start with an event keyword, such as
`[SUBSCRIPTION_REQUEST]`, `[PUBLICATION_BROADCAST]`, `[SUBSCRIPTION_BROADCAST]`
or `[MESSAGE_RECEIVED]`. Each accepted publication has one textual
`[MESSAGE_RECEIVED]` line naming its origin, forwarding peer, topic, origin region
and accepted subscription regions. Batch receipt summaries are omitted;
`[HISTORY_RECEIVED]` reports history responses with no new matching messages.
Successful push submissions, ignored replicas and unchanged subscriptions use
DEBUG. Failed push submissions remain visible at INFO. Subscription submission
failures include the reason; disconnected satellites retain their latest filters
locally and resubmit them when contact starts.
History lookup and response submission share one `[HISTORY_RESPONSE]` message,
including the topic, the active subscription's origin-region filter, the message
count and whether submission succeeded. A missing subscription is stated explicitly.
The structured `history_requested` event is retained with `regions` and `submitted`
fields and is emitted after the response submission attempt.

Structured events retain `event`, `node`, `time` and event-specific IDs, topics,
regions and timestamps. Custom Python logging handlers can read the dictionary
from `record.pubsub_event` or its JSON serialization from `record.pubsub_event_json`,
independent of the human-readable console text. Application-receipt and satellite
contact events also use human-readable text. Publication payload contents are omitted.
`LEITURA_LOG.md` contains an annotated excerpt using the updated messages; merged
comments retain their original numbers (for example, 9/10).

```python
LOG_LEVEL = "INFO"  # default; keeps execution start/end messages
# LOG_LEVEL = "DEBUG"  # shows existing simulation logs
```

`WARNING`, `ERROR` and `CRITICAL` are also supported. Detailed application
logs now use `DEBUG`, including initialization, docking, satellites, sensors,
metrics and the previous timeout/alignment warnings. GrADyS-SIM informational
status messages are also displayed only at `DEBUG` through a local handler
filter; execution start/end, elapsed time and `Simulation complete` remain at
`INFO`. The dependency is unchanged and its runtime warnings/errors remain
visible. The threshold and filter are reapplied after simulator construction.
After construction, only the newest GrADyS-SIM console handler is retained,
avoiding duplicate output from Python's default console handler. File handlers
and custom handler subclasses are preserved.
Future application messages explicitly logged at `INFO` will remain visible
at `LOG_LEVEL = "INFO"`.

```bash
python -m venv venv
# Windows
.\venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
```

## Running

Always run from the **project root** using the `-m` flag:

```bash
python -m src.main
```

### CLI flags

| Flag | Description |
|------|-------------|
| `--no-viz` | Disable the browser visualisation |
| `--force-regen` | Force regeneration of sensor positions |
| `--routing-strategy NAME` | Routing protocol: `flooding`, `dtn`, `geocasting`, or `swcore` (default: `flooding`) |
| `--topology NAME` | Core topology: `random` or `star` (default: `random`) |

### Example runs

```bash
# No visualisation, flooding:
python -m src.main --no-viz --routing-strategy flooding

# DTN routing:
python -m src.main --no-viz --routing-strategy dtn

# Geocasting with viz:
python -m src.main --routing-strategy geocasting

# Star (rotating wheel) topology:
python -m src.main --no-viz --topology star

# Random topology, DTN:
python -m src.main --no-viz --topology random --routing-strategy dtn
```

## Sensors

Each `SENSOR_POSITIONS` key (`sensor_N`) defines a stable nonnegative logical ID
`N`, bound by `make_sensor(name)` independently of simulator node order. Sensor
packets retain their `{sensor_name: count}` structure and add `sensor_id`; the
existing `sender_id` still identifies the radio node. The old node-ID-minus-one
offset is removed. Direct users of the bare template fall back to the node ID.

`topic_for_sensor(id)` selects even IDs → T2 and odd IDs → T1 through
`SENSOR_TOPIC_BY_PARITY` in `config.py`. Identity/topic mappings appear in DEBUG
logs. Counts, generation intervals, TTL and satellite accumulation are unchanged.
With `--pubsub`, each sensor batch collected during COLLECT_OUT/COLLECT_IN creates
one Publication. Its payload contains `sensor_id` and `packet_count`; its topic
comes from parity and its origin region from the satellite face (N/S/E/W).
`created_at` records collection time. IDs use satellite node ID plus an increasing
per-instance counter and remain unchanged while queued.

`SensorPublicationMixin` maintains a queue independent of the original satellite
packet counter and SwCore upload. On EXCHANGE it submits queued publications via
the contact node. The scenario gives each satellite only the actual node ID of
the first peer in `PSPEER_SLOTS`, obtained from the builder; no shared node registry
or global lookup is used. The selected peer can still be changed through the API.
Without a peer/contact or when sending returns False, entries remain queued for
the next contact. True removes an entry after submission to the first radio hop,
not after confirmed receipt: subsequent loss is admitted, without ACK/retry.

Original dock uploads, movement, collection counts and timers are preserved.
Publication generation is opt-in; without `--pubsub` sensor traffic retains its
original behavior. INFO logs identify collected batches and submission results.
`test_sensor_publications.py` covers the radio path, both parities, four regions,
stable pending IDs, loss and independence from original uploads/departure.

Sensors are placed in a **cross-shaped corridor** covering both cardinal axes:
- `|x| ≤ 25 m` (N-S corridor) OR `|y| ≤ 25 m` (E-W corridor)
- Outside the obstacle zone, within 90 m of center

This ensures each satellite sweeps past sensors on its outbound leg.

## Metrics (end of simulation)

At the end of each run, the following is logged:
- Total messages uploaded / delivered / delivery ratio
- Latency mean/median/max
- Mean hops per message
- Per route-pair breakdown (N→S, S→N, E→W, W→E)
- Per-satellite: dock count, mean wait time for alignment, mean cycle time

### Tracking hops

The hop counter is incremented on every radio transmission:
- **Hop 1**: satellite → rim node (dock upload)
- **Hop 2**: rim node → destination satellite (dock deliver)

With flooding/dtn, intermediate forwarding adds extra hops.
Expected hops = 2 for direct delivery (sender rim aligned + dest rim already aligned).

## Visualisation

The visualisation connects to the GrADySim web viewer at  
<https://project-gradys.github.io/gradys-sim-nextgen-visualization/>

Node colours:
- 🟠 Orange: Hub (star only)
- 🟡 Amber: Rim nodes (star) / random core UAVs (random)
- 🔵 Cyan: Satellites (4)
- 🟣 Violet: Sensors

> **Note (Windows):** The visualization handler spawns a subprocess for the WebSocket server.
> Any top-level code that should run only once must be inside `if __name__ == "__main__":`.

## Changes from Previous Version

- Replaced 8 patrol-loop UAVs with **13 UAVs** (1 hub + 8 rim + 4 satellites)
- Removed `FIXED_UAV_GROUPS`, track/waypoint constants, `ENDPOINT_GROUND`
- Added all core/satellite parameters to `config.py`; nothing hard-coded in protocols
- Routing mixins adapted to use `dest_face` (dock point) instead of `ENDPOINT_GROUND`
- Sensor corridor restricted to cross-shape matching satellite axes
- Full metrics table added (latency, hops, dock stats)
- `COMM_RANGE` reduced from 32 to 30 m; `SIMULATION_DURATION` reduced to 300 s
- Added `--topology {random,star}`; `random` (9 UAVs moving randomly in the obstacle area) is the new default, `star` is the previous formation
