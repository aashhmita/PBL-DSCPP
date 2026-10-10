#ifndef MEDICAL_LOG_H
#define MEDICAL_LOG_H
#define MEDICAL_NOTE_MAX 160
typedef struct MedicalRecord
{
    int record_id;
    int animal_id;
    char date[16];
    char note[MEDICAL_NOTE_MAX];
    struct MedicalRecord *prev, *next;
} MedicalRecord;
typedef struct
{
    MedicalRecord *head, *tail;
    int size;
} MedicalLog;
#ifdef __cplusplus
extern "C"
{
#endif

    void medical_log_init(MedicalLog *log);
    int medical_log_add(MedicalLog *log, int record_id, int animal_id, const char *date, const char *note);
    int medical_log_delete(MedicalLog *log, int record_id);
    int medical_log_copy(const MedicalLog *log, int animal_id, MedicalRecord *out, int capacity);
    void medical_log_free(MedicalLog *log);
#ifdef __cplusplus
}
#endif
#endif
