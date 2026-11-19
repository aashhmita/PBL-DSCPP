#include "animal_hash.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define AH_MIN_CAPACITY 4
#define AH_MAX_LOAD     0.75

/* djb2: h = h * 33 + c, kept to 32 bits (unsigned arithmetic wraps around by itself). */
static uint32_t hash_text(const char *s)
{
    uint32_t h = 5381u;
    while (*s) {
        h = (h << 5) + h + (unsigned char)*s++;
    }
    return h;
}

AnimalHash *ah_create(size_t capacity)
{
    AnimalHash *table = malloc(sizeof *table);
    if (!table) return NULL;
    table->capacity = capacity < AH_MIN_CAPACITY ? AH_MIN_CAPACITY : capacity;
    table->buckets = calloc(table->capacity, sizeof *table->buckets);
    if (!table->buckets) {
        free(table);
        return NULL;
    }
    table->size = 0;
    return table;
}

void ah_clear(AnimalHash *table)
{
    for (size_t i = 0; i < table->capacity; i++) {
        AhNode *node = table->buckets[i];
        while (node) {
            AhNode *next = node->next;
            free(node);
            node = next;
        }
        table->buckets[i] = NULL;
    }
    table->size = 0;
}

void ah_destroy(AnimalHash *table)
{
    if (!table) return;
    ah_clear(table);
    free(table->buckets);
    free(table);
}

/* Double the number of buckets and re-link every node (nodes themselves do not move). */
static void resize(AnimalHash *table)
{
    size_t new_capacity = table->capacity * 2;
    AhNode **new_buckets = calloc(new_capacity, sizeof *new_buckets);
    if (!new_buckets) return;          /* keep working with the old, more crowded table */

    for (size_t i = 0; i < table->capacity; i++) {
        AhNode *node = table->buckets[i];
        while (node) {
            AhNode *next = node->next;
            size_t index = hash_text(node->animal.id) % new_capacity;
            node->next = new_buckets[index];
            new_buckets[index] = node;
            node = next;
        }
    }
    free(table->buckets);
    table->buckets = new_buckets;
    table->capacity = new_capacity;
}

int ah_put(AnimalHash *table, const Animal *animal)
{
    size_t index = hash_text(animal->id) % table->capacity;

    for (AhNode *node = table->buckets[index]; node; node = node->next) {
        if (strcmp(node->animal.id, animal->id) == 0) {
            node->animal = *animal;    /* same ID: overwrite */
            return 0;
        }
    }

    AhNode *node = malloc(sizeof *node);
    if (!node) return -1;
    node->animal = *animal;
    node->next = table->buckets[index];     /* insert at the head of the chain */
    table->buckets[index] = node;
    table->size++;

    if ((double)table->size / (double)table->capacity > AH_MAX_LOAD) {
        resize(table);
    }
    return 0;
}

Animal *ah_get(const AnimalHash *table, const char *id)
{
    size_t index = hash_text(id) % table->capacity;
    for (AhNode *node = table->buckets[index]; node; node = node->next) {
        if (strcmp(node->animal.id, id) == 0) return &node->animal;
    }
    return NULL;
}

int ah_remove(AnimalHash *table, const char *id)
{
    size_t index = hash_text(id) % table->capacity;
    AhNode *prev = NULL;
    for (AhNode *node = table->buckets[index]; node; prev = node, node = node->next) {
        if (strcmp(node->animal.id, id) == 0) {
            if (prev) prev->next = node->next;
            else table->buckets[index] = node->next;
            free(node);
            table->size--;
            return 1;
        }
    }
    return 0;
}

size_t ah_size(const AnimalHash *table)     { return table->size; }
size_t ah_capacity(const AnimalHash *table) { return table->capacity; }

void ah_foreach(const AnimalHash *table,
                void (*callback)(const Animal *animal, void *context),
                void *context)
{
    for (size_t i = 0; i < table->capacity; i++) {
        for (const AhNode *node = table->buckets[i]; node; node = node->next) {
            callback(&node->animal, context);
        }
    }
}
