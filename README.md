## STRAYCARE: Stray Animal Management System

## Project Title and Description
STRAYCARE is a desktop application designed to streamline street animal rescue operations, bringing emergency response, medical tracking, and shelter management into a single platform.

## Problem Statement / Objective
Rescue teams currently rely on disorganized phone calls and group chats, leading to slow response times and missed information. The objective is to build an efficient system using high-performance C/C++ data structures and a Python interface to manage rescues effectively.

## Team Members
* Sahil Pandey (Team Lead)
* Aashmita Nair
* Suditi Verma
* Ashita Pundir

## Technologies and Tools Used
* Python (Desktop UI and Controller Layer)
* C / C++ (Backend engine and data structures)
* `ctypes` (Python-to-C bridge)[cite: 11]
* Git & GitHub (Version control)[cite: 11]

## Project Setup / Installation Instructions
1. Clone the repository:
   ```bash
   git clone [https://github.com/aashhmita/PBL-DSCPP.git](https://github.com/aashhmita/PBL-DSCPP.git)
   cd PBL-DSCPP
## Major Features / Modules
1. Emergency Triage: Max-priority heap to rank urgent injury reports.   
2. Animal Records: Hash tables for quick lookups by ID.   
3. Medical Logging: Linked lists for maintaining treatment history.   
4. Route Planning: Graphs for efficient rescue van dispatch.   
5. Food Surplus Distribution: Queues to manage food collections and shelter delivery.
6. Shelter Dashboard: Real-time tracking of available beds and capacity
7. Data Persistence: Binary file storage to save records across sessions

## Current Project Status & Deliverables Progress
-Python Desktop Interface & Controller Layer:(Tested & Passed)
-Food Surplus Distribution Module (Queue): Completed (Tested & Passed)
-Medical Logs Module (Linked List): Completed(Tested & Passed)
-Shelter Capacity & Management Dashboard: Completed (Tested & Passed)
-Emergency Triage Module (Max Priority Heap): Pending
-Route Planning / Emergency Dispatch Module (Graph): Pending
-Animal Record Lookup Module (Hash Table): Pending
-Data Persistence Layer (Binary File Storage): Pending
