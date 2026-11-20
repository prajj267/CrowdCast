"""CROWDSIM core: seeded agent simulation on the venue graph (WORKFLOW 3.3.1-3.3.5; DESIGN.md).

Section references (§) are to DESIGN.md. Every parameter comes from a ``Regime`` (placeholders).
Per tick (δ = 10 s):
  1. at a bucket start, snapshot occupancy N (bucket convention, §1);
  2. new arrivals queue on entry edges (§3);
  3. busy/dwell timers run down; agents whose timer ends become *ready*;
  4. ready agents dwell, choose a destination (logit, §4) or head for an exit (§7);
  5. every edge admits queued agents up to its capacity unless the target zone is jammed (§5);
  6. speeds are accumulated from the speed-density relation (§6).
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import numpy.typing as npt

from crowdcast.common.enums import ScheduleCategory
from crowdcast.venue_graph.interfaces import OUTSIDE, EventConfig, VenueConfig, VenueGraph
from tools.crowdsim.params import Regime
from tools.crowdsim.schedule import GATE_TYPES, SimItem, actual_items, published_items

# agent states
WAITING_OUTSIDE, BUSY, DWELLING, QUEUED, READY, LEFT = range(6)
NO_DEST = -1
VENUE_WIDE_CATEGORIES = {ScheduleCategory.ENTRY_OPEN, ScheduleCategory.EXIT_WAVE}

FloatArr = npt.NDArray[np.float64]
IntArr = npt.NDArray[np.int64]


@dataclass(frozen=True)
class SimResult:
    """Minute-level output. Bucket b covers [bucket_starts[b], bucket_starts[b] + 1 min)."""

    zone_codes: tuple[str, ...]
    edges: tuple[tuple[str, str], ...]  # directed, OUTSIDE allowed
    bucket_starts: tuple[datetime, ...]
    occupancy: IntArr  # (B, Z) N at the START of each bucket
    edge_flow: IntArr  # (B, E) crossings during each bucket
    inflow: IntArr  # (B, Z)
    outflow: IntArr  # (B, Z)
    mean_speed_mps: FloatArr  # (B, Z)
    entries: IntArr  # (B,) OUTSIDE -> venue
    exits: IntArr  # (B,) venue -> OUTSIDE
    published: tuple[SimItem, ...]
    actual: tuple[SimItem, ...]
    arrivals_total: int
    left_inside_at_stop: int  # agents still in the venue when the simulation stopped


class _Venue:
    """Integer-indexed view of the venue graph for the simulation loop."""

    def __init__(self, cfg: VenueConfig) -> None:
        graph = VenueGraph.from_config(cfg)
        graph.require_valid()
        self.codes = graph.zone_codes
        self.n = len(self.codes)
        self.out = self.n  # index of OUTSIDE
        idx = {c: k for k, c in enumerate(self.codes)} | {OUTSIDE: self.out}
        zones = {z.code: z for z in cfg.zones}
        self.types = [zones[c].type for c in self.codes]
        self.area = np.array([zones[c].area_m2 for c in self.codes], dtype=np.float64)
        self.capacity = np.array([cfg.capacity_of(c) for c in self.codes], dtype=np.float64)

        self.edge_codes: list[tuple[str, str]] = []
        src, dst, width, tau = [], [], [], []
        for c in cfg.connections:
            for a, b in c.directed_edges():
                self.edge_codes.append((a, b))
                src.append(idx[a])
                dst.append(idx[b])
                width.append(c.width_m)
                tau.append(float(c.travel_time_s))
        self.src = np.array(src)
        self.dst = np.array(dst)
        self.width = np.array(width, dtype=np.float64)
        self.tau = np.array(tau, dtype=np.float64)
        self.edge_of = {(int(a), int(b)): e for e, (a, b) in enumerate(zip(src, dst, strict=True))}
        self.entry_edges = np.flatnonzero(self.src == self.out)

        n = self.n
        self.dist_min = graph.travel_time_matrix() / 60.0
        self.next_hop = np.full((n, n), -1, dtype=np.int64)
        for i in range(n):
            for k in range(n):
                if i != k and math.isfinite(self.dist_min[i, k]):
                    self.next_hop[i, k] = idx[graph.shortest_path(self.codes[i], self.codes[k])[1]]
        self.next_hop_out = np.array(
            [idx[graph.shortest_path(c, OUTSIDE)[1]] for c in self.codes], dtype=np.int64
        )
        # destinations agents may choose: everything except gates (§4)
        self.choosable = np.array([t not in GATE_TYPES for t in self.types])


def _arrival_density(
    event: EventConfig, items: list[SimItem], regime: Regime, tick_times_min: FloatArr
) -> FloatArr:
    """g(t) on the tick grid, summing to 1 (§3). Surges follow the PUBLISHED schedule."""
    a = regime.arrivals
    dur = (event.event.end_time - event.event.start_time).total_seconds() / 60
    stop = dur - a.stop_before_end_min
    t = tick_times_min
    # baseline: ramp up, flat, ramp down (over ramp_up_min) to 0 at end - stop_before_end
    up = np.clip(t / a.ramp_up_min, 0, 1)
    down = np.clip((stop - t) / a.ramp_up_min, 0, 1)
    base = np.where(t < stop, np.minimum(up, down), 0.0)
    total = base / base.sum() if base.sum() > 0 else base

    surge = np.zeros_like(t)
    start = event.event.start_time
    for it in items:
        if it.zone_code is None or it.category in VENUE_WIDE_CATEGORIES:
            continue
        centre = (it.start - start).total_seconds() / 60 - a.surge_lead_min
        weight = (it.expected_attendance or 1) * it.attraction_weight
        bump = np.exp(-0.5 * ((t - centre) / a.surge_sigma_min) ** 2) * (t < stop) * (t >= 0)
        if bump.sum() > 0:
            surge += weight * bump / bump.sum()
    if surge.sum() > 0:
        total = a.baseline_weight * total + (1 - a.baseline_weight) * surge / surge.sum()
    return np.asarray(total / total.sum(), dtype=np.float64)


def simulate(
    venue_cfg: VenueConfig, event: EventConfig, regime: Regime, rng: np.random.Generator
) -> SimResult:
    """Simulate one event. Same inputs and generator state give identical output."""
    v = _Venue(venue_cfg)
    p_choice, p_dwell, p_move = regime.choice, regime.dwell, regime.movement
    dt = float(regime.tick_s)
    ticks_per_bucket = max(1, round(60 / dt))
    start, end = event.event.start_time, event.event.end_time
    dur_s = (end - start).total_seconds()
    max_ticks = math.ceil((dur_s + regime.tail_min * 60) / dt / ticks_per_bucket) * ticks_per_bucket

    published = published_items(event)
    actual = actual_items(event, venue_cfg, regime, rng)
    zoned = [it for it in actual if it.zone_code is not None]
    item_zone = np.array([v.codes.index(str(it.zone_code)) for it in zoned], dtype=np.int64)
    item_start = np.array([(it.start - start).total_seconds() for it in zoned])
    item_end = np.array([(it.end - start).total_seconds() for it in zoned])
    item_weight = np.array([it.attraction_weight * it.popularity for it in zoned])
    last_item_end = float(item_end.max()) if len(zoned) else dur_s

    # ---- arrivals (§3)
    tick_min = np.arange(max_ticks) * dt / 60
    density = _arrival_density(event, published, regime, tick_min)
    turnout = rng.uniform(*regime.arrivals.turnout)
    expected = (event.event.expected_attendance or 0) * turnout * density
    arrivals = rng.poisson(expected)
    entry_w = v.width[v.entry_edges] / v.width[v.entry_edges].sum()
    n_agents = int(arrivals.sum())

    zone = np.full(n_agents, v.out, dtype=np.int64)
    state = np.full(n_agents, WAITING_OUTSIDE, dtype=np.int64)
    timer = np.zeros(n_agents)
    dest = np.full(n_agents, NO_DEST, dtype=np.int64)
    needs_dwell = np.zeros(n_agents, dtype=bool)
    leaving = np.zeros(n_agents, dtype=bool)

    queues: list[deque[int]] = [deque() for _ in v.edge_codes]
    cap = np.zeros(len(v.edge_codes))
    q_tick = v.width * p_move.specific_flow_p_per_m_min * dt / 60
    jam = v.capacity * p_move.jam_capacity_factor
    occ = np.zeros(v.n, dtype=np.int64)

    base_attr = np.array([p_choice.base_attraction.get(t.value, 0.0) for t in v.types])
    dwell_median = np.array([p_dwell.median_min.get(t.value, 5.0) for t in v.types]) * 60
    cand = np.flatnonzero(v.choosable)

    n_buckets = max_ticks // ticks_per_bucket
    occupancy = np.zeros((n_buckets, v.n), dtype=np.int64)
    edge_flow = np.zeros((n_buckets, len(v.edge_codes)), dtype=np.int64)
    speed_sum = np.zeros((n_buckets, v.n))
    next_agent = 0
    closing = False
    used_buckets = n_buckets

    def speed() -> FloatArr:
        rho = occ / v.area
        factor = np.maximum(0.1, 1 - rho / p_move.rho_jam_p_per_m2)
        return np.asarray(p_move.v_free_mps * factor, dtype=np.float64)

    def enqueue(a: int, here: int, there: int) -> None:
        queues[v.edge_of[(here, there)]].append(a)
        state[a] = QUEUED

    def choice_probs(t_s: float) -> FloatArr:
        """(Z, len(cand) + 1) destination probabilities per origin zone; last column = leave."""
        attr = base_attr.copy()
        rise = p_choice.item_rise_min * 60
        h = np.clip((t_s - (item_start - rise)) / rise, 0, 1) * (t_s < item_end)
        np.add.at(attr, item_zone, item_weight * h)
        u = occ / v.capacity
        util = (
            p_choice.beta_attraction * attr[cand][None, :]
            - p_choice.beta_distance_per_min * v.dist_min[:, cand]
            - p_choice.beta_crowding * u[cand][None, :]
        )
        ell = min(max(t_s / dur_s, 0.0), 1.0)
        if last_item_end <= t_s <= last_item_end + p_choice.exit_wave_min * 60:
            ell += 1.0
        leave = np.full((v.n, 1), p_choice.beta_leave * ell)
        util = np.concatenate([util, leave], axis=1)
        util = np.where(np.isfinite(util), util, -np.inf)
        util -= util.max(axis=1, keepdims=True)
        w = np.exp(util)
        return np.asarray(w / w.sum(axis=1, keepdims=True), dtype=np.float64)

    def dwell_time(k: int, t_s: float) -> float:
        rise = p_choice.item_rise_min * 60
        running = (item_zone == k) & (item_start - rise <= t_s) & (t_s < item_end)
        if running.any():
            extra = rng.lognormal(
                math.log(p_dwell.after_item_median_min * 60), p_dwell.after_item_sigma
            )
            return float(item_end[running].max() - t_s + extra)
        return float(rng.lognormal(math.log(dwell_median[k]), p_dwell.sigma))

    for tick in range(max_ticks):
        t_s = tick * dt
        b = tick // ticks_per_bucket
        if tick % ticks_per_bucket == 0:
            occupancy[b] = occ  # N at the start of bucket b (§1)
            if t_s >= dur_s and occ.sum() == 0 and not any(queues[e] for e in range(len(queues))):
                used_buckets = b
                break

        # 2. arrivals queue on entry edges (they count nowhere until they cross)
        k_new = int(arrivals[tick])
        if k_new:
            gates = rng.choice(v.entry_edges, size=k_new, p=entry_w)
            for e in gates:
                queues[int(e)].append(next_agent)
                state[next_agent] = QUEUED
                next_agent += 1

        # closing time: everyone heads out (§7)
        if not closing and t_s >= dur_s:
            closing = True
            inside = zone != v.out
            leaving[inside] = True
            dwelling = state == DWELLING
            state[dwelling] = READY
            # agents queued towards a destination inside the venue turn round and leave instead;
            # otherwise a jammed destination could keep them (and the zone) stuck forever
            for e, q in enumerate(queues):
                if v.src[e] != v.out and q:
                    for a in q:
                        state[a] = READY
                    q.clear()

        # 3. timers
        active = (state == BUSY) | (state == DWELLING)
        timer[active] -= dt
        state[active & (timer <= 0)] = READY

        # 4. decisions, in random order
        ready = np.flatnonzero(state == READY)
        if len(ready):
            rng.shuffle(ready)
            probs = choice_probs(t_s)
            for agent in ready:
                a = int(agent)
                here = int(zone[a])
                if leaving[a] or closing:
                    leaving[a] = True
                    enqueue(a, here, int(v.next_hop_out[here]))
                elif dest[a] != NO_DEST and dest[a] != here:
                    enqueue(a, here, int(v.next_hop[here, dest[a]]))
                elif needs_dwell[a]:
                    needs_dwell[a] = False
                    state[a] = DWELLING
                    timer[a] = dwell_time(here, t_s)
                else:
                    c = int(rng.choice(len(cand) + 1, p=probs[here]))
                    if c == len(cand):
                        leaving[a] = True
                        enqueue(a, here, int(v.next_hop_out[here]))
                    else:
                        k = int(cand[c])
                        if k == here:
                            state[a] = DWELLING
                            timer[a] = dwell_time(here, t_s)
                        else:
                            dest[a] = k
                            enqueue(a, here, int(v.next_hop[here, k]))

        # 5. edges admit queued agents up to capacity; no admission into a jammed zone
        vel = speed()
        for e, q in enumerate(queues):
            if not q:
                cap[e] = min(cap[e], 1.0)  # no banking of unused capacity
                continue
            cap[e] += q_tick[e]
            target = int(v.dst[e])
            while q and cap[e] >= 1.0:
                if target != v.out and occ[target] >= jam[target]:
                    break  # spillback: the queue stays in the upstream zone
                a = q.popleft()
                cap[e] -= 1.0
                edge_flow[b, e] += 1
                here = int(zone[a])
                if here != v.out:
                    occ[here] -= 1
                if target == v.out:
                    zone[a] = v.out
                    state[a] = LEFT
                    continue
                occ[target] += 1
                zone[a] = target
                state[a] = BUSY
                timer[a] = v.tau[e] * p_move.v_free_mps / vel[target]
                if dest[a] == target:
                    needs_dwell[a] = True

        # 6. speeds
        speed_sum[b] += speed()

    occupancy = occupancy[:used_buckets]
    edge_flow = edge_flow[:used_buckets]
    mean_speed = speed_sum[:used_buckets] / ticks_per_bucket
    inflow = np.zeros((used_buckets, v.n), dtype=np.int64)
    outflow = np.zeros((used_buckets, v.n), dtype=np.int64)
    for e in range(len(v.edge_codes)):
        if v.dst[e] != v.out:
            inflow[:, v.dst[e]] += edge_flow[:, e]
        if v.src[e] != v.out:
            outflow[:, v.src[e]] += edge_flow[:, e]
    entries = edge_flow[:, v.src == v.out].sum(axis=1)
    exits = edge_flow[:, v.dst == v.out].sum(axis=1)
    return SimResult(
        zone_codes=v.codes,
        edges=tuple(v.edge_codes),
        bucket_starts=tuple(start + timedelta(minutes=b) for b in range(used_buckets)),
        occupancy=occupancy,
        edge_flow=edge_flow,
        inflow=inflow,
        outflow=outflow,
        mean_speed_mps=mean_speed,
        entries=entries,
        exits=exits,
        published=tuple(published),
        actual=tuple(actual),
        arrivals_total=n_agents,
        left_inside_at_stop=int(occ.sum()),
    )
