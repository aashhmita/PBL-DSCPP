#include "controller.hpp"

#include <algorithm>
#include <cctype>
#include <cerrno>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <new>
#include <set>

namespace straycare {

namespace {

// ---- vocabulary (identical to backend/constants.py) -------------------------------------
const char *const SPECIES[] = {"Dog", "Cat", "Bird", "Other", "Unknown"};
const char *const URGENCY_LEVELS[] = {"Critical", "High", "Medium", "Low"};
const char *const CASE_STATUSES[] = {"Reported",        "Awaiting rescue", "Rescue assigned", "Rescued",
                                     "Under treatment", "Monitoring",      "Closed"};
const char *const RESOLVED[] = {"Rescued", "Closed"};
const char *const OPEN_EMERGENCY[] = {"Awaiting rescue", "Rescue assigned"};
const char *const PRIORITY[] = {"Awaiting rescue", "Rescue assigned", "Under treatment"};
const char *const FOOD_STATUSES[] = {"Available", "Pickup pending", "Collected", "Cancelled"};
const char *const FOOD_INACTIVE[] = {"Collected", "Cancelled"};

constexpr size_t MAX_TEXT = 200;
constexpr size_t MAX_NOTES = 1000;
constexpr size_t MAX_ACTIVITY = 200;
constexpr double AVERAGE_SPEED_KMH = 25.0;   // only used to turn kilometres into a rough ETA

// UTF-8 separators written as raw bytes so the result does not depend on the compiler's
// source/execution character set.
const char BULLET[] = " \xE2\x80\xA2 ";     //  " • "
const char EM_DASH[] = " \xE2\x80\x94 ";    //  " — "
const char ARROWS[] = " \xE2\x86\x94 ";     //  " ↔ "

template <size_t N>
bool in_list(const char *const (&list)[N], const std::string &value)
{
    for (const char *item : list) {
        if (value == item) return true;
    }
    return false;
}

template <size_t N>
std::string join_list(const char *const (&list)[N])
{
    std::string out;
    for (size_t i = 0; i < N; i++) {
        if (i) out += ", ";
        out += list[i];
    }
    return out;
}

std::string strip(const std::string &s)
{
    const char *whitespace = " \t\n\r\v\f";
    size_t first = s.find_first_not_of(whitespace);
    if (first == std::string::npos) return "";
    size_t last = s.find_last_not_of(whitespace);
    return s.substr(first, last - first + 1);
}

// Trim, then check "required" and the length limit. Returns the cleaned text.
std::string clean(const std::string &value, const char *field, bool required = true,
                  size_t max_len = MAX_TEXT)
{
    std::string text = strip(value);
    if (required && text.empty()) throw ValidationError(std::string(field) + " is required.");
    if (text.size() > max_len) {
        throw ValidationError(std::string(field) + " is too long (maximum " + std::to_string(max_len) +
                              " characters).");
    }
    return text;
}

template <size_t N>
void choice(const std::string &value, const char *const (&list)[N], const char *field)
{
    if (!in_list(list, value)) {
        throw ValidationError(std::string(field) + " must be one of: " + join_list(list) + ".");
    }
}

// Copy text into a fixed char array; the checks above make an overflow impossible, but if
// restored data is somehow too long we refuse it instead of truncating.
template <size_t N>
void put(char (&dest)[N], const std::string &text)
{
    if (sc_copy(dest, N, text.c_str()) != 0) throw ValidationError("Text is too long.");
}

// "SC-1004" -> 1004. Used for ordering and as the tie-breaker "who was reported first".
long id_number(const char *id)
{
    const char *dash = std::strrchr(id, '-');
    const char *digits = dash ? dash + 1 : id;
    if (*digits == '\0') return 0;
    char *end = nullptr;
    errno = 0;
    long value = std::strtol(digits, &end, 10);
    return (*end == '\0' && errno == 0) ? value : 0;
}

int urgency_rank(const char *urgency)
{
    for (int i = 0; i < 4; i++) {
        if (std::strcmp(urgency, URGENCY_LEVELS[i]) == 0) return i;
    }
    return 4;                                  // unknown urgency sorts last
}

std::string lower_ascii(std::string s)
{
    for (char &c : s) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return s;
}

// ---- dates -------------------------------------------------------------------------------
std::tm local_now()
{
    std::time_t t = std::time(nullptr);
    const std::tm *lt = std::localtime(&t);
    return lt ? *lt : std::tm{};
}

std::string today_iso()
{
    std::tm t = local_now();
    char buf[64];                               // roomy on purpose: the compiler cannot know the ints are small
    std::snprintf(buf, sizeof buf, "%04d-%02d-%02d", t.tm_year + 1900, t.tm_mon + 1, t.tm_mday);
    return buf;
}

std::string now_iso()
{
    std::tm t = local_now();
    char buf[128];
    std::snprintf(buf, sizeof buf, "%04d-%02d-%02dT%02d:%02d:%02d", t.tm_year + 1900, t.tm_mon + 1,
                  t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec);
    return buf;
}

// Strict "YYYY-MM-DD" check including month lengths and leap years.
bool valid_iso_date(const std::string &s)
{
    if (s.size() != 10 || s[4] != '-' || s[7] != '-') return false;
    for (int i : {0, 1, 2, 3, 5, 6, 8, 9}) {
        if (!std::isdigit(static_cast<unsigned char>(s[i]))) return false;
    }
    int year = std::stoi(s.substr(0, 4));
    int month = std::stoi(s.substr(5, 2));
    int day = std::stoi(s.substr(8, 2));
    if (year < 1 || month < 1 || month > 12 || day < 1) return false;
    static const int days_in_month[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    int days = days_in_month[month - 1];
    if (month == 2 && ((year % 4 == 0 && year % 100 != 0) || year % 400 == 0)) days = 29;
    return day <= days;
}

long eta_minutes(double km)
{
    // nearbyint rounds halves to the nearest EVEN number, exactly like Python's round().
    return static_cast<long>(std::nearbyint(km / AVERAGE_SPEED_KMH * 60.0));
}

// ---- small constructors --------------------------------------------------------------------
Animal make_animal(const std::string &id, const std::string &name, const std::string &species,
                   const std::string &location, const std::string &condition,
                   const std::string &status, const std::string &urgency,
                   const std::string &reported)
{
    Animal a;
    std::memset(&a, 0, sizeof a);
    put(a.id, id);
    put(a.name, name);
    put(a.species, species);
    put(a.location, location);
    put(a.condition, condition);
    put(a.status, status);
    put(a.urgency, urgency);
    put(a.reported, reported);
    return a;
}

FoodOffer make_offer(const std::string &id, const std::string &donor, const std::string &food,
                     long servings, const std::string &pickup, const std::string &status)
{
    FoodOffer o;
    std::memset(&o, 0, sizeof o);
    put(o.offer_id, id);
    put(o.donor, donor);
    put(o.food, food);
    o.servings = servings;
    put(o.pickup_area, pickup);
    put(o.status, status);
    return o;
}

MedicalEntry make_entry(const std::string &date, const std::string &animal_id,
                        const std::string &treatment, const std::string &volunteer,
                        const std::string &notes)
{
    MedicalEntry e;
    std::memset(&e, 0, sizeof e);
    put(e.date, date);
    put(e.animal_id, animal_id);
    put(e.treatment, treatment);
    put(e.volunteer, volunteer);
    put(e.notes, notes);
    return e;
}

// Callbacks that let the C containers fill C++ vectors.
void collect_animal(const Animal *a, void *context)
{
    static_cast<std::vector<Animal> *>(context)->push_back(*a);
}
void collect_offer(const FoodOffer *o, void *context)
{
    static_cast<std::vector<FoodOffer> *>(context)->push_back(*o);
}
void collect_entry(const MedicalEntry *e, void *context)
{
    static_cast<std::vector<MedicalEntry> *>(context)->push_back(*e);
}
void collect_road(const char *a, const char *b, double km, void *context)
{
    Road road;
    // Report every road as (smaller name, bigger name) so the list does not depend on
    // the order in which locations were added.
    if (std::strcmp(a, b) <= 0) { road.a = a; road.b = b; }
    else                        { road.a = b; road.b = a; }
    road.km = km;
    static_cast<std::vector<Road> *>(context)->push_back(road);
}

bool status_in_list(const Animal &a, const char *const *list, size_t n)
{
    for (size_t i = 0; i < n; i++) {
        if (std::strcmp(a.status, list[i]) == 0) return true;
    }
    return false;
}
template <size_t N>
bool status_in(const Animal &a, const char *const (&list)[N])
{
    return status_in_list(a, list, N);
}

}  // namespace

// =========================================================================================
// construction, reset, demo data
// =========================================================================================

StrayCareController::StrayCareController()
    : animals_(ah_create(8)), food_queue_(fq_create()), medical_(ml_create()), graph_(rg_create())
{
    if (!animals_ || !food_queue_ || !medical_ || !graph_) throw std::bad_alloc();
}

void StrayCareController::reset_empty()
{
    ah_clear(animals_.get());
    fq_clear(food_queue_.get());
    ml_clear(medical_.get());
    rg_clear(graph_.get());
    food_offers_.clear();
    activity_.clear();
    next_animal_no_ = 1001;
    next_food_no_ = 201;
}

void StrayCareController::reset_demo()
{
    reset_empty();
    load_demo_data();
}

void StrayCareController::load_demo_data()
{
    struct Seed { const char *id, *name, *species, *location, *condition, *status, *urgency, *reported; };
    const Seed animals[] = {
        {"SC-1001", "Milo", "Dog", "Clement Town", "Injured leg", "Under treatment", "High", "2026-10-21"},
        {"SC-1002", "Luna", "Cat", "Sahastradhara Road", "Dehydration", "Rescued", "Medium", "2026-10-20"},
        {"SC-1003", "Brownie", "Dog", "Prem Nagar", "Healthy / vaccination due", "Monitoring", "Low", "2026-10-19"},
        {"SC-1004", "Unknown puppy", "Dog", "ISBT Dehradun", "Roadside emergency", "Awaiting rescue", "Critical", "2026-10-22"},
    };
    for (const Seed &s : animals) {
        store_animal(make_animal(s.id, s.name, s.species, s.location, s.condition, s.status, s.urgency, s.reported));
    }
    next_animal_no_ = 1005;

    restore_food(make_offer("FD-201", "Green Bowl Cafe", "Plain rice and vegetables", 18, "Clock Tower", "Available"));
    restore_food(make_offer("FD-202", "Campus Canteen", "Unseasoned leftovers", 12, "GEU", "Pickup pending"));
    restore_food(make_offer("FD-203", "Community Kitchen", "Rice", 25, "Clement Town", "Available"));
    next_food_no_ = 204;

    restore_medical(make_entry("2026-10-20", "SC-1002", "Fluids and observation", "Meera", "Condition improving"));
    restore_medical(make_entry("2026-10-21", "SC-1001", "Initial examination", "Aarav", "Needs follow-up assessment"));

    // Illustrative road distances in km (demo values, not surveyed measurements).
    struct RoadSeed { const char *a, *b; double km; };
    const RoadSeed roads[] = {
        {"Shelter (Base)", "Clock Tower", 3.0},   {"Clock Tower", "ISBT Dehradun", 3.5},
        {"Clock Tower", "Prem Nagar", 6.0},       {"Clock Tower", "Sahastradhara Road", 8.0},
        {"ISBT Dehradun", "Clement Town", 7.5},   {"ISBT Dehradun", "GEU", 6.5},
        {"Prem Nagar", "GEU", 4.0},               {"Prem Nagar", "Clement Town", 5.5},
    };
    for (const RoadSeed &r : roads) restore_road(r.a, r.b, r.km);

    activity_.push_back({"2026-10-22T09:15:00", "New emergency reported", std::string("SC-1004") + BULLET + "ISBT Dehradun", "Critical"});
    activity_.push_back({"2026-10-21T17:40:00", "Medical update recorded", std::string("SC-1001") + BULLET + "Milo", "Updated"});
    activity_.push_back({"2026-10-21T12:05:00", "Food donation listed", std::string("FD-203") + BULLET + "Community Kitchen", "Available"});
}

void StrayCareController::log(const std::string &title, const std::string &detail, const std::string &status)
{
    activity_.insert(activity_.begin(), ActivityItem{now_iso(), title, detail, status});
    if (activity_.size() > MAX_ACTIVITY) activity_.resize(MAX_ACTIVITY);
}

// =========================================================================================
// animals (hash table)
// =========================================================================================

void StrayCareController::store_animal(const Animal &animal)
{
    if (ah_put(animals_.get(), &animal) != 0) throw std::bad_alloc();
}

std::string StrayCareController::new_animal_id()
{
    return "SC-" + std::to_string(next_animal_no_++);
}

std::vector<Animal> StrayCareController::unsorted_animals() const
{
    std::vector<Animal> all;
    ah_foreach(animals_.get(), collect_animal, &all);
    return all;
}

Animal StrayCareController::register_animal(const std::string &name_in, const std::string &species,
                                            const std::string &location_in, const std::string &condition_in,
                                            const std::string &urgency, const std::string &status)
{
    // Validate EVERYTHING first, so a rejected form never uses up an ID number.
    std::string name = clean(name_in, "Animal name / identifier");
    std::string location = clean(location_in, "Location");
    std::string condition = clean(condition_in, "Condition", false);
    if (condition.empty()) condition = "Not assessed";
    choice(species, SPECIES, "Species");
    choice(status, CASE_STATUSES, "Status");
    choice(urgency, URGENCY_LEVELS, "Urgency");

    Animal animal = make_animal(new_animal_id(), name, species, location, condition, status, urgency, today_iso());
    store_animal(animal);
    log("Animal profile added", std::string(animal.id) + BULLET + animal.name, "Created");
    return animal;
}

Animal StrayCareController::report_emergency(const std::string &description_in, const std::string &location_in,
                                             const std::string &urgency, const std::string &species,
                                             const std::string &condition_in, const std::string &details_in)
{
    std::string description = clean(description_in, "Animal description");
    std::string location = clean(location_in, "Location");
    choice(urgency, URGENCY_LEVELS, "Urgency");
    choice(species, SPECIES, "Species");
    std::string condition = clean(condition_in, "Condition", false);
    if (condition.empty()) condition = clean(details_in, "Details", false, MAX_NOTES);
    if (condition.empty()) condition = "Assessment required";

    Animal animal = make_animal(new_animal_id(), description, species, location, condition,
                                "Awaiting rescue", urgency, today_iso());
    store_animal(animal);
    log("New emergency reported", std::string(animal.id) + BULLET + location, urgency);
    return animal;
}

Animal StrayCareController::update_case_status(const std::string &animal_id, const std::string &new_status,
                                               const std::string &note_in)
{
    Animal *animal = ah_get(animals_.get(), animal_id.c_str());      // O(1) hash lookup
    if (!animal) throw ValidationError("No animal with ID " + animal_id + ".");
    choice(new_status, CASE_STATUSES, "Status");
    std::string note = clean(note_in, "Note", false);

    put(animal->status, new_status);
    log("Rescue case updated", animal_id + BULLET + (note.empty() ? new_status : note), new_status);
    return *animal;
}

Animal StrayCareController::update_animal(const std::string &animal_id, const std::string &name_in,
                                           const std::string &species, const std::string &location_in,
                                           const std::string &condition_in, const std::string &urgency)
{
    Animal *animal = ah_get(animals_.get(), animal_id.c_str());
    if (!animal) throw ValidationError("No animal with ID " + animal_id + ".");
    // Validate everything first: a rejected edit must change nothing.
    std::string name = clean(name_in, "Animal name / identifier");
    std::string location = clean(location_in, "Location");
    std::string condition = clean(condition_in, "Condition", false);
    if (condition.empty()) condition = "Not assessed";
    choice(species, SPECIES, "Species");
    choice(urgency, URGENCY_LEVELS, "Urgency");

    put(animal->name, name);
    put(animal->species, species);
    put(animal->location, location);
    put(animal->condition, condition);
    put(animal->urgency, urgency);
    log("Animal profile edited", animal_id + BULLET + name, "Updated");
    return *animal;
}

Animal StrayCareController::delete_animal(const std::string &animal_id)
{
    const Animal *found = ah_get(animals_.get(), animal_id.c_str());
    if (!found) throw ValidationError("No animal with ID " + animal_id + ".");
    Animal copy = *found;                                      // keep a copy to return
    ah_remove(animals_.get(), animal_id.c_str());
    ml_remove_animal(medical_.get(), animal_id.c_str());       // no orphan history
    log("Animal record deleted", animal_id + BULLET + copy.name, "Deleted");
    return copy;
}

std::optional<Animal> StrayCareController::get_animal(const std::string &animal_id) const
{
    const Animal *animal = ah_get(animals_.get(), animal_id.c_str());
    if (!animal) return std::nullopt;
    return *animal;
}

std::vector<Animal> StrayCareController::list_animals(const std::string &search, const std::string &species) const
{
    std::string needle = lower_ascii(strip(search));
    std::vector<Animal> rows;
    for (const Animal &a : unsorted_animals()) {
        if (species != "All" && species != a.species) continue;
        if (!needle.empty()) {
            std::string haystack = std::string(a.id) + " " + a.name + " " + a.species + " " + a.location + " " +
                                   a.condition + " " + a.status + " " + a.urgency + " " + a.reported;
            if (lower_ascii(haystack).find(needle) == std::string::npos) continue;
        }
        rows.push_back(a);
    }
    std::stable_sort(rows.begin(), rows.end(), [](const Animal &x, const Animal &y) {
        long nx = id_number(x.id), ny = id_number(y.id);
        return nx != ny ? nx < ny : std::strcmp(x.id, y.id) < 0;
    });
    return rows;
}

std::vector<std::string> StrayCareController::animal_choices() const
{
    std::vector<std::string> labels;
    for (const Animal &a : list_animals("", "All")) labels.push_back(std::string(a.id) + EM_DASH + a.name);
    return labels;
}

// =========================================================================================
// triage (heap)
// =========================================================================================

// Build a heap from the given animals (O(n)), then pop it empty: most urgent first,
// oldest report first among equals.
std::vector<Animal> StrayCareController::ordered_by_heap(const std::vector<Animal> &subset) const
{
    std::vector<TriageEntry> entries;
    entries.reserve(subset.size());
    for (const Animal &a : subset) {
        TriageEntry entry;
        std::memset(&entry, 0, sizeof entry);
        entry.rank = urgency_rank(a.urgency);
        entry.seq = id_number(a.id);
        put(entry.id, a.id);
        entries.push_back(entry);
    }
    struct HeapDeleter { void operator()(TriageHeap *h) const { th_destroy(h); } };
    std::unique_ptr<TriageHeap, HeapDeleter> heap(th_build(entries.data(), entries.size()));
    if (!heap) throw std::bad_alloc();

    std::vector<Animal> ordered;
    TriageEntry top;
    while (th_pop(heap.get(), &top)) {
        const Animal *a = ah_get(animals_.get(), top.id);
        if (a) ordered.push_back(*a);
    }
    return ordered;
}

std::vector<Animal> StrayCareController::triage_order() const
{
    std::vector<Animal> unresolved, resolved;
    for (const Animal &a : unsorted_animals()) (status_in(a, RESOLVED) ? resolved : unresolved).push_back(a);
    std::vector<Animal> result = ordered_by_heap(unresolved);
    for (const Animal &a : ordered_by_heap(resolved)) result.push_back(a);
    return result;
}

std::vector<Animal> StrayCareController::priority_cases() const
{
    std::vector<Animal> selected;
    for (const Animal &a : unsorted_animals()) {
        if (status_in(a, PRIORITY)) selected.push_back(a);
    }
    return ordered_by_heap(selected);
}

std::optional<Animal> StrayCareController::most_urgent_case() const
{
    // Peek at the top of the heap: O(1) once the heap is built.
    std::vector<TriageEntry> entries;
    for (const Animal &a : unsorted_animals()) {
        if (status_in(a, RESOLVED)) continue;
        TriageEntry entry;
        std::memset(&entry, 0, sizeof entry);
        entry.rank = urgency_rank(a.urgency);
        entry.seq = id_number(a.id);
        put(entry.id, a.id);
        entries.push_back(entry);
    }
    if (entries.empty()) return std::nullopt;

    struct HeapDeleter { void operator()(TriageHeap *h) const { th_destroy(h); } };
    std::unique_ptr<TriageHeap, HeapDeleter> heap(th_build(entries.data(), entries.size()));
    if (!heap) throw std::bad_alloc();
    TriageEntry top;
    if (!th_peek(heap.get(), &top)) return std::nullopt;
    return get_animal(top.id);
}

std::array<long, 4> StrayCareController::urgency_counts() const
{
    std::array<long, 4> counts = {0, 0, 0, 0};
    for (const Animal &a : unsorted_animals()) {
        if (status_in(a, RESOLVED)) continue;
        int rank = urgency_rank(a.urgency);
        if (rank < 4) counts[static_cast<size_t>(rank)]++;
    }
    return counts;
}

// =========================================================================================
// food donations (queue)
// =========================================================================================


FoodOffer StrayCareController::add_food_offer(const std::string &donor_in, const std::string &food_in,
                                              long long servings, const std::string &pickup_in,
                                              bool safety_confirmed)
{
    std::string donor = clean(donor_in, "Donor / organization");
    std::string food = clean(food_in, "Food description");
    std::string pickup = clean(pickup_in, "Pickup area");

    if (servings < 1 || servings > 10000)
        throw ValidationError("Servings must be between 1 and 10,000.");
    if (!safety_confirmed)
        throw ValidationError("Please confirm the food-safety check before listing the offer.");

    FoodOffer offer = make_offer("FD-" + std::to_string(next_food_no_), donor, food,
                                 static_cast<long>(servings), pickup, "Available");

    food_offers_.push_back(offer);

    if (fq_enqueue(food_queue_.get(), &offer) != 0) {
        food_offers_.pop_back();
        throw std::bad_alloc();
    }

    next_food_no_++;
    log("Food donation listed", std::string(offer.offer_id) + BULLET + donor, "Available");

    return offer;
}


FoodOffer StrayCareController::update_food_status(const std::string &offer_id, const std::string &new_status)
{
    choice(new_status, FOOD_STATUSES, "Status");
    auto found = std::find_if(food_offers_.begin(), food_offers_.end(),
                              [&](const FoodOffer &o) { return offer_id == o.offer_id; });
    if (found == food_offers_.end()) throw ValidationError("No food offer with ID " + offer_id + ".");

    FoodOffer &offer = *found;
    bool was_active = !in_list(FOOD_INACTIVE, offer.status);
    put(offer.status, new_status);
    bool is_active = !in_list(FOOD_INACTIVE, new_status);

    if (was_active && !is_active) {
        fq_remove(food_queue_.get(), offer_id.c_str());           // collected / cancelled: leaves the queue
    } else if (is_active && !was_active) {
        if (fq_enqueue(food_queue_.get(), &offer) != 0) throw std::bad_alloc();   // rejoins at the back
    } else if (is_active) {
        FoodOffer *queued = fq_find(food_queue_.get(), offer_id.c_str());
        if (queued) *queued = offer;                              // keep the queued copy's status current
    }
    log("Food offer updated", offer_id + BULLET + new_status, new_status);
    return offer;
}

std::vector<FoodOffer> StrayCareController::list_food_offers() const
{
    return food_offers_;
}

std::optional<FoodOffer> StrayCareController::next_pickup() const
{
    const FoodOffer *head = fq_peek(food_queue_.get());
    if (!head) return std::nullopt;
    return *head;
}

FoodStats StrayCareController::food_stats() const
{
    std::vector<FoodOffer> active;
    fq_foreach(food_queue_.get(), collect_offer, &active);
    FoodStats stats;
    stats.total = static_cast<long>(food_offers_.size());
    stats.active = static_cast<long>(active.size());
    for (const FoodOffer &o : active) stats.active_servings += o.servings;
    for (const FoodOffer &o : food_offers_) {
        if (std::strcmp(o.status, "Available") == 0) stats.available++;
    }
    return stats;
}

// =========================================================================================
// medical log (linked list)
// =========================================================================================

MedicalEntry StrayCareController::add_medical_entry(const std::string &animal_id, const std::string &treatment_in,
                                                    const std::string &volunteer_in, const std::string &visit_date,
                                                    const std::string &notes_in)
{
    if (!ah_get(animals_.get(), animal_id.c_str())) throw ValidationError("No animal with ID " + animal_id + ".");
    std::string date = strip(visit_date);
    if (date.empty()) throw ValidationError("Visit date is required.");
    if (!valid_iso_date(date)) throw ValidationError("Visit date must look like 2026-10-22.");
    if (date > today_iso()) throw ValidationError("Visit date cannot be in the future.");   // ISO dates sort as text

    std::string treatment = clean(treatment_in, "Treatment / examination");
    std::string volunteer = clean(volunteer_in, "Volunteer / care provider");
    std::string notes = clean(notes_in, "Notes", false, MAX_NOTES);

    MedicalEntry entry = make_entry(date, animal_id, treatment, volunteer, notes);
    if (ml_append(medical_.get(), &entry) != 0) throw std::bad_alloc();
    log("Medical update recorded", animal_id + BULLET + treatment, "Updated");
    return entry;
}

std::vector<MedicalEntry> StrayCareController::medical_oldest_first() const
{
    std::vector<MedicalEntry> all;
    ml_foreach(medical_.get(), collect_entry, &all);
    return all;
}

std::vector<MedicalEntry> StrayCareController::list_medical_entries(const std::string &animal_id) const
{
    std::vector<MedicalEntry> rows;
    for (const MedicalEntry &e : medical_oldest_first()) {
        if (animal_id.empty() || animal_id == e.animal_id) rows.push_back(e);
    }
    std::reverse(rows.begin(), rows.end());                       // newest first
    return rows;
}

// =========================================================================================
// routes (graph)
// =========================================================================================

std::vector<std::string> StrayCareController::map_locations() const
{
    std::vector<std::string> names;
    for (int i = 0; i < rg_node_count(graph_.get()); i++) names.push_back(rg_node_name(graph_.get(), i));
    std::sort(names.begin(), names.end());
    return names;
}

std::vector<Road> StrayCareController::road_list() const
{
    std::vector<Road> roads;
    rg_foreach_road(graph_.get(), collect_road, &roads);
    std::sort(roads.begin(), roads.end(), [](const Road &x, const Road &y) {
        if (x.a != y.a) return x.a < y.a;
        if (x.b != y.b) return x.b < y.b;
        return x.km < y.km;
    });
    return roads;
}

std::vector<std::string> StrayCareController::unmapped_locations() const
{
    std::set<std::string> missing;
    for (const Animal &a : unsorted_animals()) {
        if (rg_find(graph_.get(), a.location) < 0) missing.insert(a.location);
    }
    return {missing.begin(), missing.end()};
}

std::vector<std::string> StrayCareController::open_case_locations() const
{
    std::set<std::string> places;
    for (const Animal &a : unsorted_animals()) {
        if (status_in(a, OPEN_EMERGENCY) && rg_find(graph_.get(), a.location) >= 0) places.insert(a.location);
    }
    return {places.begin(), places.end()};
}

RoutePlan StrayCareController::plan_route(const std::string &start, const std::string &destination) const
{
    if (start == destination) {
        throw ValidationError("Start and destination are the same. Please choose different locations.");
    }
    int from = rg_find(graph_.get(), start.c_str());
    int to = rg_find(graph_.get(), destination.c_str());
    if (from < 0 || to < 0) throw ValidationError("Both locations must exist on the map.");

    std::vector<int> path(static_cast<size_t>(rg_node_count(graph_.get())));
    int length = 0;
    double km = 0.0;
    int rc = rg_shortest_path(graph_.get(), from, to, &km, path.data(), &length);
    if (rc == 1) throw ValidationError("No connected road between those two locations.");
    if (rc != 0) throw std::bad_alloc();

    RoutePlan plan;
    plan.km = km;
    plan.eta_minutes = eta_minutes(km);
    for (int i = 0; i < length; i++) plan.path.push_back(rg_node_name(graph_.get(), path[static_cast<size_t>(i)]));
    return plan;
}

// Nearest-neighbour tour: from where we are, always drive to the closest stop not yet visited.
// This is a fast greedy heuristic, NOT guaranteed optimal (that is the travelling-salesman problem).
TourPlan StrayCareController::plan_multi_stop(const std::string &start, const std::vector<std::string> &stops) const
{
    if (stops.empty()) throw ValidationError("Choose at least one stop.");
    int current = rg_find(graph_.get(), start.c_str());
    if (current < 0) throw ValidationError("Starting point must exist on the map.");

    std::vector<int> remaining;                    // unique, in the order given, mapped, and not the start
    for (const std::string &stop : stops) {
        int index = rg_find(graph_.get(), stop.c_str());
        if (index < 0 || index == current) continue;
        if (std::find(remaining.begin(), remaining.end(), index) != remaining.end()) continue;
        remaining.push_back(index);
    }

    const int n = rg_node_count(graph_.get());
    std::vector<double> dist(static_cast<size_t>(n));
    std::vector<int> prev(static_cast<size_t>(n));

    TourPlan plan;
    plan.order.push_back(start);
    while (!remaining.empty()) {
        if (rg_dijkstra(graph_.get(), current, dist.data(), prev.data()) != 0) throw std::bad_alloc();

        int best = -1;
        for (int index : remaining) {
            double d = dist[static_cast<size_t>(index)];
            if (d < HUGE_VAL && (best < 0 || d < dist[static_cast<size_t>(best)])) best = index;
        }
        if (best < 0) {                            // nothing left is reachable
            for (int index : remaining) plan.unreachable.push_back(rg_node_name(graph_.get(), index));
            break;
        }

        TourLeg leg;
        leg.from = rg_node_name(graph_.get(), current);
        leg.to = rg_node_name(graph_.get(), best);
        leg.km = dist[static_cast<size_t>(best)];
        for (int node = best; node != -1; node = prev[static_cast<size_t>(node)]) {
            leg.path.push_back(rg_node_name(graph_.get(), node));
        }
        std::reverse(leg.path.begin(), leg.path.end());

        plan.total_km += leg.km;
        plan.order.push_back(leg.to);
        plan.legs.push_back(leg);
        remaining.erase(std::find(remaining.begin(), remaining.end(), best));
        current = best;
    }
    plan.eta_minutes = eta_minutes(plan.total_km);
    return plan;
}

void StrayCareController::add_road(const std::string &a_in, const std::string &b_in, double km)
{
    std::string a = clean(a_in, "First location");
    std::string b = clean(b_in, "Second location");
    int rc = rg_add_road(graph_.get(), a.c_str(), b.c_str(), km);
    if (rc == RG_ERR_SAME) throw ValidationError("A road must connect two different locations.");
    if (rc == RG_ERR_DISTANCE) throw ValidationError("Distance must be greater than zero.");
    if (rc != 0) throw std::bad_alloc();

    char km_text[32];
    std::snprintf(km_text, sizeof km_text, "%g", km);              // same style as Python's {km:g}
    log("Road map updated", a + ARROWS + b + BULLET + km_text + " km", "Updated");
}

// =========================================================================================
// dashboard
// =========================================================================================

std::vector<ActivityItem> std::vector<ActivityItem> StrayCareController::recent_activity(std::size_t limit) const const
{
    size_t count = std::min(limit, activity_.size());
    return std::vector<ActivityItem>(activity_.begin(), activity_.begin() + static_cast<std::ptrdiff_t>(count));
}

std::vector<ActivityItem> StrayCareController::all_activity() const
{
    return activity_;
}

Stats StrayCareController::stats() const
{
    Stats stats;
    stats.animals = static_cast<long>(ah_size(animals_.get()));
    for (const Animal &a : unsorted_animals()) {
        if (status_in(a, OPEN_EMERGENCY)) stats.open_emergencies++;
    }
    stats.active_food_offers = static_cast<long>(fq_size(food_queue_.get()));
    stats.medical_entries = static_cast<long>(ml_size(medical_.get()));
    return stats;
}

// =========================================================================================
// loading saved data (the Python bridge keeps the JSON file and feeds records back in)
// =========================================================================================

void StrayCareController::restore_animal(const Animal &animal)
{
    store_animal(animal);
}

void StrayCareController::restore_food(const FoodOffer &offer)
{
    food_offers_.push_back(offer);
    if (!in_list(FOOD_INACTIVE, offer.status)) {
        if (fq_enqueue(food_queue_.get(), &offer) != 0) throw std::bad_alloc();
    }
}

void StrayCareController::restore_medical(const MedicalEntry &entry)
{
    if (ml_append(medical_.get(), &entry) != 0) throw std::bad_alloc();
}

void StrayCareController::restore_road(const std::string &a, const std::string &b, double km)
{
    int rc = rg_add_road(graph_.get(), a.c_str(), b.c_str(), km);
    if (rc == RG_ERR_SAME || rc == RG_ERR_DISTANCE) throw ValidationError("Saved road data is invalid.");
    if (rc != 0) throw std::bad_alloc();
}

void StrayCareController::restore_activity(const ActivityItem &item)
{
    activity_.push_back(item);
}

void StrayCareController::set_counters(long next_animal_no, long next_food_no)
{
    next_animal_no_ = next_animal_no;
    next_food_no_ = next_food_no;
}

}  // namespace straycare
