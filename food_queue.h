#ifndef FOOD_QUEUE_H
#define FOOD_QUEUE_H
#define FOOD_NAME_MAX 64
#define DONOR_NAME_MAX 64
typedef struct { int offer_id; char donor[DONOR_NAME_MAX]; char food[FOOD_NAME_MAX]; int servings; int shelter_id; } FoodOffer;
typedef struct FoodNode { FoodOffer offer; struct FoodNode *next; } FoodNode;
typedef struct { FoodNode *front,*rear; int size; } FoodQueue;
#ifdef __cplusplus
extern "C" {
#endif

void food_queue_init(FoodQueue *q);
int food_queue_enqueue(FoodQueue *q,const FoodOffer *offer);
int food_queue_peek(const FoodQueue *q,FoodOffer *out);
int food_queue_dequeue(FoodQueue *q,FoodOffer *out);
void food_queue_free(FoodQueue *q);
#ifdef __cplusplus
}
#endif
#endif
