#include "StrayCareAPI.h"
#include "../c_core/heap/triage_heap.h"
#include "../c_core/graph/route_graph.h"
#include "../c_core/hash/animal_hash.h"
#include "../c_core/linkedlist/medical_log.h"
#include "../c_core/queue/food_queue.h"

#include <cstdio>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>
#include <cstdint>
namespace {TriageHeap heap;
RouteGraph graph;
AnimalHash animals;
MedicalLog logs;
FoodQueue foods;
bool initialized = false;

void initialize_all() {
    if (initialized) {
        return;
    }
    triage_init(&heap);
    route_graph_init(&graph);
    animal_hash_init(&animals);
    medical_log_init(&logs);
    food_queue_init(&foods);
    initialized = true;
}
