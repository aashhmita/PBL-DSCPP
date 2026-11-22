// controller.hpp : the C++ controller of StrayCare.
//
// One StrayCareController owns one instance of every C data structure:
//     animals     -> hash table      (lookup by ID)
//     triage      -> min-heap        (built on demand from the animals, most urgent first)
//     food queue  -> linked-list FIFO (active offers, oldest first)
//     medical log -> linked list     (chronological history)
//     road map    -> weighted graph  (Dijkstra for routes)
// It validates every input, keeps the structures consistent with each other, and keeps the
// activity feed. It throws ValidationError (with a user-friendly message) on bad input and
// guarantees that a rejected request changes nothing.
//
// Not thread-safe: the caller must serialize calls (the Python bridge does, with a lock).
#pragma once

#include <array>
#include <memory>
#include <optional>
#include <cstddef>
#include <stdexcept>
#include <string>
#include <vector>

#include "animal_hash.h"
#include "food_queue.h"
#include "medical_log.h"
#include "route_graph.h"
#include "straycare_types.h"
#include "triage_heap.h"

namespace straycare {

// Thrown for anything the user can fix (empty field, unknown ID, bad date ...).
class ValidationError : public std::runtime_error {
public:
    using std::runtime_error::runtime_error;
};

struct Stats {
    long animals = 0;
    long open_emergencies = 0;
    long active_food_offers = 0;
    long medical_entries = 0;
};

struct FoodStats {
    long total = 0;
    long active = 0;
    long active_servings = 0;
    long available = 0;
};

struct ActivityItem {
    std::string when;      // ISO time, e.g. 2026-10-22T09:15:00
    std::string title;
    std::string detail;
    std::string status;
};

struct Road {
    std::string a;
    std::string b;
    double km = 0.0;
};

struct RoutePlan {
    double km = 0.0;
    long eta_minutes = 0;
    std::vector<std::string> path;
};

struct TourLeg {
    std::string from;
    std::string to;
    double km = 0.0;
    std::vector<std::string> path;
};

struct TourPlan {
    std::vector<std::string> order;
    std::vector<TourLeg> legs;
    double total_km = 0.0;
    std::vector<std::string> unreachable;
    long eta_minutes = 0;
};

class StrayCareController {
public:
    StrayCareController();
    StrayCareController(const StrayCareController &) = delete;
    StrayCareController &operator=(const StrayCareController &) = delete;

    // ---- data set management ---------------------------------------------------------
    void reset_empty();      // remove everything
    void reset_demo();       // remove everything, then load the sample records

    // ---- animals (hash table) --------------------------------------------------------
    Animal register_animal(const std::string &name, const std::string &species,
                           const std::string &location, const std::string &condition,
                           const std::string &urgency, const std::string &status);
    Animal report_emergency(const std::string &description, const std::string &location,
                            const std::string &urgency, const std::string &species,
                            const std::string &condition, const std::string &details);
    Animal update_case_status(const std::string &animal_id, const std::string &new_status,
                              const std::string &note);
    Animal update_animal(const std::string &animal_id, const std::string &name,
                         const std::string &species, const std::string &location,
                         const std::string &condition, const std::string &urgency);
    Animal delete_animal(const std::string &animal_id);        // also removes its medical entries
    std::optional<Animal> get_animal(const std::string &animal_id) const;
    std::vector<Animal> list_animals(const std::string &search, const std::string &species) const;
    std::vector<std::string> animal_choices() const;           // "SC-1001 — Milo"

    // ---- triage (heap) ---------------------------------------------------------------
    std::vector<Animal> triage_order() const;                  // unresolved first, then resolved
    std::vector<Animal> priority_cases() const;
    std::optional<Animal> most_urgent_case() const;
    std::array<long, 4> urgency_counts() const;                // Critical, High, Medium, Low

    // ---- food donations (queue) ------------------------------------------------------
    FoodOffer add_food_offer(const std::string &donor, const std::string &food, long long servings,
                             const std::string &pickup_area, bool safety_confirmed);
    FoodOffer update_food_status(const std::string &offer_id, const std::string &new_status);
    std::vector<FoodOffer> list_food_offers() const;
    std::optional<FoodOffer> next_pickup() const;
    FoodStats food_stats() const;

    // ---- medical log (linked list) ---------------------------------------------------
    MedicalEntry add_medical_entry(const std::string &animal_id, const std::string &treatment,
                                   const std::string &volunteer, const std::string &visit_date,
                                   const std::string &notes);
    std::vector<MedicalEntry> list_medical_entries(const std::string &animal_id) const;  // newest first

    // ---- routes (graph) --------------------------------------------------------------
    std::vector<std::string> map_locations() const;
    std::vector<Road> road_list() const;
    std::vector<std::string> unmapped_locations() const;
    std::vector<std::string> open_case_locations() const;
    RoutePlan plan_route(const std::string &start, const std::string &destination) const;
    TourPlan plan_multi_stop(const std::string &start, const std::vector<std::string> &stops) const;
    void add_road(const std::string &a, const std::string &b, double km);

    // ---- dashboard -------------------------------------------------------------------
    std::vector<ActivityItem> recent_activity(std::size_t limit) const;
    Stats stats() const;

    // ---- saving and loading support (used by the Python bridge) ----------------------
    std::vector<ActivityItem> all_activity() const;            // newest first
    std::vector<MedicalEntry> medical_oldest_first() const;
    long next_animal_number() const { return next_animal_no_; }
    long next_food_number() const { return next_food_no_; }
    void restore_animal(const Animal &animal);
    void restore_food(const FoodOffer &offer);
    void restore_medical(const MedicalEntry &entry);
    void restore_road(const std::string &a, const std::string &b, double km);
    void restore_activity(const ActivityItem &item);
    void set_counters(long next_animal_no, long next_food_no);

private:
    struct AnimalHashDeleter { void operator()(AnimalHash *p) const { ah_destroy(p); } };
    struct FoodQueueDeleter  { void operator()(FoodQueue *p) const { fq_destroy(p); } };
    struct MedicalLogDeleter { void operator()(MedicalLog *p) const { ml_destroy(p); } };
    struct RouteGraphDeleter { void operator()(RouteGraph *p) const { rg_destroy(p); } };

    std::unique_ptr<AnimalHash, AnimalHashDeleter> animals_;
    std::unique_ptr<FoodQueue, FoodQueueDeleter> food_queue_;      // ACTIVE offers only
    std::unique_ptr<MedicalLog, MedicalLogDeleter> medical_;
    std::unique_ptr<RouteGraph, RouteGraphDeleter> graph_;
    std::vector<FoodOffer> food_offers_;                           // every offer ever listed
    std::vector<ActivityItem> activity_;                           // newest first
    long next_animal_no_ = 1001;
    long next_food_no_ = 201;

    void log(const std::string &title, const std::string &detail, const std::string &status);
    void store_animal(const Animal &animal);
    std::string new_animal_id();
    std::vector<Animal> unsorted_animals() const;
    std::vector<Animal> ordered_by_heap(const std::vector<Animal> &subset) const;
    void load_demo_data();
};

}  // namespace straycare
