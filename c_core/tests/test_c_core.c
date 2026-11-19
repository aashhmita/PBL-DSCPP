/* test_c_core.c : tests for the five C modules, no other language involved.
 * Build and run with:   python build.py --test
 */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "animal_hash.h"
#include "food_queue.h"
#include "medical_log.h"
#include "route_graph.h"
#include "triage_heap.h"

static int failures = 0;
static int checks = 0;

#define CHECK(cond)                                                              \
    do {                                                                         \
        checks++;                                                                \
        if (!(cond)) {                                                           \
            failures++;                                                          \
            printf("  FAIL  %s:%d  %s\n", __FILE__, __LINE__, #cond);            \
        }                                                                        \
    } while (0)

static Animal make_animal(const char *id, const char *name)
{
    Animal a;
    memset(&a, 0, sizeof a);
    sc_copy(a.id, sizeof a.id, id);
    sc_copy(a.name, sizeof a.name, name);
    return a;
}

static FoodOffer make_offer(const char *id)
{
    FoodOffer o;
    memset(&o, 0, sizeof o);
    sc_copy(o.offer_id, sizeof o.offer_id, id);
    return o;
}

/* ---- triage heap -------------------------------------------------------------------- */

static void test_heap_orders_by_urgency_then_age(void)
{
    TriageHeap *h = th_create();
    CHECK(h != NULL);
    th_push(h, 3, 1003, "SC-1003");   /* Low      */
    th_push(h, 1, 1001, "SC-1001");   /* High     */
    th_push(h, 0, 1004, "SC-1004");   /* Critical */
    th_push(h, 1, 1002, "SC-1002");   /* High, reported after SC-1001 */

    TriageEntry e;
    CHECK(th_peek(h, &e) && strcmp(e.id, "SC-1004") == 0);
    const char *expected[] = { "SC-1004", "SC-1001", "SC-1002", "SC-1003" };
    for (int i = 0; i < 4; i++) {
        CHECK(th_pop(h, &e) == 1);
        CHECK(strcmp(e.id, expected[i]) == 0);
    }
    CHECK(th_pop(h, &e) == 0);          /* empty now */
    CHECK(th_peek(h, &e) == 0);
    th_destroy(h);
}

static void test_heap_build_and_growth(void)
{
    enum { N = 500 };
    TriageEntry entries[N];
    srand(12345);
    for (int i = 0; i < N; i++) {
        entries[i].rank = rand() % 4;
        entries[i].seq = i;
        snprintf(entries[i].id, sizeof entries[i].id, "SC-%d", 1000 + i);
    }
    TriageHeap *built = th_build(entries, N);        /* O(n) heapify */
    TriageHeap *pushed = th_create();                /* grows past its first capacity */
    for (int i = 0; i < N; i++) th_push(pushed, entries[i].rank, entries[i].seq, entries[i].id);
    CHECK(th_size(built) == N && th_size(pushed) == N);

    int sorted = 1;
    TriageEntry a, b, prev = { -1, -1, "" };
    for (int i = 0; i < N; i++) {
        th_pop(built, &a);
        th_pop(pushed, &b);
        if (strcmp(a.id, b.id) != 0) sorted = 0;     /* both ways of building must agree */
        if (a.rank < prev.rank || (a.rank == prev.rank && a.seq < prev.seq)) sorted = 0;
        prev = a;
    }
    CHECK(sorted);
    th_destroy(built);
    th_destroy(pushed);

    TriageHeap *empty = th_build(NULL, 0);
    CHECK(empty != NULL && th_size(empty) == 0);
    th_destroy(empty);
}

/* ---- hash table --------------------------------------------------------------------- */

static void count_cb(const Animal *a, void *ctx)
{
    (void)a;
    (*(int *)ctx)++;
}

static void test_hash_put_get_overwrite_remove(void)
{
    AnimalHash *t = ah_create(8);
    Animal a = make_animal("SC-1", "first");
    CHECK(ah_put(t, &a) == 0);
    sc_copy(a.name, sizeof a.name, "second");
    CHECK(ah_put(t, &a) == 0);                       /* same ID: overwrite, not a duplicate */
    CHECK(ah_size(t) == 1);
    CHECK(strcmp(ah_get(t, "SC-1")->name, "second") == 0);
    CHECK(ah_get(t, "SC-404") == NULL);
    CHECK(ah_remove(t, "SC-1") == 1);
    CHECK(ah_remove(t, "SC-1") == 0);
    CHECK(ah_size(t) == 0 && ah_get(t, "SC-1") == NULL);
    ah_destroy(t);
}

static void test_hash_resize_keeps_everything_and_pointers_stay_valid(void)
{
    AnimalHash *t = ah_create(4);
    Animal first = make_animal("SC-0", "zero");
    ah_put(t, &first);
    Animal *kept = ah_get(t, "SC-0");                /* pointer taken BEFORE the table grows */

    char id[16];
    for (int i = 1; i < 1000; i++) {
        snprintf(id, sizeof id, "SC-%d", i);
        Animal a = make_animal(id, "x");
        CHECK(ah_put(t, &a) == 0);
    }
    CHECK(ah_size(t) == 1000);
    CHECK(ah_capacity(t) > 4);
    CHECK((double)ah_size(t) / (double)ah_capacity(t) <= 0.75);
    CHECK(ah_get(t, "SC-0") == kept);                /* nodes never move */
    CHECK(strcmp(kept->name, "zero") == 0);

    int found = 0;
    for (int i = 0; i < 1000; i++) {
        snprintf(id, sizeof id, "SC-%d", i);
        if (ah_get(t, id)) found++;
    }
    CHECK(found == 1000);

    int visited = 0;
    ah_foreach(t, count_cb, &visited);
    CHECK(visited == 1000);

    ah_clear(t);
    CHECK(ah_size(t) == 0 && ah_get(t, "SC-5") == NULL);
    ah_destroy(t);
}

/* ---- food queue --------------------------------------------------------------------- */

static void collect_ids(const FoodOffer *o, void *ctx)
{
    strcat((char *)ctx, o->offer_id);
    strcat((char *)ctx, ",");
}

static void test_queue_is_fifo(void)
{
    FoodQueue *q = fq_create();
    FoodOffer o1 = make_offer("FD-1"), o2 = make_offer("FD-2"), o3 = make_offer("FD-3");
    CHECK(fq_peek(q) == NULL);
    fq_enqueue(q, &o1);
    fq_enqueue(q, &o2);
    fq_enqueue(q, &o3);
    CHECK(fq_size(q) == 3);
    CHECK(strcmp(fq_peek(q)->offer_id, "FD-1") == 0);

    FoodOffer out;
    CHECK(fq_dequeue(q, &out) && strcmp(out.offer_id, "FD-1") == 0);
    CHECK(fq_dequeue(q, &out) && strcmp(out.offer_id, "FD-2") == 0);
    CHECK(fq_dequeue(q, &out) && strcmp(out.offer_id, "FD-3") == 0);
    CHECK(fq_dequeue(q, &out) == 0);
    CHECK(fq_size(q) == 0);
    fq_enqueue(q, &o1);                              /* queue must work again after being emptied */
    CHECK(strcmp(fq_peek(q)->offer_id, "FD-1") == 0);
    fq_destroy(q);
}

static void test_queue_remove_head_middle_tail_and_find(void)
{
    FoodQueue *q = fq_create();
    char names[4][8] = { "FD-1", "FD-2", "FD-3", "FD-4" };
    for (int i = 0; i < 4; i++) {
        FoodOffer o = make_offer(names[i]);
        fq_enqueue(q, &o);
    }
    CHECK(fq_remove(q, "FD-2") == 1);                /* middle */
    CHECK(fq_remove(q, "FD-4") == 1);                /* tail   */
    CHECK(fq_remove(q, "FD-1") == 1);                /* head   */
    CHECK(fq_remove(q, "FD-99") == 0);

    char order[64] = "";
    fq_foreach(q, collect_ids, order);
    CHECK(strcmp(order, "FD-3,") == 0);

    FoodOffer five = make_offer("FD-5");
    fq_enqueue(q, &five);                            /* the tail pointer must still be valid */
    order[0] = '\0';
    fq_foreach(q, collect_ids, order);
    CHECK(strcmp(order, "FD-3,FD-5,") == 0);

    FoodOffer *found = fq_find(q, "FD-5");
    CHECK(found != NULL);
    sc_copy(found->status, sizeof found->status, "Pickup pending");   /* edit in place */
    CHECK(strcmp(fq_find(q, "FD-5")->status, "Pickup pending") == 0);
    CHECK(fq_find(q, "FD-2") == NULL);
    fq_clear(q);
    CHECK(fq_size(q) == 0 && fq_peek(q) == NULL);
    fq_destroy(q);
}

/* ---- medical log -------------------------------------------------------------------- */

static void collect_treatments(const MedicalEntry *e, void *ctx)
{
    strcat((char *)ctx, e->treatment);
    strcat((char *)ctx, ",");
}

static void test_medical_log_keeps_order(void)
{
    MedicalLog *log = ml_create();
    const char *treatments[] = { "t1", "t2", "t3" };
    for (int i = 0; i < 3; i++) {
        MedicalEntry e;
        memset(&e, 0, sizeof e);
        sc_copy(e.treatment, sizeof e.treatment, treatments[i]);
        CHECK(ml_append(log, &e) == 0);
    }
    CHECK(ml_size(log) == 3);
    char order[64] = "";
    ml_foreach(log, collect_treatments, order);
    CHECK(strcmp(order, "t1,t2,t3,") == 0);          /* oldest first */
    ml_clear(log);
    CHECK(ml_size(log) == 0);
    ml_destroy(log);
}

/* ---- route graph -------------------------------------------------------------------- */

static RouteGraph *sample_graph(void)
{
    RouteGraph *g = rg_create();
    rg_add_road(g, "A", "B", 1);
    rg_add_road(g, "B", "C", 1);
    rg_add_road(g, "A", "C", 5);                     /* the direct road is LONGER than A-B-C */
    rg_add_road(g, "C", "D", 2);
    rg_add_location(g, "Island");                    /* connected to nothing */
    return g;
}

static void count_roads(const char *a, const char *b, double km, void *ctx)
{
    (void)a; (void)b; (void)km;
    (*(int *)ctx)++;
}

static void test_medical_log_remove_animal(void)
{
    MedicalLog *log = ml_create();
    /* order: A B A C A -> remove A leaves B C; remove head, middle and tail cases */
    const char *ids[] = { "A", "B", "A", "C", "A" };
    const char *names[] = { "1", "2", "3", "4", "5" };
    for (int i = 0; i < 5; i++) {
        MedicalEntry e;
        memset(&e, 0, sizeof e);
        sc_copy(e.animal_id, sizeof e.animal_id, ids[i]);
        sc_copy(e.treatment, sizeof e.treatment, names[i]);
        CHECK(ml_append(log, &e) == 0);
    }
    CHECK(ml_remove_animal(log, "Z") == 0);
    CHECK(ml_size(log) == 5);
    CHECK(ml_remove_animal(log, "A") == 3);
    CHECK(ml_size(log) == 2);
    char order[64] = "";
    ml_foreach(log, collect_treatments, order);
    CHECK(strcmp(order, "2,4,") == 0);
    MedicalEntry e;                                   /* tail pointer must still be valid */
    memset(&e, 0, sizeof e);
    sc_copy(e.animal_id, sizeof e.animal_id, "D");
    sc_copy(e.treatment, sizeof e.treatment, "6");
    CHECK(ml_append(log, &e) == 0);
    order[0] = 0;
    ml_foreach(log, collect_treatments, order);
    CHECK(strcmp(order, "2,4,6,") == 0);
    CHECK(ml_remove_animal(log, "B") == 1);
    CHECK(ml_remove_animal(log, "C") == 1);
    CHECK(ml_remove_animal(log, "D") == 1);           /* now empty */
    CHECK(ml_size(log) == 0);
    CHECK(log->head == NULL && log->tail == NULL);
    CHECK(ml_append(log, &e) == 0);
    CHECK(ml_size(log) == 1);
    ml_destroy(log);
}

static void test_graph_shortest_path_prefers_the_detour(void)
{
    RouteGraph *g = sample_graph();
    int path[16], len = 0;
    double km = 0;
    CHECK(rg_shortest_path(g, rg_find(g, "A"), rg_find(g, "D"), &km, path, &len) == 0);
    CHECK(fabs(km - 4.0) < 1e-9);
    CHECK(len == 4);
    const char *expected[] = { "A", "B", "C", "D" };
    for (int i = 0; i < len && i < 4; i++) CHECK(strcmp(rg_node_name(g, path[i]), expected[i]) == 0);
    rg_destroy(g);
}

static void test_graph_edge_cases(void)
{
    RouteGraph *g = sample_graph();
    int path[16], len = 0;
    double km = -1;

    CHECK(rg_shortest_path(g, rg_find(g, "A"), rg_find(g, "Island"), &km, path, &len) == 1);   /* no route */
    CHECK(rg_shortest_path(g, rg_find(g, "A"), rg_find(g, "A"), &km, path, &len) == 0);        /* same place */
    CHECK(km == 0.0 && len == 1);

    CHECK(rg_add_road(g, "A", "A", 1) == RG_ERR_SAME);
    CHECK(rg_add_road(g, "A", "Z", 0) == RG_ERR_DISTANCE);
    CHECK(rg_add_road(g, "A", "Z", -3) == RG_ERR_DISTANCE);
    CHECK(rg_add_road(g, "A", "Z", NAN) == RG_ERR_DISTANCE);
    CHECK(rg_find(g, "Z") == -1);                    /* a rejected road adds no location */

    CHECK(rg_add_road(g, "A", "C", 1.5) == 0);       /* update an existing road, both directions */
    CHECK(rg_shortest_path(g, rg_find(g, "A"), rg_find(g, "C"), &km, path, &len) == 0);
    CHECK(fabs(km - 1.5) < 1e-9 && len == 2);

    int roads = 0;
    rg_foreach_road(g, count_roads, &roads);
    CHECK(roads == 4);                               /* every road reported once, not twice */
    rg_destroy(g);
}

static void test_graph_dijkstra_all_distances_and_growth(void)
{
    RouteGraph *g = rg_create();
    char a[16], b[16];
    for (int i = 0; i < 100; i++) {                  /* a long chain forces the node array to grow */
        snprintf(a, sizeof a, "N%03d", i);
        snprintf(b, sizeof b, "N%03d", i + 1);
        CHECK(rg_add_road(g, a, b, 2.0) == 0);
    }
    CHECK(rg_node_count(g) == 101);
    double dist[101];
    int prev[101];
    CHECK(rg_dijkstra(g, rg_find(g, "N000"), dist, prev) == 0);
    CHECK(fabs(dist[rg_find(g, "N100")] - 200.0) < 1e-9);
    CHECK(prev[rg_find(g, "N000")] == -1);
    rg_clear(g);
    CHECK(rg_node_count(g) == 0);
    rg_destroy(g);
}

int main(void)
{
    test_heap_orders_by_urgency_then_age();
    test_heap_build_and_growth();
    test_hash_put_get_overwrite_remove();
    test_hash_resize_keeps_everything_and_pointers_stay_valid();
    test_queue_is_fifo();
    test_queue_remove_head_middle_tail_and_find();
    test_medical_log_keeps_order();
    test_medical_log_remove_animal();
    test_graph_shortest_path_prefers_the_detour();
    test_graph_edge_cases();
    test_graph_dijkstra_all_distances_and_growth();

    printf("C core tests: %d checks, %d failed\n", checks, failures);
    return failures ? 1 : 0;
}
