from controller import Supervisor
import math

# ============================================================
# INITIALIZATION
# ============================================================
supervisor = Supervisor()
timestep = int(supervisor.getBasicTimeStep())

# ============================================================
# CONFIGURATION
# ============================================================

vehicle_lifetime = 300.0  # Increased lifetime for longer grid travel
spawn_interval = 3.5      # Slightly faster spawn
max_vehicles = 80         # Increased limit for grid

# ---- GRID DEFINITION ----
# The square grid is defined by 4 intersections centered at these coordinates:
#    (NW)   (NE)
#      |     |
#    (SW)   (SE)
GRID_OFFSET = 25.0
INTERSECTIONS = [
    {"id": "NW", "x": -GRID_OFFSET, "y":  GRID_OFFSET}, # Top-Left
    {"id": "NE", "x":  GRID_OFFSET, "y":  GRID_OFFSET}, # Top-Right
    {"id": "SW", "x": -GRID_OFFSET, "y": -GRID_OFFSET}, # Bottom-Left
    {"id": "SE", "x":  GRID_OFFSET, "y": -GRID_OFFSET}  # Bottom-Right
]

# Stop line settings
STOP_DIST_FROM_CENTER = 12.0  # Distance from intersection center to stop line
STOP_ZONE_DEPTH = 4.0         # Detection range for stopping
SAFE_DISTANCE = 5.0           # Anti-piling distance

# Traffic light cycle (Synchronized for all 4)
EW_GREEN_TIME = 15.0
NS_GREEN_TIME = 15.0

# ---- SPAWN CONFIGURATION ----
# Cars only spawn at the "entrances" of the grid (Outer edges)
LANE_OFFSET = 3.0
SPAWN_DIST  = 75.0  # Distance from center (outside the grid)

SPAWN_POINTS = [
    # --- EASTBOUND (Going +X) ---
    # Enters at NW (Top-Left) and SW (Bottom-Left)
    {"dir": "east", "pos": [-SPAWN_DIST, GRID_OFFSET + LANE_OFFSET, 0],  "rot": [0, 1, 0, 0]},
    {"dir": "east", "pos": [-SPAWN_DIST, -GRID_OFFSET + LANE_OFFSET, 0], "rot": [0, 1, 0, 0]},

    # --- WESTBOUND (Going -X) ---
    # Enters at NE (Top-Right) and SE (Bottom-Right)
    {"dir": "west", "pos": [SPAWN_DIST, GRID_OFFSET - LANE_OFFSET, 0],   "rot": [0, 1, 0, math.pi]},
    {"dir": "west", "pos": [SPAWN_DIST, -GRID_OFFSET - LANE_OFFSET, 0],  "rot": [0, 1, 0, math.pi]},

    # --- NORTHBOUND (Going +Y) ---
    # Enters at SW (Bottom-Left) and SE (Bottom-Right)
    {"dir": "north", "pos": [-GRID_OFFSET - LANE_OFFSET, -SPAWN_DIST, 0], "rot": [0, 0, 1, math.pi/2]},
    {"dir": "north", "pos": [GRID_OFFSET - LANE_OFFSET, -SPAWN_DIST, 0],  "rot": [0, 0, 1, math.pi/2]},

    # --- SOUTHBOUND (Going -Y) ---
    # Enters at NW (Top-Left) and NE (Top-Right)
    {"dir": "south", "pos": [-GRID_OFFSET + LANE_OFFSET, SPAWN_DIST, 0], "rot": [0, 0, 1, -math.pi/2]},
    {"dir": "south", "pos": [GRID_OFFSET + LANE_OFFSET, SPAWN_DIST, 0],  "rot": [0, 0, 1, -math.pi/2]},
]

# Deletion boundaries (World Limits)
DELETE_LIMIT = 80.0 


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def vehicle_string(def_name, position, rotation):
    return f"""
DEF {def_name} SimpleVehicle {{
  translation {position[0]} {position[1]} {position[2]}
  rotation {rotation[0]} {rotation[1]} {rotation[2]} {rotation[3]}
}}
"""

def spawn_vehicle(def_name, spawn_data):
    root = supervisor.getRoot()
    children = root.getField("children")
    children.importMFNodeFromString(-1, vehicle_string(def_name, spawn_data["pos"], spawn_data["rot"]))

def delete_vehicle(def_name):
    node = supervisor.getFromDef(def_name)
    if node:
        node.remove()

def hold_vehicle_at(node, pos):
    node.getField("translation").setSFVec3f(pos)

def get_closest_intersection(pos):
    """Finds the intersection closest to the vehicle."""
    closest = None
    min_dist = 1e9
    
    for inter in INTERSECTIONS:
        # Euclidean distance ignoring Z
        d = math.sqrt((pos[0] - inter["x"])**2 + (pos[1] - inter["y"])**2)
        if d < min_dist:
            min_dist = d
            closest = inter
            
    return closest, min_dist

def is_ew_green(sim_time):
    cycle = EW_GREEN_TIME + NS_GREEN_TIME
    phase = sim_time % cycle
    return phase < EW_GREEN_TIME


# ============================================================
# STATE MANAGEMENT
# ============================================================

vehicles = []  # List of dicts: {def, direction, spawn_time}
next_spawn_time = 0.0
spawn_index = 0 # To cycle through spawn points

# ============================================================
# MAIN LOOP
# ============================================================

while supervisor.step(timestep) != -1:
    sim_time = supervisor.getTime()
    ew_green = is_ew_green(sim_time)

    # --------------------------------------------------------
    # 1. SPAWN VEHICLES (Round Robin Strategy)
    # --------------------------------------------------------
    if sim_time >= next_spawn_time and len(vehicles) < max_vehicles:
        # Spawn at one of the 8 points, then cycle to the next
        spawn_data = SPAWN_POINTS[spawn_index]
        
        name = f"V_{int(sim_time * 10)}_{spawn_index}" # Unique ID
        spawn_vehicle(name, spawn_data)
        
        vehicles.append({
            "def": name, 
            "direction": spawn_data["dir"], 
            "spawn_time": sim_time
        })

        # Move to next spawn point for the next cycle
        spawn_index = (spawn_index + 1) % len(SPAWN_POINTS)
        next_spawn_time = sim_time + (spawn_interval / 2.0) # Spawn faster to fill grid


    # --------------------------------------------------------
    # 2. UPDATE VEHICLES
    # --------------------------------------------------------
    vehicles_to_delete = []

    for v in vehicles:
        node = supervisor.getFromDef(v["def"])

        if not node:
            vehicles_to_delete.append(v)
            continue

        pos = node.getPosition()
        direction = v["direction"]
        age = sim_time - v["spawn_time"]

        # ====================================================
        # A. GLOBAL DELETION CHECK (Out of Map)
        # ====================================================
        # Only delete if they are FAR outside the grid (passed all intersections)
        if (abs(pos[0]) > DELETE_LIMIT or abs(pos[1]) > DELETE_LIMIT or age > vehicle_lifetime):
            delete_vehicle(v["def"])
            vehicles_to_delete.append(v)
            continue

        # ====================================================
        # B. SAFETY STOP (Anti-Piling Priority)
        # ====================================================
        nearest_front_dist = 1e9
        nearest_front_pos = None

        # Check against all other vehicles
        for other in vehicles:
            if other is v: continue
            
            onode = supervisor.getFromDef(other["def"])
            if not onode: continue
            opos = onode.getPosition()

            lane_tolerance = 1.0 # Vehicles must be in same lane

            # Logic to detect car in front based on direction
            dist = 1e9
            is_front = False

            if direction == "east" and abs(pos[1] - opos[1]) < lane_tolerance and opos[0] > pos[0]:
                dist = opos[0] - pos[0]
                is_front = True
            elif direction == "west" and abs(pos[1] - opos[1]) < lane_tolerance and opos[0] < pos[0]:
                dist = pos[0] - opos[0]
                is_front = True
            elif direction == "north" and abs(pos[0] - opos[0]) < lane_tolerance and opos[1] > pos[1]:
                dist = opos[1] - pos[1]
                is_front = True
            elif direction == "south" and abs(pos[0] - opos[0]) < lane_tolerance and opos[1] < pos[1]:
                dist = pos[1] - opos[1]
                is_front = True
            
            if is_front and dist < nearest_front_dist:
                nearest_front_dist = dist
                nearest_front_pos = opos

        # If car ahead is too close, calculate specific stop coordinate
        if nearest_front_pos and nearest_front_dist < SAFE_DISTANCE:
            if direction == "east":
                hold_vehicle_at(node, [nearest_front_pos[0] - SAFE_DISTANCE, pos[1], pos[2]])
            elif direction == "west":
                hold_vehicle_at(node, [nearest_front_pos[0] + SAFE_DISTANCE, pos[1], pos[2]])
            elif direction == "north":
                hold_vehicle_at(node, [pos[0], nearest_front_pos[1] - SAFE_DISTANCE, pos[2]])
            elif direction == "south":
                hold_vehicle_at(node, [pos[0], nearest_front_pos[1] + SAFE_DISTANCE, pos[2]])
            
            continue # Skip traffic light check

        # ====================================================
        # C. TRAFFIC LIGHT CHECK (Multi-Intersection)
        # ====================================================
        
        # 1. Find which intersection we are approaching
        target_inter, dist_to_inter = get_closest_intersection(pos)
        
        # 2. Only check lights if we are reasonably close (e.g., within 35m)
        #    This prevents cars in the middle of the road from stopping randomly.
        if target_inter and dist_to_inter < 35.0:
            
            stopped_by_light = False
            ix = target_inter["x"]
            iy = target_inter["y"]

            # Calculate Stop Lines for THIS specific intersection
            stop_line_east  = ix - STOP_DIST_FROM_CENTER
            stop_line_west  = ix + STOP_DIST_FROM_CENTER
            stop_line_north = iy - STOP_DIST_FROM_CENTER
            stop_line_south = iy + STOP_DIST_FROM_CENTER

            # Apply Logic
            if direction == "east":
                # Check if we are approaching the stop line from the left
                dist_to_line = stop_line_east - pos[0]
                if not ew_green and 0 < dist_to_line <= STOP_ZONE_DEPTH:
                    hold_vehicle_at(node, [stop_line_east - 1.0, pos[1], pos[2]])
                    stopped_by_light = True

            elif direction == "west":
                # Check if we are approaching from the right
                dist_to_line = pos[0] - stop_line_west
                if not ew_green and 0 < dist_to_line <= STOP_ZONE_DEPTH:
                    hold_vehicle_at(node, [stop_line_west + 1.0, pos[1], pos[2]])
                    stopped_by_light = True

            elif direction == "north":
                # Check if we are approaching from bottom
                dist_to_line = stop_line_north - pos[1]
                if ew_green and 0 < dist_to_line <= STOP_ZONE_DEPTH: # NS Stops when EW Green
                    hold_vehicle_at(node, [pos[0], stop_line_north - 1.0, pos[2]])
                    stopped_by_light = True

            elif direction == "south":
                # Check if we are approaching from top
                dist_to_line = pos[1] - stop_line_south
                if ew_green and 0 < dist_to_line <= STOP_ZONE_DEPTH: # NS Stops when EW Green
                    hold_vehicle_at(node, [pos[0], stop_line_south + 1.0, pos[2]])
                    stopped_by_light = True
            
            if stopped_by_light:
                continue

    # Clean up deleted vehicles
    for v_del in vehicles_to_delete:
        if v_del in vehicles:
            vehicles.remove(v_del)