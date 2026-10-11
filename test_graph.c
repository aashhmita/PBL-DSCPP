#include "../backend/c_core/graph/route_graph.h"
#include <assert.h>

int main(void) {
    RouteGraph graph;
    int path[10];
    int distance = 0;

    route_graph_init(&graph);

    assert(route_add_location(&graph, 1, "A"));
    assert(route_add_location(&graph, 2, "B"));
    assert(route_add_location(&graph, 3, "C"));
    assert(!route_add_location(&graph, 1, "Duplicate"));

    assert(route_add_road(&graph, 1, 2, 4, 1));
    assert(route_add_road(&graph, 2, 3, 2, 1));
    assert(route_add_road(&graph, 1, 3, 10, 1));

    int count = route_shortest_path(&graph, 1, 3, path, 10, &distance);
    assert(count == 3);
    assert(distance == 6);
    assert(path[0] == 1 && path[1] == 2 && path[2] == 3);

    route_graph_free(&graph);
    return 0;
}
