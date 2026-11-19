#include "food_queue.h"

#include <stdlib.h>
#include <string.h>

FoodQueue *fq_create(void)
{
    FoodQueue *queue = malloc(sizeof *queue);
    if (!queue) return NULL;
    queue->head = queue->tail = NULL;
    queue->size = 0;
    return queue;
}

void fq_clear(FoodQueue *queue)
{
    FqNode *node = queue->head;
    while (node) {
        FqNode *next = node->next;
        free(node);
        node = next;
    }
    queue->head = queue->tail = NULL;
    queue->size = 0;
}

void fq_destroy(FoodQueue *queue)
{
    if (!queue) return;
    fq_clear(queue);
    free(queue);
}

int fq_enqueue(FoodQueue *queue, const FoodOffer *offer)
{
    FqNode *node = malloc(sizeof *node);
    if (!node) return -1;
    node->offer = *offer;
    node->next = NULL;
    if (queue->tail) queue->tail->next = node;
    else queue->head = node;                 /* the queue was empty */
    queue->tail = node;
    queue->size++;
    return 0;
}

int fq_dequeue(FoodQueue *queue, FoodOffer *out)
{
    FqNode *node = queue->head;
    if (!node) return 0;
    if (out) *out = node->offer;
    queue->head = node->next;
    if (!queue->head) queue->tail = NULL;    /* we removed the last element */
    free(node);
    queue->size--;
    return 1;
}

const FoodOffer *fq_peek(const FoodQueue *queue)
{
    return queue->head ? &queue->head->offer : NULL;
}

FoodOffer *fq_find(const FoodQueue *queue, const char *offer_id)
{
    for (FqNode *node = queue->head; node; node = node->next) {
        if (strcmp(node->offer.offer_id, offer_id) == 0) return &node->offer;
    }
    return NULL;
}

int fq_remove(FoodQueue *queue, const char *offer_id)
{
    FqNode *prev = NULL;
    for (FqNode *node = queue->head; node; prev = node, node = node->next) {
        if (strcmp(node->offer.offer_id, offer_id) == 0) {
            if (prev) prev->next = node->next;
            else queue->head = node->next;
            if (node == queue->tail) queue->tail = prev;   /* removed the last node */
            free(node);
            queue->size--;
            return 1;
        }
    }
    return 0;
}

size_t fq_size(const FoodQueue *queue)
{
    return queue->size;
}

void fq_foreach(const FoodQueue *queue,
                void (*callback)(const FoodOffer *offer, void *context),
                void *context)
{
    for (const FqNode *node = queue->head; node; node = node->next) {
        callback(&node->offer, context);
    }
}
