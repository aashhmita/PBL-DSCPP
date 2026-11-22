#include "medical_log.h"

#include <stdlib.h>
#include <string.h>

MedicalLog *ml_create(void)
{
    MedicalLog *log = malloc(sizeof *log);
    if (!log) return NULL;
    log->head = log->tail = NULL;
    log->size = 0;
    return log;
}

void ml_clear(MedicalLog *log)
{
    if(log == NULL)
        return;
    MlNode *node = log->head;
    while (node) {
        MlNode *next = node->next;
        free(node);
        node = next;
    }
    log->head = log->tail = NULL;
    log->size = 0;
}

void ml_destroy(MedicalLog *log)
{
    if (!log) return;
    ml_clear(log);
    free(log);
}

int ml_append(MedicalLog *log, const MedicalEntry *entry)
{
    if (log == NULL || entry == NULL ||
        entry->animal_id[0] == '\0' ||
        memchr(entry->animal_id, '\0', sizeof entry->animal_id) == NULL)
        return -1;

    MlNode *node = malloc(sizeof *node);
    if (!node) return -1;

    node->entry = *entry;
    node->next = NULL;

    if (log->tail) log->tail->next = node;
    else log->head = node;

    log->tail = node;
    log->size++;

    return 0;
}

size_t ml_remove_animal(MedicalLog *log, const char *animal_id)
{
    /* Walk once with a pointer-to-pointer, unlinking every node of this animal.
       `link` always points at the pointer that leads to the current node. */
    if(log == NULL||animal_id == NULL||animal_id[0] == '\0')
        return 0;
    size_t removed = 0;
    MlNode **link = &log->head;
    MlNode *previous = NULL;           /* last node we kept: becomes the new tail */
    while (*link) {
        MlNode *node = *link;
        if (strcmp(node->entry.animal_id, animal_id) == 0) {
            *link = node->next;
            free(node);
            removed++;
        } else {
            previous = node;
            link = &node->next;
        }
    }
    log->tail = previous;
    log->size -= removed;
    return removed;
}

size_t ml_size(const MedicalLog *log)
{
    if(log ==NULL)
        return 0;
    return log->size;
}

void ml_foreach(const MedicalLog *log,
                void (*callback)(const MedicalEntry *entry, void *context),
                void *context)
{
    if (log == NULL || callback == NULL)
        return;

    for (const MlNode *node = log->head; node; node = node->next) {
        callback(&node->entry, context);
    }
}
