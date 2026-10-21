"""Small Tkinter front end for the STRAYCARE C/C++ shared library."""
import ctypes
import os
import tkinter as tk
from tkinter import ttk, messagebox
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LIBRARY = os.path.join(ROOT, "build", "straycare.dll" if os.name == "nt" else "libstraycare.so")
def load_api():
    if not os.path.exists(LIBRARY):
        raise FileNotFoundError(f"Shared library not found: {LIBRARY}\nBuild the project first (see README.md).")
    lib = ctypes.CDLL(LIBRARY)
    lib.sc_reset.argtypes = []; lib.sc_reset.restype = None
    lib.sc_report_emergency.argtypes = [ctypes.c_int]*4; lib.sc_report_emergency.restype = ctypes.c_int
    lib.sc_next_emergency.argtypes = [ctypes.POINTER(ctypes.c_int)]*4; lib.sc_next_emergency.restype = ctypes.c_int
    lib.sc_add_animal.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]; lib.sc_add_animal.restype = ctypes.c_int
    lib.sc_find_animal.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]; lib.sc_find_animal.restype = ctypes.c_int
    lib.sc_add_medical_record.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p]; lib.sc_add_medical_record.restype = ctypes.c_int
    lib.sc_add_food_offer.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_int]; lib.sc_add_food_offer.restype = ctypes.c_int
    lib.sc_next_food.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]; lib.sc_next_food.restype = ctypes.c_int
    lib.sc_add_location.argtypes = [ctypes.c_int, ctypes.c_char_p]; lib.sc_add_location.restype = ctypes.c_int
    lib.sc_add_road.argtypes = [ctypes.c_int]*4; lib.sc_add_road.restype = ctypes.c_int
    lib.sc_find_route.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int), ctypes.c_int, ctypes.POINTER(ctypes.c_int)]; lib.sc_find_route.restype = ctypes.c_int
    lib.sc_save.argtypes = [ctypes.c_char_p]; lib.sc_save.restype = ctypes.c_int
    lib.sc_load.argtypes = [ctypes.c_char_p]; lib.sc_load.restype = ctypes.c_int
    return lib
class App(tk.Tk):
    def __init__(self, api):
        super().__init__(); self.api = api; self.title("STRAYCARE | Stray Animal Management"); self.geometry("760x620")
        tabs = ttk.Notebook(self); tabs.pack(fill="both", expand=True, padx=10, pady=10)
        self._animal_tab(tabs); self._emergency_tab(tabs); self._medical_tab(tabs); self._food_tab(tabs); self._route_tab(tabs); self._storage_tab(tabs)
    def _tab(self, tabs, name):
        frame=ttk.Frame(tabs,padding=14);tabs.add(frame,text=name);return frame
    def _entry(self, parent, label, row, default=""):
        ttk.Label(parent,text=label).grid(row=row,column=0,sticky="w",padx=5,pady=5);e=ttk.Entry(parent,width=42);e.grid(row=row,column=1,sticky="ew",padx=5,pady=5);e.insert(0,default);return e
    def _animal_tab(self,tabs):
        f=self._tab(tabs,"Animals");self.aid=self._entry(f,"Animal ID",0);self.aname=self._entry(f,"Name",1);self.species=self._entry(f,"Species",2);self.aloc=self._entry(f,"Location",3)
        ttk.Button(f,text="Register animal",command=self.add_animal).grid(row=4,column=1,sticky="w",pady=8)
        self.searchid=self._entry(f,"Search ID",5);ttk.Button(f,text="Search",command=self.find_animal).grid(row=6,column=1,sticky="w");self.animal_result=ttk.Label(f,text="");self.animal_result.grid(row=7,column=0,columnspan=2,sticky="w")
    def add_animal(self):
        try: ok=self.api.sc_add_animal(int(self.aid.get()),self.aname.get().encode(),self.species.get().encode(),self.aloc.get().encode())
        except ValueError: messagebox.showerror("Invalid input","Animal ID must be an integer.");return
        messagebox.showinfo("STRAYCARE","Animal registered." if ok else "Could not register animal. Check ID and duplicate IDs.")
    def find_animal(self):
        try: ident=int(self.searchid.get())
        except ValueError: messagebox.showerror("Invalid input","Enter an integer animal ID.");return
        n=ctypes.create_string_buffer(50);s=ctypes.create_string_buffer(24);l=ctypes.create_string_buffer(100)
        ok=self.api.sc_find_animal(ident,n,50,s,24,l,100);self.animal_result.config(text=f"{n.value.decode()} | {s.value.decode()} | {l.value.decode()}" if ok else "Animal not found.")
    def _emergency_tab(self,tabs):
        f=self._tab(tabs,"Emergency triage");self.iid=self._entry(f,"Incident ID",0);self.eaid=self._entry(f,"Animal ID",1);self.severity=self._entry(f,"Severity (1-10)",2);self.eloc=self._entry(f,"Location ID",3)
        ttk.Button(f,text="Report emergency",command=self.add_emergency).grid(row=4,column=1,sticky="w",pady=8);ttk.Button(f,text="Process highest priority",command=self.next_emergency).grid(row=5,column=1,sticky="w");self.er=ttk.Label(f,text="");self.er.grid(row=6,column=0,columnspan=2,sticky="w")
    def add_emergency(self):
        try: vals=[int(x.get()) for x in (self.iid,self.eaid,self.severity,self.eloc)]
        except ValueError: messagebox.showerror("Invalid input","All incident fields must be integers.");return
        ok=self.api.sc_report_emergency(*vals);self.er.config(text="Emergency added to max heap." if ok else "Invalid or duplicate incident, or heap is full.")
    def next_emergency(self):
        vals=[ctypes.c_int() for _ in range(4)];ok=self.api.sc_next_emergency(*(ctypes.byref(v) for v in vals));self.er.config(text=(f"Processed incident {vals[0].value}; animal {vals[1].value}; severity {vals[2].value}; location {vals[3].value}" if ok else "No active emergencies."))
    def _medical_tab(self,tabs):
        f=self._tab(tabs,"Medical logs");self.mid=self._entry(f,"Record ID",0);self.maid=self._entry(f,"Animal ID",1);self.mdate=self._entry(f,"Date (YYYY-MM-DD)",2);self.note=self._entry(f,"Note",3)
        ttk.Button(f,text="Add medical record",command=self.add_medical).grid(row=4,column=1,sticky="w");ttk.Label(f,text="Records are stored in insertion order in a doubly linked list.").grid(row=5,column=0,columnspan=2,sticky="w",pady=10)
    def add_medical(self):
        try: rid,aid=int(self.mid.get()),int(self.maid.get())
        except ValueError: messagebox.showerror("Invalid input","Record and animal IDs must be integers.");return
        ok=self.api.sc_add_medical_record(rid,aid,self.mdate.get().encode(),self.note.get().encode());messagebox.showinfo("STRAYCARE","Medical record added." if ok else "Could not add record; check fields and duplicate ID.")
    def _food_tab(self,tabs):
        f=self._tab(tabs,"Food queue");self.fid=self._entry(f,"Offer ID",0);self.donor=self._entry(f,"Donor",1);self.food=self._entry(f,"Food",2);self.servings=self._entry(f,"Servings",3);self.shelter=self._entry(f,"Shelter ID",4)
        ttk.Button(f,text="Add offer",command=self.add_food).grid(row=5,column=1,sticky="w",pady=6);ttk.Button(f,text="Process oldest offer",command=self.next_food).grid(row=6,column=1,sticky="w");self.fr=ttk.Label(f,text="");self.fr.grid(row=7,column=0,columnspan=2,sticky="w")
    def add_food(self):
        try: vals=[int(self.fid.get()),self.donor.get().encode(),self.food.get().encode(),int(self.servings.get()),int(self.shelter.get())]
        except ValueError: messagebox.showerror("Invalid input","Offer ID, servings and shelter ID must be integers.");return
        ok=self.api.sc_add_food_offer(*vals);self.fr.config(text="Food offer queued." if ok else "Could not queue offer; check fields and duplicate ID.")
    def next_food(self):
        i=ctypes.c_int();s=ctypes.c_int();sh=ctypes.c_int();d=ctypes.create_string_buffer(64);food=ctypes.create_string_buffer(64)
        ok=self.api.sc_next_food(ctypes.byref(i),d,64,food,64,ctypes.byref(s),ctypes.byref(sh));self.fr.config(text=f"Offer {i.value}: {d.value.decode()} donated {food.value.decode()}, {s.value} servings for shelter {sh.value}." if ok else "Food queue is empty.")
    def _route_tab(self,tabs):
        f=self._tab(tabs,"Route planning");self.lid=self._entry(f,"Location ID",0);self.lname=self._entry(f,"Location name",1);ttk.Button(f,text="Add location",command=self.add_location).grid(row=2,column=1,sticky="w")
        self.rfrom=self._entry(f,"Road from ID",3);self.rto=self._entry(f,"Road to ID",4);self.rdist=self._entry(f,"Distance (positive integer)",5);ttk.Button(f,text="Add two-way road",command=self.add_road).grid(row=6,column=1,sticky="w")
        self.start=self._entry(f,"Route start ID",7);self.end=self._entry(f,"Route end ID",8);ttk.Button(f,text="Find shortest route",command=self.find_route).grid(row=9,column=1,sticky="w");self.rr=ttk.Label(f,text="");self.rr.grid(row=10,column=0,columnspan=2,sticky="w")
    def add_location(self):
        try: i=int(self.lid.get())
        except ValueError: messagebox.showerror("Invalid input","Location ID must be an integer.");return
        self.rr.config(text="Location added." if self.api.sc_add_location(i,self.lname.get().encode()) else "Could not add location.")
    def add_road(self):
        try: a,b,d=int(self.rfrom.get()),int(self.rto.get()),int(self.rdist.get())
        except ValueError: messagebox.showerror("Invalid input","Road fields must be integers.");return
        self.rr.config(text="Two-way road added." if self.api.sc_add_road(a,b,d,1) else "Could not add road; add locations first and use positive distance.")
    def find_route(self):
        try: a,b=int(self.start.get()),int(self.end.get())
        except ValueError: messagebox.showerror("Invalid input","Start and end IDs must be integers.");return
        path=(ctypes.c_int*100)();dist=ctypes.c_int();n=self.api.sc_find_route(a,b,path,100,ctypes.byref(dist));self.rr.config(text=(f"Route: {' -> '.join(map(str,path[:n]))}; distance = {dist.value}" if n else "No route found, or path buffer too small."))
    def _storage_tab(self,tabs):
        f=self._tab(tabs,"Save / Load");self.filename=self._entry(f,"File name",0,"straycare.dat");ttk.Button(f,text="Save all data",command=self.save).grid(row=1,column=1,sticky="w",pady=6);ttk.Button(f,text="Load data",command=self.load).grid(row=2,column=1,sticky="w");ttk.Label(f,text="Loading replaces current in-memory data.").grid(row=3,column=0,columnspan=2,sticky="w",pady=10)
    def save(self): self.storage_result(self.api.sc_save(self.filename.get().encode()),"Data saved.","Save failed.")
    def load(self): self.storage_result(self.api.sc_load(self.filename.get().encode()),"Data loaded.","Load failed; file may be missing or invalid.")
    @staticmethod
    def storage_result(ok,yes,no): messagebox.showinfo("STRAYCARE",yes if ok else no)

if __name__ == "__main__":
    try: api=load_api()
    except OSError as exc: raise SystemExit(str(exc))
    App(api).mainloop()
