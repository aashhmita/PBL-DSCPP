// integration.cpp : the C++ integration layer between the controller and the Python frontend.
//
// Python can only call plain C functions, so this file exposes the whole C++ controller through
// four of them:
//
//     void *sc_create(void)                      make a controller (returns a handle)
//     void  sc_destroy(void *handle)             delete it
//     char *sc_invoke(handle, method, argc, argv) run one controller method by name
//     void  sc_free_string(char *text)           free a string that sc_invoke returned
//
// sc_invoke takes the method name and its arguments as text, and returns JSON text:
//     {"ok": true,  "data": ...}                                   success
//     {"ok": false, "kind": "validation", "error": "..."}          the user can fix this
//     {"ok": false, "kind": "internal",   "error": "..."}          a bug or a bad call
// No C++ exception ever crosses this boundary: everything is caught and turned into JSON.
//
// Not thread-safe (see controller.hpp); the Python bridge serializes the calls.

#include <cerrno>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

#include "controller.hpp"

#if defined(_WIN32)
#define SC_EXPORT extern "C" __declspec(dllexport)
#else
#define SC_EXPORT extern "C" __attribute__((visibility("default")))
#endif

using namespace straycare;

namespace {

using Args = std::vector<std::string>;
using Handler = std::function<std::string(StrayCareController &, const Args &)>;

// ---- JSON writing (just what we need) ----------------------------------------------------

std::string q(const std::string &text)             // JSON string literal with escaping
{
    std::string out = "\"";
    for (unsigned char c : text) {
        switch (c) {
            case '"':  out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (c < 0x20) {
                    char buf[8];
                    std::snprintf(buf, sizeof buf, "\\u%04x", c);
                    out += buf;
                } else {
                    out += static_cast<char>(c);
                }
        }
    }
    out += '"';
    return out;
}

std::string num(double value)                      // exact round-trip, always a JSON number
{
    char buf[40];
    std::snprintf(buf, sizeof buf, "%.17g", value);
    std::string text = buf;
    if (text.find_first_of(".eE") == std::string::npos) text += ".0";
    return text;
}

std::string num(long value) { return std::to_string(value); }

template <typename T, typename F>
std::string array_of(const std::vector<T> &items, F to_json)
{
    std::string out = "[";
    for (size_t i = 0; i < items.size(); i++) {
        if (i) out += ",";
        out += to_json(items[i]);
    }
    return out + "]";
}

std::string strings_json(const std::vector<std::string> &items)
{
    return array_of(items, [](const std::string &s) { return q(s); });
}

// Keys keep the same order the Streamlit tables expect for their columns.
std::string to_json(const Animal &a)
{
    return "{\"ID\":" + q(a.id) + ",\"Name\":" + q(a.name) + ",\"Species\":" + q(a.species) +
           ",\"Location\":" + q(a.location) + ",\"Condition\":" + q(a.condition) +
           ",\"Status\":" + q(a.status) + ",\"Urgency\":" + q(a.urgency) +
           ",\"Reported\":" + q(a.reported) + "}";
}

std::string to_json(const FoodOffer &o)
{
    return "{\"Offer ID\":" + q(o.offer_id) + ",\"Donor\":" + q(o.donor) + ",\"Food\":" + q(o.food) +
           ",\"Servings\":" + num(o.servings) + ",\"Pickup area\":" + q(o.pickup_area) +
           ",\"Status\":" + q(o.status) + "}";
}

std::string to_json(const MedicalEntry &e)
{
    return "{\"Date\":" + q(e.date) + ",\"Animal ID\":" + q(e.animal_id) + ",\"Treatment\":" + q(e.treatment) +
           ",\"Volunteer\":" + q(e.volunteer) + ",\"Notes\":" + q(e.notes) + "}";
}

std::string to_json(const ActivityItem &i)
{
    return "{\"when\":" + q(i.when) + ",\"title\":" + q(i.title) + ",\"detail\":" + q(i.detail) +
           ",\"status\":" + q(i.status) + "}";
}

std::string to_json(const RoutePlan &p)
{
    return "{\"km\":" + num(p.km) + ",\"eta_minutes\":" + num(p.eta_minutes) + ",\"path\":" + strings_json(p.path) + "}";
}

std::string to_json(const TourPlan &p)
{
    std::string legs = array_of(p.legs, [](const TourLeg &l) {
        return "{\"from\":" + q(l.from) + ",\"to\":" + q(l.to) + ",\"km\":" + num(l.km) +
               ",\"path\":" + strings_json(l.path) + "}";
    });
    return "{\"order\":" + strings_json(p.order) + ",\"legs\":" + legs + ",\"total_km\":" + num(p.total_km) +
           ",\"unreachable\":" + strings_json(p.unreachable) + ",\"eta_minutes\":" + num(p.eta_minutes) + "}";
}

template <typename T>
std::string optional_json(const std::optional<T> &value)
{
    return value ? to_json(*value) : "null";
}

// ---- reading arguments -------------------------------------------------------------------

void need(const Args &args, size_t count, const char *method)
{
    if (args.size() != count) {
        throw std::logic_error(std::string(method) + " expects " + std::to_string(count) + " arguments, got " +
                               std::to_string(args.size()));
    }
}

long parse_long(const std::string &text, const char *what)    // internal numbers (limits, counters)
{
    char *end = nullptr;
    errno = 0;
    long value = std::strtol(text.c_str(), &end, 10);
    if (text.empty() || *end != '\0' || errno != 0) throw std::logic_error(std::string("bad number for ") + what);
    return value;
}

long long parse_servings(const std::string &text)
{
    char *end = nullptr;
    errno = 0;
    long long value = std::strtoll(text.c_str(), &end, 10);
    if (text.empty() || *end != '\0') throw ValidationError("Servings must be a whole number.");
    if (errno == ERANGE) throw ValidationError("Servings must be between 1 and 10,000.");
    return value;
}

double parse_km(const std::string &text)
{
    char *end = nullptr;
    double value = std::strtod(text.c_str(), &end);
    if (text.empty() || *end != '\0' || !std::isfinite(value)) throw ValidationError("Distance must be a number.");
    return value;
}

bool parse_bool(const std::string &text)
{
    return text == "1" || text == "true" || text == "True";
}

// Copies of saved records, used by the restore_* methods.
Animal animal_from(const Args &a)
{
    Animal animal;
    std::memset(&animal, 0, sizeof animal);
    auto fill = [](char *dest, size_t cap, const std::string &text) {
        if (sc_copy(dest, cap, text.c_str()) != 0) throw ValidationError("Saved text is too long.");
    };
    fill(animal.id, sizeof animal.id, a[0]);
    fill(animal.name, sizeof animal.name, a[1]);
    fill(animal.species, sizeof animal.species, a[2]);
    fill(animal.location, sizeof animal.location, a[3]);
    fill(animal.condition, sizeof animal.condition, a[4]);
    fill(animal.status, sizeof animal.status, a[5]);
    fill(animal.urgency, sizeof animal.urgency, a[6]);
    fill(animal.reported, sizeof animal.reported, a[7]);
    return animal;
}

FoodOffer offer_from(const Args &a)
{
    FoodOffer offer;
    std::memset(&offer, 0, sizeof offer);
    auto fill = [](char *dest, size_t cap, const std::string &text) {
        if (sc_copy(dest, cap, text.c_str()) != 0) throw ValidationError("Saved text is too long.");
    };
    fill(offer.offer_id, sizeof offer.offer_id, a[0]);
    fill(offer.donor, sizeof offer.donor, a[1]);
    fill(offer.food, sizeof offer.food, a[2]);
    offer.servings = parse_long(a[3], "servings");
    fill(offer.pickup_area, sizeof offer.pickup_area, a[4]);
    fill(offer.status, sizeof offer.status, a[5]);
    return offer;
}

MedicalEntry entry_from(const Args &a)
{
    MedicalEntry entry;
    std::memset(&entry, 0, sizeof entry);
    auto fill = [](char *dest, size_t cap, const std::string &text) {
        if (sc_copy(dest, cap, text.c_str()) != 0) throw ValidationError("Saved text is too long.");
    };
    fill(entry.date, sizeof entry.date, a[0]);
    fill(entry.animal_id, sizeof entry.animal_id, a[1]);
    fill(entry.treatment, sizeof entry.treatment, a[2]);
    fill(entry.volunteer, sizeof entry.volunteer, a[3]);
    fill(entry.notes, sizeof entry.notes, a[4]);
    return entry;
}

// ---- the method table: name -> what to call ----------------------------------------------

std::string export_state(StrayCareController &c)
{
    std::string roads = array_of(c.road_list(), [](const Road &r) {
        return "[" + q(r.a) + "," + q(r.b) + "," + num(r.km) + "]";
    });
    return "{\"animals\":" + array_of(c.list_animals("", "All"), [](const Animal &a) { return to_json(a); }) +
           ",\"food_offers\":" + array_of(c.list_food_offers(), [](const FoodOffer &o) { return to_json(o); }) +
           ",\"medical_logs\":" + array_of(c.medical_oldest_first(), [](const MedicalEntry &e) { return to_json(e); }) +
           ",\"activity\":" + array_of(c.all_activity(), [](const ActivityItem &i) { return to_json(i); }) +
           ",\"roads\":" + roads + ",\"next_animal_no\":" + num(c.next_animal_number()) +
           ",\"next_food_no\":" + num(c.next_food_number()) + "}";
}

const std::map<std::string, Handler> &handlers()
{
    static const std::map<std::string, Handler> table = {
        // ---- animals ----
        {"register_animal", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 6, "register_animal");
             return to_json(c.register_animal(a[0], a[1], a[2], a[3], a[4], a[5]));
         }},
        {"report_emergency", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 6, "report_emergency");
             return to_json(c.report_emergency(a[0], a[1], a[2], a[3], a[4], a[5]));
         }},
        {"update_animal", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 6, "update_animal");
             return to_json(c.update_animal(a[0], a[1], a[2], a[3], a[4], a[5]));
         }},
        {"delete_animal", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 1, "delete_animal");
             return to_json(c.delete_animal(a[0]));
         }},
        {"update_case_status", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 3, "update_case_status");
             return to_json(c.update_case_status(a[0], a[1], a[2]));
         }},
        {"get_animal", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 1, "get_animal");
             return optional_json(c.get_animal(a[0]));
         }},
        {"list_animals", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 2, "list_animals");
             return array_of(c.list_animals(a[0], a[1]), [](const Animal &x) { return to_json(x); });
         }},
        {"animal_choices", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 0, "animal_choices");
             return strings_json(c.animal_choices());
         }},
        // ---- triage ----
        {"triage_order", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 0, "triage_order");
             return array_of(c.triage_order(), [](const Animal &x) { return to_json(x); });
         }},
        {"priority_cases", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 0, "priority_cases");
             return array_of(c.priority_cases(), [](const Animal &x) { return to_json(x); });
         }},
        {"most_urgent_case", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 0, "most_urgent_case");
             return optional_json(c.most_urgent_case());
         }},
        {"urgency_counts", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 0, "urgency_counts");
             auto n = c.urgency_counts();
             return "{\"Critical\":" + num(n[0]) + ",\"High\":" + num(n[1]) + ",\"Medium\":" + num(n[2]) +
                    ",\"Low\":" + num(n[3]) + "}";
         }},
        // ---- food ----
        {"add_food_offer", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 5, "add_food_offer");
             return to_json(c.add_food_offer(a[0], a[1], parse_servings(a[2]), a[3], parse_bool(a[4])));
         }},
        {"update_food_status", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 2, "update_food_status");
             return to_json(c.update_food_status(a[0], a[1]));
         }},
        {"list_food_offers", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 0, "list_food_offers");
             return array_of(c.list_food_offers(), [](const FoodOffer &o) { return to_json(o); });
         }},
        {"next_pickup", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 0, "next_pickup");
             return optional_json(c.next_pickup());
         }},
        {"food_stats", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 0, "food_stats");
             FoodStats s = c.food_stats();
             return "{\"total\":" + num(s.total) + ",\"active\":" + num(s.active) + ",\"active_servings\":" +
                    num(s.active_servings) + ",\"available\":" + num(s.available) + "}";
         }},
        // ---- medical ----
        {"add_medical_entry", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 5, "add_medical_entry");
             return to_json(c.add_medical_entry(a[0], a[1], a[2], a[3], a[4]));
         }},
        {"list_medical_entries", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 1, "list_medical_entries");
             return array_of(c.list_medical_entries(a[0]), [](const MedicalEntry &e) { return to_json(e); });
         }},
        // ---- routes ----
        {"map_locations", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 0, "map_locations");
             return strings_json(c.map_locations());
         }},
        {"road_list", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 0, "road_list");
             return array_of(c.road_list(), [](const Road &r) {
                 return "{\"From\":" + q(r.a) + ",\"To\":" + q(r.b) + ",\"Distance (km)\":" + num(r.km) + "}";
             });
         }},
        {"unmapped_locations", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 0, "unmapped_locations");
             return strings_json(c.unmapped_locations());
         }},
        {"open_case_locations", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 0, "open_case_locations");
             return strings_json(c.open_case_locations());
         }},
        {"plan_route", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 2, "plan_route");
             return to_json(c.plan_route(a[0], a[1]));
         }},
        {"plan_multi_stop", [](StrayCareController &c, const Args &a) -> std::string {
             if (a.empty()) throw std::logic_error("plan_multi_stop needs a starting point");
             return to_json(c.plan_multi_stop(a[0], Args(a.begin() + 1, a.end())));   // the rest are the stops
         }},
        {"add_road", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 3, "add_road");
             c.add_road(a[0], a[1], parse_km(a[2]));
             return "null";
         }},
        // ---- dashboard ----
        {"recent_activity", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 1, "recent_activity");
             long limit = parse_long(a[0], "limit");
             return array_of(c.recent_activity(limit < 0 ? 0 : static_cast<size_t>(limit)),
                             [](const ActivityItem &i) { return to_json(i); });
         }},
        {"stats", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 0, "stats");
             Stats s = c.stats();
             return "{\"animals\":" + num(s.animals) + ",\"open_emergencies\":" + num(s.open_emergencies) +
                    ",\"active_food_offers\":" + num(s.active_food_offers) + ",\"medical_entries\":" +
                    num(s.medical_entries) + "}";
         }},
        // ---- data set management, saving and loading ----
        {"reset_demo", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 0, "reset_demo");
             c.reset_demo();
             return "null";
         }},
        {"reset_empty", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 0, "reset_empty");
             c.reset_empty();
             return "null";
         }},
        {"export_state", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 0, "export_state");
             return export_state(c);
         }},
        {"restore_animal", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 8, "restore_animal");
             c.restore_animal(animal_from(a));
             return "null";
         }},
        {"restore_food", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 6, "restore_food");
             c.restore_food(offer_from(a));
             return "null";
         }},
        {"restore_medical", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 5, "restore_medical");
             c.restore_medical(entry_from(a));
             return "null";
         }},
        {"restore_road", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 3, "restore_road");
             c.restore_road(a[0], a[1], parse_km(a[2]));
             return "null";
         }},
        {"restore_activity", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 4, "restore_activity");
             c.restore_activity(ActivityItem{a[0], a[1], a[2], a[3]});
             return "null";
         }},
        {"set_counters", [](StrayCareController &c, const Args &a) -> std::string {
             need(a, 2, "set_counters");
             c.set_counters(parse_long(a[0], "next_animal_no"), parse_long(a[1], "next_food_no"));
             return "null";
         }},
    };
    return table;
}

std::string error_json(const char *kind, const std::string &message)
{
    return std::string("{\"ok\":false,\"kind\":") + q(kind) + ",\"error\":" + q(message) + "}";
}

char *copy_to_c_string(const std::string &text)
{
    char *out = static_cast<char *>(std::malloc(text.size() + 1));
    if (!out) return nullptr;
    std::memcpy(out, text.c_str(), text.size() + 1);
    return out;
}

}  // namespace

// =========================================================================================
// The C interface that Python loads
// =========================================================================================

SC_EXPORT void *sc_create(void)
{
    try {
        return new StrayCareController();
    } catch (...) {
        return nullptr;
    }
}

SC_EXPORT void sc_destroy(void *handle)
{
    delete static_cast<StrayCareController *>(handle);
}

SC_EXPORT char *sc_invoke(void *handle, const char *method, int argc, const char *const *argv)
{
    std::string reply;
    try {
        if (!handle || !method) throw std::logic_error("null handle or method name");
        Args args;
        for (int i = 0; i < argc; i++) args.emplace_back(argv && argv[i] ? argv[i] : "");

        const auto &table = handlers();
        auto found = table.find(method);
        if (found == table.end()) throw std::logic_error(std::string("unknown method: ") + method);

        reply = "{\"ok\":true,\"data\":" + found->second(*static_cast<StrayCareController *>(handle), args) + "}";
    } catch (const ValidationError &e) {
        reply = error_json("validation", e.what());
    } catch (const std::exception &e) {
        reply = error_json("internal", e.what());
    } catch (...) {
        reply = error_json("internal", "unknown error");
    }
    return copy_to_c_string(reply);
}

SC_EXPORT void sc_free_string(char *text)
{
    std::free(text);
}

SC_EXPORT const char *sc_version(void)
{
    return "StrayCare native core 1.0 (C core + C++ controller)";
}
