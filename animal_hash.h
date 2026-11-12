#ifdef ANIMAL_HASH_H
#define ANIMAL_HASH_Hgit add animal_hash.h
#define ANIMAL_BUCKETS 101
typedef struct { int animal_id; char name[50]; char species[24]; char location[100]; } Animal;
typedef struct AnimalEntry { Animal animal; struct AnimalEntry *next; } AnimalEntry;
typedef struct { AnimalEntry *buckets[ANIMAL_BUCKETS]; } 
AnimalHash;
#ifdef __cplusplus
extern "C" {
#endif