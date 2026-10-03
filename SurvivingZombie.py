"""
=============================================================================
 Surviving Zombie  —  GROUP-12
 A 3D top-down action shooter built with legacy OpenGL.
 
 Controls:
   WASD        – Move player (world-axis aligned)
   Mouse Move  – Aim (player faces cursor)
   Left Click  – Shoot toward cursor
   Right Click – Toggle camera mode (3rd-person / 1st-person)
   Arrow Keys  – Orbit / raise-lower camera
   1/2/3       – Buy items in Shop (between waves)
   C           – Toggle cheat mode (auto-aim turret)
   V           – Toggle cheat vision (1st-person follows turret)
   R           – Restart game
   
 Weapons (unlocked via Shop):
   Pistol       – Default. Single slow shot.
   Machine Gun  – Rapid fire, single bullet.
   Shotgun      – 3-bullet spread per shot.

 Waves:
   Level 1 – Slow regular zombies (green-ish)
   Level 2 – Faster mutant zombies  (purple)
   Level 3 – Boss zombie + minions   (boss = huge red)
=============================================================================
"""

import math
import random
import time
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *

# ===========================================================================
# Constants
# ===========================================================================
WINDOW_WIDTH  = 1000
WINDOW_HEIGHT = 800
GRID_LENGTH   = 600

# ===========================================================================
# Player state
# ===========================================================================
player_pos        = [0.0, 0.0, 0.0]
gun_angle         = 90.0
manual_gun_angle  = 90.0
player_max_hp     = 5
player_hp         = 5
player_speed      = 10.0

# Weapon system: 0=Pistol, 1=MachineGun, 2=Shotgun
current_weapon    = 0
weapons_unlocked  = [True, False, False]  # Pistol unlocked by default
weapon_names      = ["Pistol", "Machine Gun", "Shotgun"]
weapon_fire_delay = [0.35, 0.08, 0.45]   # seconds between shots
weapon_colors     = [(0.7, 0.7, 0.7), (0.2, 0.2, 0.8), (0.8, 0.4, 0.1)]

# ===========================================================================
# Camera
# ===========================================================================
camera_angle  = 90.0
camera_height = 500.0
camera_zoom   = 1.0
camera_mode   = 3          # 3 = third-person orbit, 1 = first-person, 2 = top-down
prev_camera_mode = 3

# ===========================================================================
# Economy
# ===========================================================================
money = 0

# ===========================================================================
# Game state
# ===========================================================================
cheat_mode    = False
cheat_vision  = False
game_over     = False
game_won      = False
score         = 0
current_wave  = 1          # 1, 2, 3
wave_active   = True       # True = gameplay, False = shop phase
wave_clear_pending = False  # True = wave done, waiting for player to collect cash
wave_zombie_count    = [8, 12, 10]   # Zombies to kill per wave
wave_zombies_killed  = 0
boss_alive           = False

# Keys currently held down — polled each idle frame for smooth movement
keys_held = set()

# Timing
last_time       = 0.0
last_fire_time  = 0.0
frame_count     = 0

# ===========================================================================
# Bullets, Enemies, Cash drops
# ===========================================================================
bullets   = []
enemies   = []
cash_drops = []

# Cannon system
cannons         = []   # placed cannons: {x, y, angle, last_fire}
cannon_balls    = []   # cannon projectiles: {x, y, angle, src_x, src_y}
cannon_inventory = 0   # number of cannons available to place
CANNON_FIRE_DELAY  = 1.5    # seconds between shots
CANNON_RANGE       = 400.0  # targeting range
CANNON_BALL_SPEED  = 12.0
CANNON_SPLASH_RADIUS = 80.0 # area damage radius
CANNON_DAMAGE      = 3      # damage per hit
splash_effects     = []     # visual splash rings: {x, y, radius, max_radius, alpha}

# Mouse tracking
mouse_x = WINDOW_WIDTH  // 2
mouse_y = WINDOW_HEIGHT // 2

# First-person mouse look: warp-based center-lock
fp_ignore_warp = False         # flag to skip the motion event triggered by glutWarpPointer
FP_MOUSE_SENSITIVITY = 0.30   # degrees per pixel of horizontal mouse movement

# Shop items: (name, cost, description, effect_applied_flag)
SHOP_ITEMS = [
    {"name": "Max HP +3",       "cost": 50,  "key": "1"},
    {"name": "Machine Gun",     "cost": 80,  "key": "2"},
    {"name": "Shotgun",         "cost": 120, "key": "3"},
    {"name": "Cannon (placeable)", "cost": 100, "key": "4"},
]

# ===========================================================================
# Helper: 3-D math for mouse ray-cast
# ===========================================================================
def _norm3(x, y, z):
    l = math.sqrt(x*x + y*y + z*z)
    if l < 1e-9:
        return x, y, z
    return x/l, y/l, z/l

def _cross3(ax, ay, az, bx, by, bz):
    return (ay*bz - az*by,
            az*bx - ax*bz,
            ax*by - ay*bx)

def mouse_world_pos(win_x, win_y):
    """
    Cast ray from camera through mouse pixel and intersect with Z=0 plane.
    Returns (world_x, world_y) or (None, None).
    """
    ndc_x =  (2.0 * win_x / WINDOW_WIDTH)  - 1.0
    ndc_y =   1.0 - (2.0 * win_y / WINDOW_HEIGHT)

    tan_half = math.tan(math.radians(120.0 / 2.0))
    aspect   = 1.25

    # Default Up Vector for projection alignment
    up_x, up_y, up_z = 0.0, 0.0, 1.0

    if camera_mode == 3:
        cam_dist = 800.0 * camera_zoom
        rad = math.radians(camera_angle)
        ex  = math.cos(rad) * cam_dist
        ey  = math.sin(rad) * cam_dist
        ez  = camera_height * camera_zoom
        tx, ty, tz = 0.0, 0.0, 0.0
    elif camera_mode == 2:
        rad = math.radians(camera_angle)
        ex  = 0.0
        ey  = 0.0
        ez  = 1000.0 * camera_zoom
        tx, ty, tz = 0.0, 0.0, 0.0
        # In exact top-down, looking down exactly parallel to Z crashes generic cross paths
        # We manually use the camera's rotation angle mapped to the XY plane as our Up vector
        up_x, up_y, up_z = math.cos(rad), math.sin(rad), 0.0
    else:
        look_angle = gun_angle if (cheat_mode and cheat_vision) else manual_gun_angle
        rad = math.radians(look_angle)
        ex  = player_pos[0] - math.cos(rad) * 150
        ey  = player_pos[1] - math.sin(rad) * 150
        ez  = 150.0 + (camera_height - 500.0)
        tx  = player_pos[0] + math.cos(rad) * 100
        ty  = player_pos[1] + math.sin(rad) * 100
        tz  = ez

    fx, fy, fz = _norm3(tx - ex, ty - ey, tz - ez)
    rx, ry, rz = _norm3(*_cross3(fx, fy, fz, up_x, up_y, up_z))
    ux, uy, uz = _cross3(rx, ry, rz, fx, fy, fz)

    rdx = ndc_x * aspect * tan_half * rx + ndc_y * tan_half * ux + fx
    rdy = ndc_x * aspect * tan_half * ry + ndc_y * tan_half * uy + fy
    rdz = ndc_x * aspect * tan_half * rz + ndc_y * tan_half * uz + fz
    rdx, rdy, rdz = _norm3(rdx, rdy, rdz)

    if abs(rdz) < 1e-6:
        return None, None
    t = -ez / rdz
    if t < 0:
        return None, None
    return ex + t * rdx, ey + t * rdy

# ===========================================================================
# Enemy helpers
# ===========================================================================
def _zombie_defaults(ztype="regular"):
    """Return dict of zombie properties based on type."""
    if ztype == "regular":
        return {"hp": 1, "speed": 0.6,  "color": (0.1, 0.6, 0.1), "scale": 1.0,
                "scale_dir": 1, "cash": 10, "damage": 1, "type": "regular"}
    elif ztype == "mutant":
        return {"hp": 2, "speed": 1.2,  "color": (0.6, 0.1, 0.8), "scale": 1.1,
                "scale_dir": 1, "cash": 20, "damage": 1, "type": "mutant"}
    elif ztype == "boss":
        return {"hp": 25, "speed": 0.4, "color": (0.9, 0.05, 0.05), "scale": 3.0,
                "scale_dir": 1, "cash": 200, "damage": 2, "type": "boss"}
    # fallback
    return {"hp": 1, "speed": 0.6, "color": (0.1, 0.6, 0.1), "scale": 1.0,
            "scale_dir": 1, "cash": 10, "damage": 1, "type": "regular"}

def spawn_enemy(ztype="regular"):
    """Spawn a single zombie at a random edge position."""
    props = _zombie_defaults(ztype)
    # Spawn at a random map edge
    edge = random.randint(0, 3)
    margin = 50
    if edge == 0:   # top
        ex = random.uniform(-GRID_LENGTH + margin, GRID_LENGTH - margin)
        ey = GRID_LENGTH - margin
    elif edge == 1: # bottom
        ex = random.uniform(-GRID_LENGTH + margin, GRID_LENGTH - margin)
        ey = -GRID_LENGTH + margin
    elif edge == 2: # left
        ex = -GRID_LENGTH + margin
        ey = random.uniform(-GRID_LENGTH + margin, GRID_LENGTH - margin)
    else:           # right
        ex = GRID_LENGTH - margin
        ey = random.uniform(-GRID_LENGTH + margin, GRID_LENGTH - margin)
    props['x'] = ex
    props['y'] = ey
    props['base_scale'] = props['scale']
    enemies.append(props)

def start_wave(wave_num):
    """Populate enemies for the given wave number."""
    global enemies, wave_active, wave_zombies_killed, boss_alive, current_wave
    global wave_clear_pending
    enemies = []
    wave_zombies_killed = 0
    wave_active = True
    wave_clear_pending = False
    current_wave = wave_num
    boss_alive = False

    if wave_num == 1:
        for _ in range(wave_zombie_count[0]):
            spawn_enemy("regular")
    elif wave_num == 2:
        for _ in range(wave_zombie_count[1] // 2):
            spawn_enemy("regular")
        for _ in range(wave_zombie_count[1] // 2):
            spawn_enemy("mutant")
    elif wave_num == 3:
        # Minions + boss
        for _ in range(wave_zombie_count[2] - 1):
            spawn_enemy("mutant")
        spawn_enemy("boss")
        boss_alive = True

# ===========================================================================
# Drawing helpers
# ===========================================================================
def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18):
    # Disable depth test: glRasterPos silently fails GL_LESS when
    # another 2D quad already wrote the same depth value to the buffer.
    glDisable(GL_DEPTH_TEST)
    glColor3f(1, 1, 1)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glRasterPos2f(x, y)
    for ch in str(text):
        glutBitmapCharacter(font, ord(ch))
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)

def draw_colored_text(x, y, text, r, g, b, font=GLUT_BITMAP_HELVETICA_18):
    glDisable(GL_DEPTH_TEST)
    glColor3f(r, g, b)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glRasterPos2f(x, y)
    for ch in str(text):
        glutBitmapCharacter(font, ord(ch))
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)

# ---- Grid & Boundaries ----------------------------------------------------
def draw_grid():
    num_cells = 12
    step = (GRID_LENGTH * 2.0) / num_cells

    glBegin(GL_QUADS)
    for i in range(num_cells):
        for j in range(num_cells):
            if (i + j) % 2 == 0:
                glColor3f(0.25, 0.25, 0.25)        # dark grey
            else:
                glColor3f(0.18, 0.18, 0.18)        # slightly darker
            x0 = -GRID_LENGTH + i * step
            x1 = x0 + step
            y0 = -GRID_LENGTH + j * step
            y1 = y0 + step
            glVertex3f(x0, y1, 0)
            glVertex3f(x1, y1, 0)
            glVertex3f(x1, y0, 0)
            glVertex3f(x0, y0, 0)
    glEnd()

    # Boundary walls
    h = 50
    glBegin(GL_QUADS)
    glColor3f(0.0, 0.7, 0.7)
    glVertex3f(-GRID_LENGTH, GRID_LENGTH, h)
    glVertex3f( GRID_LENGTH, GRID_LENGTH, h)
    glVertex3f( GRID_LENGTH, GRID_LENGTH, 0)
    glVertex3f(-GRID_LENGTH, GRID_LENGTH, 0)

    glColor3f(0.4, 0.8, 0.4)
    glVertex3f( GRID_LENGTH, -GRID_LENGTH, h)
    glVertex3f(-GRID_LENGTH, -GRID_LENGTH, h)
    glVertex3f(-GRID_LENGTH, -GRID_LENGTH, 0)
    glVertex3f( GRID_LENGTH, -GRID_LENGTH, 0)

    glColor3f(0.0, 0.0, 0.8)
    glVertex3f(-GRID_LENGTH, -GRID_LENGTH, h)
    glVertex3f(-GRID_LENGTH,  GRID_LENGTH, h)
    glVertex3f(-GRID_LENGTH,  GRID_LENGTH, 0)
    glVertex3f(-GRID_LENGTH, -GRID_LENGTH, 0)

    glColor3f(0.8, 0.8, 0.8)
    glVertex3f(GRID_LENGTH,  GRID_LENGTH, h)
    glVertex3f(GRID_LENGTH, -GRID_LENGTH, h)
    glVertex3f(GRID_LENGTH, -GRID_LENGTH, 0)
    glVertex3f(GRID_LENGTH,  GRID_LENGTH, 0)
    glEnd()

# ---- Player ---------------------------------------------------------------
def draw_player():
    glPushMatrix()
    glTranslatef(player_pos[0], player_pos[1], 0)

    if game_over:
        glRotatef(90, 1, 0, 0)
        glTranslatef(0, -20, -20)

    glRotatef(gun_angle - 90, 0, 0, 1)

    # Legs (blue cylinders)
    glColor3f(0.0, 0.0, 0.7)
    glPushMatrix()
    glTranslatef(-12, 0, 0)
    gluCylinder(gluNewQuadric(), 7, 5, 25, 10, 10)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(12, 0, 0)
    gluCylinder(gluNewQuadric(), 7, 5, 25, 10, 10)
    glPopMatrix()

    # Torso (green cube, scaled)
    glPushMatrix()
    glColor3f(0.2, 0.5, 0.2)
    glTranslatef(0, 0, 45)
    glScalef(0.8, 0.5, 1.0)
    glutSolidCube(50)
    glPopMatrix()

    # Backpack (small brown cube on back)
    glPushMatrix()
    glColor3f(0.45, 0.3, 0.15)
    glTranslatef(0, -18, 45)
    glScalef(0.5, 0.3, 0.6)
    glutSolidCube(40)
    glPopMatrix()

    # Shoulders (small spheres)
    glColor3f(0.2, 0.5, 0.2)
    glPushMatrix()
    glTranslatef(-22, 0, 58)
    gluSphere(gluNewQuadric(), 8, 8, 8)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(22, 0, 58)
    gluSphere(gluNewQuadric(), 8, 8, 8)
    glPopMatrix()

    # Arms (skin-colored cylinders)
    glColor3f(0.85, 0.7, 0.55)
    glPushMatrix()
    glTranslatef(-25, 0, 50)
    glRotatef(-90, 1, 0, 0)
    gluCylinder(gluNewQuadric(), 6, 6, 35, 10, 10)
    glPopMatrix()
    glPushMatrix()
    glTranslatef(25, 0, 50)
    glRotatef(-90, 1, 0, 0)
    gluCylinder(gluNewQuadric(), 6, 6, 35, 10, 10)
    glPopMatrix()

    # Head (dark sphere)
    glPushMatrix()
    glColor3f(0.85, 0.7, 0.55)
    glTranslatef(0, 0, 78)
    gluSphere(gluNewQuadric(), 14, 10, 10)
    glPopMatrix()

    # Gun barrel (different color per weapon)
    cr, cg, cb = weapon_colors[current_weapon]
    glColor3f(cr, cg, cb)
    glPushMatrix()
    glTranslatef(0, 0, 50)
    glRotatef(-90, 1, 0, 0)
    if current_weapon == 0:       # Pistol — thin short barrel
        gluCylinder(gluNewQuadric(), 5, 2, 50, 10, 10)
    elif current_weapon == 1:     # Machine Gun — thicker longer barrel
        gluCylinder(gluNewQuadric(), 7, 4, 75, 10, 10)
    elif current_weapon == 2:     # Shotgun — fat short barrel
        gluCylinder(gluNewQuadric(), 10, 8, 55, 10, 10)
    glPopMatrix()

    # Extra visual for Machine Gun: second barrel
    if current_weapon == 1:
        glColor3f(0.15, 0.15, 0.6)
        glPushMatrix()
        glTranslatef(8, 0, 50)
        glRotatef(-90, 1, 0, 0)
        gluCylinder(gluNewQuadric(), 4, 2, 70, 10, 10)
        glPopMatrix()

    # Extra visual for Shotgun: wide muzzle cube
    if current_weapon == 2:
        glColor3f(0.6, 0.3, 0.05)
        glPushMatrix()
        glTranslatef(0, 0, 52)
        glRotatef(-90, 1, 0, 0)
        glTranslatef(0, 0, 55)
        glScalef(2.0, 1.0, 0.3)
        glutSolidCube(12)
        glPopMatrix()

    glPopMatrix()

# ---- Zombies --------------------------------------------------------------
def draw_enemies():
    for e in enemies:
        glPushMatrix()
        glTranslatef(e['x'], e['y'], 0)
        s = e['scale']
        r, g, b = e['color']

        if e['type'] == 'boss':
            # Boss: huge body
            glColor3f(r, g, b)
            glPushMatrix()
            glTranslatef(0, 0, 30 * s)
            gluSphere(gluNewQuadric(), 30 * s, 12, 12)
            glPopMatrix()

            # Boss chest cube
            glColor3f(r * 0.7, g * 0.7, b * 0.7)
            glPushMatrix()
            glTranslatef(0, 0, 60 * s)
            glScalef(s, s * 0.6, s * 0.8)
            glutSolidCube(40)
            glPopMatrix()

            # Boss head
            glColor3f(0.2, 0.0, 0.0)
            glPushMatrix()
            glTranslatef(0, 0, 85 * s)
            gluSphere(gluNewQuadric(), 15 * s, 10, 10)
            glPopMatrix()

            # Boss arms
            glColor3f(r, g, b)
            glPushMatrix()
            glTranslatef(-25 * s, 0, 55 * s)
            glRotatef(-90, 1, 0, 0)
            gluCylinder(gluNewQuadric(), 8 * s, 6 * s, 40 * s, 10, 10)
            glPopMatrix()
            glPushMatrix()
            glTranslatef(25 * s, 0, 55 * s)
            glRotatef(-90, 1, 0, 0)
            gluCylinder(gluNewQuadric(), 8 * s, 6 * s, 40 * s, 10, 10)
            glPopMatrix()

            # HP bar above boss
            hp_frac = e['hp'] / 25.0
            bar_w = 60 * s
            glColor3f(1.0, 0.0, 0.0)
            glPushMatrix()
            glTranslatef(0, 0, 100 * s + 10)
            glScalef(bar_w * hp_frac, 4, 2)
            glutSolidCube(1)
            glPopMatrix()
        else:
            # Regular / Mutant zombie: humanoid shape
            # Legs
            glColor3f(r * 0.6, g * 0.6, b * 0.6)
            glPushMatrix()
            glTranslatef(-8 * s, 0, 0)
            gluCylinder(gluNewQuadric(), 5 * s, 4 * s, 20 * s, 8, 8)
            glPopMatrix()
            glPushMatrix()
            glTranslatef(8 * s, 0, 0)
            gluCylinder(gluNewQuadric(), 5 * s, 4 * s, 20 * s, 8, 8)
            glPopMatrix()

            # Body sphere
            glColor3f(r, g, b)
            glPushMatrix()
            glTranslatef(0, 0, 30 * s)
            gluSphere(gluNewQuadric(), 15 * s, 10, 10)
            glPopMatrix()

            # Head
            glColor3f(r * 0.5, g * 0.5, b * 0.5)
            glPushMatrix()
            glTranslatef(0, 0, 50 * s)
            gluSphere(gluNewQuadric(), 8 * s, 8, 8)
            glPopMatrix()

            # Arms reaching forward
            glColor3f(r, g, b)
            glPushMatrix()
            glTranslatef(-15 * s, 0, 35 * s)
            glRotatef(-70, 1, 0, 0)
            gluCylinder(gluNewQuadric(), 4 * s, 3 * s, 25 * s, 8, 8)
            glPopMatrix()
            glPushMatrix()
            glTranslatef(15 * s, 0, 35 * s)
            glRotatef(-70, 1, 0, 0)
            gluCylinder(gluNewQuadric(), 4 * s, 3 * s, 25 * s, 8, 8)
            glPopMatrix()

        glPopMatrix()

# ---- Bullets ---------------------------------------------------------------
def draw_bullets():
    for b in bullets:
        glPushMatrix()
        glTranslatef(b['x'], b['y'], 50)
        glColor3f(1.0, 1.0, 0.0)
        glutSolidCube(8)
        glPopMatrix()

# ---- Cash drops ------------------------------------------------------------
def draw_cash_drops():
    for c in cash_drops:
        glPushMatrix()
        glTranslatef(c['x'], c['y'], 10)
        # Spinning golden cube
        glRotatef(c['spin'], 0, 0, 1)
        glColor3f(1.0, 0.85, 0.0)
        glutSolidCube(15)
        # Inner smaller green cube
        glColor3f(0.0, 0.8, 0.0)
        glutSolidCube(8)
        glPopMatrix()

# ---- Cannon drawing -------------------------------------------------------
def draw_cannons():
    for c in cannons:
        glPushMatrix()
        glTranslatef(c['x'], c['y'], 0)

        # Base platform (dark grey cube)
        glColor3f(0.25, 0.25, 0.25)
        glPushMatrix()
        glTranslatef(0, 0, 8)
        glScalef(1.5, 1.5, 0.5)
        glutSolidCube(20)
        glPopMatrix()

        # Rotating turret head
        glPushMatrix()
        glRotatef(c['angle'], 0, 0, 1)

        # Turret body (sphere)
        glColor3f(0.4, 0.4, 0.45)
        glTranslatef(0, 0, 18)
        gluSphere(gluNewQuadric(), 12, 10, 10)

        # Barrel (cylinder pointing forward)
        glColor3f(0.3, 0.3, 0.35)
        glRotatef(-90, 0, 0, 1)
        glRotatef(-90, 1, 0, 0)
        gluCylinder(gluNewQuadric(), 5, 3, 35, 8, 8)

        glPopMatrix()
        glPopMatrix()

def draw_cannon_balls():
    for cb in cannon_balls:
        glPushMatrix()
        glTranslatef(cb['x'], cb['y'], 18)
        glColor3f(1.0, 0.5, 0.0)
        gluSphere(gluNewQuadric(), 6, 8, 8)
        glPopMatrix()

def draw_splash_effects():
    """Draw expanding ring on the ground for cannon splash hits."""
    for s in splash_effects:
        glPushMatrix()
        glTranslatef(s['x'], s['y'], 1)
        glColor4f(1.0, 0.4, 0.0, s['alpha'])
        # Draw a circle using GL_LINE_LOOP
        glLineWidth(2.0)
        glBegin(GL_LINE_LOOP)
        segments = 24
        for i in range(segments):
            theta = 2.0 * math.pi * i / segments
            glVertex3f(math.cos(theta) * s['radius'],
                       math.sin(theta) * s['radius'], 0)
        glEnd()
        glLineWidth(1.0)
        glPopMatrix()

# ---- Crosshair ------------------------------------------------------------
def draw_crosshair():
    if camera_mode == 1:
        # First-person: draw a 3D crosshair at bullet height along the aim direction
        # so it visually aligns with where bullets actually hit.
        rad = math.radians(gun_angle)
        dist = 300.0  # distance ahead of player to place crosshair
        cx3d = player_pos[0] + math.cos(rad) * dist
        cy3d = player_pos[1] + math.sin(rad) * dist
        cz3d = 50.0   # bullet travel height

        # Crosshair arms oriented to face the camera:
        # horizontal = perpendicular to aim in XY plane, vertical = Z axis
        perp_x = -math.sin(rad)
        perp_y =  math.cos(rad)
        arm = 10.0

        glDisable(GL_DEPTH_TEST)
        glColor3f(1.0, 0.2, 0.2)
        glLineWidth(2.0)
        glBegin(GL_LINES)
        # Horizontal arm
        glVertex3f(cx3d - arm * perp_x, cy3d - arm * perp_y, cz3d)
        glVertex3f(cx3d + arm * perp_x, cy3d + arm * perp_y, cz3d)
        # Vertical arm
        glVertex3f(cx3d, cy3d, cz3d - arm)
        glVertex3f(cx3d, cy3d, cz3d + arm)
        glEnd()
        glLineWidth(1.0)
        glEnable(GL_DEPTH_TEST)
        return

    # Other modes: 2D screen-space crosshair at mouse position
    cx = mouse_x
    cy = WINDOW_HEIGHT - mouse_y

    glDisable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glColor3f(1.0, 0.2, 0.2)
    size = 14
    glBegin(GL_LINES)
    glVertex2f(cx - size, cy)
    glVertex2f(cx + size, cy)
    glVertex2f(cx, cy - size)
    glVertex2f(cx, cy + size)
    glEnd()

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)

# ---- HP bar (screen-space) ------------------------------------------------
def draw_hp_bar():
    """Draw a filled HP bar at top-left of screen using orthographic overlay."""
    glDisable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    bar_x = 10
    bar_y = 755
    bar_w = 200
    bar_h = 16
    hp_frac = max(0, player_hp) / player_max_hp

    # Background (dark red)
    glColor3f(0.3, 0.0, 0.0)
    glBegin(GL_QUADS)
    glVertex2f(bar_x, bar_y)
    glVertex2f(bar_x + bar_w, bar_y)
    glVertex2f(bar_x + bar_w, bar_y + bar_h)
    glVertex2f(bar_x, bar_y + bar_h)
    glEnd()

    # Foreground (green -> red gradient)
    glColor3f(1.0 - hp_frac, hp_frac, 0.0)
    glBegin(GL_QUADS)
    glVertex2f(bar_x, bar_y)
    glVertex2f(bar_x + bar_w * hp_frac, bar_y)
    glVertex2f(bar_x + bar_w * hp_frac, bar_y + bar_h)
    glVertex2f(bar_x, bar_y + bar_h)
    glEnd()

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)

# ---- Shop Overlay ----------------------------------------------------------
def draw_shop():
    """Full-screen orthographic 2D shop overlay between waves."""
    # Must disable depth test for all 2D shop rendering.
    # Panel quads write depth=0.5; text glRasterPos at same z would
    # fail GL_LESS (0.5 < 0.5 is false) making all text invisible.
    glDisable(GL_DEPTH_TEST)
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_WIDTH, 0, WINDOW_HEIGHT)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    # Background panel — clearly visible dark blue-grey
    glColor3f(0.08, 0.10, 0.18)
    glBegin(GL_QUADS)
    glVertex2f(0, 0)
    glVertex2f(WINDOW_WIDTH, 0)
    glVertex2f(WINDOW_WIDTH, WINDOW_HEIGHT)
    glVertex2f(0, WINDOW_HEIGHT)
    glEnd()

    # Inner shop panel (slightly lighter)
    glColor3f(0.12, 0.14, 0.24)
    glBegin(GL_QUADS)
    glVertex2f(140, 90)
    glVertex2f(860, 90)
    glVertex2f(860, 710)
    glVertex2f(140, 710)
    glEnd()

    # Gold border
    glColor3f(0.9, 0.75, 0.0)
    glLineWidth(2.0)
    glBegin(GL_LINES)
    glVertex2f(140, 90);  glVertex2f(860, 90)
    glVertex2f(860, 90);  glVertex2f(860, 710)
    glVertex2f(860, 710); glVertex2f(140, 710)
    glVertex2f(140, 710); glVertex2f(140, 90)
    glEnd()
    glLineWidth(1.0)

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    # depth test remains OFF — draw_colored_text will manage its own toggle

    # Title
    draw_colored_text(340, 660, "=== ITEM SHOP ===", 1.0, 0.85, 0.0, GLUT_BITMAP_HELVETICA_18)
    draw_colored_text(380, 620, f"Your Cash: ${money}", 0.0, 1.0, 0.3, GLUT_BITMAP_HELVETICA_18)

    # Items
    y_start = 560
    for idx, item in enumerate(SHOP_ITEMS):
        iy = y_start - idx * 70
        already_owned = False
        if idx == 1 and weapons_unlocked[1]:
            already_owned = True
        if idx == 2 and weapons_unlocked[2]:
            already_owned = True
        # Cannon (idx 3) is stackable — never "owned"

        if already_owned:
            draw_colored_text(180, iy, f"[{item['key']}]  {item['name']}", 0.5, 0.5, 0.5, GLUT_BITMAP_HELVETICA_18)
            draw_colored_text(650, iy, "OWNED", 0.3, 0.9, 0.3, GLUT_BITMAP_HELVETICA_18)
        else:
            can_afford = money >= item['cost']
            tc = (1.0, 1.0, 1.0) if can_afford else (0.6, 0.35, 0.35)
            draw_colored_text(180, iy, f"[{item['key']}]  {item['name']}", *tc, GLUT_BITMAP_HELVETICA_18)
            price_label = f"${item['cost']}"
            if idx == 3:
                price_label += f"  (owned: {cannon_inventory})"
            draw_colored_text(650, iy, price_label, 1.0, 0.85, 0.0, GLUT_BITMAP_HELVETICA_18)

    # Divider line label
    draw_colored_text(180, 240, "─" * 60, 0.4, 0.4, 0.6, GLUT_BITMAP_HELVETICA_18)

    # Instructions
    next_wave = current_wave + 1
    if next_wave <= 3:
        draw_colored_text(260, 200, f"Press  SPACE  to begin Wave {next_wave}  >>>>", 0.6, 0.8, 1.0, GLUT_BITMAP_HELVETICA_18)
    else:
        draw_colored_text(280, 200, "All waves cleared!  Press R to play again.", 0.5, 1.0, 0.5, GLUT_BITMAP_HELVETICA_18)

    draw_colored_text(180, 180, f"HP: {player_hp} / {player_max_hp}     Current Weapon: {weapon_names[current_weapon]}", 0.8, 0.85, 0.8, GLUT_BITMAP_HELVETICA_18)
    draw_colored_text(180, 150, f"Score: {score}     Total Cash: ${money}     Cannons: {cannon_inventory}", 0.7, 0.9, 0.7, GLUT_BITMAP_HELVETICA_18)
    draw_colored_text(180, 120, "Press F during gameplay to place a cannon", 0.5, 0.7, 1.0, GLUT_BITMAP_HELVETICA_18)

# ===========================================================================
# Firing
# ===========================================================================
def _update_gun_angle_from_mouse(win_x, win_y):
    global gun_angle, manual_gun_angle
    wx, wy = mouse_world_pos(win_x, win_y)
    if wx is None:
        return
    dx = wx - player_pos[0]
    dy = wy - player_pos[1]
    if abs(dx) < 1e-4 and abs(dy) < 1e-4:
        return
    angle = math.degrees(math.atan2(dy, dx))
    if angle < 0:
        angle += 360.0
    gun_angle = angle
    manual_gun_angle = angle

def fire_bullet(angle=None):
    if angle is None:
        angle = gun_angle
    rad = math.radians(angle)
    bx = player_pos[0] + math.cos(rad) * 40
    by = player_pos[1] + math.sin(rad) * 40
    bullets.append({'x': bx, 'y': by, 'angle': angle})

def fire_weapon(win_x, win_y):
    """Fire based on current weapon type."""
    global last_fire_time
    now = time.time()
    if now - last_fire_time < weapon_fire_delay[current_weapon]:
        return      # rate-limited
    last_fire_time = now

    # In first-person mode, fire straight ahead (gun_angle is already set by mouse look)
    if not cheat_mode and camera_mode != 1:
        _update_gun_angle_from_mouse(win_x, win_y)

    if current_weapon == 0:    # Pistol
        fire_bullet(gun_angle)
    elif current_weapon == 1:  # Machine Gun
        fire_bullet(gun_angle)
    elif current_weapon == 2:  # Shotgun – 3 bullets in a spread
        spread = 12.0
        fire_bullet(gun_angle - spread)
        fire_bullet(gun_angle)
        fire_bullet(gun_angle + spread)

    print(f"Fired {weapon_names[current_weapon]}!")

# ===========================================================================
# Input callbacks
# ===========================================================================
def keyboardListener(key, x, y):
    global player_pos, gun_angle, manual_gun_angle, cheat_mode, cheat_vision
    global game_over, game_won, player_hp, score, money, current_weapon
    global player_max_hp, weapons_unlocked, current_wave, wave_active
    global bullets, cash_drops, enemies, wave_zombies_killed, player_speed
    global wave_clear_pending, keys_held, camera_mode, prev_camera_mode
    global cannons, cannon_balls, cannon_inventory, splash_effects

    # Track held keys for smooth movement polled in idle()
    keys_held.add(key)

    # ---- Restart ----
    if key == b'r' or key == b'R':
        game_over    = False
        game_won     = False
        player_hp    = 5
        player_max_hp = 5
        score        = 0
        money        = 0
        player_pos   = [0.0, 0.0, 0.0]
        gun_angle    = 90.0
        manual_gun_angle = 90.0
        bullets      = []
        cash_drops   = []
        cannons      = []
        cannon_balls = []
        cannon_inventory = 0
        splash_effects = []
        current_weapon = 0
        weapons_unlocked = [True, False, False]
        cheat_mode   = False
        cheat_vision = False
        current_wave = 1
        wave_active  = True
        wave_clear_pending = False
        player_speed = 10.0
        wave_zombies_killed = 0
        keys_held.clear()
        start_wave(1)
        return

    # ---- Wave-clear collect phase: press SPACE to open shop ----
    if wave_clear_pending:
        if key == b' ':
            wave_clear_pending = False
            wave_active = False
        return  # all other input blocked; movement via keys_held in idle()

    # ---- Shop keys (only when shop is open) ----
    if not wave_active and not game_over and not game_won:
        if key == b' ':    # SPACE to start next wave
            next_wave = current_wave + 1
            if next_wave <= 3:
                start_wave(next_wave)
            return
        if key == b'1':    # Buy HP upgrade
            cost = SHOP_ITEMS[0]['cost']
            if money >= cost:
                money -= cost
                player_max_hp += 3
                player_hp = min(player_hp + 3, player_max_hp)
                print(f"Bought HP upgrade! Max HP now {player_max_hp}")
        if key == b'2':    # Buy Machine Gun
            if not weapons_unlocked[1]:
                cost = SHOP_ITEMS[1]['cost']
                if money >= cost:
                    money -= cost
                    weapons_unlocked[1] = True
                    current_weapon = 1
                    print("Bought Machine Gun!")
        if key == b'3':    # Buy Shotgun
            if not weapons_unlocked[2]:
                cost = SHOP_ITEMS[2]['cost']
                if money >= cost:
                    money -= cost
                    weapons_unlocked[2] = True
                    current_weapon = 2
                    print("Bought Shotgun!")
        if key == b'4':    # Buy Cannon
            cost = SHOP_ITEMS[3]['cost']
            if money >= cost:
                money -= cost
                cannon_inventory += 1
                print(f"Bought Cannon! Inventory: {cannon_inventory}")
        return

    if game_over or game_won:
        return

    # WASD movement is handled in idle() via keys_held — no per-key action here

    # ---- Weapon switch (Q/E during gameplay) ----
    if key == b'q' or key == b'Q':
        # Cycle weapon backward
        for i in range(3):
            nw = (current_weapon - 1) % 3
            if weapons_unlocked[nw]:
                current_weapon = nw
                break
            current_weapon = nw
    if key == b'e' or key == b'E':
        # Cycle weapon forward
        for i in range(3):
            nw = (current_weapon + 1) % 3
            if weapons_unlocked[nw]:
                current_weapon = nw
                break
            current_weapon = nw

    # ---- Cheat ----
    if key == b'c' or key == b'C':
        cheat_mode = not cheat_mode
        if not cheat_mode:
            gun_angle = manual_gun_angle
            cheat_vision = False
    if key == b'v' or key == b'V':
        if cheat_mode:
            cheat_vision = not cheat_vision

    # ---- Display Toggle ----
    if key == b't' or key == b'T':
        if camera_mode != 2:
            prev_camera_mode = camera_mode
            camera_mode = 2
        else:
            camera_mode = prev_camera_mode

    # ---- Place Cannon ----
    if key == b'f' or key == b'F':
        if cannon_inventory > 0:
            cannon_inventory -= 1
            cannons.append({
                'x': player_pos[0],
                'y': player_pos[1],
                'angle': 0.0,
                'last_fire': 0.0
            })
            print(f"Cannon placed at ({player_pos[0]:.0f}, {player_pos[1]:.0f})! Remaining: {cannon_inventory}")
        else:
            print("No cannons in inventory! Buy from shop.")

def specialKeyListener(key, x, y):
    global camera_height, camera_angle
    if key == GLUT_KEY_UP:
        camera_height += 10.0
    if key == GLUT_KEY_DOWN:
        camera_height -= 10.0
        if camera_height < 10.0:
            camera_height = 10.0
    if key == GLUT_KEY_LEFT:
        camera_angle += 5.0
        if camera_angle >= 360:
            camera_angle -= 360
    if key == GLUT_KEY_RIGHT:
        camera_angle -= 5.0
        if camera_angle < 0:
            camera_angle += 360

def keyboardUpListener(key, x, y):
    """Remove key from held-set on release for smooth movement tracking."""
    keys_held.discard(key)

def _fp_mouse_look(x, y):
    """Rotate manual_gun_angle by how far the mouse is from screen center, then warp back."""
    global fp_ignore_warp, manual_gun_angle, gun_angle
    cx = WINDOW_WIDTH // 2
    dx = x - cx
    if dx == 0:
        return
    manual_gun_angle -= dx * FP_MOUSE_SENSITIVITY
    manual_gun_angle %= 360.0
    if not cheat_mode:
        gun_angle = manual_gun_angle
    # Warp cursor back to center; set flag so the resulting motion event is ignored
    fp_ignore_warp = True
    glutWarpPointer(cx, WINDOW_HEIGHT // 2)

def _handle_motion(x, y):
    """Shared logic for both motionListener and passiveMotionListener."""
    global mouse_x, mouse_y, fp_ignore_warp
    # In first-person mode, ignore the motion event triggered by glutWarpPointer
    if camera_mode == 1 and fp_ignore_warp:
        fp_ignore_warp = False
        # Keep mouse coords at center for crosshair
        mouse_x = WINDOW_WIDTH // 2
        mouse_y = WINDOW_HEIGHT // 2
        return
    if camera_mode == 1:
        # Keep mouse coords at center for crosshair / HUD
        mouse_x = WINDOW_WIDTH // 2
        mouse_y = WINDOW_HEIGHT // 2
    else:
        mouse_x = x
        mouse_y = y
    if game_over or not wave_active or cheat_mode:
        return
    if camera_mode == 1:
        _fp_mouse_look(x, y)
    else:
        _update_gun_angle_from_mouse(x, y)
    glutPostRedisplay()

def motionListener(x, y):
    _handle_motion(x, y)

def passiveMotionListener(x, y):
    _handle_motion(x, y)

def mouseListener(button, state, x, y):
    global camera_mode, camera_zoom
    if game_over or not wave_active:
        return
    if button == GLUT_LEFT_BUTTON and state == GLUT_DOWN:
        fire_weapon(x, y)
    if button == GLUT_RIGHT_BUTTON and state == GLUT_DOWN:
        entering_fp = camera_mode != 1
        camera_mode = 1 if camera_mode == 3 else 3
        if entering_fp and camera_mode == 1:
            # Warp cursor to center when entering first-person mode
            fp_ignore_warp = True
            glutWarpPointer(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)

    # Legacy scroll wheel support (some GLUT ports map wheel to btn 3 and 4)
    if button == 3 and state == GLUT_DOWN:
        camera_zoom = max(0.3, camera_zoom - 0.1)
    if button == 4 and state == GLUT_DOWN:
        camera_zoom = min(3.0, camera_zoom + 0.1)

def mouseWheelListener(wheel, direction, x, y):
    """Modern freeglut scroll wheel listener."""
    global camera_zoom
    if game_over or not wave_active:
        return
    if direction > 0:
        camera_zoom = max(0.3, camera_zoom - 0.1)
    else:
        camera_zoom = min(3.0, camera_zoom + 0.1)
    glutPostRedisplay()

# ===========================================================================
# Camera
# ===========================================================================
def setupCamera():
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(120, 1.25, 0.1, 3000)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

    if camera_mode == 3:
        cam_dist = 800.0 * camera_zoom
        rad = math.radians(camera_angle)
        cx = math.cos(rad) * cam_dist
        cy = math.sin(rad) * cam_dist
        gluLookAt(cx, cy, camera_height * camera_zoom,
                  0, 0, 0,
                  0, 0, 1)
    elif camera_mode == 2:
        rad = math.radians(camera_angle)
        up_x = math.cos(rad)
        up_y = math.sin(rad)
        gluLookAt(0.0, 0.0, 1000.0 * camera_zoom,
                  0.0, 0.0, 0.0,
                  up_x, up_y, 0.0)
    else:
        if cheat_mode and cheat_vision:
            look_angle = gun_angle
        else:
            look_angle = manual_gun_angle
        rad = math.radians(look_angle)
        cx = player_pos[0] - math.cos(rad) * 150
        cy = player_pos[1] - math.sin(rad) * 150
        cz = 150.0 + (camera_height - 500.0)
        tx = player_pos[0] + math.cos(rad) * 100
        ty = player_pos[1] + math.sin(rad) * 100
        tz = cz
        gluLookAt(cx, cy, cz,
                  tx, ty, tz,
                  0, 0, 1)

# ===========================================================================
# Game loop (idle)
# ===========================================================================
def idle():
    global game_over, game_won, player_hp, score, gun_angle, money
    global frame_count, last_time
    global wave_active, wave_zombies_killed, boss_alive, current_wave
    global wave_clear_pending, splash_effects

    current_time = time.time()
    if current_time - last_time < (1.0 / 60.0):
        return
    last_time = current_time

    if game_over or game_won:
        glutPostRedisplay()
        return

    if not wave_active and not wave_clear_pending:
        glutPostRedisplay()
        return

    frame_count += 1

    # ---- Pulse zombie scale (breathing effect) ----
    for e in enemies:
        if e['type'] != 'boss':
            e['scale'] += e['scale_dir'] * 0.005
            upper = e['base_scale'] * 1.15
            lower = e['base_scale'] * 0.85
            if e['scale'] > upper:
                e['scale'] = upper
                e['scale_dir'] = -1
            elif e['scale'] < lower:
                e['scale'] = lower
                e['scale_dir'] = 1

    # ---- Move enemies toward player ----
    for e in list(enemies):
        dx = player_pos[0] - e['x']
        dy = player_pos[1] - e['y']
        dist = math.hypot(dx, dy)
        
        hit_range = 25 * e['scale'] if e['type'] != 'boss' else 40 * e['scale']

        # Move only if not already overlapping entirely (prevents stacking perfectly inside player)
        if dist > hit_range * 0.8:
            e['x'] += (dx / dist) * e['speed']
            e['y'] += (dy / dist) * e['speed']

        # Collision / Damage with player
        if dist < hit_range:
            if current_time - e.get('last_attack_time', 0.0) >= 1.0:
                player_hp -= e['damage']
                print(f"Player hit! HP: {player_hp}")
                e['last_attack_time'] = current_time
                if player_hp <= 0:
                    game_over = True
                    print("GAME OVER!")

    # ---- Move bullets ----
    bullet_speed = 18.0
    i = 0
    while i < len(bullets):
        b = bullets[i]
        rad = math.radians(b['angle'])
        b['x'] += math.cos(rad) * bullet_speed
        b['y'] += math.sin(rad) * bullet_speed

        hit = False
        for e in list(enemies):
            hit_r = 20 * e['scale'] if e['type'] != 'boss' else 35 * e['scale']
            dist = math.hypot(b['x'] - e['x'], b['y'] - e['y'])
            if dist < hit_r:
                e['hp'] -= 1
                if e['hp'] <= 0:
                    # Enemy killed
                    score += 1
                    wave_zombies_killed += 1
                    # Drop cash — store spawn time for 5-second expiry
                    cash_drops.append({
                        'x': e['x'],
                        'y': e['y'],
                        'value': e['cash'],
                        'spin': 0.0,
                        'spawn_time': current_time
                    })
                    if e['type'] == 'boss':
                        boss_alive = False
                    if e in enemies:
                        enemies.remove(e)
                hit = True
                break

        if hit:
            bullets.pop(i)
            continue

        # Out of bounds
        if abs(b['x']) > GRID_LENGTH or abs(b['y']) > GRID_LENGTH:
            bullets.pop(i)
            continue

        i += 1

    # ---- Cash pickup (player proximity / cheat auto-collect) + 5 s expiry ----
    j = 0
    while j < len(cash_drops):
        c = cash_drops[j]
        c['spin'] += 3.0   # Rotate the cash drop
        if c['spin'] >= 360:
            c['spin'] -= 360

        # Expire after 5 seconds
        if current_time - c.get('spawn_time', current_time) > 5.0:
            cash_drops.pop(j)
            continue

        dist = math.hypot(c['x'] - player_pos[0], c['y'] - player_pos[1])
        # Cheat mode: auto-collect from anywhere; normal: require proximity
        if cheat_mode or dist < 40:
            money += c['value']
            print(f"Picked up ${c['value']}!  Total: ${money}")
            cash_drops.pop(j)
            continue
        j += 1

    # ---- Cheat mode auto-aim ----
    if cheat_mode:
        old_gun = gun_angle
        gun_angle += 3.0
        if gun_angle >= 360.0:
            gun_angle -= 360.0

        for e in enemies:
            dx = e['x'] - player_pos[0]
            dy = e['y'] - player_pos[1]
            ta = math.degrees(math.atan2(dy, dx))
            if ta < 0:
                ta += 360
            t_angle = ta
            if t_angle < old_gun and old_gun + 3.0 >= 360.0:
                t_angle += 360.0
            if old_gun <= t_angle <= old_gun + 3.0:
                fire_bullet(ta)
                break

    # ---- Camera-relative WASD movement from held keys (smooth + diagonal) ----
    if not game_over and not game_won:
        if camera_mode == 2:
            move_rad = math.radians(camera_angle)
            fwd_x = math.cos(move_rad)
            fwd_y = math.sin(move_rad)
            rgt_x = -math.sin(move_rad)
            rgt_y =  math.cos(move_rad)
        else:
            if camera_mode == 3:
                move_rad = math.radians(camera_angle)
            else:
                move_rad = math.radians(manual_gun_angle)
            fwd_x = -math.cos(move_rad)
            fwd_y = -math.sin(move_rad)
            rgt_x =  math.sin(move_rad)
            rgt_y = -math.cos(move_rad)

        mdx, mdy = 0.0, 0.0
        if b'w' in keys_held: mdx += fwd_x; mdy += fwd_y
        if b's' in keys_held: mdx -= fwd_x; mdy -= fwd_y
        if b'a' in keys_held: mdx += rgt_x; mdy += rgt_y
        if b'd' in keys_held: mdx -= rgt_x; mdy -= rgt_y

        mag = math.hypot(mdx, mdy)
        if mag > 0:
            mdx = mdx / mag * player_speed
            mdy = mdy / mag * player_speed
            nx = player_pos[0] + mdx
            ny = player_pos[1] + mdy
            if -GRID_LENGTH + 20 < nx < GRID_LENGTH - 20:
                player_pos[0] = nx
            if -GRID_LENGTH + 20 < ny < GRID_LENGTH - 20:
                player_pos[1] = ny

    # ---- Cannon AI: auto-target, fire, move cannon balls ----
    for c in cannons:
        # Find nearest enemy in range
        best_e = None
        best_dist = CANNON_RANGE
        for e in enemies:
            d = math.hypot(e['x'] - c['x'], e['y'] - c['y'])
            if d < best_dist:
                best_dist = d
                best_e = e
        # Rotate toward target
        if best_e is not None:
            dx = best_e['x'] - c['x']
            dy = best_e['y'] - c['y']
            target_angle = math.degrees(math.atan2(dy, dx))
            if target_angle < 0:
                target_angle += 360.0
            # Smooth rotation toward target
            diff = target_angle - c['angle']
            if diff > 180: diff -= 360
            if diff < -180: diff += 360
            c['angle'] += max(-3.0, min(3.0, diff))  # rotate max 3 deg/frame
            c['angle'] %= 360.0

            # Fire if aligned and cooldown ready
            if abs(diff) < 10.0 and current_time - c['last_fire'] >= CANNON_FIRE_DELAY:
                c['last_fire'] = current_time
                rad = math.radians(c['angle'])
                cannon_balls.append({
                    'x': c['x'] + math.cos(rad) * 35,
                    'y': c['y'] + math.sin(rad) * 35,
                    'angle': c['angle']
                })

    # ---- Move cannon balls & check hits with area damage ----
    ci = 0
    while ci < len(cannon_balls):
        cb = cannon_balls[ci]
        rad = math.radians(cb['angle'])
        cb['x'] += math.cos(rad) * CANNON_BALL_SPEED
        cb['y'] += math.sin(rad) * CANNON_BALL_SPEED

        hit = False
        for e in list(enemies):
            hit_r = 25 * e['scale'] if e['type'] != 'boss' else 40 * e['scale']
            dist = math.hypot(cb['x'] - e['x'], cb['y'] - e['y'])
            if dist < hit_r + 10:
                # Area damage: hurt all enemies within splash radius
                splash_effects.append({
                    'x': cb['x'], 'y': cb['y'],
                    'radius': 5.0, 'max_radius': CANNON_SPLASH_RADIUS,
                    'alpha': 1.0
                })
                for ae in list(enemies):
                    ae_dist = math.hypot(cb['x'] - ae['x'], cb['y'] - ae['y'])
                    if ae_dist < CANNON_SPLASH_RADIUS:
                        ae['hp'] -= CANNON_DAMAGE
                        if ae['hp'] <= 0:
                            score += 1
                            wave_zombies_killed += 1
                            cash_drops.append({
                                'x': ae['x'], 'y': ae['y'],
                                'value': ae['cash'], 'spin': 0.0,
                                'spawn_time': current_time
                            })
                            if ae['type'] == 'boss':
                                boss_alive = False
                            if ae in enemies:
                                enemies.remove(ae)
                hit = True
                break

        if hit:
            cannon_balls.pop(ci)
            continue

        # Out of bounds
        if abs(cb['x']) > GRID_LENGTH or abs(cb['y']) > GRID_LENGTH:
            cannon_balls.pop(ci)
            continue
        ci += 1

    # ---- Update splash effects ----
    si = 0
    while si < len(splash_effects):
        s = splash_effects[si]
        s['radius'] += 4.0
        s['alpha'] -= 0.04
        if s['alpha'] <= 0 or s['radius'] >= s['max_radius']:
            splash_effects.pop(si)
            continue
        si += 1

    # ---- Check wave completion ----
    if len(enemies) == 0 and not wave_clear_pending:
        if current_wave == 3:
            game_won = True
            print("YOU WIN! All waves cleared!")
        else:
            wave_clear_pending = True
            print(f"Wave {current_wave} cleared! Collect cash then press SPACE for shop.")

    glutPostRedisplay()

# ===========================================================================
# Display
# ===========================================================================
def showScreen():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, WINDOW_WIDTH, WINDOW_HEIGHT)

    if not wave_active and not wave_clear_pending and not game_over and not game_won:
        # Shop phase: draw shop overlay on black background
        draw_shop()
        glutSwapBuffers()
        return

    setupCamera()
    draw_grid()
    draw_cannons()
    draw_cannon_balls()
    draw_splash_effects()
    draw_enemies()
    draw_bullets()
    draw_cash_drops()
    draw_player()

    # HUD
    draw_hp_bar()
    draw_text(220, 760, f"HP: {player_hp}/{player_max_hp}")
    draw_text(10, 730, f"Score: {score}   Cash: ${money}   Cannons: {cannon_inventory}")
    draw_text(10, 700, f"Wave: {current_wave}/3   Weapon: {weapon_names[current_weapon]}")
    draw_text(10, 670, "LMB=Shoot | RMB=Camera | F=Place Cannon | Q/E=Switch | R=Restart")

    if cheat_mode:
        draw_colored_text(10, 640, "CHEAT MODE ON", 1.0, 0.3, 0.3)

    # Wave-clear collect phase banner
    if wave_clear_pending:
        draw_colored_text(250, 430, f"  Wave {current_wave} Complete!  ", 0.2, 1.0, 0.2, GLUT_BITMAP_HELVETICA_18)
        draw_colored_text(170, 395, "Press SPACE to move to new level", 1.0, 1.0, 0.4, GLUT_BITMAP_HELVETICA_18)

    if game_over:
        draw_colored_text(340, 420, "GAME OVER!", 1.0, 0.15, 0.15, GLUT_BITMAP_HELVETICA_18)
        draw_text(330, 380, "Press 'R' to Restart")

    if game_won:
        draw_colored_text(300, 420, "YOU SURVIVED!", 0.2, 1.0, 0.2, GLUT_BITMAP_HELVETICA_18)
        draw_colored_text(270, 380, "All waves cleared! Press R to play again.", 0.8, 1.0, 0.8)

    # Crosshair
    draw_crosshair()

    glutSwapBuffers()

# ===========================================================================
# Entry point
# ===========================================================================
def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(WINDOW_WIDTH, WINDOW_HEIGHT)
    glutInitWindowPosition(0, 0)
    glutCreateWindow(b"Surviving Zombie - GROUP 12")

    glutDisplayFunc(showScreen)
    glutKeyboardFunc(keyboardListener)
    glutKeyboardUpFunc(keyboardUpListener)   # track key releases for smooth movement
    glutSpecialFunc(specialKeyListener)
    glutMouseFunc(mouseListener)
    try:
        glutMouseWheelFunc(mouseWheelListener)
    except:
        pass  # not supported on all PyOpenGL distributions
    glutMotionFunc(motionListener)
    glutPassiveMotionFunc(passiveMotionListener)
    glutIdleFunc(idle)

    glEnable(GL_DEPTH_TEST)

    start_wave(1)
    glutMainLoop()

if __name__ == "__main__":
    main()
