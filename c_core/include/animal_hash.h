#include "triage_heap.h"

#include <stdlib.h>
#include <string.h>

#define TH_MIN_CAPACITY 8

/* 1 if a must come out before b. */
static int entry_less(const TriageEntry *a, const TriageEntry *b)
{
    if (a->rank != b->rank) return a->rank < b->rank;
    if (a->seq  != b->seq)  return a->seq  < b->seq;
    return strcmp(a->id, b->id) < 0;
}

static void swap_entries(TriageEntry *a, TriageEntry *b)
{
    TriageEntry tmp = *a;
    *a = *b;
    *b = tmp;
}

static void sift_up(TriageHeap *heap, size_t i)
{
    while (i > 0) {
        size_t parent = (i - 1) / 2;
        if (!entry_less(&heap->data[i], &heap->data[parent])) break;
        swap_entries(&heap->data[i], &heap->data[parent]);
        i = parent;
    }
}

static void sift_down(TriageHeap *heap, size_t i)
{
    for (;;) {
        size_t left = 2 * i + 1, right = 2 * i + 2, best = i;
        if (left  < heap->size && entry_less(&heap->data[left],  &heap->data[best])) best = left;
        if (right < heap->size && entry_less(&heap->data[right], &heap->data[best])) best = right;
        if (best == i) break;
        swap_entries(&heap->data[i], &heap->data[best]);
        i = best;
    }
}

static TriageHeap *alloc_heap(size_t capacity)
{
    TriageHeap *heap = malloc(sizeof *heap);
    if (!heap) return NULL;
    heap->capacity = capacity < TH_MIN_CAPACITY ? TH_MIN_CAPACITY : capacity;
    heap->data = malloc(heap->capacity * sizeof *heap->data);
    if (!heap->data) {
        free(heap);
        return NULL;
    }
    heap->size = 0;
    return heap;
}

TriageHeap *th_create(void)
{
    return alloc_heap(TH_MIN_CAPACITY);
}

TriageHeap *th_build(const TriageEntry *entries, size_t count)
{
    TriageHeap *heap = alloc_heap(count);
    if (!heap) return NULL;
    if (count > 0) memcpy(heap->data, entries, count * sizeof *entries);
    heap->size = count;
    /* Fix every non-leaf node, last one first: O(n) in total. */
    for (size_t i = count / 2; i-- > 0; ) {
        sift_down(heap, i);
    }
    return heap;
}

void th_destroy(TriageHeap *heap)
{
    if (!heap) return;
    free(heap->data);
    free(heap);
}

int th_push(TriageHeap *heap, int rank, long seq, const char *id)
{
    if (heap->size == heap->capacity) {
        size_t new_capacity = heap->capacity * 2;
        TriageEntry *bigger = realloc(heap->data, new_capacity * sizeof *bigger);
        if (!bigger) return -1;
        heap->data = bigger;
        heap->capacity = new_capacity;
    }
    TriageEntry *slot = &heap->data[heap->size];
    slot->rank = rank;
    slot->seq = seq;
    if (sc_copy(slot->id, sizeof slot->id, id) != 0) return -1;
    heap->size++;
    sift_up(heap, heap->size - 1);
    return 0;
}

int th_pop(TriageHeap *heap, TriageEntry *out)
{
    if (heap->size == 0) return 0;
    if (out) *out = heap->data[0];
    heap->size--;
    if (heap->size > 0) {
        heap->data[0] = heap->data[heap->size];   /* move the last leaf to the root ... */
        sift_down(heap, 0);                       /* ... and let it sink to its place   */
    }
    return 1;
}

int th_peek(const TriageHeap *heap, TriageEntry *out)
{
    if (heap->size == 0) return 0;
    if (out) *out = heap->data[0];
    return 1;
}

size_t th_size(const TriageHeap *heap)
{
    return heap->size;
}
