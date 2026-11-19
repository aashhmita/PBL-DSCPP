/* straycare_types.h : record types shared by every C module and by the C++ controller.
 *
 * All text lives in fixed-size char arrays, so a record is one plain block of memory that
 * can be copied with a simple assignment (no pointers inside, nothing to free).
 * The controller checks lengths BEFORE copying: text is limited to 200 bytes (notes: 1000),
 * which always fits these buffers. sc_copy() is the safety net: it never overflows.
 */
#ifndef STRAYCARE_TYPES_H
#define STRAYCARE_TYPES_H

#include <string.h>

#define SC_ID_LEN     16     /* "SC-1004", "FD-201"                         */
#define SC_SHORT_LEN  32     /* species, status, urgency, dates             */
#define SC_TEXT_LEN   256    /* names, places, donors (<= 200 bytes + NUL)  */
#define SC_NOTES_LEN  1024   /* conditions and notes  (<= 1000 bytes + NUL) */

typedef struct {
    char id[SC_ID_LEN];
    char name[SC_TEXT_LEN];
    char species[SC_SHORT_LEN];
    char location[SC_TEXT_LEN];
    char condition[SC_NOTES_LEN];
    char status[SC_SHORT_LEN];
    char urgency[SC_SHORT_LEN];
    char reported[SC_SHORT_LEN];      /* YYYY-MM-DD */
} Animal;

typedef struct {
    char offer_id[SC_ID_LEN];
    char donor[SC_TEXT_LEN];
    char food[SC_TEXT_LEN];
    long servings;
    char pickup_area[SC_TEXT_LEN];
    char status[SC_SHORT_LEN];
} FoodOffer;

typedef struct {
    char date[SC_SHORT_LEN];          /* YYYY-MM-DD */
    char animal_id[SC_ID_LEN];
    char treatment[SC_TEXT_LEN];
    char volunteer[SC_TEXT_LEN];
    char notes[SC_NOTES_LEN];
} MedicalEntry;

/* Copy src into dst (capacity cap, including the NUL).
 * Returns 0 on success, -1 if it would not fit (dst is then left as an empty string). */
static inline int sc_copy(char *dst, size_t cap, const char *src)
{
    size_t n = strlen(src);
    if (n >= cap) {
        if (cap > 0) dst[0] = '\0';
        return -1;
    }
    memcpy(dst, src, n + 1);
    return 0;
}

#endif /* STRAYCARE_TYPES_H */
