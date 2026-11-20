"""Chronological medical history stored as a singly linked list with a tail pointer.

Entries are only ever appended (history is not rewritten), so appending at the tail is O(1)
and reading the list in order gives the history oldest -> newest.
"""


class _LogNode:
    __slots__ = ("entry", "next")

    def __init__(self, entry):
        self.entry = entry
        self.next = None


class MedicalLog:
    def __init__(self):
        self._head = None
        self._tail = None
        self._size = 0

    def __len__(self):
        return self._size

    def __iter__(self):
        """Oldest entry first."""
        node = self._head
        while node:
            yield node.entry
            node = node.next

    def append(self, entry):
        node = _LogNode(entry)
        if self._tail is None:
            self._head = self._tail = node
        else:
            self._tail.next = node
            self._tail = node
        self._size += 1

    def to_list(self, newest_first=True):
        entries = list(self)
        return entries[::-1] if newest_first else entries

    def for_animal(self, animal_id, newest_first=True):
        entries = [e for e in self if e["Animal ID"] == animal_id]
        return entries[::-1] if newest_first else entries

    def remove_animal(self, animal_id):
        """Unlink every entry of one animal (used when the animal record is deleted). Returns the count."""
        removed = 0
        previous = None
        node = self._head
        while node:
            following = node.next
            if node.entry["Animal ID"] == animal_id:
                if previous is None:
                    self._head = following
                else:
                    previous.next = following
                removed += 1
            else:
                previous = node
            node = following
        self._tail = previous
        self._size -= removed
        return removed
