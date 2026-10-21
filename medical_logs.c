#include "medical_log.h"
#include <stdlib.h>
#include <string.h>
void medical_log_init(MedicalLog *l)
{ if (l)
    { l->head = l->tail = NULL; l->size = 0;
    }}
int medical_log_add(MedicalLog *l, int rid, int aid, const char *date, const char *note)
{
    if (!l || rid <= 0 || aid <= 0 || !date || !note || strlen(date) >= 16 || strlen(note) >= MEDICAL_NOTE_MAX)
        return 0;
    for (MedicalRecord *r = l->head; r; r = r->next)
        if (r->record_id == rid)
            return 0;
    MedicalRecord *r = (MedicalRecord *)calloc(1, sizeof *r);
    if (!r)
        return 0;
    r->record_id = rid;
    r->animal_id = aid;
    strcpy(r->date, date);
    strcpy(r->note, note);
    r->prev = l->tail;
    if (l->tail)
        l->tail->next = r;
    else
     l->head = r;
    l->tail = r;
    l->size++;
    return 1;
}
int medical_log_delete(MedicalLog *l, int id)
{ if (!l)
        return 0;
    for (MedicalRecord *r = l->head; r; r = r->next)
        if (r->record_id == id)
        {
            if (r->prev)
                r->prev->next = r->next;
            else
                l->head = r->next;
            if (r->next)
                r->next->prev = r->prev;
            else
                l->tail = r->prev;
            free(r);
            l->size--;
            return 1;
        }
    return 0;
}
int medical_log_copy(const MedicalLog *l, int aid, MedicalRecord *out, int cap)
{
    if (!l || cap < 0 || (!out && cap))
        return -1;
    int n = 0;
    for (MedicalRecord *r = l->head; r && n < cap; r = r->next)
        if (aid == 0 || r->animal_id == aid)
        {out[n] = *r;
            out[n].prev = out[n].next = NULL;
            n++; }
    return n;
}
void medical_log_free(MedicalLog *l)
{
    if (!l)
        return;
    MedicalRecord *r = l->head;
    while (r)
    {MedicalRecord *n = r->next;
        free(r);
        r = n; }
    medical_log_init(l);
}
