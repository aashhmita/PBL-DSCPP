"""FIFO queue implemented as a singly linked list.

Food spoils, so the oldest active donation should be collected first. A queue gives exactly
that: items join at the tail and leave from the head, both in O(1) because we keep a
pointer to each end.
"""


class _FoodNode:
    __slots__ = ("data", "next")

    def __init__(self, data):
        self.data = data
        self.next = None


class FoodQueue:
    def __init__(self):
        self._head = None
        self._tail = None
        self._size = 0

    def __len__(self):
        return self._size

    def __iter__(self):
        node = self._head
        while node:
            yield node.data
            node = node.next

    def enqueue(self, offer):
        """Add an offer at the tail. O(1)."""
        node = _FoodNode(offer)
        if self._tail is None:
            self._head = self._tail = node
        else:
            self._tail.next = node
            self._tail = node
        self._size += 1

    def dequeue(self):
        """Remove and return the oldest offer. O(1)."""
        if self._head is None:
            raise IndexError("dequeue from an empty queue")
        node = self._head
        self._head = node.next
        if self._head is None:
            self._tail = None
        self._size -= 1
        return node.data

    def peek(self):
        """Return the oldest offer without removing it, or None if empty."""
        return self._head.data if self._head else None

    def remove(self, offer_id):
        """Remove an offer from anywhere in the queue (e.g. cancelled). O(n)."""
        prev, node = None, self._head
        while node:
            if node.data["Offer ID"] == offer_id:
                if prev:
                    prev.next = node.next
                else:
                    self._head = node.next
                if node is self._tail:
                    self._tail = prev
                self._size -= 1
                return True
            prev, node = node, node.next
        return False

    def to_list(self):
        return list(self)
