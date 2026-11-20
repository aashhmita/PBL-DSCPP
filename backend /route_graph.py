"""Weighted undirected graph of locations with Dijkstra shortest paths.

Representation: an adjacency dictionary  {location: {neighbour: distance_km}}.
Dijkstra's algorithm repeatedly settles the closest unsettled location, using a min-heap to
find it quickly: O((V + E) log V).
"""

from .triage_heap import MinHeap

INFINITY = float("inf")


class RouteGraph:
    def __init__(self):
        self._adj = {}

    # ---- building the map ----------------------------------------------------
    def add_location(self, name):
        self._adj.setdefault(name, {})

    def add_road(self, a, b, km):
        """Add (or update) a two-way road between two locations."""
        if a == b:
            raise ValueError("A road must connect two different locations.")
        if km <= 0:
            raise ValueError("Distance must be greater than zero.")
        self.add_location(a)
        self.add_location(b)
        self._adj[a][b] = float(km)
        self._adj[b][a] = float(km)

    def has_location(self, name):
        return name in self._adj

    def locations(self):
        return sorted(self._adj)

    def roads(self):
        """Each road once, as (a, b, km) with a < b."""
        seen = []
        for a, neighbours in self._adj.items():
            for b, km in neighbours.items():
                if a < b:
                    seen.append((a, b, km))
        return sorted(seen)

    # ---- shortest path -------------------------------------------------------
    def _dijkstra(self, start):
        dist = {node: INFINITY for node in self._adj}
        prev = {}
        dist[start] = 0.0
        heap = MinHeap([(0.0, start)])
        while len(heap):
            d, node = heap.pop()
            if d > dist[node]:           # stale heap entry, a shorter route was already found
                continue
            for neighbour, km in self._adj[node].items():
                candidate = d + km
                if candidate < dist[neighbour]:
                    dist[neighbour] = candidate
                    prev[neighbour] = node
                    heap.push((candidate, neighbour))
        return dist, prev

    def shortest_path(self, start, end):
        """Return (distance_km, [locations...]) or None if there is no route."""
        if start not in self._adj or end not in self._adj:
            raise ValueError("Both locations must exist on the map.")
        dist, prev = self._dijkstra(start)
        if dist[end] == INFINITY:
            return None
        path = [end]
        while path[-1] != start:
            path.append(prev[path[-1]])
        path.reverse()
        return dist[end], path

    # ---- multi-stop tour -----------------------------------------------------
    def tour(self, start, stops):
        """Visit every stop using the nearest-neighbour heuristic (a fast, good-enough greedy).

        From the current position, always drive to the closest stop not yet visited.
        This is NOT guaranteed optimal (that is the travelling-salesman problem), but it is
        simple and sensible for a handful of rescue calls.
        Returns {"order", "legs", "total_km", "unreachable"}.
        """
        if start not in self._adj:
            raise ValueError("Starting point must exist on the map.")
        remaining = [s for s in dict.fromkeys(stops) if s != start and s in self._adj]
        current, legs, total, order, unreachable = start, [], 0.0, [start], []
        while remaining:
            dist, prev = self._dijkstra(current)
            reachable = [s for s in remaining if dist[s] < INFINITY]
            if not reachable:
                unreachable.extend(remaining)
                break
            nxt = min(reachable, key=lambda s: dist[s])
            path = [nxt]
            while path[-1] != current:
                path.append(prev[path[-1]])
            path.reverse()
            legs.append({"from": current, "to": nxt, "km": dist[nxt], "path": path})
            total += dist[nxt]
            order.append(nxt)
            remaining.remove(nxt)
            current = nxt
        return {"order": order, "legs": legs, "total_km": total, "unreachable": unreachable}
