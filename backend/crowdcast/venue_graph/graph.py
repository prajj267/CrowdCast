"""Venue graph G = (V, E) and its validation rules (doc 11 §1 and §9; WORKFLOW 2.2.1).

Nodes are the zone codes plus the virtual ``OUTSIDE`` node (omega). Every connection in the venue
file becomes one directed edge, or two when it is bidirectional. Edge attributes: ``width_m`` and
``travel_time_s`` (doc 11 §3).

Nodes are keyed by zone *code* because the graph is built from the venue YAML; mapping codes to
database ids is the loader's job (task 2.3.1).
"""

from __future__ import annotations

import math
from collections.abc import Collection
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

import networkx as nx
import numpy as np
import numpy.typing as npt

from crowdcast.venue_graph.config import OUTSIDE, VenueConfig


class Severity(StrEnum):
    ERROR = "ERROR"  # the venue cannot be used (event cannot go LIVE, doc 14 §3.4)
    WARNING = "WARNING"  # usable, but some quantity will be unobserved


class IssueCode(StrEnum):
    ISOLATED = "ISOLATED"  # rule 1: zone has no connection at all
    UNREACHABLE = "UNREACHABLE"  # rule 2: no path from OUTSIDE into the zone
    NO_PATH_OUT = "NO_PATH_OUT"  # rule 2: no path from the zone back to OUTSIDE
    NO_COUNTING_LINE = "NO_COUNTING_LINE"  # rule 4: flows on this connection are unobserved


@dataclass(frozen=True, slots=True)
class GraphIssue:
    code: IssueCode
    severity: Severity
    subject: str  # zone code, or "A->B" for a connection
    message: str


class InvalidVenueGraphError(ValueError):
    def __init__(self, issues: list[GraphIssue]) -> None:
        self.issues = issues
        super().__init__("; ".join(f"{i.code} {i.subject}: {i.message}" for i in issues))


class VenueGraph:
    """Immutable directed graph of one venue."""

    def __init__(self, config: VenueConfig) -> None:
        g: nx.DiGraph[str] = nx.DiGraph()
        g.add_node(OUTSIDE)
        g.add_nodes_from(z.code for z in config.zones)
        for c in config.connections:
            for src, dst in c.directed_edges():
                g.add_edge(src, dst, width_m=c.width_m, travel_time_s=c.travel_time_s)
        nx.freeze(g)  # in place: any later add/remove raises
        self._g: nx.DiGraph[str] = g
        self._connections = [(c.from_, c.to) for c in config.connections]
        self.zone_codes: tuple[str, ...] = tuple(z.code for z in config.zones)

    @classmethod
    def from_config(cls, config: VenueConfig) -> VenueGraph:
        return cls(config)

    # ------------------------------------------------------------------ structure
    def neighbours(self, code: str, direction: Literal["in", "out", "both"] = "both") -> list[str]:
        """Zones (and possibly OUTSIDE) one step away, sorted for deterministic output."""
        if code not in self._g:
            raise KeyError(f"unknown zone {code!r}")
        found: set[str] = set()
        if direction in ("in", "both"):
            found.update(self._g.predecessors(code))
        if direction in ("out", "both"):
            found.update(self._g.successors(code))
        return sorted(found)

    def edges(self) -> list[tuple[str, str]]:
        return sorted(self._g.edges())

    def index(self) -> dict[str, int]:
        """Row/column position of each zone in the matrices (venue-file order)."""
        return {code: k for k, code in enumerate(self.zone_codes)}

    # ------------------------------------------------------------------ matrices (doc 11 §5.3)
    def adjacency(self, weighted: bool = False) -> npt.NDArray[np.float64]:
        """Zones x zones matrix, rows = from-zone j, columns = to-zone i (OUTSIDE excluded).

        Binary: A[j, i] = 1 if (j, i) in E. Weighted: A_w[j, i] = w_ji / max w, where the
        maximum is taken over the zone-to-zone edges in the matrix.
        """
        idx = self.index()
        n = len(self.zone_codes)
        a = np.zeros((n, n), dtype=np.float64)
        for src, dst in self._g.edges():
            if src in idx and dst in idx:
                width = float(self._g.edges[src, dst]["width_m"])
                a[idx[src], idx[dst]] = width if weighted else 1.0
        if weighted and a.max() > 0:
            a /= a.max()
        return a

    # ------------------------------------------------------------------ travel times
    def _routing_graph(self, src: str, dst: str) -> nx.DiGraph[str]:
        # OUTSIDE may be the start or end of a route but never a shortcut through the middle:
        # leaving by one gate and re-entering by another is not a path inside the venue.
        if OUTSIDE in (src, dst):
            return self._g
        inside: nx.DiGraph[str] = self._g.subgraph(n for n in self._g if n != OUTSIDE)
        return inside

    def shortest_path(self, src: str, dst: str) -> list[str]:
        """Fastest route by summed typical travel time; raises ``nx.NetworkXNoPath`` if none."""
        for code in (src, dst):
            if code not in self._g:
                raise KeyError(f"unknown zone {code!r}")
        path: list[str] = nx.dijkstra_path(
            self._routing_graph(src, dst), src, dst, weight="travel_time_s"
        )
        return path

    def travel_time_s(self, src: str, dst: str) -> float:
        """Shortest-path travel time tau in seconds; ``math.inf`` when no route exists."""
        for code in (src, dst):
            if code not in self._g:
                raise KeyError(f"unknown zone {code!r}")
        try:
            t = nx.dijkstra_path_length(
                self._routing_graph(src, dst), src, dst, weight="travel_time_s"
            )
        except nx.NetworkXNoPath:
            return math.inf
        return float(t)

    def travel_time_matrix(self) -> npt.NDArray[np.float64]:
        """Zones x zones shortest travel times d_ik (s); 0 on the diagonal, inf if unreachable.

        Used for destination choice in CROWDSIM (doc 12 §5.1).
        """
        zones_only = self._g.subgraph(n for n in self._g if n != OUTSIDE)
        lengths = dict(nx.all_pairs_dijkstra_path_length(zones_only, weight="travel_time_s"))
        idx = self.index()
        d = np.full((len(idx), len(idx)), math.inf, dtype=np.float64)
        for src, row in lengths.items():
            for dst, t in row.items():
                d[idx[src], idx[dst]] = float(t)
        return d

    # ------------------------------------------------------------------ validation
    def validate(
        self, observed_connections: Collection[tuple[str, str]] | None = None
    ) -> list[GraphIssue]:
        """Check doc 11 §9. Rule 3 (width and travel time > 0) is enforced by the YAML parser.

        ``observed_connections``: connections (from, to) that have a counting line, in either
        orientation. ``None`` means camera configuration is not loaded yet, so rule 4 is skipped
        rather than warning about every connection.
        """
        issues: list[GraphIssue] = []
        reachable = nx.descendants(self._g, OUTSIDE)
        can_leave = nx.ancestors(self._g, OUTSIDE)
        for code in self.zone_codes:
            if self._g.degree(code) == 0:
                issues.append(
                    GraphIssue(IssueCode.ISOLATED, Severity.ERROR, code, "zone has no connections")
                )
                continue  # an isolated zone is trivially unreachable; report it once
            if code not in reachable:
                issues.append(
                    GraphIssue(
                        IssueCode.UNREACHABLE,
                        Severity.ERROR,
                        code,
                        "no path from OUTSIDE into this zone",
                    )
                )
            if code not in can_leave:
                issues.append(
                    GraphIssue(
                        IssueCode.NO_PATH_OUT,
                        Severity.ERROR,
                        code,
                        "no path from this zone to OUTSIDE",
                    )
                )
        if observed_connections is not None:
            observed = {frozenset(c) for c in observed_connections}
            for src, dst in self._connections:
                if frozenset((src, dst)) not in observed:
                    issues.append(
                        GraphIssue(
                            IssueCode.NO_COUNTING_LINE,
                            Severity.WARNING,
                            f"{src}->{dst}",
                            "no counting line; flows on this connection are unobserved",
                        )
                    )
        return issues

    def require_valid(self) -> list[GraphIssue]:
        """Raise ``InvalidVenueGraphError`` if any ERROR issue exists; return the warnings."""
        issues = self.validate()
        errors = [i for i in issues if i.severity is Severity.ERROR]
        if errors:
            raise InvalidVenueGraphError(errors)
        return issues
