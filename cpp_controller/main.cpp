// main.cpp : console demo + self-check of the C++ controller (no Python, no web page).
//
//     python build.py --test        builds and runs this program
//
// It walks through the same workflow as the web app: report an emergency, triage, assign a
// rescue, plan a route, handle a donation, add a medical note, check the validation rules.
// Every CHECK is a small test; the program exits with a non-zero code if any of them fails.

#include <cstdio>
#include <cstring>
#include <functional>
#include <iostream>
#include <string>
#include <vector>

#include "controller.hpp"

using namespace straycare;

static int checks = 0;
static int failures = 0;

#define CHECK(cond)                                                          \
    do {                                                                     \
        checks++;                                                            \
        if (!(cond)) {                                                       \
            failures++;                                                      \
            std::printf("  FAIL  line %d:  %s\n", __LINE__, #cond);          \
        }                                                                    \
    } while (0)

// Run code that must be rejected with a ValidationError; returns the message ("" if it was accepted).
static std::string rejected(const std::function<void()> &action)
{
    try {
        action();
    } catch (const ValidationError &e) {
        return e.what();
    }
    return "";
}

static void heading(const char *text) { std::printf("\n== %s ==\n", text); }

int main()
{
    StrayCareController c;
    c.reset_demo();

    heading("Dashboard");
    Stats s = c.stats();
    std::printf("animals=%ld  open emergencies=%ld  active food offers=%ld  medical entries=%ld\n",
                s.animals, s.open_emergencies, s.active_food_offers, s.medical_entries);
    CHECK(s.animals == 4 && s.open_emergencies == 1 && s.active_food_offers == 3 && s.medical_entries == 2);

    heading("Triage (min-heap)");
    for (const Animal &a : c.triage_order()) std::printf("  %-8s %-14s %-9s %s\n", a.id, a.name, a.urgency, a.status);
    std::vector<Animal> order = c.triage_order();
    CHECK(order.size() == 4);
    CHECK(std::strcmp(order[0].id, "SC-1004") == 0);      // Critical first
    CHECK(std::strcmp(order[3].id, "SC-1002") == 0);      // the Rescued case is last
    CHECK(std::strcmp(c.most_urgent_case()->id, "SC-1004") == 0);

    heading("Report an emergency, then assign a rescue");
    Animal calf = c.report_emergency("Injured calf", "Prem Nagar", "Critical", "Other", "", "Hit by a scooter");
    std::printf("created %s (%s) -> status %s\n", calf.id, calf.name, calf.status);
    CHECK(std::strcmp(calf.id, "SC-1005") == 0 && std::strcmp(calf.condition, "Hit by a scooter") == 0);
    CHECK(std::strcmp(c.most_urgent_case()->id, "SC-1004") == 0);   // older Critical case stays first
    c.update_case_status("SC-1004", "Rescue assigned", "Volunteer Aarav on the way");
    CHECK(c.stats().open_emergencies == 2);               // "Rescue assigned" is still open
    CHECK(c.urgency_counts()[0] == 2);

    heading("Route planning (graph + Dijkstra)");
    RoutePlan route = c.plan_route("Shelter (Base)", "ISBT Dehradun");
    std::printf("%.1f km, about %ld min:", route.km, route.eta_minutes);
    for (const std::string &stop : route.path) std::printf("  %s", stop.c_str());
    std::printf("\n");
    CHECK(route.path.size() == 3 && route.path[1] == "Clock Tower" && route.km > 6.49 && route.km < 6.51);
    CHECK(route.eta_minutes == 16);
    TourPlan tour = c.plan_multi_stop("Shelter (Base)", {"ISBT Dehradun", "Prem Nagar", "Clock Tower"});
    std::printf("tour:");
    for (const std::string &stop : tour.order) std::printf("  %s", stop.c_str());
    std::printf("   (%.1f km)\n", tour.total_km);
    CHECK(tour.order.size() == 4 && tour.order[1] == "Clock Tower");
    CHECK(tour.unreachable.empty());

    heading("Food donations (queue)");
    CHECK(std::strcmp(c.next_pickup()->offer_id, "FD-201") == 0);
    c.update_food_status("FD-201", "Collected");
    CHECK(std::strcmp(c.next_pickup()->offer_id, "FD-202") == 0);   // the next oldest is now first
    FoodOffer offer = c.add_food_offer("Sweet Corner", "Plain rice", 20, "GEU", true);
    std::printf("added %s; next pickup is %s\n", offer.offer_id, c.next_pickup()->offer_id);
    CHECK(c.food_stats().active == 3);

    heading("Medical log (linked list)");
    c.add_medical_entry("SC-1004", "Wound cleaning", "Aarav", "2026-10-22", "Bleeding stopped");
    std::vector<MedicalEntry> history = c.list_medical_entries("");
    CHECK(history.size() == 3 && std::strcmp(history[0].animal_id, "SC-1004") == 0);   // newest first

    heading("Validation: bad input is rejected and changes nothing");
    long animals_before = c.stats().animals;
    CHECK(rejected([&] { c.register_animal("  ", "Dog", "GEU", "", "Low", "Reported"); }) == "Animal name / identifier is required.");
    CHECK(!rejected([&] { c.register_animal("X", "Dragon", "GEU", "", "Low", "Reported"); }).empty());
    CHECK(!rejected([&] { c.update_case_status("SC-9999", "Closed", ""); }).empty());
    CHECK(!rejected([&] { c.add_food_offer("Cafe", "Rice", 0, "GEU", true); }).empty());
    CHECK(rejected([&] { c.add_food_offer("Cafe", "Rice", 5, "GEU", false); }).find("food-safety") != std::string::npos);
    CHECK(!rejected([&] { c.add_medical_entry("SC-1004", "x", "y", "2999-01-01", ""); }).empty());   // future
    CHECK(!rejected([&] { c.add_medical_entry("SC-1004", "x", "y", "2026-02-30", ""); }).empty());   // no such day
    CHECK(!rejected([&] { c.add_medical_entry("SC-1004", "x", "y", "yesterday", ""); }).empty());
    CHECK(!rejected([&] { c.plan_route("GEU", "GEU"); }).empty());
    CHECK(!rejected([&] { c.add_road("A", "A", 1.0); }).empty());
    CHECK(!rejected([&] { c.add_road("A", "B", 0.0); }).empty());
    CHECK(!rejected([&] { c.register_animal(std::string(300, 'x'), "Dog", "GEU", "", "Low", "Reported"); }).empty());
    CHECK(c.stats().animals == animals_before);
    CHECK(std::strcmp(c.register_animal("Y", "Dog", "GEU", "", "Low", "Reported").id, "SC-1006") == 0);   // no ID wasted

    heading("Searching (hash table lookup + scan)");
    CHECK(c.list_animals("milo", "All").size() == 1);
    CHECK(c.list_animals("", "Cat").size() == 1);
    CHECK(c.list_animals("zzz-nothing", "All").empty());
    CHECK(c.get_animal("SC-1001").has_value() && !c.get_animal("SC-0000").has_value());

    heading("Edit, delete, erase");
    Animal edited = c.update_animal("SC-1003", "Brownie II", "Cat", "GEU", "", "Medium");
    CHECK(std::string(edited.name) == "Brownie II" && std::string(edited.condition) == "Not assessed");
    CHECK(!rejected([&] { c.update_animal("SC-1003", "", "Cat", "GEU", "", "Medium"); }).empty());
    CHECK(std::string(c.get_animal("SC-1003")->name) == "Brownie II");     // rejected edit changed nothing
    c.add_medical_entry("SC-1003", "Vaccination", "Meera", "2026-10-22", "");
    size_t medical_before = c.list_medical_entries("").size();
    c.delete_animal("SC-1003");
    CHECK(!c.get_animal("SC-1003").has_value());
    CHECK(c.list_medical_entries("SC-1003").empty());
    CHECK(c.list_medical_entries("").size() == medical_before - 1);
    CHECK(!rejected([&] { c.delete_animal("SC-1003"); }).empty());
    c.reset_empty();
    CHECK(c.stats().animals == 0 && c.stats().medical_entries == 0 && c.map_locations().empty());

    std::printf("\nC++ controller self-check: %d checks, %d failed\n", checks, failures);
    return failures ? 1 : 0;
}
