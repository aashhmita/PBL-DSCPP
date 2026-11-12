#include "animal_hash.h"
#include <stdlib.h>
#include <string.h>

static unsigned bucket(int id) {
    return (unsigned)id % ANIMAL_BUCKETS;
}

void animal_hash_init(AnimalHash *t) {
    if (t) {
        for (int i = 0; i < ANIMAL_BUCKETS; i++) {
            t->buckets[i] = NULL;
        }
    }
}

int animal_hash_insert(AnimalHash *t, const Animal *a) {
    if (!t || !a || a->animal_id <= 0) return 0;
    
    unsigned b = bucket(a->animal_id);
    for (AnimalEntry *e = t->buckets[b]; e; e = e->next) {
        if (e->animal.animal_id == a->animal_id) return 0;
    }
    
    AnimalEntry *e = (AnimalEntry *)malloc(sizeof(*e));
    if (!e) return 0;
    
    e->animal = *a;
    e->next = t->buckets[b];
    t->buckets[b] = e;
    
    return 1;
}

int animal_hash_find(const AnimalHash *t, int id, Animal *out) {
    if (!t || !out || id <= 0) return 0;
    
    for (AnimalEntry *e = t->buckets[bucket(id)]; e; e = e->next) {
        if (e->animal.animal_id == id) {
            *out = e->animal;
            return 1;
        }
    }
    
    return 0;
}

int animal_hash_delete(AnimalHash *t, int id) {
    if (!t || id <= 0) return 0;
    
    AnimalEntry **p = &t->buckets[bucket(id)];
    while (*p) {
        if ((*p)->animal.animal_id == id) {
            AnimalEntry *old = *p;
            *p = old->next;
            free(old);
            return 1;
        }
        p = &(*p)->next;
    }
    
    return 0;
}

void animal_hash_free(AnimalHash *t) {
    if (!t) return;
    
    for (int i = 0; i < ANIMAL_BUCKETS; i++) {
        AnimalEntry *e = t->buckets[i];
        while (e) {
            AnimalEntry *n = e->next;
            free(e);
            e = n;
        }
        t->buckets[i] = NULL;
    }
}