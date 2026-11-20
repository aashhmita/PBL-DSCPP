"""Binary min-heap and the triage priority queue built on top of it.

A heap stores a complete binary tree inside a plain list:
    parent of index i  -> (i - 1) // 2
    children of index i -> 2*i + 1  and  2*i + 2
Every parent is <= its children, so the smallest item is always at index 0.

    peek      O(1)
    push/pop  O(log n)
    build     O(n)   (bottom-up heapify)
"""

from .constants import URGENCY_RANK


class MinHeap:
    """Generic min-heap. Items must be comparable (tuples work well)."""

    def __init__(self, items=None):
        self._data = list(items) if items else []
        # Bottom-up heapify: fix every non-leaf node, starting from the last one.
        for i in range(len(self._data) // 2 - 1, -1, -1):
            self._sift_down(i)

    def __len__(self):
        return len(self._data)

    def push(self, item):
        self._data.append(item)
        self._sift_up(len(self._data) - 1)

    def pop(self):
        if not self._data:
            raise IndexError("pop from an empty heap")
        top = self._data[0]
        last = self._data.pop()
        if self._data:                 # move the last leaf to the root, then sink it
            self._data[0] = last
            self._sift_down(0)
        return top

    def peek(self):
        if not self._data:
            raise IndexError("peek at an empty heap")
        return self._data[0]

    def copy(self):
        clone = MinHeap()
        clone._data = list(self._data)
        return clone

    def _sift_up(self, i):
        data = self._data
        while i > 0:
            parent = (i - 1) // 2
            if data[i] < data[parent]:
                data[i], data[parent] = data[parent], data[i]
                i = parent
            else:
                break

    def _sift_down(self, i):
        data = self._data
        n = len(data)
        while True:
            left, right, smallest = 2 * i + 1, 2 * i + 2, i
            if left < n and data[left] < data[smallest]:
                smallest = left
            if right < n and data[right] < data[smallest]:
                smallest = right
            if smallest == i:
                break
            data[i], data[smallest] = data[smallest], data[i]
            i = smallest


def _sequence_number(animal_id):
    """'SC-1004' -> 1004. Used as a tie-breaker so equal urgencies stay first-come first-served."""
    try:
        return int(str(animal_id).split("-")[-1])
    except ValueError:
        return 0


class TriageHeap:
    """Priority queue of rescue cases: most urgent first, oldest first on ties.

    Each entry is the tuple (urgency_rank, sequence_number, animal_id).
    Tuples compare element by element, which gives exactly that ordering.
    """

    def __init__(self, animals=None):
        entries = [self._entry(a) for a in (animals or [])]
        self._heap = MinHeap(entries)

    @staticmethod
    def _entry(animal):
        rank = URGENCY_RANK.get(animal["Urgency"], len(URGENCY_RANK))
        return (rank, _sequence_number(animal["ID"]), animal["ID"])

    def __len__(self):
        return len(self._heap)

    def push_case(self, animal):
        self._heap.push(self._entry(animal))

    def pop_case(self):
        """Remove and return the animal ID of the most urgent case."""
        return self._heap.pop()[2]

    def peek_case(self):
        """Return (without removing) the animal ID of the most urgent case."""
        return self._heap.peek()[2]

    def ordered_ids(self):
        """All IDs from most to least urgent, without destroying the heap (heap-sort on a copy)."""
        clone = self._heap.copy()
        return [clone.pop()[2] for _ in range(len(clone))]
