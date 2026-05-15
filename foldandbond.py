"""
Fold & Bond v2 — Pygame UI with Protein Structure Art
======================================================
Each card features a procedurally drawn protein secondary structure:
  • α-helix  — animated ribbon helix with H-bond dashes
  • β-sheet  — anti-parallel arrow strands with H-bond ladder
  • coil     — organic backbone squiggle with side-chain stubs
  • Cys      — two coils bridged by glowing S-S bond
  • Pro      — helix entering a danger-red kink break
  • Gly      — three ghost conformations showing flexibility

Run:  python fold_and_bond_gui.py
Requires: pip install pygame
"""

import pygame
import pygame.gfxdraw
import random, math, time
from dataclasses import dataclass, field
from typing import Optional

pygame.init()
pygame.font.init()

# ── WINDOW ───────────────────────────────────────────────────────────────────
W, H = 1440, 900
screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
pygame.display.set_caption("Fold & Bond — Protein Structure Card Game")
clock = pygame.time.Clock()

# ── PALETTE ──────────────────────────────────────────────────────────────────
BG        = (5,   9,  14)
BG2       = (10,  16,  22)
SURFACE   = (18,  27,  38)
SURFACE2  = (24,  36,  52)
BORDER    = (28,  44,  64)
BORDER2   = (40,  60,  90)
TEXT      = (200, 223, 240)
TEXT2     = (118, 152, 182)
TEXT3     = (90, 116,  145)
HELIX     = (167, 139, 250)
HELIX_D   = (80,  55,  160)
SHEET     = (52,  211, 153)
SHEET_D   = (15,  110,  70)
COIL      = (148, 163, 184)
COIL_D    = (70,   85, 105)
SPECIAL   = (251, 191,  36)
SPECIAL_D = (140, 100,   8)
ACCENT    = (56,  189, 248)
ACCENT_D  = (10,  100, 170)
DANGER    = (248, 113, 113)
SUCCESS   = (74,  222, 128)
GOLD      = (251, 191,  36)
BLACK     = (0,     0,   0)
WHITE     = (255, 255, 255)

def pref_col(p):  return {'helix':HELIX,'sheet':SHEET,'coil':COIL,'special':SPECIAL}[p]
def pref_dark(p): return {'helix':HELIX_D,'sheet':SHEET_D,'coil':COIL_D,'special':SPECIAL_D}[p]
def lerp(a,b,t):  return a + (b-a)*t
def lerpC(a,b,t): return tuple(int(lerp(a[i],b[i],min(1,max(0,t)))) for i in range(3))

# ── TYPOGRAPHY ───────────────────────────────────────────────────────────────
# Four clear roles — no more than four sizes in any one screen area:
#
#   CAPTION  12px regular  — metadata, timestamps, sequence strings
#   BODY     15px regular  — all running text, step labels, tips
#   LABEL    15px bold     — section headers, stat labels, step names when active
#   TITLE    22px bold     — card names, panel headers, result structure
#   HERO     36px bold     — score number, game-over score
#
# Platform-aware: prefers Segoe UI (Windows) / Inter / DejaVu Sans (Linux).
def _mk_fonts():
    sans = ["Inter","Segoe UI","DejaVu Sans","Liberation Sans","FreeSans","Arial","Helvetica"]
    def F(size, bold=False):
        for name in sans:
            try:
                f = pygame.font.SysFont(name, size, bold=bold)
                if f.get_height() >= size - 3:
                    return f
            except Exception:
                pass
        return pygame.font.Font(None, size + 4)
    return (
        F(12),          # CAPTION — metadata, short sequences
        F(15),          # BODY    — step labels, tips, body text
        F(15, True),    # LABEL   — section headers, active step names
        F(19, True),    # TITLE   — panel titles, result structure, card names
        F(28, True),    # DISPLAY — score value, large numbers
        F(36, True),    # HERO    — game-over score
        # legacy aliases kept so nothing breaks
        F(15),          # FMD  → same as BODY
        F(12),          # FXS  → same as CAPTION
    )

_fonts = _mk_fonts()
CAPTION, BODY, LABEL, TITLE, DISPLAY, HERO = _fonts[:6]

# Legacy aliases — all existing code keeps working unchanged
FXS  = CAPTION   # was 13px bold → now 12px regular (cleaner as metadata)
FSM  = BODY      # was 14px      → now 15px
FMD  = BODY      # was 15px      → same
FDSM = LABEL     # was 14px bold → now 15px bold
FDMD = TITLE     # was 18px bold → now 19px bold
FDLG = DISPLAY   # was 25px bold → now 28px bold
FDXL = HERO      # was 36px bold → unchanged

# ── TEXT SHADOW helper — improves legibility on complex backgrounds ────────────
def txs(surf, s, font, col, x, y, anchor="topleft", shadow_col=(0,0,0), sdx=1, sdy=1):
    """Render text with a drop-shadow for readability."""
    sh = font.render(str(s), True, shadow_col)
    r_sh = sh.get_rect(**{anchor: (x+sdx, y+sdy)})
    surf.blit(sh, r_sh)
    r = font.render(str(s), True, col)
    r_r = r.get_rect(**{anchor: (x, y)})
    surf.blit(r, r_r)
    return r_r

def txcs(surf, s, font, col, cx, cy, shadow_col=(0,0,0)):
    return txs(surf, s, font, col, cx, cy, "center", shadow_col)

# ── DRAW HELPERS ─────────────────────────────────────────────────────────────
def rr(surf, col, rect, rad=8, bw=0, bc=None):
    pygame.draw.rect(surf, col, rect, border_radius=rad)
    if bw and bc:
        pygame.draw.rect(surf, bc, rect, bw, border_radius=rad)

def glow_rect(surf, col, rect, rad=10, strength=55):
    x, y, w, h = rect
    pad = rad * 3
    gs = pygame.Surface((w + pad*2, h + pad*2), pygame.SRCALPHA)
    for i in range(rad, 0, -1):
        a = int(strength * (i/rad)**1.8)
        pygame.draw.rect(gs, (*col[:3], a),
                         (pad-i, pad-i, w+i*2, h+i*2), border_radius=rad+i)
    surf.blit(gs, (x-pad, y-pad))

def txt(surf, s, font, col, x, y, anchor="topleft"):
    r = font.render(str(s), True, col)
    surf.blit(r, r.get_rect(**{anchor: (x, y)}))
    return r.get_rect(**{anchor: (x, y)})

def txc(surf, s, font, col, cx, cy):
    return txt(surf, s, font, col, cx, cy, "center")

# ── STRUCTURE DRAWERS ────────────────────────────────────────────────────────

def draw_helix(surf, x, y, w, h, col, dark, t=0.0):
    cx = x + w//2
    amp = w * 0.28
    coils = 26
    n_turns = 2.1
    pts_f, pts_b = [], []
    for i in range(coils+1):
        p = i/coils
        ang = p*n_turns*2*math.pi + t
        ry = y+6 + p*(h-14)
        pts_f.append((cx + math.sin(ang)*amp, ry))
        pts_b.append((cx - math.sin(ang)*amp*0.35, ry))
    # back ribbon
    for i in range(len(pts_b)-1):
        a1,a2 = pts_b[i], pts_b[i+1]
        pygame.draw.line(surf, dark, (int(a1[0]),int(a1[1])), (int(a2[0]),int(a2[1])), 3)
    # H-bond dashes
    for i in range(coils):
        ang = i/coils*n_turns*2*math.pi + t
        if abs(math.sin(ang)) < 0.22:
            hy = int(y+6 + i/coils*(h-14))
            hs = pygame.Surface((w-8,3), pygame.SRCALPHA)
            for dx in range(0,w-8,5): pygame.draw.circle(hs, (*col,50),(dx,1),1)
            surf.blit(hs,(x+4,hy))
    # front ribbon
    for i in range(len(pts_f)-1):
        p1,p2 = pts_f[i], pts_f[i+1]
        depth = (math.sin(i/coils*n_turns*2*math.pi+t)+1)*0.5
        lw = max(2,int(2+depth*4))
        c = lerpC(dark, col, depth)
        pygame.draw.line(surf, c, (int(p1[0]),int(p1[1])), (int(p2[0]),int(p2[1])), lw)
    # arrow tip
    lp, pp2 = pts_f[-1], pts_f[-4]
    ang = math.atan2(lp[1]-pp2[1], lp[0]-pp2[0])
    tip = (int(lp[0]+math.cos(ang)*7), int(lp[1]+math.sin(ang)*7))
    pl  = (int(lp[0]+math.cos(ang+2.5)*7), int(lp[1]+math.sin(ang+2.5)*7))
    pr  = (int(lp[0]+math.cos(ang-2.5)*7), int(lp[1]+math.sin(ang-2.5)*7))
    pygame.draw.polygon(surf, col, [tip,pl,pr])


def draw_sheet(surf, x, y, w, h, col, dark, t=0.0):
    n_strands = 2
    sh2 = (h-18)//n_strands
    for si in range(n_strands):
        sy = y+8 + si*(sh2+8)
        ey = sy + sh2 - 4
        mid_y = (sy+ey)//2
        d = 1 if si%2==0 else -1
        sx_s = x+5 if d==1 else x+w-5
        sx_e = x+w-5 if d==1 else x+5
        # ribbon body polygon
        body=[
            (sx_s,        mid_y-4),
            (sx_e-d*13,   mid_y-4),
            (sx_e-d*13,   mid_y-9),
            (sx_e,        mid_y),
            (sx_e-d*13,   mid_y+9),
            (sx_e-d*13,   mid_y+4),
            (sx_s,        mid_y+4),
        ]
        pygame.draw.polygon(surf, dark,  [(int(p[0]),int(p[1])) for p in body])
        pygame.draw.polygon(surf, col,   [(int(p[0]),int(p[1])) for p in body], 2)
        # pleat lines
        for pi in range(1,6):
            px = sx_s + (sx_e-d*13-sx_s)*pi/6
            pygame.draw.line(surf, dark, (int(px),mid_y-4), (int(px),mid_y+4), 1)
    # H-bond ladder between strands
    if n_strands >= 2:
        y1 = y+8 + 0*(sh2+8) + sh2//2
        y2 = y+8 + 1*(sh2+8) + sh2//2
        n_hb = 5
        for i in range(n_hb):
            hx = x+10 + i*(w-20)//(n_hb-1)
            hs = pygame.Surface((3,int(y2-y1)), pygame.SRCALPHA)
            for dy2 in range(0,int(y2-y1),4): pygame.draw.circle(hs,(*col,70),(1,dy2),1)
            surf.blit(hs,(hx,y1))


def draw_coil(surf, x, y, w, h, col, dark, t=0.0, seed=42):
    cx = x+w//2; n=20
    rng = random.Random(seed)
    pts=[]
    for i in range(n):
        p=i/(n-1); ry=y+8+p*(h-16)
        noise = math.sin(i*2.1+0.7)*(w*0.18)+math.cos(i*3.3+1.2)*(w*0.10)+rng.uniform(-4,4)
        pts.append((int(cx+noise),int(ry)))
    for i in range(len(pts)-1):
        t2=i/(len(pts)-1); c=lerpC(dark,col,0.4+0.6*t2)
        pygame.draw.line(surf,c,pts[i],pts[i+1],2)
        if i%3==0:
            pygame.draw.circle(surf,col,pts[i],3)
            pygame.draw.circle(surf,dark,pts[i],3,1)
    for i in range(1,len(pts)-1,3):
        ox=pts[i][0]+(9 if i%2==0 else -9); oy=pts[i][1]
        ds=pygame.Surface((20,10),pygame.SRCALPHA)
        pygame.draw.line(ds,(*col,130),(0 if i%2==0 else 20,5),(9 if i%2==0 else 11,5),2)
        pygame.draw.circle(ds,(*col,160),(9 if i%2==0 else 11,5),3)
        surf.blit(ds,(pts[i][0]-9,pts[i][1]-5))
    pygame.draw.circle(surf,col,pts[0],4)
    pygame.draw.circle(surf,col,pts[-1],4)


def draw_disulfide(surf, x, y, w, h, col, dark, t=0.0):
    cx=x+w//2; mid_y=y+h//2
    rng=random.Random(31)
    for side, (x0,x1) in enumerate([(x+4,cx-3),(cx+3,x+w-4)]):
        for seg, (ys,ye) in enumerate([(y+6,mid_y-5),(mid_y+5,y+h-6)]):
            pts=[]
            for i in range(10):
                p=i/9; ry=ys+p*(ye-ys)
                noise=math.sin(i*2.2+side+seg)*w*0.10+rng.uniform(-3,3)
                rx=x0+p*(x1-x0)+noise
                pts.append((int(rx),int(ry)))
            for i in range(len(pts)-1):
                pygame.draw.line(surf,col,pts[i],pts[i+1],2)
            for pt in pts[::3]: pygame.draw.circle(surf,col,pt,2)
    # S-S bridge
    ss_pts=[]
    for i in range(9):
        p=i/8; bx=cx-10+p*20; by=mid_y+(4 if i%2==0 else -4)
        ss_pts.append((int(bx),int(by)))
    for i in range(len(ss_pts)-1):
        pygame.draw.line(surf,SPECIAL,ss_pts[i],ss_pts[i+1],3)
    for pt in ss_pts[::2]:
        pygame.draw.circle(surf,SPECIAL,pt,4)
        pygame.draw.circle(surf,SPECIAL_D,pt,4,1)
    txc(surf,"S-S",FXS,SPECIAL,cx,mid_y+16)


def draw_proline(surf, x, y, w, h, col, dark, t=0.0):
    cx=x+w//2; brk=y+h*0.44
    amp=w*0.22; coils=10
    prev_pt=None
    for i in range(coils):
        p=i/coils; ang=p*1.6*2*math.pi+t
        ry=y+8+p*(brk-y-14)
        rx=cx+math.sin(ang)*amp
        depth=(math.sin(ang)+1)*0.5
        c=lerpC(dark,col,depth)
        if prev_pt:
            pygame.draw.line(surf,c,prev_pt,(int(rx),int(ry)),max(2,int(2+depth*3)))
        prev_pt=(int(rx),int(ry))
    # kink wedge
    kpts=[(cx-14,int(brk)),(cx+14,int(brk)),(cx+6,int(brk+15)),(cx-6,int(brk+15))]
    pygame.draw.polygon(surf,DANGER,kpts)
    pygame.draw.polygon(surf,(180,50,50),kpts,2)
    txc(surf,"KINK",FXS,WHITE,cx,int(brk+7))
    # coil after kink
    prx=pry=None
    rng=random.Random(77)
    for i in range(11):
        p=i/10; ry=int(brk+18+p*(y+h-8-brk-18))
        noise=math.sin(i*2.3+1.2)*w*0.13+rng.uniform(-3,3)
        rx=int(cx+noise)
        pygame.draw.circle(surf,col,(rx,ry),2)
        if prx is not None: pygame.draw.line(surf,dark,(prx,pry),(rx,ry),2)
        prx,pry=rx,ry


def draw_glycine(surf, x, y, w, h, col, dark, t=0.0):
    cx=x+w//2
    offsets=[(-w*0.24,50),( 0,120),( w*0.24,50)]
    for oi,(off,al) in enumerate(offsets):
        pts=[]
        rng=random.Random(oi*17+3)
        for i in range(12):
            p=i/11; ry=y+8+p*(h-20)
            noise=math.sin(i*1.9+off*0.25+oi*1.1)*w*0.14+rng.uniform(-3,3)
            pts.append((int(cx+off+noise),int(ry)))
        for i in range(len(pts)-1):
            ds=pygame.Surface((abs(pts[i+1][0]-pts[i][0])+4,abs(pts[i+1][1]-pts[i][1])+4),pygame.SRCALPHA)
            dx2=pts[i+1][0]-pts[i][0]; dy2=pts[i+1][1]-pts[i][1]
            px=min(pts[i][0],pts[i+1][0])-2; py=min(pts[i][1],pts[i+1][1])-2
            pygame.draw.line(surf,(*col,al),(pts[i][0],pts[i][1]),(pts[i+1][0],pts[i+1][1]),2)
        for pt in pts[::3]: pygame.draw.circle(surf,(*col,al),pt,2)
    # central G node
    pygame.draw.circle(surf,col,(cx,y+h//2),9,2)
    txc(surf,"G",FXS,col,cx,y+h//2)
    # flex arrows
    for dy2,d in [(-20,-1),(20,1)]:
        for ix in range(cx-8,cx+9,8):
            iy=y+h//2+dy2
            pygame.draw.line(surf,(*SPECIAL,160),(ix,iy),(ix,iy+d*6),2)


def draw_structure(surf, rect, pref, special, col, dark, t=0.0):
    x,y,w,h = rect
    if special=='disulfide':    draw_disulfide(surf,x,y,w,h,col,dark,t)
    elif special=='helix-break':draw_proline(surf,x,y,w,h,col,dark,t)
    elif special=='flexible':   draw_glycine(surf,x,y,w,h,col,dark,t)
    elif pref=='helix':         draw_helix(surf,x,y,w,h,col,dark,t)
    elif pref=='sheet':         draw_sheet(surf,x,y,w,h,col,dark,t)
    else:                       draw_coil(surf,x,y,w,h,col,dark,t,seed=hash(col)%9999)


# ── PARTICLES ────────────────────────────────────────────────────────────────
class Particle:
    def __init__(self,rand_y=False):
        self.x=random.uniform(0,W); self.y=random.uniform(0,H) if rand_y else H+4
        self.vy=-random.uniform(0.3,0.9); self.vx=random.uniform(-0.15,0.15)
        self.size=random.uniform(0.8,2.2); self.life=random.uniform(0,1) if rand_y else 0
        self.max_life=random.uniform(4,10)
        self.color=random.choice([HELIX,SHEET,ACCENT,SPECIAL,(140,110,230)])
    def reset(self):
        self.__init__(False)
    def update(self,dt):
        self.life+=dt; self.x+=self.vx; self.y+=self.vy
        if self.life>self.max_life or self.y<-4: self.reset()
    def draw(self,surf):
        t=self.life/self.max_life; a=int(160*math.sin(t*math.pi))
        if a<4: return
        s=pygame.Surface((6,6),pygame.SRCALPHA)
        pygame.draw.circle(s,(*self.color,a),(3,3),int(self.size)+1)
        surf.blit(s,(int(self.x)-3,int(self.y)-3))

PARTICLES=[Particle(True) for _ in range(50)]


class ScorePopup:
    def __init__(self,pts,x,y):
        self.pts=pts; self.x=float(x); self.y=float(y); self.life=0.0; self.max_life=2.0
    def update(self,dt): self.life+=dt; self.y-=55*dt
    def draw(self,surf):
        t=self.life/self.max_life; a=int(255*(1-t**1.5))
        if a<4: return
        s=FDLG.render(f"+{self.pts}",True,GOLD); s.set_alpha(a)
        surf.blit(s,s.get_rect(center=(int(self.x),int(self.y))))
    @property
    def dead(self): return self.life>=self.max_life

POPUPS=[]


# ── AMINO ACID DATA ──────────────────────────────────────────────────────────
# Chou-Fasman (1974/1978) propensity parameters:
#   P(α)  = fraction in α-helix / background frequency
#   P(β)  = fraction in β-sheet / background frequency
#   P(t)  = turn propensity (Levitt 1978)
# Values from Table I, Chou & Fasman (1978) Adv. Enzymol. 47:45-148.
# KD hydrophobicity scale: Kyte & Doolittle (1982) J. Mol. Biol. 157:105-132.
@dataclass
class AminoAcid:
    letter:str
    name:str
    pref:str        # dominant preference: helix/sheet/coil/special
    charge:str      # '+'/'-'/'N'
    hydro:str       # 'H' hydrophobic, 'P' hydrophilic  (KD > 0 → H)
    hbonds:int      # side-chain H-bond donors+acceptors
    cf_helix:float  # P(α)  Chou-Fasman 1978
    cf_sheet:float  # P(β)  Chou-Fasman 1978
    cf_turn:float   # P(t)  Levitt 1978
    kd_hydro:float  # Kyte-Doolittle hydrophobicity scale
    mw:float        # residue molecular weight (Da)
    special:Optional[str]=None

# letter, name, pref, charge, hydro, hbonds,  P(α),  P(β),  P(t),    KD,    MW,  special
AMINO_ACIDS=[
    AminoAcid('A','Alanine',     'helix',  'N','H',0,  1.42,  0.83,  0.66,  1.8,  89.1),
    AminoAcid('R','Arginine',    'helix',  '+','P',5,  0.98,  0.93,  0.95, -4.5, 174.2),
    AminoAcid('N','Asparagine',  'coil',   'N','P',4,  0.67,  0.89,  1.56, -3.5, 132.1),
    AminoAcid('D','Aspartate',   'coil',   '-','P',4,  1.01,  0.54,  1.46, -3.5, 133.1),
    AminoAcid('C','Cysteine',    'special','N','H',1,  0.70,  1.19,  1.19,  2.5, 121.2, special='disulfide'),
    AminoAcid('E','Glutamate',   'helix',  '-','P',4,  1.51,  0.37,  0.74, -3.5, 147.1),
    AminoAcid('Q','Glutamine',   'helix',  'N','P',5,  1.11,  1.10,  0.98, -3.5, 146.2),
    AminoAcid('G','Glycine',     'special','N','H',0,  0.57,  0.75,  1.56, -0.4,  75.0, special='flexible'),
    AminoAcid('H','Histidine',   'helix',  '+','P',4,  1.00,  0.87,  0.95, -3.2, 155.2),
    AminoAcid('I','Isoleucine',  'sheet',  'N','H',0,  1.08,  1.60,  0.47,  4.5, 131.2),
    AminoAcid('L','Leucine',     'helix',  'N','H',0,  1.21,  1.30,  0.59,  3.8, 131.2),
    AminoAcid('K','Lysine',      'helix',  '+','P',4,  1.16,  0.74,  1.01, -3.9, 146.2),
    AminoAcid('M','Methionine',  'helix',  'N','H',0,  1.45,  1.05,  0.60,  1.9, 149.2),
    AminoAcid('F','Phenylalanine','sheet', 'N','H',0,  1.13,  1.38,  0.60,  2.8, 165.2),
    AminoAcid('P','Proline',     'special','N','H',0,  0.57,  0.55,  1.52, -1.6, 115.1, special='helix-break'),
    AminoAcid('S','Serine',      'coil',   'N','P',3,  0.77,  0.75,  1.43, -0.8, 105.1),
    AminoAcid('T','Threonine',   'sheet',  'N','P',3,  0.83,  1.19,  0.96, -0.7, 119.1),
    AminoAcid('W','Tryptophan',  'sheet',  'N','H',2,  1.08,  1.37,  0.96, -0.9, 204.2),
    AminoAcid('Y','Tyrosine',    'sheet',  'N','P',3,  0.69,  1.47,  1.14, -1.3, 181.2),
    AminoAcid('V','Valine',      'sheet',  'N','H',0,  1.06,  1.70,  0.50,  4.2, 117.1),
]
AA_MAP={aa.letter:aa for aa in AMINO_ACIDS}

# Biological abundance frequency (UniProt Swiss-Prot statistics, 2023)
FREQ={'A':8,'R':5,'N':4,'D':5,'C':2,'E':6,'Q':4,'G':7,'H':2,
      'I':5,'L':9,'K':5,'M':2,'F':4,'P':5,'S':7,'T':6,'W':1,'Y':3,'V':6}

def build_deck():
    d=[]
    for aa in AMINO_ACIDS: d.extend([aa]*max(1,FREQ.get(aa.letter,2)))
    random.shuffle(d); return d

def cf_predict_window(residues):
    """
    Apply the Chou-Fasman sliding-window algorithm to a list of AminoAcid.
    Returns list of ('H','E','C') secondary structure predictions, one per residue.
    Uses 6-residue windows for helix (Chou-Fasman nucleation: 4 of 6 > 1.0)
    and 5-residue windows for sheet.
    """
    n=len(residues); pred=['C']*n
    # helix nucleation: 4 of any 6 consecutive with P(α) > 1.00
    for i in range(n-5):
        win=residues[i:i+6]
        strong=[r for r in win if r.cf_helix>1.00]
        if len(strong)>=4:
            avg_h=sum(r.cf_helix for r in win)/6
            avg_s=sum(r.cf_sheet for r in win)/6
            if avg_h>avg_s:
                # extend helix until average drops below 1.0
                j=i
                while j<n and residues[j].cf_helix>=1.0: j+=1
                for k in range(i,min(j,n)):
                    pred[k]='H'
    # sheet nucleation: 3 of any 5 consecutive with P(β) > 1.00
    for i in range(n-4):
        win=residues[i:i+5]
        strong=[r for r in win if r.cf_sheet>1.00]
        if len(strong)>=3:
            avg_s=sum(r.cf_sheet for r in win)/5
            avg_h=sum(r.cf_helix for r in win)/5
            if avg_s>avg_h:
                j=i
                while j<n and residues[j].cf_sheet>=1.0: j+=1
                for k in range(i,min(j,n)):
                    if pred[k]!='H': pred[k]='E'
    return pred


# ══════════════════════════════════════════════════════════════════════════
# ── INTERACTION NETWORK ENGINE ────────────────────────────────────────────
# Pairwise residue interactions, sequence motifs, local patterns,
# structure propagation — all biologically grounded.
# ══════════════════════════════════════════════════════════════════════════

EDGE_HBOND     = "hbond"
EDGE_HYDROPHOB = "hydrophob"
EDGE_SALT      = "salt"
EDGE_DISULFIDE = "disulfide"
EDGE_STACK     = "stack"
EDGE_REPULSION = "repulsion"
EDGE_BREAK     = "break"

EDGE_COLORS = {
    EDGE_HBOND:     (120, 200, 255),
    EDGE_HYDROPHOB: (200, 150,  80),
    EDGE_SALT:      ( 80, 230, 160),
    EDGE_DISULFIDE: (251, 191,  36),
    EDGE_STACK:     (200, 120, 255),
    EDGE_REPULSION: (248, 113, 113),
    EDGE_BREAK:     (248, 113, 113),
}

AROMATIC = {'F','W','Y','H'}

@dataclass
class NetworkEdge:
    i: int; j: int; kind: str; pts: int; label: str

@dataclass
class FoldResult:
    structure:  str
    points:     int
    breakdown:  list
    sequence:   str
    cf_helix:   float
    cf_sheet:   float
    edges:      list
    propagation: list
    valid:      bool = True


def pairwise_interactions(cards, structure):
    edges = []; pts = 0; n = len(cards)
    for i in range(n):
        for j in range(i+1, min(i+5, n)):
            a, b = cards[i], cards[j]; gap = j-i
            if structure == "alpha-helix" and gap == 4:
                bonus = round((a.cf_helix+b.cf_helix)*1.5)
                edges.append(NetworkEdge(i,j,EDGE_HBOND,bonus,f"H-bond i+4 +{bonus}")); pts+=bonus
            elif structure == "beta-sheet" and gap == 2:
                bonus = round((a.cf_sheet+b.cf_sheet)*1.2)
                edges.append(NetworkEdge(i,j,EDGE_HBOND,bonus,f"H-bond i+2 +{bonus}")); pts+=bonus
            if a.hydro=='H' and b.hydro=='H' and gap<=3:
                bonus = 3 if gap==1 else 2
                edges.append(NetworkEdge(i,j,EDGE_HYDROPHOB,bonus,f"Hydrophob +{bonus}")); pts+=bonus
            if a.charge in ('+','-') and b.charge in ('+','-'):
                if a.charge!=b.charge and gap<=2:
                    bonus = 5 if gap==1 else 3
                    edges.append(NetworkEdge(i,j,EDGE_SALT,bonus,f"Salt +{bonus}")); pts+=bonus
                elif a.charge==b.charge and gap==1:
                    edges.append(NetworkEdge(i,j,EDGE_REPULSION,-3,"Repulsion -3")); pts-=3
            if a.special=='disulfide' and b.special=='disulfide':
                edges.append(NetworkEdge(i,j,EDGE_DISULFIDE,12,"S-S bridge +12")); pts+=12
            if a.letter in AROMATIC and b.letter in AROMATIC and gap<=3:
                edges.append(NetworkEdge(i,j,EDGE_STACK,4,f"Pi-stack +4")); pts+=4
            if structure == "alpha-helix":
                if (a.special=='helix-break' or b.special=='helix-break') and gap<=2:
                    edges.append(NetworkEdge(i,j,EDGE_BREAK,-5,"Pro break -5")); pts-=5
    return edges, pts


MOTIFS = [
    {"name":"Leu heptad",      "color":HELIX,   "window":2,
     "check":lambda cs:len(cs)==2 and cs[0].letter=='L' and cs[1].letter=='L',
     "gap":4, "pts":8, "desc":"Leu heptad +8"},
    {"name":"EF-hand seed",    "color":ACCENT,  "window":2,
     "check":lambda cs:cs[0].charge=='-' and cs[1].hydro=='P',
     "gap":1, "pts":5, "desc":"EF-hand +5"},
    {"name":"RGD motif",       "color":SPECIAL, "window":3,
     "check":lambda cs:len(cs)==3 and cs[0].letter=='R' and cs[1].letter=='G' and cs[2].letter=='D',
     "gap":None, "pts":10, "desc":"RGD motif +10"},
    {"name":"PEST signal",     "color":DANGER,  "window":2,
     "check":lambda cs:cs[0].letter=='P' and cs[1].charge=='-',
     "gap":1, "pts":-6, "desc":"PEST signal -6"},
    {"name":"Hydrophob zipper","color":SHEET,   "window":3,
     "check":lambda cs:all(c.hydro=='H' for c in cs),
     "gap":None, "pts":7, "desc":"Hydrophob zipper +7"},
    {"name":"GG hinge",        "color":COIL,    "window":2,
     "check":lambda cs:all(c.special=='flexible' for c in cs),
     "gap":1, "pts":6, "desc":"GG hinge +6"},
    {"name":"Charged cluster", "color":ACCENT,  "window":4,
     "check":lambda cs:sum(1 for c in cs if c.charge!='N')>=3,
     "gap":None, "pts":5, "desc":"Charge cluster +5"},
    {"name":"Trp anchor",      "color":(200,120,255), "window":2,
     "check":lambda cs:any(c.letter=='W' for c in cs) and any(c.pref=='helix' for c in cs),
     "gap":1, "pts":6, "desc":"Trp anchor +6"},
]

def scan_motifs(cards):
    hits = []; n = len(cards)
    for m in MOTIFS:
        w = m["window"]; gap = m.get("gap")
        for i in range(n-w+1):
            window = cards[i:i+w]
            if gap is not None and w==2 and i+gap<n:
                window = [cards[i], cards[i+gap]]
            try:
                if m["check"](window):
                    hits.append((i, i+w-1, m, m["pts"]))
            except Exception:
                pass
    return hits


def local_patterns(cards, structure):
    bd=[]; pts=0; n=len(cards)
    i=0
    while i<n:
        rp=cards[i].pref; j=i
        while j<n and cards[j].pref==rp: j+=1
        rl=j-i
        if rl>=3:
            amp=(rl-2)*3
            col=pref_col(rp) if rp!='special' else SPECIAL
            bd.append((f"+{amp} {rp} run x{rl}", col)); pts+=amp
        i=j
    if structure=="alpha-helix" and n>=2:
        if cards[0].letter in ('S','T','N'):
            pts+=4; bd.append((f"+4 {cards[0].letter} N-cap", SUCCESS))
        if cards[-1].letter in ('G','A'):
            pts+=3; bd.append((f"+3 {cards[-1].letter} C-cap", SUCCESS))
    if structure=="beta-sheet" and n>=3:
        if cards[0].cf_sheet>=1.3:
            pts+=3; bd.append((f"+3 {cards[0].letter} sheet edge", SHEET))
        if cards[-1].cf_sheet>=1.3:
            pts+=3; bd.append((f"+3 {cards[-1].letter} sheet edge", SHEET))
    for i in range(1,n-1):
        if cards[i].pref=='coil':
            left =any(cards[k].pref!='coil' for k in range(max(0,i-2),i))
            right=any(cards[k].pref!='coil' for k in range(i+1,min(n,i+3)))
            if left and right:
                pts+=2; bd.append((f"+2 turn at {cards[i].letter}{i+1}", COIL)); break
    return pts, bd


def structure_propagation(cards, base_structure):
    n=len(cards); pts=0; labels=[]
    kernel=[0.5,1.0,0.5]
    if base_structure=="alpha-helix":
        pa='cf_helix'; pc2=HELIX; pt=0.9
    elif base_structure=="beta-sheet":
        pa='cf_sheet'; pc2=SHEET; pt=0.9
    else:
        return pts, labels
    smoothed=[]
    for i in range(n):
        ws=0.0; sc=0.0
        for di,kw in enumerate(kernel):
            ni=i+di-1
            if 0<=ni<n: sc+=getattr(cards[ni],pa)*kw; ws+=kw
        smoothed.append(sc/ws if ws else 0)
    inducted=[]
    exp_pref='helix' if base_structure=="alpha-helix" else 'sheet'
    for i,(c,s) in enumerate(zip(cards,smoothed)):
        if c.pref!=exp_pref and s>=pt:
            inducted.append(i); labels.append((i,"inducted",pc2))
    for i in inducted:
        pts+=round(getattr(cards[i],pa)*2)
    nat_or_ind=set(inducted)|{i for i,c in enumerate(cards) if c.pref==exp_pref}
    streak=best=0
    for i in range(n):
        streak=(streak+1) if i in nat_or_ind else 0
        best=max(best,streak)
    if best>=5:
        sb=(best-4)*3; pts+=sb
        labels.append((-1,f"+{sb} propagation streak x{best}",pc2))
    return pts, labels


def score_chain(cards) -> FoldResult:
    n=len(cards)
    if n<2:
        return FoldResult("too short",0,[("Need >= 2 residues",DANGER)],"",0,0,[],[],False)
    seq="-".join(c.letter for c in cards); bd=[]; pts=0
    hn=sum(1 for c in cards if c.pref=='helix')
    sn=sum(1 for c in cards if c.pref=='sheet')
    cn=sum(1 for c in cards if c.pref=='coil')
    ah=sum(c.cf_helix for c in cards)/n
    as_=sum(c.cf_sheet for c in cards)/n
    if ah>=1.03 and ah>as_:
        structure="alpha-helix"; display_struct="α-helix"
        base=round(hn*4+ah*5); pts+=base
        bd.append((f"+{base} α-helix base (CF {ah:.2f})",SUCCESS))
    elif as_>=1.05 and as_>ah:
        structure="beta-sheet"; display_struct="β-sheet"
        hp=[c for c in cards if c.hydro=='H' and c.pref=='sheet']
        base=round(sn*3+as_*4); hb2=len(hp)*2; pts+=base+hb2
        bd.append((f"+{base} β-sheet base (CF {as_:.2f})",SUCCESS))
        if hb2: bd.append((f"+{hb2} hydrophobic core x{len(hp)}",SUCCESS))
    else:
        structure="coil"; display_struct="random coil"; pts+=cn
        bd.append((f"+{cn} coil base ({cn} coil res)",TEXT2))
    thb=sum(c.hbonds for c in cards); hbp=round(thb*1.5); pts+=hbp
    bd.append((f"+{hbp} H-bonds ({thb}x1.5)",SUCCESS))
    edges,net_pts=pairwise_interactions(cards,structure)
    if net_pts!=0:
        pts+=net_pts
        col=SUCCESS if net_pts>0 else DANGER
        bd.append((f"{'+' if net_pts>=0 else ''}{net_pts} network ({len(edges)} edges)",col))
    motif_hits=scan_motifs(cards)
    seen=set()
    motif_edges=[]
    for i0,i1,m,mpts in motif_hits:
        if m["name"] not in seen:
            seen.add(m["name"]); pts+=mpts
            bd.append((m["desc"],m["color"] if mpts>0 else DANGER))
        if i0!=i1:
            motif_edges.append(NetworkEdge(i0,i1,EDGE_STACK,mpts,m["name"]))
    lp_pts,lp_bd=local_patterns(cards,structure)
    pts+=lp_pts; bd.extend(lp_bd)
    prop_pts,prop_labels=structure_propagation(cards,structure)
    pts+=prop_pts
    if prop_pts>0:
        sc_col=pref_col('helix' if structure=="alpha-helix" else 'sheet' if structure=="beta-sheet" else 'coil')
        bd.append((f"+{prop_pts} structure propagation",sc_col))
    if n>=8:   pts+=5; bd.append(("+5 ext chain >=8",TEXT2))
    elif n>=5: pts+=3; bd.append(("+3 long chain >=5",TEXT2))
    return FoldResult(display_struct,max(0,pts),bd,seq,ah,as_,edges+motif_edges,prop_labels)


# ── CARD WIDGET ──────────────────────────────────────────────────────────────
CARD_W, CARD_H = 108, 168

class CardWidget:
    def __init__(self,aa,x,y,idx):
        self.aa=aa; self.x=float(x); self.y=float(y)
        self.tx=float(x); self.ty=float(y)
        self.lift=0.0; self.selected=False; self.idx=idx
        self.hover=False; self._sanim=0.0; self._tanim=0.0

    def update(self,dt):
        self.x+=(self.tx-self.x)*min(1,dt*14)
        self.y+=(self.ty-self.y)*min(1,dt*14)
        tl=1.0 if (self.hover or self.selected) else 0.0
        self.lift+=(tl-self.lift)*min(1,dt*10)
        if self.selected or self.hover:
            self._sanim=(self._sanim+dt*2.5)%(2*math.pi)
        self._tanim=(self._tanim+dt*0.9)%(2*math.pi)

    def rect(self):
        ly=self.lift*(24 if self.selected else 10)
        return pygame.Rect(int(self.x),int(self.y-ly),CARD_W,CARD_H)

    def draw(self,surf):
        r=self.rect(); pc=pref_col(self.aa.pref); pd=pref_dark(self.aa.pref)
        # glow
        if self.selected:
            pulse=0.55+0.45*math.sin(self._sanim)
            glow_rect(surf,ACCENT,r,rad=14,strength=int(80*pulse))
        elif self.hover:
            glow_rect(surf,pc,r,rad=10,strength=30)
        # body
        rr(surf,SURFACE2 if self.hover else SURFACE,r,rad=11)
        bc=ACCENT if self.selected else (BORDER2 if self.hover else BORDER)
        rr(surf,BLACK,r,rad=11,bw=2 if self.selected else 1,bc=bc)

        # ── TOP LABEL BAR ──────────────────────────────────────────────
        bar=pygame.Rect(r.x+6,r.y+6,CARD_W-12,16)
        rr(surf,pd,bar,rad=4)
        txt(surf,self.aa.letter,FDMD,pc,bar.x+5,bar.y+1)
        tag={'helix':'α-HELIX','sheet':'β-SHEET','coil':'COIL','special':'SPECIAL'}[self.aa.pref]
        txt(surf,tag,FXS,pc,bar.right-FXS.size(tag)[0]-4,bar.y+4)

        # ── STRUCTURE ART ──────────────────────────────────────────────
        art=pygame.Rect(r.x+6,r.y+26,CARD_W-12,80)
        art_s=pygame.Surface((art.w,art.h),pygame.SRCALPHA)
        # dark tinted background
        pygame.draw.rect(art_s,(*pd,35),(0,0,art.w,art.h),border_radius=6)
        # draw structure
        col2=tuple(min(255,c+25) for c in pc) if self.hover else pc
        draw_structure(art_s,(0,0,art.w,art.h),self.aa.pref,self.aa.special,col2,pd,self._tanim)
        surf.blit(art_s,art.topleft)
        pygame.draw.rect(surf,(*pc,55),art,1,border_radius=6)

        # ── NAME ───────────────────────────────────────────────────────
        txc(surf,self.aa.name[:12],FSM,TEXT2,r.centerx,r.y+112)

        # ── STATS LINE ─────────────────────────────────────────────────
        sty=r.y+124
        pygame.draw.line(surf,BORDER,(r.x+6,sty),(r.right-6,sty))
        cf=max(self.aa.cf_helix,self.aa.cf_sheet)
        cf_col=SUCCESS if cf>=1.1 else (TEXT2 if cf>=1.0 else TEXT3)
        txt(surf,f"CF{cf:.2f}",FSM,cf_col,r.x+5,sty+3)
        chg_col={'+':ACCENT,'-':DANGER,'N':TEXT3}[self.aa.charge]
        txc(surf,self.aa.charge if self.aa.charge!='N' else '·',FSM,chg_col,r.centerx,sty+5)
        hyd_sym="◆" if self.aa.hydro=='H' else "○"
        hyd_col=HELIX_D if self.aa.hydro=='H' else (100,200,255)
        txt(surf,hyd_sym,FSM,hyd_col,r.right-30,sty+3)
        txt(surf,f"{self.aa.hbonds}H",FSM,ACCENT_D,r.right-16,sty+3)

        # ── SPECIAL BADGE or CF BARS ───────────────────────────────────
        if self.aa.special:
            sp_y=r.y+140
            sp_labels={'disulfide':'S-S BRIDGE','helix-break':'BREAKS HELIX','flexible':'FLEXIBLE'}
            sp_txt=sp_labels.get(self.aa.special,'SPECIAL')
            sp_col={'disulfide':SPECIAL,'helix-break':DANGER,'flexible':SHEET}[self.aa.special]
            sp_w=FXS.size(sp_txt)[0]+10
            sp_r=pygame.Rect(r.centerx-sp_w//2,sp_y,sp_w,14)
            rr(surf,tuple(c//6 for c in sp_col),sp_r,rad=3)
            txc(surf,sp_txt,FSM,sp_col,r.centerx,sp_y+7)
            # second line: effect
            eff={'disulfide':'+10/pair','helix-break':'-6 pts','flexible':'+2 coil'}[self.aa.special]
            txc(surf,eff,FSM,TEXT3,r.centerx,r.y+158)
        else:
            by2=r.y+142; bfw=CARD_W-14
            # helix bar
            pygame.draw.rect(surf,HELIX_D,(r.x+6,by2,bfw,4),border_radius=2)
            hw=int(bfw*min(1,self.aa.cf_helix/2.0))
            pygame.draw.rect(surf,HELIX,(r.x+6,by2,hw,4),border_radius=2)
            # sheet bar
            pygame.draw.rect(surf,SHEET_D,(r.x+6,by2+6,bfw,4),border_radius=2)
            sw2=int(bfw*min(1,self.aa.cf_sheet/2.0))
            pygame.draw.rect(surf,SHEET,(r.x+6,by2+6,sw2,4),border_radius=2)
            # labels
            txt(surf,"H",FXS,HELIX,r.x+6+hw+2,by2) if hw<bfw-8 else None
            txt(surf,"S",FXS,SHEET,r.x+6+sw2+2,by2+6) if sw2<bfw-8 else None

        # selection badge
        if self.selected:
            br=pygame.Rect(r.right-16,r.y-8,18,18)
            pygame.draw.circle(surf,ACCENT,br.center,9)
            pygame.draw.circle(surf,BLACK,br.center,9,1)
            txc(surf,"v",FXS,BLACK,br.centerx,br.centery)

    def hit(self,mx,my): return self.rect().collidepoint(mx,my)


# ── BUTTON ───────────────────────────────────────────────────────────────────
class Button:
    def __init__(self,label,x,y,w=130,h=36,color=ACCENT,style='normal'):
        self.label=label; self.rect=pygame.Rect(x,y,w,h)
        self.color=color; self.style=style
        self.hover=False; self.enabled=True; self._press=0.0
    def draw(self,surf):
        r=self.rect
        if not self.enabled:
            rr(surf,SURFACE,r,rad=7,bw=1,bc=BORDER)
            s=FSM.render(self.label,True,TEXT3); surf.blit(s,s.get_rect(center=r.center))
            return
        if self.style=='primary':
            bg=tuple(min(255,int(c*(1.25 if self.hover else 1.0))) for c in self.color)
            glow_rect(surf,self.color,r,rad=8,strength=45 if self.hover else 20)
            rr(surf,bg,r,rad=7,bw=2,bc=self.color); tc=BLACK
        else:
            rr(surf,SURFACE2 if self.hover else SURFACE,r,rad=7,bw=1,
               bc=self.color if self.hover else BORDER)
            tc=self.color if self.hover else TEXT
        sc=1-self._press*0.05
        s=FSM.render(self.label,True,tc)
        if sc<1.0: s=pygame.transform.scale(s,(int(s.get_width()*sc),int(s.get_height()*sc)))
        surf.blit(s,s.get_rect(center=r.center))
    def update(self,dt): self._press=max(0,self._press-dt*8)
    def hit(self,mx,my): return self.enabled and self.rect.collidepoint(mx,my)
    def click(self): self._press=1.0


# ── TOOLTIP ──────────────────────────────────────────────────────────────────
class Tooltip:
    def __init__(self): self.aa=None; self.x=0; self.y=0; self.alpha=0.0
    def show(self,aa,x,y): self.aa=aa; self.x=x; self.y=y
    def hide(self): self.aa=None
    def update(self,dt):
        target=255.0 if self.aa else 0.0
        self.alpha+=(target-self.alpha)*min(1,dt*10)
    def draw(self,surf):
        if not self.aa or self.alpha<10: return
        aa=self.aa; a=int(self.alpha)
        plab={'helix':'α-helix','sheet':'β-sheet','coil':'random coil','special':'special'}[aa.pref]
        clab={'+':'positive','-':'negative','N':'neutral'}[aa.charge]
        cfhm=' v' if aa.cf_helix>=1.03 else ''
        cfsm=' v' if aa.cf_sheet>=1.05 else ''
        lines=[(aa.name,FDMD,pref_col(aa.pref)),
               (f"Pref: {plab}",FSM,TEXT2),
               (f"CF helix: {aa.cf_helix:.2f}{cfhm}",FSM,SUCCESS if aa.cf_helix>=1.03 else TEXT2),
               (f"CF sheet: {aa.cf_sheet:.2f}{cfsm}",FSM,SUCCESS if aa.cf_sheet>=1.05 else TEXT2),
               (f"Charge: {clab}",FSM,TEXT2),
               (f"Hydro: {'hydrophobic' if aa.hydro=='H' else 'hydrophilic'}",FSM,TEXT2),
               (f"H-bonds: {aa.hbonds}",FSM,TEXT2)]
        if aa.special:
            sp={'disulfide':'S-S bridge w/Cys +10','helix-break':'Breaks helix -6','flexible':'Coil flex +2'}
            lines.append((sp.get(aa.special,''),FSM,SPECIAL))
        tw=max(f.size(t)[0] for t,f,_ in lines)+22
        th=sum(f.get_height()+3 for _,f,_ in lines)+16
        tx=min(self.x+16,W-tw-8); ty=max(8,min(self.y-10,H-th-8))
        ts=pygame.Surface((tw,th),pygame.SRCALPHA)
        pygame.draw.rect(ts,(*BG2,a),(0,0,tw,th),border_radius=9)
        pygame.draw.rect(ts,(*BORDER2,a),(0,0,tw,th),1,border_radius=9)
        cy=8
        for t2,f,c in lines:
            s=f.render(t2,True,(*c,a)); ts.blit(s,(10,cy)); cy+=f.get_height()+3
        surf.blit(ts,(tx,ty))


# ── GAME STATE ───────────────────────────────────────────────────────────────
@dataclass
class GameState:
    deck:list=field(default_factory=list); hand:list=field(default_factory=list)
    discard:list=field(default_factory=list); selected:set=field(default_factory=set)
    score:int=0; round_num:int=1; max_rounds:int=5
    folds_left:int=2; max_folds:int=2
    history:list=field(default_factory=list); best_fold:Optional[FoldResult]=None
    game_over:bool=False; last_result:Optional[FoldResult]=None
    # NEW: missions, stability, failures, tertiary
    missions:list=field(default_factory=list)        # current round missions
    completed_missions:list=field(default_factory=list)
    mission_bonus:int=0
    last_stability:Optional[object]=None
    last_failures:list=field(default_factory=list)
    last_tertiary:list=field(default_factory=list)
    round_folds:list=field(default_factory=list)     # folds this round for tertiary
    total_stability:int=0   # cumulative net stability score
    sidebar_scroll:int=0   # pixels scrolled down in sidebar

    def draw_cards(self,n=1):
        for _ in range(n):
            if not self.deck:
                if self.discard: self.deck=self.discard[:]; self.discard.clear(); random.shuffle(self.deck)
                else: break
            if self.deck: self.hand.append(self.deck.pop())
    def fill_hand(self,size=7):
        if (need:=size-len(self.hand))>0: self.draw_cards(need)




# ══════════════════════════════════════════════════════════════════════════════
# ── A. MISSION / OBJECTIVE SYSTEM ─────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MissionStep:
    label: str          # short one-line instruction shown on card
    key:   str          # machine key for progress check
    goal:  int          # target count / 1 for boolean
    tip:   str          # which cards to use (shown in grey)

@dataclass
class Mission:
    name:        str
    tagline:     str
    icon:        str
    color:       tuple
    req_structure: str
    req_min_len:   int
    req_hydro:     str
    req_special:   str
    bonus_pts:     int
    desc:          str
    steps:         list   # list[MissionStep]
    bio_fact:      str    # one-sentence biology flavour

MISSIONS = [
    Mission(
        name="Membrane Anchor",
        tagline="Pack the lipid bilayer",
        icon="M", color=(100,180,255),
        req_structure="alpha-helix", req_min_len=5,
        req_hydro="H", req_special="", bonus_pts=30,
        desc="Transmembrane helices are hydrophobic so they partition into the lipid bilayer.",
        steps=[
            MissionStep("Fold an α-helix",           "structure",  1, "Use A,E,L,K,M,Q cards (high P(α))"),
            MissionStep("At least 5 residues long",  "length",     5, "Add more helix-forming cards"),
            MissionStep("60%+ hydrophobic residues", "hydro_frac", 1, "Pick I,L,V,F,A,M — KD score > 0"),
        ],
        bio_fact="WALP23 and KALP23 peptides are classic TM helix models studied by solid-state NMR."
    ),
    Mission(
        name="Antibody CDR Loop",
        tagline="Flexible recognition loop",
        icon="L", color=(200,120,255),
        req_structure="coil", req_min_len=4,
        req_hydro="any", req_special="GG hinge", bonus_pts=25,
        desc="Complementarity-determining regions are hypervariable coils that contact antigens.",
        steps=[
            MissionStep("Fold a random coil",         "structure",   1, "Use N,D,S,G cards (P(α)<0.8)"),
            MissionStep("At least 4 residues long",   "length",      4, "Select 4+ coil residues"),
            MissionStep("Include a GG hinge motif",   "motif_GG hinge", 1, "Place two G (Glycine) cards adjacent"),
        ],
        bio_fact="CDR-H3 loops average 12 residues and determine most antibody specificity (Chothia 1989)."
    ),
    Mission(
        name="Amyloid Fibril",
        tagline="Cross-beta spine",
        icon="F", color=(255,160,60),
        req_structure="beta-sheet", req_min_len=6,
        req_hydro="H", req_special="Hydrophob zipper", bonus_pts=35,
        desc="Amyloid fibrils form when hydrophobic beta-sheets stack into insoluble protofilaments.",
        steps=[
            MissionStep("Fold a β-sheet",                       "structure",             1, "Use I,V,F,T,W,Y cards (high P(β))"),
            MissionStep("At least 6 residues long",             "length",                6, "Chain needs 6+ sheet residues"),
            MissionStep("60%+ hydrophobic residues",            "hydro_frac",            1, "Use I,V,F,L,W — avoid D,E,K,R"),
            MissionStep("Trigger hydrophobic zipper motif",     "motif_Hydrophob zipper",1, "Place 3 hydrophobic residues in a row"),
        ],
        bio_fact="The steric zipper at the amyloid core was solved by Eisenberg et al. (2006) to 1 Å resolution."
    ),
    Mission(
        name="Zinc Finger",
        tagline="Coordinate a metal ion",
        icon="Z", color=(80,230,180),
        req_structure="any", req_min_len=3,
        req_hydro="any", req_special="", bonus_pts=20,
        desc="Zinc fingers use Cys and His side-chains to tetrahedrally coordinate Zn2+.",
        steps=[
            MissionStep("At least 3 residues",      "length",   3, "Any 3+ cards"),
            MissionStep("Include 2+ Cys (C) cards", "cys_his",  2, "C card = Cysteine — special disulfide card"),
            MissionStep("OR include C+H together",  "cys_his",  2, "H card = Histidine — also coordinates Zn2+"),
        ],
        bio_fact="The classical CCHH zinc finger (Klug 1985) contacts 3 bp of DNA per repeat domain."
    ),
    Mission(
        name="Coiled-Coil",
        tagline="Weave a leucine zipper",
        icon="C", color=(167,139,250),
        req_structure="alpha-helix", req_min_len=6,
        req_hydro="H", req_special="Leu heptad", bonus_pts=40,
        desc="Coiled-coils form when two amphipathic helices wrap around each other via a heptad repeat.",
        steps=[
            MissionStep("Fold an α-helix",              "structure",        1, "Use A,E,L,K,M cards (P(α)>1.0)"),
            MissionStep("At least 6 residues long",     "length",           6, "Need 6+ helix residues"),
            MissionStep("60%+ hydrophobic residues",    "hydro_frac",       1, "Pack I,L,V,A,M — hydrophobic core"),
            MissionStep("Trigger Leu heptad motif",     "motif_Leu heptad", 1, "Place L (Leucine) at positions 4 apart"),
        ],
        bio_fact="GCN4 leucine zipper (O'Shea 1991) was the first coiled-coil crystal structure solved — a landmark in protein design."
    ),
    Mission(
        name="EF-Hand Sensor",
        tagline="Sense calcium ions",
        icon="E", color=(56,189,248),
        req_structure="any", req_min_len=4,
        req_hydro="any", req_special="EF-hand seed", bonus_pts=25,
        desc="EF-hand motifs use a 12-residue loop with acidic residues to chelate Ca2+ at nanomolar affinity.",
        steps=[
            MissionStep("At least 4 residues",            "length",           4, "Any 4+ cards"),
            MissionStep("Start with D or E (acidic)",     "starts_acidic",    1, "First card must be D (Aspartate) or E (Glutamate)"),
            MissionStep("Trigger EF-hand seed motif",     "motif_EF-hand seed", 1, "Acidic residue followed by a hydrophilic card"),
        ],
        bio_fact="Calmodulin has 4 EF-hand domains and regulates >300 target proteins upon Ca2+ binding (Bhatt 2020)."
    ),
    Mission(
        name="RGD Adhesion Peptide",
        tagline="Mediate cell attachment",
        icon="R", color=(74,222,128),
        req_structure="any", req_min_len=3,
        req_hydro="any", req_special="RGD motif", bonus_pts=30,
        desc="The Arg-Gly-Asp tripeptide is the minimal integrin-binding sequence found in fibronectin and vitronectin.",
        steps=[
            MissionStep("Play R (Arginine) card",        "has_R",        1, "R card = Arginine — positively charged"),
            MissionStep("Play G (Glycine) next to R",    "has_RG",       1, "G card = Glycine — flexible special card"),
            MissionStep("Play D (Aspartate) next to G",  "motif_RGD motif", 1, "D card = Aspartate — negatively charged"),
        ],
        bio_fact="Pierschbacher & Ruoslahti (1984) identified RGD as the fibronectin cell-attachment sequence — now used in biomaterial scaffolds."
    ),
    Mission(
        name="TM Helix Bundle",
        tagline="Build a helix bundle",
        icon="T", color=(255,100,120),
        req_structure="alpha-helix", req_min_len=7,
        req_hydro="H", req_special="", bonus_pts=45,
        desc="Seven-helix bundles (like GPCRs) are the most common transmembrane receptor architecture.",
        steps=[
            MissionStep("Fold an α-helix",              "structure",  1, "Use A,E,L,K,M,Q cards (P(α)>1.0)"),
            MissionStep("At least 7 residues",          "length",     7, "Need 7+ helix residues — longest chain bonus"),
            MissionStep("60%+ hydrophobic residues",    "hydro_frac", 1, "Use I,L,V,F,A — avoid charged residues"),
            MissionStep("No proline (P) cards",         "no_pro",     1, "P (Proline) breaks helices — avoid it"),
        ],
        bio_fact="The first GPCR crystal structure (rhodopsin, 2000) revealed 7 TM helices spanning ~25 residues each."
    ),
]

def roll_missions(n=3):
    return random.sample(MISSIONS, min(n, len(MISSIONS)))

def check_step(step, cards, result=None):
    """
    Return (current_value, goal, done) for a single MissionStep.
    Works on a live hand selection (result may be None for preview).
    """
    key = step.key
    n   = len(cards) if cards else 0
    if key == "structure":
        if result is None: return (0,1,False)
        disp_map={"alpha-helix":"α-helix","beta-sheet":"β-sheet","coil":"random coil"}
        # find which mission this step belongs to — we just check result
        # the step.goal is 1, result.structure must match whatever structure is expected
        # We check externally via check_mission; here just return 1/1 if folded anything
        return (1,1,True)
    if key == "length":
        return (n, step.goal, n >= step.goal)
    if key == "hydro_frac":
        hcount = sum(1 for c in cards if c.hydro=='H')
        done   = n>0 and hcount/n >= 0.6
        return (hcount, max(1,round(n*0.6)), done)
    if key.startswith("motif_"):
        motif_name = key[6:]
        hits = scan_motifs(cards) if cards else []
        found = any(m["name"]==motif_name for _,_,m,_ in hits)
        return (1 if found else 0, 1, found)
    if key == "cys_his":
        count = sum(1 for c in cards if c.letter in ("C","H"))
        return (count, step.goal, count >= step.goal)
    if key == "starts_acidic":
        ok = bool(cards) and cards[0].charge == '-'
        return (1 if ok else 0, 1, ok)
    if key == "has_R":
        ok = any(c.letter=='R' for c in cards)
        return (1 if ok else 0, 1, ok)
    if key == "has_RG":
        for i in range(len(cards)-1):
            if cards[i].letter=='R' and cards[i+1].letter=='G': return (1,1,True)
        return (0,1,False)
    if key == "no_pro":
        ok = not any(c.special=='helix-break' for c in cards)
        return (1 if ok else 0, 1, ok)
    return (0, step.goal, False)

def mission_progress(mission, cards, result=None):
    """
    Return list of (step, cur, goal, done) for every step in mission.
    cards = currently selected cards (live preview) or folded cards.
    """
    out = []
    for step in mission.steps:
        cur, goal, done = check_step(step, cards, result)
        out.append((step, cur, goal, done))
    return out

def check_mission(mission, result, cards):
    """Full pass/fail for completed fold."""
    disp_map = {"alpha-helix":"α-helix","beta-sheet":"β-sheet","coil":"random coil"}
    req_disp = disp_map.get(mission.req_structure,"")
    if mission.req_structure != "any" and result.structure != req_disp:
        return False
    if len(cards) < mission.req_min_len:
        return False
    if mission.req_hydro != "any":
        if sum(1 for c in cards if c.hydro==mission.req_hydro) < len(cards)*0.6:
            return False
    if mission.req_special:
        hits = scan_motifs(cards)
        if not any(m["name"]==mission.req_special for _,_,m,_ in hits):
            return False
    if mission.name in ("Zinc Finger","EF-Hand Sensor"):
        if sum(1 for c in cards if c.letter in ("C","H")) < 2 and mission.name=="Zinc Finger":
            return False
    return True


# ══════════════════════════════════════════════════════════════════════════════
# ── B. ENERGY / STABILITY SYSTEM ──────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class StabilityReport:
    fold_score:int; entropy_pen:int; exposure_pen:int
    stability:int; label:str; color:tuple; details:list

def compute_stability(cards, result):
    n=len(cards); details=[]; entropy_pen=0; exposure_pen=0
    # Coil entropy
    coil_run=best_run=0
    for c in cards:
        coil_run=(coil_run+1) if c.pref=="coil" else 0
        best_run=max(best_run,coil_run)
    if best_run>=4:
        ep=(best_run-3)*4; entropy_pen+=ep
        details.append((f"-{ep} entropy (coil run {best_run})",DANGER))
    # Charge overload
    pos_c=sum(1 for c in cards if c.charge=="+")
    neg_c=sum(1 for c in cards if c.charge=="-")
    clash=max(0,pos_c-2)+max(0,neg_c-2)
    if clash:
        cp=clash*3; entropy_pen+=cp
        details.append((f"-{cp} charge overload (+{pos_c}/-{neg_c})",DANGER))
    # Gly in helix
    if result.structure=="α-helix":
        gly=sum(1 for c in cards if c.special=="flexible")
        if gly>1:
            gp=gly*3; entropy_pen+=gp
            details.append((f"-{gp} Gly in helix ({gly}x)",DANGER))
    # Exposed hydrophobics
    exposed=0
    for i,c in enumerate(cards):
        if c.hydro=="H":
            l_ok=i>0 and cards[i-1].hydro=="H"
            r_ok=i<n-1 and cards[i+1].hydro=="H"
            if not l_ok and not r_ok: exposed+=1
    if exposed:
        ep2=exposed*3; exposure_pen+=ep2
        details.append((f"-{ep2} exposed hydrophobic ({exposed}x)",(255,180,80)))
    raw=result.points-entropy_pen-exposure_pen; stab=max(0,raw)
    if stab>=result.points*0.75:
        lbl="Stable";   col=SUCCESS
    elif stab>=result.points*0.45:
        lbl="Marginal"; col=SPECIAL
    else:
        lbl="Unstable"; col=DANGER
    details.insert(0,(f"{lbl}  ({stab} net energy)",col))
    return StabilityReport(result.points,entropy_pen,exposure_pen,stab,lbl,col,details)


# ══════════════════════════════════════════════════════════════════════════════
# ── C. FOLDING FAILURES ────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FoldingFailure:
    kind:str; penalty:int; message:str; color:tuple

def detect_failures(cards, result):
    failures=[]; n=len(cards)
    # Aggregation: 3+ hydrophobes in coil
    run=0
    for c in cards:
        run=(run+1) if (c.hydro=="H" and c.pref!="sheet") else 0
        if run>=3 and result.structure=="random coil":
            failures.append(FoldingFailure("aggregation",12,
                "Hydrophobic patch exposed — aggregation risk!",(255,100,80))); break
    # Misfold: interior Pro in helix
    if result.structure=="α-helix" and n>=5:
        interior=[i for i,c in enumerate(cards) if c.special=="helix-break" and 0<i<n-1]
        if interior:
            failures.append(FoldingFailure("misfold",8,
                f"Pro at pos {interior[0]+1} kinked the helix!",DANGER))
    # Degradation: PEST signal
    if any(m["name"]=="PEST signal" for _,_,m,_ in scan_motifs(cards)):
        failures.append(FoldingFailure("degradation",0,
            "PEST signal — proteasome target!",(255,140,60)))
    # Charge exposure in buried structure
    if result.structure in ("α-helix","β-sheet"):
        net=sum(1 if c.charge=="+" else -1 if c.charge=="-" else 0 for c in cards)
        if abs(net)>=4:
            failures.append(FoldingFailure("exposure",6,
                f"Net charge {net:+d} destabilises burial.",(180,120,255)))
    # Lone Cys
    cys=[c for c in cards if c.special=="disulfide"]
    if len(cys)==1:
        failures.append(FoldingFailure("exposure",4,
            "Unpaired Cys — free thiol oxidation risk!",SPECIAL))
    return failures


# ══════════════════════════════════════════════════════════════════════════════
# ── D. TERTIARY STRUCTURE MECHANICS ───────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TertiaryContact:
    kind:str; bonus:int; label:str; color:tuple

def detect_tertiary(round_folds):
    if len(round_folds)<2: return []
    contacts=[]; structs=[r.structure for r in round_folds]
    # β-α-β Rossmann
    for i in range(1,len(structs)-1):
        if structs[i-1]=="β-sheet" and structs[i]=="α-helix" and structs[i+1]=="β-sheet":
            contacts.append(TertiaryContact("supersecondary",20,"β-α-β Rossmann fold! +20",(200,120,255)))
    # Helix-Turn-Helix
    for i in range(len(structs)-2):
        if structs[i]=="α-helix" and structs[i+1]=="random coil" and structs[i+2]=="α-helix":
            contacts.append(TertiaryContact("supersecondary",15,"Helix-Turn-Helix! +15",HELIX))
    # Greek key: 4 consecutive sheets
    sheet_run=best_sr=0
    for s in structs:
        sheet_run=(sheet_run+1) if s=="β-sheet" else 0
        best_sr=max(best_sr,sheet_run)
    if best_sr>=4:
        contacts.append(TertiaryContact("supersecondary",18,"Greek Key motif! +18",SHEET))
    # Hydrophobic collapse
    for i in range(len(round_folds)-1):
        def hfrac(r):
            seq=r.sequence.replace("-","")
            return sum(1 for l in seq if AA_MAP.get(l) and AA_MAP[l].hydro=="H")/max(1,len(seq))
        if hfrac(round_folds[i])>=0.6 and hfrac(round_folds[i+1])>=0.6:
            contacts.append(TertiaryContact("hydrophobic_collapse",12,"Hydrophobic core collapse! +12",(255,180,80)))
    # Long-range S-S
    seqs=[r.sequence.replace("-","") for r in round_folds]
    cys_folds=[i for i,s in enumerate(seqs) if "C" in s]
    if len(cys_folds)>=2:
        contacts.append(TertiaryContact("long_range_ss",14,"Long-range S-S bridge! +14",SPECIAL))
    # Domain-domain electrostatics
    for i in range(len(round_folds)-1):
        def charges(r):
            seq=r.sequence.replace("-","")
            p=sum(1 for l in seq if AA_MAP.get(l) and AA_MAP[l].charge=="+")
            n2=sum(1 for l in seq if AA_MAP.get(l) and AA_MAP[l].charge=="-")
            return p,n2
        pa,na=charges(round_folds[i]); pb,nb=charges(round_folds[i+1])
        if (pa>=2 and nb>=2) or (pb>=2 and na>=2):
            contacts.append(TertiaryContact("domain_contact",10,"Domain electrostatic contact! +10",ACCENT))
    seen=set(); unique=[]
    for c in contacts:
        if c.kind not in seen: seen.add(c.kind); unique.append(c)
    return unique

# ── APP ───────────────────────────────────────────────────────────────────────
class App:
    HY   = 716    # hand Y
    HX   = 20     # hand X start
    BZX  = 20     # build zone X
    BZY  = 132    # build zone Y  — below stat strip (header 54 + stat 58 + gap 20)
    BZH  = CARD_H + 28
    SBX  = 960    # sidebar X  — wider sidebar (480px)
    PAD  = 12     # universal inner padding

    def __init__(self):
        self.gs=GameState(deck=build_deck()); self.gs.fill_hand()
        self.gs.missions=roll_missions(3)
        self._sb_total_h=0   # total sidebar content height, updated each frame
        self.cards=[]
        self.tooltip=Tooltip()
        self.msg=""; self.msg_col=TEXT2; self.msg_t=0.0
        self.mode="game"
        self._bg=self._mk_bg(); self._scan=self._mk_scan()
        self._build_cards(); self._build_btns()
        self._sb_drag=False; self._sb_drag_start_y=0; self._sb_drag_start_scroll=0

    def _mk_bg(self):
        s=pygame.Surface((W,H)); s.fill(BG)
        for x in range(0,W,44): pygame.draw.line(s,(7,13,19),(x,0),(x,H))
        for y in range(0,H,44): pygame.draw.line(s,(7,13,19),(0,y),(W,y))
        for cx2,cy2,r2,c in [(0,0,240,(*HELIX_D,14)),(W,0,180,(*SHEET_D,12)),(W//2,H,200,(*ACCENT_D,10))]:
            bs=pygame.Surface((r2*2,r2*2),pygame.SRCALPHA)
            pygame.draw.circle(bs,c,(r2,r2),r2); s.blit(bs,(cx2-r2,cy2-r2))
        return s

    def _mk_scan(self):
        s=pygame.Surface((W,H),pygame.SRCALPHA)
        for y in range(0,H,4): pygame.draw.line(s,(0,0,0,15),(0,y),(W,y))
        return s

    def _build_cards(self):
        self.cards.clear()
        for i,aa in enumerate(self.gs.hand):
            w=CardWidget(aa,self.HX+i*(CARD_W+8),self.HY,i)
            w.selected=i in self.gs.selected
            self.cards.append(w)

    def _build_btns(self):
        bx=self.BZX; by=self.BZY+self.BZH+14
        self.btn_fold    =Button("⬡  FOLD",      bx,     by,120,40,ACCENT,'primary')
        self.btn_clear   =Button("Clear",         bx+130, by, 90,40,TEXT2)
        self.btn_discard =Button("Discard + Draw",bx+230, by,140,40,SPECIAL)
        self.btn_next    =Button("Next Round  →", bx+382, by,148,40,SHEET,'primary')
        self.btn_new     =Button("New Game",      W//2-75,H//2+140,150,44,ACCENT,'primary')
        self.btn_next.enabled=False
        self.btns=[self.btn_fold,self.btn_clear,self.btn_discard,self.btn_next]

    def _upd_btns(self):
        self.btn_fold.enabled=len(self.gs.selected)>=2 and self.gs.folds_left>0 and not self.gs.game_over
        self.btn_discard.enabled=len(self.gs.selected)>=1 and not self.gs.game_over

    def set_msg(self,t,c=TEXT2,dur=3.5): self.msg=t; self.msg_col=c; self.msg_t=dur

    def toggle(self,idx):
        if self.gs.game_over: return
        if idx in self.gs.selected: self.gs.selected.discard(idx)
        else: self.gs.selected.add(idx)
        for w in self.cards: w.selected=w.idx in self.gs.selected
        self._upd_btns()

    def do_fold(self):
        if len(self.gs.selected)<2: self.set_msg("Select >= 2 cards first.",DANGER); return
        idxs=sorted(self.gs.selected); cards=[self.gs.hand[i] for i in idxs]
        res=score_chain(cards)
        if not res.valid: self.set_msg("Invalid chain.",DANGER); return

        # ── B. Stability ──────────────────────────────────────────────────
        stab=compute_stability(cards,res)
        self.gs.last_stability=stab
        self.gs.total_stability+=stab.stability

        # ── C. Folding failures ───────────────────────────────────────────
        failures=detect_failures(cards,res)
        self.gs.last_failures=failures
        failure_pen=sum(f.penalty for f in failures)
        net_pts=max(0,res.points-failure_pen)

        # ── A. Mission check ──────────────────────────────────────────────
        mission_bonus=0
        newly_completed=[]
        for m in self.gs.missions:
            if m not in self.gs.completed_missions and check_mission(m,res,cards):
                self.gs.completed_missions.append(m)
                mission_bonus+=m.bonus_pts
                newly_completed.append(m)
        self.gs.mission_bonus+=mission_bonus
        total_pts=net_pts+mission_bonus

        self.gs.score+=total_pts; self.gs.history.insert(0,res)
        if not self.gs.best_fold or res.points>self.gs.best_fold.points: self.gs.best_fold=res
        self.gs.last_result=res
        self.gs.round_folds.append(res)

        # ── D. Tertiary contacts ──────────────────────────────────────────
        tertiary=detect_tertiary(self.gs.round_folds)
        self.gs.last_tertiary=tertiary
        tert_bonus=sum(c.bonus for c in tertiary)
        if tert_bonus:
            self.gs.score+=tert_bonus; total_pts+=tert_bonus

        POPUPS.append(ScorePopup(total_pts,self.BZX+len(idxs)*(CARD_W+14)//2,self.BZY+CARD_H//2))
        for i in sorted(idxs,reverse=True): self.gs.discard.append(self.gs.hand.pop(i))
        self.gs.selected.clear(); self.gs.folds_left-=1; self.gs.fill_hand()
        self._build_cards(); self._upd_btns()

        # Build message
        cols={'α-helix':SUCCESS,'β-sheet':SHEET,'random coil':TEXT2}
        msg_parts=[f"Folded {res.structure}! +{net_pts}pts"]
        if failure_pen: msg_parts.append(f"Failures: -{failure_pen}")
        if newly_completed: msg_parts.append(f"Mission: {newly_completed[0].name} +{newly_completed[0].bonus_pts}!")
        if tert_bonus: msg_parts.append(f"Tertiary +{tert_bonus}!")
        self.set_msg("  |  ".join(msg_parts), cols.get(res.structure,TEXT2))

        if self.gs.folds_left<=0:
            self.btn_next.enabled=True
            if self.gs.round_num>=self.gs.max_rounds: self.btn_next.label="End Game ->"

    def do_clear(self):
        self.gs.selected.clear()
        for w in self.cards: w.selected=False
        self._upd_btns()

    def do_discard(self):
        if not self.gs.selected: self.set_msg("Select cards first.",DANGER); return
        if len(self.gs.selected)>3: self.set_msg("Max 3 cards.",DANGER); return
        idxs=sorted(self.gs.selected,reverse=True)
        for i in idxs: self.gs.discard.append(self.gs.hand.pop(i))
        self.gs.selected.clear(); self.gs.draw_cards(len(idxs)); self.gs.fill_hand()
        self._build_cards(); self._upd_btns()
        self.set_msg(f"Discarded {len(idxs)}, drew replacements.",ACCENT)

    def do_next(self):
        if self.gs.round_num>=self.gs.max_rounds: self.mode="gameover"; return
        self.gs.round_num+=1; self.gs.folds_left=self.gs.max_folds
        self.gs.selected.clear(); self.gs.last_result=None; self.gs.fill_hand()
        self.gs.missions=roll_missions(3); self.gs.round_folds=[]
        self._build_cards(); self.btn_next.enabled=False; self.btn_next.label="Next Round ->"
        self._upd_btns(); self.set_msg(f"Round {self.gs.round_num} — new missions available!",ACCENT)

    def do_new(self):
        global POPUPS; POPUPS=[]
        self.gs=GameState(deck=build_deck()); self.gs.fill_hand()
        self.gs.missions=roll_missions(3)
        self.mode="game"; self._build_cards(); self._build_btns()
        self.set_msg("New game! Check your missions in the sidebar.",SHEET)

    # ── DRAW GAME ────────────────────────────────────────────────────────
    def draw_game(self,surf):
        surf.blit(self._bg,(0,0))

        # ── HEADER BAR ─────────────────────────────────────────────────────
        rr(surf,BG2,(0,0,W,54),rad=0)
        pygame.draw.line(surf,BORDER,(0,54),(W,54))
        txs(surf,"FOLD & BOND",FDLG,HELIX,18,10,shadow_col=(20,8,50))
        txt(surf,"Protein Secondary Structure Card Game",BODY,TEXT3,
            FDLG.size("FOLD & BOND")[0]+26,20)

        # round pips — right of header
        for i in range(self.gs.max_rounds):
            dx=W-200+i*30; dy=27
            col=SHEET if i+1<self.gs.round_num else ACCENT if i+1==self.gs.round_num else BORDER2
            pygame.draw.circle(surf,col,(dx,dy),9)
            if i+1==self.gs.round_num:
                pa=int(22+16*math.sin(time.time()*2.5))
                ts2=pygame.Surface((40,40),pygame.SRCALPHA)
                pygame.draw.circle(ts2,(*ACCENT,pa),(20,20),15,2)
                surf.blit(ts2,(dx-20,dy-20))
            elif i+1<self.gs.round_num:
                # checkmark for completed rounds
                pygame.draw.line(surf,BG2,(dx-4,dy),(dx-1,dy+4),2)
                pygame.draw.line(surf,BG2,(dx-1,dy+4),(dx+5,dy-3),2)

        # ── STAT BAR — full width strip below header ─────────────────────
        rr(surf,SURFACE,(0,56,W,58),rad=0)
        pygame.draw.line(surf,BORDER,(0,114),(W,114))
        stat_items=[
            ("SCORE",        str(self.gs.score),           GOLD),
            ("ROUND",        f"{self.gs.round_num} of {self.gs.max_rounds}", TEXT),
            ("FOLDS LEFT",   str(self.gs.folds_left),      ACCENT),
            ("DECK",         str(len(self.gs.deck)),        TEXT2),
            ("STABILITY",    str(self.gs.total_stability),  SUCCESS),
            ("MISSIONS",     f"{len(self.gs.completed_missions)}/{len(self.gs.missions)}", SPECIAL),
        ]
        item_w = W // len(stat_items)
        for i,(lbl,val,col) in enumerate(stat_items):
            ix = i*item_w + item_w//2
            txt(surf,lbl,CAPTION,TEXT3,ix-CAPTION.size(lbl)[0]//2,62)
            txt(surf,val,LABEL,col,ix-LABEL.size(val)[0]//2,78)
        # fold pips inline with FOLDS LEFT
        fp_ix = 3*item_w + item_w//2
        for i in range(self.gs.max_folds):
            px=fp_ix-12+i*28; py=99
            col=HELIX_D if i<self.gs.max_folds-self.gs.folds_left else ACCENT
            pygame.draw.rect(surf,col,(px,py,22,7),border_radius=3)

        # build zone
        bz_w=self.SBX-self.BZX-12
        rr(surf,BG2,(self.BZX,self.BZY,bz_w,self.BZH),rad=10,bw=1,bc=BORDER)
        txs(surf,"BUILD ZONE",LABEL,TEXT2,self.BZX,self.BZY-22)

        sel=sorted(self.gs.selected)
        if sel:
            sel_cards=[self.gs.hand[i] for i in sel]
            n2=len(sel_cards)
            # card positions in build zone
            card_centers=[]
            for j,idx in enumerate(sel):
                bx2=self.BZX+10+j*(CARD_W+16); by2=self.BZY+10
                card_centers.append((bx2+CARD_W//2, by2+CARD_H//2))

            # ── LIVE INTERACTION NETWORK EDGES ───────────────────────────
            # compute live edges from current selection
            live_ah=sum(c.cf_helix for c in sel_cards)/n2
            live_as=sum(c.cf_sheet for c in sel_cards)/n2
            if live_ah>=1.03 and live_ah>live_as: live_struct="alpha-helix"
            elif live_as>=1.05 and live_as>live_ah: live_struct="beta-sheet"
            else: live_struct="coil"
            live_edges,_=pairwise_interactions(sel_cards, live_struct)
            live_motif_hits=scan_motifs(sel_cards)
            live_motif_edges=[]
            for i0,i1,m,mpts in live_motif_hits:
                if i0!=i1 and i1<n2:
                    live_motif_edges.append(NetworkEdge(i0,i1,EDGE_STACK,mpts,m["name"]))
            all_live_edges = live_edges + live_motif_edges

            # draw edges BEHIND cards (arcs above chain line)
            ta=time.time()
            edge_surf=pygame.Surface((bz_w,self.BZH),pygame.SRCALPHA)
            edge_offsets={}  # (i,j)->draw count for stacking
            for e in all_live_edges:
                if e.i>=n2 or e.j>=n2: continue
                ecol=EDGE_COLORS.get(e.kind,(180,180,180))
                alpha=180 if e.pts>0 else 130
                # animated dash offset for positive edges
                dash_t=int(ta*40)%20
                # arc midpoint raised above cards
                x1,y1=card_centers[e.i]; x2,y2=card_centers[e.j]
                # arc height proportional to gap
                gap=e.j-e.i; arc_h=gap*22+12
                mx2=(x1+x2)//2-self.BZX; my2=(y1+y2)//2-self.BZY-arc_h
                ax1=x1-self.BZX; ay1=y1-self.BZY
                ax2=x2-self.BZX; ay2=y2-self.BZY
                # draw bezier-like arc as segments
                segs=12
                prev_pt=None
                for si in range(segs+1):
                    tt=si/segs
                    # quadratic bezier
                    bpx=int((1-tt)**2*ax1+2*(1-tt)*tt*mx2+tt**2*ax2)
                    bpy=int((1-tt)**2*ay1+2*(1-tt)*tt*my2+tt**2*ay2)
                    if prev_pt:
                        # dashed for negative, solid for positive
                        if e.pts<0:
                            if (si+dash_t//3)%3!=0: prev_pt=(bpx,bpy); continue
                        lw=2 if abs(e.pts)>=5 else 1
                        pygame.draw.line(edge_surf,(*ecol,alpha),prev_pt,(bpx,bpy),lw)
                    prev_pt=(bpx,bpy)
                # edge label at midpoint
                lbl_s=FSM.render(e.label[:14],True,(*ecol,220))
                edge_surf.blit(lbl_s,(mx2-lbl_s.get_width()//2,my2-10))
            surf.blit(edge_surf,(self.BZX,self.BZY))

            # draw cards on top of edges
            for j,idx in enumerate(sel):
                aa=self.gs.hand[idx]
                bx2=self.BZX+10+j*(CARD_W+16); by2=self.BZY+10
                # backbone connector
                if j>0:
                    cx2=bx2-16; cy2=by2+CARD_H//2
                    pygame.draw.line(surf,BORDER2,(cx2,cy2),(bx2,cy2),2)
                    pygame.draw.circle(surf,ACCENT,(cx2+8,cy2),3)
                # propagation induction highlight
                prop_pts2,prop_labels2=structure_propagation(sel_cards,live_struct)
                inducted_idxs={l[0] for l in prop_labels2 if l[0]>=0}
                if j in inducted_idxs:
                    glow_rect(surf,SHEET,(bx2,by2,CARD_W,CARD_H),rad=8,strength=25)
                tmp=CardWidget(aa,bx2,by2,idx); tmp._tanim=ta*0.9; tmp.draw(surf)

            # live prediction panel to right of cards
            lx2=self.BZX+10+len(sel)*(CARD_W+16)+10
            if lx2+160<self.SBX-20:
                if live_ah>=1.03 and live_ah>live_as:   pred2,pcol2="->alpha-HELIX",HELIX
                elif live_as>=1.05 and live_as>live_ah:  pred2,pcol2="->beta-SHEET",SHEET
                else:                                     pred2,pcol2="->COIL",COIL
                txt(surf,f"CF h:{live_ah:.2f}",FSM,TEXT2,lx2,self.BZY+12)
                txt(surf,f"CF s:{live_as:.2f}",FSM,TEXT2,lx2,self.BZY+24)
                txt(surf,pred2,FDSM,pcol2,lx2,self.BZY+38)
                # show active edge count
                pos_e=sum(1 for e in all_live_edges if e.pts>0)
                neg_e=sum(1 for e in all_live_edges if e.pts<0)
                if pos_e: txt(surf,f"+{pos_e} bonds",FSM,SUCCESS,lx2,self.BZY+58)
                if neg_e: txt(surf,f"{neg_e} clash",FSM,DANGER,lx2,self.BZY+72)
                # motif names
                seen_m=set()
                my_y=self.BZY+84
                for _,_,m,mpts in live_motif_hits:
                    if m["name"] not in seen_m:
                        seen_m.add(m["name"])
                        mc=m["color"] if mpts>0 else DANGER
                        txt(surf,m["name"][:18],FSM,mc,lx2,my_y); my_y+=16
        else:
            txc(surf,"Select cards from your hand below, then click  FOLD",
                BODY,TEXT3,self.BZX+bz_w//2,self.BZY+self.BZH//2)

        # last result
        if self.gs.last_result:
            res=self.gs.last_result; ry2=self.BZY+self.BZH+54
            res_h=118
            rr(surf,SURFACE,(self.BZX,ry2,bz_w,res_h),rad=8,bw=1,bc=BORDER2)
            scm={'α-helix':HELIX,'β-sheet':SHEET,'random coil':COIL}
            sc3=scm.get(res.structure,TEXT2)
            txt(surf,res.structure,FDMD,sc3,self.BZX+12,ry2+8)
            txt(surf,f"+{res.points} pts",FDMD,GOLD,self.BZX+210,ry2+8)
            txt(surf,res.sequence[:52],BODY,ACCENT,self.BZX+16,ry2+32)
            # network edge summary
            if res.edges:
                ecounts={}
                for e in res.edges:
                    ecounts[e.kind]=ecounts.get(e.kind,0)+1
                ex=self.BZX+12; ey=ry2+47
                for kind,cnt in list(ecounts.items())[:5]:
                    ec=EDGE_COLORS.get(kind,(180,180,180))
                    pygame.draw.circle(surf,ec,(ex+4,ey+5),4)
                    txt(surf,f"{cnt}x {kind}",FXS,ec,ex+12,ey); ex+=FXS.size(f"{cnt}x {kind}")[0]+26
            # breakdown lines
            for k,(bt,bc2) in enumerate(res.breakdown[:6]):
                col2=k//3; row2=k%3
                txt(surf,f"  {bt}",BODY,bc2,self.BZX+16+col2*430,ry2+66+row2*17)

        # buttons
        for b in self.btns: b.draw(surf)

        # msg
        if self.msg and self.msg_t>0:
            txt(surf,self.msg,BODY,self.msg_col,self.BZX,self.BZY+self.BZH+58)

        # hand
        txs(surf,"YOUR HAND",LABEL,TEXT2,self.HX,self.HY-22)
        for w in self.cards: w.draw(surf)

        self._draw_sidebar(surf)
        for p in PARTICLES: p.draw(surf)
        for pp in POPUPS:   pp.draw(surf)
        surf.blit(self._scan,(0,0))
        self.tooltip.draw(surf)

    def _draw_sidebar(self,surf):
        """Render sidebar into a tall offscreen surface, then clip+scroll onto screen."""
        sx=self.SBX; sw=W-sx-18   # leave 18px for scrollbar
        PAD=14; GAP=12
        VIEWPORT_Y=120; VIEWPORT_H=H-VIEWPORT_Y
        scm={"alpha-helix":HELIX,"β-sheet":SHEET,"random coil":COIL,"α-helix":HELIX}
        def scolor(s): return scm.get(s,TEXT2)

        # ── helpers ───────────────────────────────────────────────────────
        def draw_panel_header(cs, title, h, accent=BORDER):
            """Draw panel bg + header strip onto content surface. Returns content_y."""
            rr(cs,BG2,(0,0,sw,h),rad=12,bw=1,bc=accent)
            ph=TITLE.get_height()+PAD*2
            rr(cs,SURFACE,(0,0,sw,ph),rad=12)
            pygame.draw.rect(cs,SURFACE,(0,6,sw,ph-6))
            pygame.draw.line(cs,accent,(0,ph),(sw,ph))
            cs.blit(TITLE.render(title,True,TEXT),(PAD,PAD-2))
            return ph+PAD//2

        live_cards=[self.gs.hand[i] for i in sorted(self.gs.selected)] if self.gs.selected else []

        # ══ measure total content height first ════════════════════════════
        def mission_card_h(m):
            if m in self.gs.completed_missions:
                return PAD + TITLE.get_height() + 6 + BODY.get_height() + PAD
            step_rows=0
            for step in m.steps:
                prog=mission_progress(m,live_cards)
                step_done=[d for s,c,g,d in prog if s is step]
                done=step_done[0] if step_done else False
                step_rows+=BODY.get_height()+(CAPTION.get_height()+3 if not done else 0)+8
            bio_lines=max(1,len(m.bio_fact)//38+1)
            return PAD+TITLE.get_height()+8+step_rows+bio_lines*(CAPTION.get_height()+2)+PAD+4

        def stab_h():
            stab=self.gs.last_stability
            if not stab: return TITLE.get_height()+PAD*2+BODY.get_height()+PAD*2
            return TITLE.get_height()+PAD*2+16+(len(stab.details))*(BODY.get_height()+5)+PAD

        def fail_h():
            f=self.gs.last_failures
            n=max(1,len(f))
            return TITLE.get_height()+PAD*2+PAD//2+n*(BODY.get_height()+8)+PAD

        def tert_h():
            t=self.gs.last_tertiary
            if not t: return TITLE.get_height()+PAD*2+BODY.get_height()+PAD*2
            return TITLE.get_height()+PAD*2+PAD//2+len(t)*(BODY.get_height()+10)+PAD

        def hist_h():
            n=min(len(self.gs.history),8)
            if n==0: return 0
            return TITLE.get_height()+PAD*2+PAD//2+n*(BODY.get_height()+7)+PAD

        missions_total_h = (TITLE.get_height()+PAD*2+4 +
                            sum(mission_card_h(m)+GAP for m in self.gs.missions) + GAP)
        total_h = (missions_total_h + GAP +
                   stab_h() + GAP + fail_h() + GAP + tert_h() + GAP + hist_h() + 20)
        self._sb_total_h = total_h
        self._clamp_scroll()

        # ══ render into offscreen surface ═════════════════════════════════
        cs=pygame.Surface((sw, total_h), pygame.SRCALPHA)
        cy=0   # running y on content surface

        # ── MISSIONS ──────────────────────────────────────────────────────
        mh_outer=missions_total_h
        rr(cs,BG2,(0,cy,sw,mh_outer),rad=12,bw=1,bc=BORDER)
        ph=TITLE.get_height()+PAD*2
        rr(cs,SURFACE,(0,cy,sw,ph),rad=12)
        pygame.draw.rect(cs,SURFACE,(0,cy+6,sw,ph-6))
        pygame.draw.line(cs,BORDER,(0,cy+ph),(sw,cy+ph))
        cs.blit(TITLE.render("MISSIONS",True,TEXT),(PAD,cy+PAD-2))
        n_done=len(self.gs.completed_missions); n_tot=len(self.gs.missions)
        badge=f"{n_done}/{n_tot}"
        bw3=LABEL.size(badge)[0]+14
        pygame.draw.rect(cs,tuple(c//3 for c in ACCENT),(sw-bw3-PAD,cy+PAD-2,bw3,LABEL.get_height()+6),border_radius=5)
        cs.blit(LABEL.render(badge,True,ACCENT),(sw-bw3-PAD+7,cy+PAD-1))
        card_y=cy+ph+GAP//2

        for m in self.gs.missions:
            done=m in self.gs.completed_missions
            mhc=mission_card_h(m); mc=m.color
            # bg
            rr(cs,tuple(max(0,c-6) for c in BG2),(0,card_y,sw,mhc),rad=9)
            rr(cs,BLACK,(0,card_y,sw,mhc),rad=9,bw=2 if done else 1,bc=mc if done else BORDER)
            if done: glow_rect(cs,mc,(0,card_y,sw,mhc),rad=7,strength=16)
            # accent bar
            pygame.draw.rect(cs,SUCCESS if done else mc,(0,card_y+8,4,mhc-16),border_radius=2)
            # icon
            ic_x=PAD+10; ic_y=card_y+PAD+TITLE.get_height()//2
            pygame.draw.circle(cs,tuple(c//4 for c in mc),(ic_x,ic_y),12)
            pygame.draw.circle(cs,mc,(ic_x,ic_y),12,2)
            cs.blit(LABEL.render(m.icon,True,mc),
                    LABEL.render(m.icon,True,mc).get_rect(center=(ic_x,ic_y)))
            # name row
            ny=card_y+PAD
            cs.blit(TITLE.render(m.name,True,SUCCESS if done else mc),(PAD+26,ny))
            bstr=f"+{m.bonus_pts}"; bsrf=LABEL.render(bstr,True,SUCCESS if done else TEXT3)
            cs.blit(bsrf,(sw-bsrf.get_width()-PAD,ny+3))

            if done:
                s2=BODY.render(f"  Completed  —  {m.tagline}",True,SUCCESS)
                cs.blit(s2,(PAD+26,ny+TITLE.get_height()+6))
            else:
                prog=mission_progress(m,live_cards)
                sy=ny+TITLE.get_height()+10
                for (step,cur,goal,step_done) in prog:
                    tk_x=PAD+8; tk_y=sy+BODY.get_height()//2
                    if step_done:
                        pygame.draw.circle(cs,SUCCESS,(tk_x,tk_y),7)
                        pygame.draw.line(cs,BG2,(tk_x-4,tk_y),(tk_x-1,tk_y+3),2)
                        pygame.draw.line(cs,BG2,(tk_x-1,tk_y+3),(tk_x+5,tk_y-3),2)
                    else:
                        pygame.draw.circle(cs,SURFACE2,(tk_x,tk_y),7)
                        pygame.draw.circle(cs,BORDER2,(tk_x,tk_y),7,1)
                    # step label
                    lc=SUCCESS if step_done else TEXT
                    cs.blit(BODY.render(step.label,True,lc),(PAD+22,sy))
                    # progress bar (right)
                    if goal>1:
                        bw4=56; bh4=8
                        bx4=sw-bw4-PAD; by4=sy+BODY.get_height()//2-bh4//2
                        pygame.draw.rect(cs,SURFACE,(bx4,by4,bw4,bh4),border_radius=4)
                        fw=int(bw4*min(1,cur/goal))
                        if fw>0: pygame.draw.rect(cs,SUCCESS if step_done else mc,(bx4,by4,fw,bh4),border_radius=4)
                        pt=f"{min(cur,goal)}/{goal}"; pts=CAPTION.render(pt,True,TEXT3)
                        cs.blit(pts,(bx4-pts.get_width()-4,by4+1))
                    # tip (only when not done)
                    if not step_done:
                        tip_s=CAPTION.render(step.tip[:46],True,TEXT3)
                        cs.blit(tip_s,(PAD+22,sy+BODY.get_height()+2))
                        sy+=BODY.get_height()+CAPTION.get_height()+9
                    else:
                        sy+=BODY.get_height()+8
                # bio fact — word wrap
                bio_col=tuple(min(255,int(c*0.4+105)) for c in mc)
                words=m.bio_fact.split(); line=""; bio_y=sy+6
                for w2 in words:
                    test=line+(" " if line else "")+w2
                    if CAPTION.size(test)[0]>sw-PAD*2-8 and line:
                        cs.blit(CAPTION.render(line,True,bio_col),(PAD+4,bio_y))
                        bio_y+=CAPTION.get_height()+3; line=w2
                    else: line=test
                if line: cs.blit(CAPTION.render(line,True,bio_col),(PAD+4,bio_y))
            card_y+=mhc+GAP
        cy=card_y+GAP

        # ── STABILITY ─────────────────────────────────────────────────────
        sh2=stab_h(); stab=self.gs.last_stability
        cy2=draw_panel_header(cs,"STABILITY",sh2)
        cs_sub=cs.subsurface((0,0,sw,total_h)) if False else cs  # draw onto cs directly
        # redo: draw content below header manually
        content_y=cy+TITLE.get_height()+PAD*2+PAD//2
        rr(cs,BG2,(0,cy,sw,sh2),rad=12,bw=1,bc=BORDER)
        rr(cs,SURFACE,(0,cy,sw,TITLE.get_height()+PAD*2),rad=12)
        pygame.draw.rect(cs,SURFACE,(0,cy+6,sw,TITLE.get_height()+PAD*2-6))
        pygame.draw.line(cs,BORDER,(0,cy+TITLE.get_height()+PAD*2),(sw,cy+TITLE.get_height()+PAD*2))
        cs.blit(TITLE.render("STABILITY",True,TEXT),(PAD,cy+PAD-2))
        csy=cy+TITLE.get_height()+PAD*2+PAD//2
        if stab:
            bw5=sw-PAD*2; bf=int(bw5*min(1,stab.stability/max(1,stab.fold_score)))
            pygame.draw.rect(cs,SURFACE,(PAD,csy,bw5,10),border_radius=5)
            if bf>0: pygame.draw.rect(cs,stab.color,(PAD,csy,bf,10),border_radius=5)
            csy+=14
            cs.blit(BODY.render(f"{stab.label}  —  {stab.stability} / {stab.fold_score} net energy",True,stab.color),(PAD,csy))
            csy+=BODY.get_height()+5
            for (dt2,dc) in stab.details[1:]:
                cs.blit(BODY.render(f"  {dt2}",True,dc),(PAD,csy))
                csy+=BODY.get_height()+5
        else:
            s2=BODY.render("Fold a chain to see stability",True,TEXT3)
            cs.blit(s2,(sw//2-s2.get_width()//2,csy+4))
        cy+=sh2+GAP

        # ── FOLD HEALTH ────────────────────────────────────────────────────
        failures=self.gs.last_failures; fh2=fail_h()
        rr(cs,BG2,(0,cy,sw,fh2),rad=12,bw=1,bc=BORDER)
        rr(cs,SURFACE,(0,cy,sw,TITLE.get_height()+PAD*2),rad=12)
        pygame.draw.rect(cs,SURFACE,(0,cy+6,sw,TITLE.get_height()+PAD*2-6))
        pygame.draw.line(cs,BORDER,(0,cy+TITLE.get_height()+PAD*2),(sw,cy+TITLE.get_height()+PAD*2))
        cs.blit(TITLE.render("FOLD HEALTH",True,TEXT),(PAD,cy+PAD-2))
        cfy=cy+TITLE.get_height()+PAD*2+PAD//2
        if failures:
            for f in failures[:4]:
                rr(cs,tuple(c//6 for c in f.color),(0,cfy,sw,BODY.get_height()+8),rad=5)
                pygame.draw.rect(cs,f.color,(0,cfy,3,BODY.get_height()+8),border_radius=1)
                cs.blit(BODY.render(f.message,True,f.color),(PAD+8,cfy+4))
                cfy+=BODY.get_height()+10
        else:
            rr(cs,tuple(c//6 for c in SUCCESS),(PAD,cfy,sw-PAD*2,BODY.get_height()+8),rad=5)
            s2=BODY.render("No failures — clean fold!",True,SUCCESS)
            cs.blit(s2,(sw//2-s2.get_width()//2,cfy+4))
        cy+=fh2+GAP

        # ── TERTIARY ──────────────────────────────────────────────────────
        tert=self.gs.last_tertiary; th3=tert_h()
        rr(cs,BG2,(0,cy,sw,th3),rad=12,bw=1,bc=BORDER)
        rr(cs,SURFACE,(0,cy,sw,TITLE.get_height()+PAD*2),rad=12)
        pygame.draw.rect(cs,SURFACE,(0,cy+6,sw,TITLE.get_height()+PAD*2-6))
        pygame.draw.line(cs,BORDER,(0,cy+TITLE.get_height()+PAD*2),(sw,cy+TITLE.get_height()+PAD*2))
        cs.blit(TITLE.render("TERTIARY CONTACTS",True,TEXT),(PAD,cy+PAD-2))
        cty=cy+TITLE.get_height()+PAD*2+PAD//2
        if tert:
            for ct in tert[:4]:
                rr(cs,tuple(c//5 for c in ct.color),(0,cty,sw,BODY.get_height()+10),rad=6)
                pygame.draw.rect(cs,ct.color,(0,cty,4,BODY.get_height()+10),border_radius=2)
                # icon dot
                pygame.draw.circle(cs,ct.color,(PAD+8,cty+BODY.get_height()//2+5),5)
                s2=BODY.render(ct.label,True,ct.color)
                cs.blit(s2,(PAD+18,cty+4))
                cty+=BODY.get_height()+12
        else:
            s2=BODY.render("Fold 2+ chains this round to see contacts",True,TEXT3)
            cs.blit(s2,(sw//2-s2.get_width()//2,cty+4))
        cy+=th3+GAP

        # ── HISTORY ────────────────────────────────────────────────────────
        hh=hist_h()
        if hh>0:
            rr(cs,BG2,(0,cy,sw,hh),rad=12,bw=1,bc=BORDER)
            rr(cs,SURFACE,(0,cy,sw,TITLE.get_height()+PAD*2),rad=12)
            pygame.draw.rect(cs,SURFACE,(0,cy+6,sw,TITLE.get_height()+PAD*2-6))
            pygame.draw.line(cs,BORDER,(0,cy+TITLE.get_height()+PAD*2),(sw,cy+TITLE.get_height()+PAD*2))
            cs.blit(TITLE.render("HISTORY",True,TEXT),(PAD,cy+PAD-2))
            chy=cy+TITLE.get_height()+PAD*2+PAD//2
            for r in self.gs.history[:8]:
                rr(cs,SURFACE,(PAD,chy,sw-PAD*2,BODY.get_height()+8),rad=5)
                col=scolor(r.structure)
                cs.blit(LABEL.render(f"+{r.points:>3}",True,GOLD),(PAD+6,chy+4))
                cs.blit(BODY.render(r.structure,True,col),(PAD+58,chy+4))
                seq_s=r.sequence.replace("-","")[:14]
                ss=CAPTION.render(seq_s,True,TEXT3)
                cs.blit(ss,(sw-ss.get_width()-PAD,chy+6))
                chy+=BODY.get_height()+10
            cy+=hh+GAP

        # ══ blit scrolled region onto screen ═════════════════════════════
        scroll=self.gs.sidebar_scroll
        # background for sidebar area
        pygame.draw.rect(surf,BG,(sx,VIEWPORT_Y,W-sx,VIEWPORT_H))
        # clip region
        view_rect=pygame.Rect(0,scroll,sw,min(VIEWPORT_H,total_h-scroll))
        if view_rect.height>0 and view_rect.width>0:
            try:
                sub=cs.subsurface(view_rect)
                surf.blit(sub,(sx,VIEWPORT_Y))
            except ValueError:
                pass

        # ── SCROLLBAR ─────────────────────────────────────────────────────
        sb_x=W-14; sb_w=8
        sb_track_h=VIEWPORT_H-8
        pygame.draw.rect(surf,SURFACE,(sb_x,VIEWPORT_Y+4,sb_w,sb_track_h),border_radius=4)
        if total_h>VIEWPORT_H:
            thumb_h=max(28,int(sb_track_h*VIEWPORT_H/total_h))
            thumb_y=VIEWPORT_Y+4+int((sb_track_h-thumb_h)*scroll/max(1,total_h-VIEWPORT_H))
            # thumb hover
            mx2,my2=pygame.mouse.get_pos()
            hovering_sb=abs(mx2-sb_x)<12 and VIEWPORT_Y<my2<VIEWPORT_Y+sb_track_h
            thumb_col=ACCENT if (hovering_sb or getattr(self,'_sb_drag',False)) else BORDER2
            pygame.draw.rect(surf,thumb_col,(sb_x,thumb_y,sb_w,thumb_h),border_radius=4)
            # subtle track dots
            for dy in range(8,sb_track_h,18):
                pygame.draw.circle(surf,BORDER,(sb_x+sb_w//2,VIEWPORT_Y+4+dy),1)

    def draw_gameover(self,surf):
        surf.blit(self._bg,(0,0))
        for p in PARTICLES: p.draw(surf)
        surf.blit(self._scan,(0,0))
        ov=pygame.Surface((W,H),pygame.SRCALPHA); ov.fill((5,9,14,215)); surf.blit(ov,(0,0))
        bw2,bh2=500,430; bx2,by2=W//2-bw2//2,H//2-bh2//2
        glow_rect(surf,ACCENT,(bx2,by2,bw2,bh2),rad=22,strength=28)
        rr(surf,BG2,(bx2,by2,bw2,bh2),rad=16,bw=2,bc=BORDER2)
        txc(surf,"GAME OVER",FDXL,HELIX,W//2,by2+36)
        txc(surf,"FINAL SCORE",FSM,TEXT3,W//2,by2+76)
        pa=int(90+70*math.sin(time.time()*2.2))
        gs2=pygame.Surface((160,70),pygame.SRCALPHA)
        pygame.draw.ellipse(gs2,(*GOLD,pa),(0,0,160,70)); surf.blit(gs2,(W//2-80,by2+84))
        txc(surf,str(self.gs.score),FDXL,GOLD,W//2,by2+110)
        txc(surf,"pts",FSM,TEXT2,W//2,by2+150)
        rating=("Nobel-worthy architect!" if self.gs.score>=200 else
                "Expert biochemist!"      if self.gs.score>=140 else
                "Competent folder!"       if self.gs.score>=80  else
                "Promising student."      if self.gs.score>=40  else
                "Study those CF tables...")
        txc(surf,rating,FSM,TEXT2,W//2,by2+172)
        scm={'α-helix':HELIX,'β-sheet':SHEET,'random coil':COIL}
        if self.gs.best_fold:
            bf=self.gs.best_fold; col=scm.get(bf.structure,TEXT2)
            rr(surf,SURFACE,(bx2+24,by2+194,bw2-48,46),rad=8)
            txc(surf,"Best fold",FSM,TEXT3,W//2,by2+204)
            txc(surf,f"{bf.structure}  +{bf.points} pts",FSM,col,W//2,by2+218)
            txc(surf,bf.sequence[:36],FSM,TEXT3,W//2,by2+234)
        pygame.draw.line(surf,BORDER,(bx2+24,by2+254),(bx2+bw2-24,by2+254))
        for k,r in enumerate(self.gs.history[:5]):
            hy=by2+262+k*22; col=scm.get(r.structure,TEXT2)
            txt(surf,f"+{r.points:>3}",FSM,GOLD,bx2+44,hy)
            txt(surf,r.structure,FSM,col,bx2+96,hy+2)
            txt(surf,r.sequence.replace('-','')[:18],FXS,TEXT3,bx2+230,hy+3)
        self.btn_new.draw(surf)

    def update(self,dt,mx,my):
        for p in PARTICLES: p.update(dt)
        for pp in POPUPS:   pp.update(dt)
        POPUPS[:]=[pp for pp in POPUPS if not pp.dead]
        self.tooltip.update(dt)
        for b in self.btns: b.update(dt)
        self.btn_new.update(dt)
        if self.msg_t>0: self.msg_t-=dt
        hovered=None
        for w in self.cards:
            w.hover=w.hit(mx,my)
            if w.hover: hovered=w.aa
            w.update(dt)
        if hovered: self.tooltip.show(hovered,mx,my)
        else:       self.tooltip.hide()
        for b in self.btns: b.hover=b.hit(mx,my)
        self.btn_new.hover=self.btn_new.hit(mx,my)

    def _sb_rect(self):
        """Sidebar viewport rect on screen."""
        return pygame.Rect(self.SBX, 120, W-self.SBX, H-120)

    def _clamp_scroll(self):
        viewport_h = H - 120
        max_scroll  = max(0, self._sb_total_h - viewport_h + 20)
        self.gs.sidebar_scroll = max(0, min(self.gs.sidebar_scroll, max_scroll))

    def handle(self,event):
        if event.type==pygame.QUIT: return False
        if event.type==pygame.VIDEORESIZE:
            global W,H,screen
            W,H=event.w,event.h
            screen=pygame.display.set_mode((W,H),pygame.RESIZABLE)
            self._bg=self._mk_bg(); self._scan=self._mk_scan()
        if event.type==pygame.MOUSEWHEEL:
            mx,my=pygame.mouse.get_pos()
            if mx >= self.SBX:   # only when hovering sidebar
                self.gs.sidebar_scroll -= event.y * 28
                self._clamp_scroll()
            return True
        if event.type==pygame.MOUSEBUTTONDOWN:
            mx,my=event.pos
            # scrollbar drag start
            if event.button==1 and mx >= W-12 and my >= 120:
                self._sb_drag=True; self._sb_drag_start_y=my
                self._sb_drag_start_scroll=self.gs.sidebar_scroll
                return True
            if event.button==1:
                if self.mode=="gameover":
                    if self.btn_new.hit(mx,my): self.btn_new.click(); self.do_new()
                    return True
                for w in self.cards:
                    if w.hit(mx,my): self.toggle(w.idx); return True
                if self.btn_fold.hit(mx,my):     self.btn_fold.click();    self.do_fold()
                elif self.btn_clear.hit(mx,my):  self.btn_clear.click();   self.do_clear()
                elif self.btn_discard.hit(mx,my):self.btn_discard.click(); self.do_discard()
                elif self.btn_next.hit(mx,my):   self.btn_next.click();    self.do_next()
            if event.button==4: # scroll wheel up (older pygame)
                mx2,my2=pygame.mouse.get_pos()
                if mx2>=self.SBX: self.gs.sidebar_scroll-=28; self._clamp_scroll()
            if event.button==5: # scroll wheel down
                mx2,my2=pygame.mouse.get_pos()
                if mx2>=self.SBX: self.gs.sidebar_scroll+=28; self._clamp_scroll()
        if event.type==pygame.MOUSEBUTTONUP and event.button==1:
            self._sb_drag=False
        if event.type==pygame.MOUSEMOTION:
            if getattr(self,'_sb_drag',False):
                viewport_h=H-120
                max_scroll=max(1,self._sb_total_h-viewport_h+20)
                dy=event.pos[1]-self._sb_drag_start_y
                scroll_per_px=max_scroll/max(1,viewport_h-40)
                self.gs.sidebar_scroll=max(0,min(max_scroll,
                    self._sb_drag_start_scroll+int(dy*scroll_per_px)))
        return True

    def run(self):
        prev=time.time(); running=True
        while running:
            now=time.time(); dt=min(now-prev,0.05); prev=now
            mx,my=pygame.mouse.get_pos()
            for e in pygame.event.get():
                if not self.handle(e): running=False
            self.update(dt,mx,my)
            if self.mode=="game": self.draw_game(screen)
            else:                 self.draw_gameover(screen)
            pygame.display.flip(); clock.tick(60)
        pygame.quit()

if __name__=="__main__":
    App().run()