#ifndef ROUTE_GRAPH_H
#define ROUTE_GRAPH_H
#define ROUTE_MAX_NODES 100
#define ROUTE_INF 1000000000

typedef struct RouteEdge { int to; int distance; struct RouteEdge *next; } RouteEdge;
typedef struct { int id; char name[64]; RouteEdge *edges; } RouteNode;
typedef struct { RouteNode nodes[ROUTE_MAX_NODES]; int count; } RouteGraph;
#ifdef __cplusplus
extern "C" {
#endif

void route_graph_init(RouteGraph *g);
int route_add_location(RouteGraph *g,int id,const char *name);
int route_add_road(RouteGraph *g,int from_id,int to_id,int distance,int bidirectional);
int route_shortest_path(const RouteGraph *g,int start_id,int end_id,int *path_ids,int capacity,int *distance_out);
void route_graph_free(RouteGraph *g);
#ifdef __cplusplus
}
#endif
#endif
