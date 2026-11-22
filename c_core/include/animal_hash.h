#ifndef ANIMAL_HASH_H
#define ANIMAL_HASH_H

#include <stddef.h>
#include "straycare_types.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct AhNode {
    Animal animal;
    struct AhNode *next;          /* next node in the same bucket (the chain) */
} AhNode;

typedef struct {
    AhNode **buckets;
    size_t capacity;
    size_t size;
} AnimalHash;

AnimalHash *ah_create(size_t capacity);              /* NULL if out of memory        */
void        ah_destroy(AnimalHash *table);
void        ah_clear(AnimalHash *table);             /* remove every animal          */
int         ah_put(AnimalHash *table, const Animal *animal);   /* 0 ok, -1 no memory; same ID overwrites */
Animal     *ah_get(const AnimalHash *table, const char *id);   /* NULL if not found    */
int         ah_remove(AnimalHash *table, const char *id);      /* 1 removed, 0 not found */
size_t      ah_size(const AnimalHash *table);
size_t      ah_capacity(const AnimalHash *table);
void        ah_foreach(const AnimalHash *table,
                       void (*callback)(const Animal *animal, void *context),
                       void *context);

#ifdef __cplusplus
}
#endif

#endif /* ANIMAL_HASH_H */
