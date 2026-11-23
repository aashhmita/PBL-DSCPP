
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
    RgEdge *first;              
    RgEdge *last;
} RgNode;

typedef struct {
    RgNode *nodes;
    int count;
    int capacity;
} RouteGraph;

RouteGraph *rg_create(void);                               
void        rg_destroy(RouteGraph *graph);
void        rg_clear(RouteGraph *graph);

int         rg_add_location(RouteGraph *graph, const char *name);  
int         rg_find(const RouteGraph *graph, const char *name);     /* index, or -1 if unknown  */
int         rg_node_count(const RouteGraph *graph);
const char *rg_node_name(const RouteGraph *graph, int index);

/* Add or update a two-way road. Returns 0, or RG_ERR_SAME / RG_ERR_DISTANCE / RG_ERR_NOMEM. */
int         rg_add_road(RouteGraph *graph, const char *a, const char *b, double km);

/* Calls callback once per road. */
void        rg_foreach_road(const RouteGraph *graph,
                            void (*callback)(const char *a, const char *b, double km, void *context),
                            void *context);


int         rg_dijkstra(const RouteGraph *graph, int src, double *dist, int *prev);

/* Shortest path between two nodes. path_out must hold node_count entries.

int         rg_shortest_path(const RouteGraph *graph, int from, int to,
                             double *km, int *path_out, int *path_len);

#ifdef __cplusplus
}
#endif

#endif /* ROUTE_GRAPH_H */
