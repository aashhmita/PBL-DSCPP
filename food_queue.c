#include "food_queue.h"
#include <stdlib.h>
#include <string.h>

void food_queue_init(FoodQueue *q) {
    if (q) {
        q->front = q->rear = NULL;
        q->size = 0;
    }
}

int food_queue_enqueue(FoodQueue *q, const FoodOffer *o) {
    if (!q || !o || o->offer_id <= 0 || o->servings <= 0 ||
        !memchr(o->donor, '\0', DONOR_NAME_MAX) ||
        !memchr(o->food, '\0', FOOD_NAME_MAX))
        return 0;

    for (FoodNode *n = q->front; n; n = n->next) {
        if (n->offer.offer_id == o->offer_id)
            return 0;
    }

    FoodNode *n = (FoodNode *)malloc(sizeof *n);
    if (!n)
        return 0;

    n->offer = *o;
    n->next = NULL;

    if (q->rear)
        q->rear->next = n;
    else
        q->front = n;

    q->rear = n;
    q->size++;
    return 1;
}

int food_queue_peek(const FoodQueue *q, FoodOffer *out) {
    if (!q || !out || !q->front)
        return 0;
    *out = q->front->offer;
    return 1;
}

int food_queue_dequeue(FoodQueue *q, FoodOffer *out) {
    if (!q || !out || !q->front)
        return 0;

    FoodNode *n = q->front;
    *out = n->offer;
    q->front = n->next;

    if (!q->front)
        q->rear = NULL;

    free(n);
    q->size--;
    return 1;
}

void food_queue_free(FoodQueue *q) {
    if (!q)
        return;

    FoodNode *n = q->front;
    while (n) {
        FoodNode *x = n->next;
        free(n);
        n = x;
    }
    food_queue_init(q);
}