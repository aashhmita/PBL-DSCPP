#include "medical_log.h"
#include <assert.h>

int main(void)
{
    MedicalLog l;
    medical_log_init(&l);

    assert(medical_log_add(&l, 1, 10, "2026-10-01", "Vaccination"));
    assert(medical_log_add(&l, 2, 10, "2026-10-02", "Check-up"));

    /* Test invalid inputs */
    assert(!medical_log_add(&l, 3, 10, "", "Check-up"));
    assert(!medical_log_add(&l, 3, 10, "2026-10-03", ""));
    assert(!medical_log_add(&l, 0, 10, "2026-10-03", "Check-up"));

    MedicalRecord r[4];
    assert(medical_log_copy(&l, 10, r, 4) == 2);
    assert(r[0].record_id == 1 && r[1].record_id == 2);
    assert(!medical_log_delete(&l, 99));
    assert(l.size == 2);
    /* Test deleting a missing record */
    assert(!medical_log_delete(&l, 99));
    assert(l.size == 2);

    assert(medical_log_delete(&l, 1));
    medical_log_free(&l);

    return 0;
}