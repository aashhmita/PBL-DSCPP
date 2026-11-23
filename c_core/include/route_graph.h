
#ifndef ROUTE_GRAPH_H
#define ROUTE_GRAPH_H

#include "straycare_types.h"

#ifdef __cplusplus
extern "C" {
#endif

#define RG_ERR_NOMEM     (-1)
#define RG_ERR_SAME      (-2)   
#define RG_ERR_DISTANCE  (-3)  

typedef struct RgEdge {
    int to;                    
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

RouteGraph *rg_create(void);                                   /* NULL if out of memory */
void        rg_destroy(RouteGraph *graph);
void        rg_clear(RouteGraph *graph);

int         rg_add_location(RouteGraph *graph, const char *name);   /* index of the node, or -1 */
int         rg_find(const RouteGraph *graph, const char *name);     /* index, or -1 if unknown  */
int         rg_node_count(const RouteGraph *graph);
const char *rg_node_name(const RouteGraph *graph, int index);

/* Add or update a two-way road. Returns 0, or RG_ERR_SAME / RG_ERR_DISTANCE / RG_ERR_NOMEM. */
int         rg_add_road(RouteGraph *graph, const char *a, const char *b, double km);

/* Calls callback once per road. */
void        rg_foreach_road(const RouteGraph *graph,
                            void (*callback)(const char *a, const char *b, double km, void *context),
                            void *context);

/* Shortest distance from node src to EVERY node. dist[] and prev[] must hold node_count entries.
 * Unreachable nodes get dist = HUGE_VAL (infinity); prev[] is -1 for src and unreachable nodes.
 * Returns 0, or -1 if out of memory. */
int         rg_dijkstra(const RouteGraph *graph, int src, double *dist, int *prev);

/* Shortest path between two nodes. path_out must hold node_count entries.
 * Returns 0 and fills *km, path_out[0..*path_len) (start first);  1 if no route;  -1 on error. */
int         rg_shortest_path(const RouteGraph *graph, int from, int to,
                             double *km, int *path_out, int *path_len);

#ifdef __cplusplus
}
#endif

#endif /* ROUTE_GRAPH_H */
