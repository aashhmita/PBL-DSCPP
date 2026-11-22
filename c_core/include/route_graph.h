/* route_graph.h : weighted, undirected graph of locations + Dijkstra's shortest path.
 *
 * Representation: an array of nodes (one per location); each node owns a linked list of edges
 * {neighbour index, distance in km}. A road A-B is stored twice (A->B and B->A).
 * Dijkstra settles the closest unsettled location first, using a min-heap:  O((V + E) log V).
 */
#ifndef ROUTE_GRAPH_H
#define ROUTE_GRAPH_H

#include "straycare_types.h"

#ifdef __cplusplus
extern "C" {
#endif

#define RG_ERR_NOMEM     (-1)
#define RG_ERR_SAME      (-2)   /* a road must join two different places */
#define RG_ERR_DISTANCE  (-3)   /* distance must be greater than zero    */

typedef struct RgEdge {
    int to;                      /* index of the neighbour */
    double km;
    struct RgEdge *next;
} RgEdge;

typedef struct {
    char name[SC_TEXT_LEN];
    RgEdge *first;               /* edges in the order they were added */
    RgEdge *last;
} RgNode;

typedef struct {
    RgNode *nodes;
    int count;
    int capacity;
} RouteGraph;
