/* animal_hash.h : hash table with separate chaining, keyed by animal ID.
 *
 *   put / get / remove : O(1) on average (O(n) worst case if everything collides)
 *   The table doubles when size/capacity > 0.75, which keeps the chains short.
 *   Nodes are never moved in memory, so a pointer returned by ah_get() stays valid
 *   until that animal is removed (even if the table grows meanwhile).
 */
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
