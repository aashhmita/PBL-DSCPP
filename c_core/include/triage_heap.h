/* triage_heap.h : binary min-heap that always keeps the most urgent rescue case on top.
 *
 * The tree lives inside a plain array:
 *     parent of i   = (i - 1) / 2
 *     children of i = 2*i + 1 and 2*i + 2
 * Every parent is "smaller" (= more urgent) than its children.
 *
 * Ordering of two entries: lower rank first (0 = Critical ... 3 = Low); on equal rank the
 * lower sequence number (the older report) first; on equal sequence the ID text.
 *
 *   peek O(1)   push O(log n)   pop O(log n)   build from an array O(n)
 */
#ifndef TRIAGE_HEAP_H
#define TRIAGE_HEAP_H

#include <stddef.h>
#include "straycare_types.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    int  rank;                 /* urgency rank: smaller = more urgent */
    long seq;                  /* number inside the animal ID: smaller = reported earlier */
    char id[SC_ID_LEN];
} TriageEntry;

typedef struct {
    TriageEntry *data;
    size_t size;
    size_t capacity;
} TriageHeap;

TriageHeap *th_create(void);                                          /* NULL if out of memory */
TriageHeap *th_build(const TriageEntry *entries, size_t count);       /* bottom-up heapify, O(n) */
void        th_destroy(TriageHeap *heap);
int         th_push(TriageHeap *heap, int rank, long seq, const char *id);   /* 0 ok, -1 failure */
int         th_pop(TriageHeap *heap, TriageEntry *out);               /* 1 popped, 0 empty */
int         th_peek(const TriageHeap *heap, TriageEntry *out);        /* 1 found, 0 empty  */
size_t      th_size(const TriageHeap *heap);

#ifdef __cplusplus
}
#endif

#endif /* TRIAGE_HEAP_H */
