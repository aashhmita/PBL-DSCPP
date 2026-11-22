
/* medical_log.h : chronological treatment history using a singly linked list.
 *
 * New records are appended at the tail, maintaining insertion order.
 * Traversing from head displays records from oldest to newest.
 *
 * Time complexity:
 * Append: O(1)
 * Traversal: O(n)
 */

#ifndef MEDICAL_LOG_H
#define MEDICAL_LOG_H

#include <stddef.h>
#include "straycare_types.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Node containing one medical record */
typedef struct MlNode {
    MedicalEntry entry;
    struct MlNode *next;
} MlNode;

/* Medical log with head, tail and entry count */
typedef struct {
    MlNode *head;
    MlNode *tail;
    size_t size;
} MedicalLog;

/* Creates an empty log; returns NULL on failure */
MedicalLog *ml_create(void);

/* Releases all memory used by the log */
void ml_destroy(MedicalLog *log);

/* Removes all entries while keeping the log usable */
void ml_clear(MedicalLog *log);

/* Adds a new entry; returns 0 on success, -1 on failure */
int ml_append(MedicalLog *log, const MedicalEntry *entry);

/* Removes all entries for the given animal and returns the count */
size_t ml_remove_animal(MedicalLog *log, const char *animal_id);

/* Returns the total number of entries */
size_t ml_size(const MedicalLog *log);

/* Visits entries in insertion order (oldest first) */
void ml_foreach(const MedicalLog *log,
                void (*callback)(const MedicalEntry *entry, void *context),
                void *context);

#ifdef __cplusplus
}
#endif

#endif /* MEDICAL_LOG_H */
