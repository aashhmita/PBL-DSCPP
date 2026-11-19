/* medical_log.h : chronological treatment history, a singly linked list with a tail pointer.
 *
 * History is only ever appended (never rewritten), so appending at the tail is O(1) and
 * walking the list from the head gives the entries oldest -> newest.
 *
 *   append O(1)   walk O(n)
 */
#ifndef MEDICAL_LOG_H
#define MEDICAL_LOG_H

#include <stddef.h>
#include "straycare_types.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct MlNode {
    MedicalEntry entry;
    struct MlNode *next;
} MlNode;

typedef struct {
    MlNode *head;
    MlNode *tail;
    size_t size;
} MedicalLog;

MedicalLog *ml_create(void);                                   /* NULL if out of memory */
void        ml_destroy(MedicalLog *log);
void        ml_clear(MedicalLog *log);
int         ml_append(MedicalLog *log, const MedicalEntry *entry);   /* 0 ok, -1 no memory */
size_t      ml_remove_animal(MedicalLog *log, const char *animal_id);  /* returns how many removed */
size_t      ml_size(const MedicalLog *log);
void        ml_foreach(const MedicalLog *log,                        /* oldest first */
                       void (*callback)(const MedicalEntry *entry, void *context),
                       void *context);

#ifdef __cplusplus
}
#endif

#endif /* MEDICAL_LOG_H */
