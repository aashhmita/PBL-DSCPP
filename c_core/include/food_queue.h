#ifndef FOOD_QUEUE_H
#define FOOD_QUEUE_H

#include <stddef.h>
#include "straycare_types.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct FqNode {
    FoodOffer offer;
    struct FqNode *next;
} FqNode;

typedef struct {
    FqNode *head;              /* oldest offer: leaves first */
    FqNode *tail;              /* newest offer: last in line */
    size_t size;
} FoodQueue;

FoodQueue *fq_create(void);                                  /* NULL if out of memory */
void       fq_destroy(FoodQueue *queue);
void       fq_clear(FoodQueue *queue);
int        fq_enqueue(FoodQueue *queue, const FoodOffer *offer);   /* 0 ok, -1 no memory */
int        fq_dequeue(FoodQueue *queue, FoodOffer *out);           /* 1 removed, 0 empty */
const FoodOffer *fq_peek(const FoodQueue *queue);                  /* NULL if empty      */
FoodOffer *fq_find(const FoodQueue *queue, const char *offer_id);  /* NULL if not queued */
int        fq_remove(FoodQueue *queue, const char *offer_id);      /* 1 removed, 0 not found */
size_t     fq_size(const FoodQueue *queue);
void       fq_foreach(const FoodQueue *queue,                      /* oldest first */
                      void (*callback)(const FoodOffer *offer, void *context),
                      void *context);

#ifdef __cplusplus
}
#endif

#endif /* FOOD_QUEUE_H */
