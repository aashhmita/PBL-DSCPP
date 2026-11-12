#ifndef ANIMAL_HASH_H
#define ANIMAL_HASH_H

#define ANIMAL_BUCKETS 101

typedef struct {
    int animal_id;
    char name[50];
    char species[24];
    char location[100];
} Animal;

typedef struct AnimalEntry {
    Animal animal;
    struct AnimalEntry *next;
} AnimalEntry;

typedef struct {
    AnimalEntry *buckets[ANIMAL_BUCKETS];
} AnimalHash;

#ifdef __cplusplus
extern "C" {
#endif

void animal_hash_init(AnimalHash *table);
int animal_hash_insert(AnimalHash *table, const Animal *animal);
int animal_hash_find(const AnimalHash *table, int animal_id, Animal *out);
int animal_hash_delete(AnimalHash *table, int animal_id);
void animal_hash_free(AnimalHash *table);

#ifdef __cplusplus
}
#endif

#endif /* ANIMAL_HASH_H */