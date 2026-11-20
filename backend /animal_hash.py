"""Hash table with separate chaining, for O(1) average animal lookup by ID.

Layout: a list of `capacity` buckets; each bucket is a list of [key, value] pairs.
Collisions (two keys landing in the same bucket) simply share that bucket's list.
When the load factor (size / capacity) passes `max_load` the table doubles and re-hashes,
which keeps buckets short and lookups fast.
"""


class AnimalHashTable:
    def __init__(self, capacity=8, max_load=0.75):
        self._capacity = max(4, capacity)
        self._max_load = max_load
        self._buckets = [[] for _ in range(self._capacity)]
        self._size = 0

    # ---- hashing -------------------------------------------------------------
    @staticmethod
    def _hash_text(key):
        """djb2 string hash (hash = hash * 33 + char), kept to 32 bits."""
        h = 5381
        for ch in str(key):
            h = ((h << 5) + h + ord(ch)) & 0xFFFFFFFF
        return h

    def _index(self, key):
        return self._hash_text(key) % self._capacity

    # ---- core operations -----------------------------------------------------
    def put(self, key, value):
        bucket = self._buckets[self._index(key)]
        for pair in bucket:
            if pair[0] == key:          # key already present -> overwrite
                pair[1] = value
                return
        bucket.append([key, value])
        self._size += 1
        if self._size / self._capacity > self._max_load:
            self._resize()

    def get(self, key, default=None):
        for k, v in self._buckets[self._index(key)]:
            if k == key:
                return v
        return default

    def remove(self, key):
        bucket = self._buckets[self._index(key)]
        for i, pair in enumerate(bucket):
            if pair[0] == key:
                del bucket[i]
                self._size -= 1
                return True
        return False

    def _resize(self):
        old_buckets = self._buckets
        self._capacity *= 2
        self._buckets = [[] for _ in range(self._capacity)]
        for bucket in old_buckets:
            for key, value in bucket:
                self._buckets[self._index(key)].append([key, value])

    # ---- conveniences --------------------------------------------------------
    def __contains__(self, key):
        return any(k == key for k, _ in self._buckets[self._index(key)])

    def __len__(self):
        return self._size

    def items(self):
        for bucket in self._buckets:
            for key, value in bucket:
                yield key, value

    def values(self):
        return [v for _, v in self.items()]

    def keys(self):
        return [k for k, _ in self.items()]

    @property
    def capacity(self):
        return self._capacity

    @property
    def load_factor(self):
        return self._size / self._capacity
