#include "route_graph.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

#define RG_MIN_CAPACITY 8

/* ------------------------------------------------------------------------------------
 * Building the graph
 * ------------------------------------------------------------------------------------ */

RouteGraph *rg_create(void)
{
    RouteGraph *graph = malloc(sizeof *graph);
    if (!graph) return NULL;
    graph->count = 0;
    graph->capacity = RG_MIN_CAPACITY;
    graph->nodes = malloc((size_t)graph->capacity * sizeof *graph->nodes);
    if (!graph->nodes) {
        free(graph);
        return NULL;
    }
    return graph;
}

void rg_clear(RouteGraph *graph)
{
    for (int i = 0; i < graph->count; i++) {
        RgEdge *edge = graph->nodes[i].first;
        while (edge) {
            RgEdge *next = edge->next;
            free(edge);
            edge = next;
        }
    }
    graph->count = 0;
}

void rg_destroy(RouteGraph *graph)
{
    if (!graph) return;
    rg_clear(graph);
    free(graph->nodes);
    free(graph);
}

int rg_find(const RouteGraph *graph, const char *name)
{
    for (int i = 0; i < graph->count; i++) {      /* O(V): fine for a city-sized map */
        if (strcmp(graph->nodes[i].name, name) == 0) return i;
    }
    return -1;
}

int rg_add_location(RouteGraph *graph, const char *name)
{
    int existing = rg_find(graph, name);
    if (existing >= 0) return existing;

    if (graph->count == graph->capacity) {
        int new_capacity = graph->capacity * 2;
        RgNode *bigger = realloc(graph->nodes, (size_t)new_capacity * sizeof *bigger);
        if (!bigger) return -1;
        graph->nodes = bigger;                  /* edges use indices, so moving nodes is safe */
        graph->capacity = new_capacity;
    }
    RgNode *node = &graph->nodes[graph->count];
    if (sc_copy(node->name, sizeof node->name, name) != 0) return -1;
    node->first = node->last = NULL;
    return graph->count++;
}

int rg_node_count(const RouteGraph *graph)
{
    return graph->count;
}

const char *rg_node_name(const RouteGraph *graph, int index)
{
    return graph->nodes[index].name;
}

/* Set the edge from -> to; update it if it already exists, otherwise append a new one. */
static int set_edge(RgNode *from, int to, double km)
{
    for (RgEdge *edge = from->first; edge; edge = edge->next) {
        if (edge->to == to) {
            edge->km = km;
            return 0;
        }
    }
    RgEdge *edge = malloc(sizeof *edge);
    if (!edge) return RG_ERR_NOMEM;
    edge->to = to;
    edge->km = km;
    edge->next = NULL;
    if (from->last) from->last->next = edge;
    else from->first = edge;
    from->last = edge;
    return 0;
}

int rg_add_road(RouteGraph *graph, const char *a, const char *b, double km)
{
    if (strcmp(a, b) == 0) return RG_ERR_SAME;
    if (!(km > 0.0)) return RG_ERR_DISTANCE;        /* also rejects NaN */

    int ia = rg_add_location(graph, a);
    int ib = rg_add_location(graph, b);
    if (ia < 0 || ib < 0) return RG_ERR_NOMEM;

    int rc = set_edge(&graph->nodes[ia], ib, km);
    if (rc != 0) return rc;
    return set_edge(&graph->nodes[ib], ia, km);
}

void rg_foreach_road(const RouteGraph *graph,
                     void (*callback)(const char *a, const char *b, double km, void *context),
                     void *context)
{
    for (int i = 0; i < graph->count; i++) {
        for (const RgEdge *edge = graph->nodes[i].first; edge; edge = edge->next) {
            if (i < edge->to) {                     /* each road is stored twice: report it once */
                callback(graph->nodes[i].name, graph->nodes[edge->to].name, edge->km, context);
            }
        }
    }
}

/* ------------------------------------------------------------------------------------
 * Dijkstra with a small private min-heap of (distance, node) pairs
 * ------------------------------------------------------------------------------------ */

typedef struct {
    double d;
    int node;
} PqItem;

typedef struct {
    PqItem *items;
    size_t size;
    size_t capacity;
    const RouteGraph *graph;
} Pq;

/* Smaller distance first. Ties are broken by location name, so results do not depend on
 * the order in which locations happened to be added. */
static int pq_less(const Pq *pq, PqItem a, PqItem b)
{
    if (a.d != b.d) return a.d < b.d;
    return strcmp(pq->graph->nodes[a.node].name, pq->graph->nodes[b.node].name) < 0;
}

static int pq_push(Pq *pq, double d, int node)
{
    if (pq->size == pq->capacity) {
        size_t new_capacity = pq->capacity ? pq->capacity * 2 : 16;
        PqItem *bigger = realloc(pq->items, new_capacity * sizeof *bigger);
        if (!bigger) return -1;
        pq->items = bigger;
        pq->capacity = new_capacity;
    }
    size_t i = pq->size++;
    pq->items[i].d = d;
    pq->items[i].node = node;
    while (i > 0) {                                     /* sift up */
        size_t parent = (i - 1) / 2;
        if (!pq_less(pq, pq->items[i], pq->items[parent])) break;
        PqItem tmp = pq->items[i];
        pq->items[i] = pq->items[parent];
        pq->items[parent] = tmp;
        i = parent;
    }
    return 0;
}

static PqItem pq_pop(Pq *pq)                            /* caller checks size > 0 */
{
    PqItem top = pq->items[0];
    pq->items[0] = pq->items[--pq->size];
    size_t i = 0;
    for (;;) {                                          /* sift down */
        size_t left = 2 * i + 1, right = 2 * i + 2, best = i;
        if (left  < pq->size && pq_less(pq, pq->items[left],  pq->items[best])) best = left;
        if (right < pq->size && pq_less(pq, pq->items[right], pq->items[best])) best = right;
        if (best == i) break;
        PqItem tmp = pq->items[i];
        pq->items[i] = pq->items[best];
        pq->items[best] = tmp;
        i = best;
    }
    return top;
}

int rg_dijkstra(const RouteGraph *graph, int src, double *dist, int *prev)
{
    for (int i = 0; i < graph->count; i++) {
        dist[i] = HUGE_VAL;
        prev[i] = -1;
    }
    dist[src] = 0.0;

    Pq pq = { NULL, 0, 0, graph };
    if (pq_push(&pq, 0.0, src) != 0) return -1;

    while (pq.size > 0) {
        PqItem top = pq_pop(&pq);
        if (top.d > dist[top.node]) continue;           /* stale entry: a shorter route was found later */

        for (const RgEdge *edge = graph->nodes[top.node].first; edge; edge = edge->next) {
            double candidate = top.d + edge->km;
            if (candidate < dist[edge->to]) {           /* found a shorter way to the neighbour */
                dist[edge->to] = candidate;
                prev[edge->to] = top.node;
                if (pq_push(&pq, candidate, edge->to) != 0) {
                    free(pq.items);
                    return -1;
                }
            }
        }
    }
    free(pq.items);
    return 0;
}

int rg_shortest_path(const RouteGraph *graph, int from, int to,
                     double *km, int *path_out, int *path_len)
{
    int n = graph->count;
    double *dist = malloc((size_t)n * sizeof *dist);
    int *prev = malloc((size_t)n * sizeof *prev);
    if (!dist || !prev) {
        free(dist);
        free(prev);
        return -1;
    }
    if (rg_dijkstra(graph, from, dist, prev) != 0) {
        free(dist);
        free(prev);
        return -1;
    }

    int result;
    if (dist[to] == HUGE_VAL) {
        result = 1;                                     /* no road connects them */
    } else {
        int len = 0;                                    /* walk back from the end ... */
        for (int node = to; node != -1; node = prev[node]) path_out[len++] = node;
        for (int i = 0, j = len - 1; i < j; i++, j--) { /* ... then reverse it */
            int tmp = path_out[i];
            path_out[i] = path_out[j];
            path_out[j] = tmp;
        }
        *km = dist[to];
        *path_len = len;
        result = 0;
    }
    free(dist);
    free(prev);
    return result;
}
