#!/usr/bin/env python3
"""
ClassicOS 7.5 — Mac System 7.5 Platinum style desktop
PyQt5 single-file, no images required.
Run: python3 classicos75.py
"""

import sys, os, math, io, threading, subprocess, re
from datetime import datetime
from pathlib import Path

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from PyQt5.QtWidgets import *
from PyQt5.QtCore    import *
from PyQt5.QtGui     import *

# ─────────────────────────────────────────────────────────────
#  SYSTEM 7.5 PLATINUM PALETTE
# ─────────────────────────────────────────────────────────────
# Platinum gray colours — exact System 7.5 look
C_PLATINUM      = QColor(0xCC, 0xCC, 0xCC)   # main window bg / desktop
C_PLATINUM_LT   = QColor(0xEE, 0xEE, 0xEE)   # highlight / lighter surfaces
C_PLATINUM_DK   = QColor(0xAA, 0xAA, 0xAA)   # shadow side
C_DESKTOP       = QColor(0x00, 0x80, 0x80)   # classic teal-green desktop
C_WHITE         = QColor(0xFF, 0xFF, 0xFF)
C_BLACK         = QColor(0x00, 0x00, 0x00)
C_TITLE_STRIPE1 = QColor(0xDD, 0xDD, 0xDD)
C_TITLE_STRIPE2 = QColor(0x88, 0x88, 0x88)
C_TITLE_TEXT    = QColor(0x00, 0x00, 0x00)
C_SCROLL_BG     = QColor(0xBB, 0xBB, 0xBB)
C_MENUBAR       = QColor(0xFF, 0xFF, 0xFF)
C_BORDER        = QColor(0x00, 0x00, 0x00)
C_WIN_BG        = QColor(0xFF, 0xFF, 0xFF)
C_TOOLBAR_BG    = QColor(0xDD, 0xDD, 0xDD)
C_INACTIVE_TITLE= QColor(0xEE, 0xEE, 0xEE)
C_HILITE        = QColor(0x00, 0x00, 0x80)   # Classic Mac selection blue

# Highlight / selection colour (user-selectable in real System 7, we default to cyan-blue)
C_SELECT        = QColor(0x00, 0x00, 0x77)
C_SELECT_TEXT   = QColor(0xFF, 0xFF, 0xFF)


def make_dither_brush(light=0xDD, dark=0xBB):
    """2×2 checkerboard dither brush — classic System 7 Finder background."""
    img = QImage(2, 2, QImage.Format_RGB32)
    img.setPixel(0, 0, QColor(light, light, light).rgb())
    img.setPixel(1, 1, QColor(light, light, light).rgb())
    img.setPixel(1, 0, QColor(dark,  dark,  dark ).rgb())
    img.setPixel(0, 1, QColor(dark,  dark,  dark ).rgb())
    return QBrush(img)


# cached brush — create once, reuse everywhere
_DITHER_BRUSH = None
def dither_brush():
    global _DITHER_BRUSH
    if _DITHER_BRUSH is None:
        _DITHER_BRUSH = make_dither_brush()
    return _DITHER_BRUSH


def font_chicago(size=12, bold=False):
    """Geneva as substitute for Chicago (closest available cross-platform)."""
    for family in ("Chicago", "Geneva", "Charcoal", "Helvetica", "Arial"):
        f = QFont(family, size)
        if bold:
            f.setBold(True)
        # System 7 had NO anti-aliasing — force pixel-sharp text
        f.setStyleStrategy(QFont.NoAntialias)
        fm = QFontMetrics(f)
        if fm.height() > 0:
            return f
    f = QFont()
    f.setPixelSize(size)
    f.setBold(bold)
    f.setStyleStrategy(QFont.NoAntialias)
    return f


# ─────────────────────────────────────────────────────────────
#  SYSTEM 7.5 ICON PAINTER  (pure QPainter, no images)
# ─────────────────────────────────────────────────────────────
def draw_icon(painter: QPainter, name: str, x: int, y: int, size: int = 32):
    s = size
    p = painter
    p.save()
    p.translate(x, y)
    bk = C_BLACK
    wh = C_WHITE
    gy = QColor(0xAA, 0xAA, 0xAA)
    lt = QColor(0xDD, 0xDD, 0xDD)

    def bbox(rx, ry, rw, rh, fill=wh, border=bk, bw=1):
        p.fillRect(rx, ry, rw, rh, fill)
        pen = QPen(border, bw)
        p.setPen(pen)
        p.drawRect(rx, ry, rw-1, rh-1)

    n = name.lower()

    if n == "finder":
        # Classic happy mac face
        bbox(2, 2, s-4, s-4, wh, bk, 2)
        p.fillRect(2, 2, s-4, 8, bk)          # black header
        p.fillRect(4, 3, s-8, 6, wh)           # white stripe in header
        p.fillRect(6, 12, 5, 5, bk)            # left eye
        p.fillRect(s-12, 12, 5, 5, bk)         # right eye
        # smile
        for i in range(6):
            xo = 7 + i * 2
            yo = int(22 + math.sin(i / 5 * math.pi) * 3)
            p.fillRect(xo, yo, 2, 2, bk)

    elif n == "macintosh_hd" or n == "hd" or n == "disk":
        # Hard disk drive icon
        bbox(3, 6, s-6, s-8, lt, bk, 2)
        p.fillRect(4, 7, s-8, 6, gy)           # top face
        p.setPen(QPen(bk, 1))
        p.drawLine(4, 13, s-5, 13)
        # small indicator
        p.fillRect(s-12, s-6, 6, 4, QColor(0x00, 0xAA, 0x00))
        p.fillRect(5, s-8, 8, 3, gy)

    elif n == "folder":
        # System 7 folder — teal-blue body with subtle 3-stop gradient + highlight
        body_pts = QPolygon([
            QPoint(2, 12), QPoint(2, s-4),
            QPoint(s-3, s-4), QPoint(s-3, 10),
            QPoint(14, 10), QPoint(12, 12),
        ])
        tab_pts = QPolygon([QPoint(2, 12), QPoint(12, 12), QPoint(14, 10), QPoint(4, 10)])
        # Fill body with vertical gradient bands: light top → mid → shadow bottom
        body_colors = [
            QColor(0xA0, 0xD8, 0xEF),  # pale sky-blue top highlight
            QColor(0x50, 0xA0, 0xD0),  # mid teal
            QColor(0x28, 0x70, 0xA8),  # deeper blue bottom
        ]
        p.setClipRegion(QRegion(body_pts))
        band_h = (s - 4 - 10) // 3
        for i, col in enumerate(body_colors):
            p.fillRect(2, 10 + i * band_h, s - 4, band_h + 2, col)
        p.fillRect(2, 10 + 2 * band_h, s - 4, s - 4 - (10 + 2 * band_h), body_colors[2])
        # specular 1-px white line near top of body
        p.setPen(QPen(QColor(0xFF, 0xFF, 0xFF, 160), 1))
        p.drawLine(4, 14, s - 5, 14)
        p.setClipping(False)
        # tab: slightly lighter than body mid
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(0x70, 0xB8, 0xE0)))
        p.drawPolygon(tab_pts)
        # outer border
        p.setPen(QPen(QColor(0x10, 0x50, 0x80), 1))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(body_pts)
        p.drawPolygon(tab_pts)

    elif n == "trash" or n == "trash_empty":
        # Trash can (empty)
        p.setPen(QPen(bk, 1))
        p.setBrush(QBrush(wh))
        # can body
        p.drawRect(7, 10, s-15, s-13)
        # lid
        p.drawLine(4, 10, s-5, 10)
        p.drawLine(s//2-3, 6, s//2+3, 6)
        p.drawLine(s//2-3, 6, s//2-3, 10)
        p.drawLine(s//2+3, 6, s//2+3, 10)
        # lines on can
        p.setPen(QPen(gy, 1))
        for i in range(3):
            p.drawLine(11+i*5, 13, 11+i*5, s-5)

    elif n == "trash_full":
        p.setPen(QPen(bk, 1))
        p.setBrush(QBrush(wh))
        p.drawRect(7, 10, s-15, s-13)
        p.drawLine(4, 10, s-5, 10)
        p.drawLine(s//2-3, 6, s//2+3, 6)
        p.drawLine(s//2-3, 6, s//2-3, 10)
        p.drawLine(s//2+3, 6, s//2+3, 10)
        p.setPen(QPen(gy, 1))
        for i in range(3):
            p.drawLine(11+i*5, 13, 11+i*5, s-5)
        # crumpled paper
        p.setPen(QPen(bk, 1))
        p.setBrush(QBrush(wh))
        p.drawEllipse(9, 6, 8, 6)
        p.drawEllipse(17, 5, 7, 5)

    elif n == "terminal":
        bbox(2, 2, s-4, s-4, bk, bk, 2)
        p.setPen(QPen(QColor(0x00, 0xFF, 0x41), 1))
        f = font_chicago(7)
        p.setFont(f)
        p.drawText(4, 13, "% _")
        p.drawText(4, 21, "ls -l")
        p.drawText(4, 29, "ok")

    elif n == "notepad":
        bbox(4, 1, s-6, s-3, wh, bk, 1)
        p.fillRect(4, 1, s-6, 5, lt)
        p.setPen(QPen(QColor(0xAA, 0xAA, 0xFF), 1))
        for row in range(5):
            p.drawLine(6, 9 + row*5, s-4, 9 + row*5)
        p.setPen(QPen(bk, 1))
        for i in range(5):
            p.drawLine(2, 4+i*5, 4, 4+i*5)

    elif n == "browser":
        bbox(2, 2, s-4, s-4, wh, bk, 1)
        p.fillRect(3, 3, s-6, 6, lt)
        p.setPen(QPen(bk, 1))
        for row in range(4):
            p.fillRect(3, 11+row*5, s-6-(row%3)*4, 3, gy)

    elif n == "settings" or n == "control_panel":
        # Control Panels slider icon
        bbox(2, 2, s-4, s-4, lt, bk, 1)
        p.setPen(QPen(bk, 1))
        # Three sliders
        for i, xpos in enumerate([6, 10, 16]):
            p.drawLine(xpos, 8, xpos, s-8)
            p.fillRect(xpos-2, 8+(i*6), 5, 4, wh)
            p.setPen(QPen(bk, 1))
            p.drawRect(xpos-2, 8+(i*6), 4, 3)

    elif n == "about":
        p.setPen(QPen(bk, 2))
        p.setBrush(QBrush(wh))
        p.drawEllipse(2, 2, s-4, s-4)
        f = font_chicago(14, True)
        p.setFont(f)
        p.setPen(bk)
        p.drawText(QRect(0, 0, s, s), Qt.AlignCenter, "i")

    elif n == "macpaint":
        # MacPaint icon — canvas with pencil and bucket
        bbox(2, 2, s-4, s-4, wh, bk, 1)
        # canvas area (light blue tint)
        p.fillRect(3, 3, s-6, s-10, QColor(0xDD, 0xEE, 0xFF))
        # horizontal grid lines on canvas
        p.setPen(QPen(QColor(0xBB, 0xCC, 0xDD), 1))
        for gy2 in range(7, s-10, 5):
            p.drawLine(3, gy2, s-4, gy2)
        # pencil — diagonal line top-right to mid
        p.setPen(QPen(bk, 1))
        p.drawLine(s-8, 5, s//2+2, s//2)
        p.fillRect(s-9, 4, 3, 3, QColor(0xEE, 0xCC, 0x88))  # pencil tip
        # bucket bottom left
        bucket = [
            QPoint(4, s-8), QPoint(4, s-4),
            QPoint(10, s-4), QPoint(10, s-8),
            QPoint(8, s-11), QPoint(6, s-11),
        ]
        p.setBrush(QBrush(QColor(0x44, 0x88, 0xFF)))
        p.setPen(QPen(bk, 1))
        p.drawPolygon(QPolygon(bucket))
        # tool palette strip on right
        p.fillRect(s-7, 3, 5, s-6, QColor(0xCC, 0xCC, 0xCC))
        p.setPen(QPen(bk, 1))
        p.drawLine(s-7, 3, s-7, s-4)

    elif n == "stickies":
        p.fillRect(2, 2, s-4, s-6, QColor(0xFF, 0xFF, 0x99))
        p.fillRect(6, 6, s-4, s-6, QColor(0xCC, 0xFF, 0x99))
        p.setPen(QPen(bk, 1))
        p.drawRect(2, 2, s-5, s-7)
        p.drawRect(6, 6, s-5, s-7)
        p.setPen(QPen(gy, 1))
        for row in range(3):
            p.drawLine(9, 12+row*4, s-4, 12+row*4)

    elif n == "puzzle":
        # 15-puzzle icon
        p.fillRect(2, 2, s-4, s-4, lt)
        p.setPen(QPen(bk, 1))
        p.drawRect(2, 2, s-5, s-5)
        cell = (s-6)//4
        for row in range(4):
            for col in range(4):
                if row == 3 and col == 3:
                    continue  # missing piece
                cx2 = 3 + col*cell
                cy2 = 3 + row*cell
                p.fillRect(cx2, cy2, cell-1, cell-1, wh)
                p.drawRect(cx2, cy2, cell-2, cell-2)
                p.setFont(font_chicago(5))
                n2 = row*4+col+1
                p.drawText(QRect(cx2, cy2, cell-2, cell-2), Qt.AlignCenter, str(n2))

    elif n == "scrapbook":
        # Scrapbook icon — album pages
        p.fillRect(4, 6, s-8, s-8, QColor(0xFF, 0xEE, 0xCC))
        p.fillRect(2, 4, s-8, s-8, QColor(0xFF, 0xFF, 0xEE))
        p.fillRect(6, 8, s-8, s-8, wh)
        p.setPen(QPen(bk, 1))
        p.drawRect(6, 8, s-9, s-9)
        # small picture in scrapbook
        p.fillRect(8, 10, 12, 10, QColor(0xCC, 0xDD, 0xFF))
        p.setPen(QPen(QColor(0x88, 0x88, 0xAA), 1))
        p.drawLine(8, 16, 14, 12)
        p.drawLine(14, 12, 20, 18)

    elif n == "calculator":
        # Proper calculator icon — silver body with display + buttons
        # Body
        p.fillRect(3, 2, s-6, s-4, QColor(0xDD, 0xDD, 0xDD))
        p.setPen(QPen(bk, 1))
        p.drawRoundedRect(3, 2, s-7, s-5, 2, 2)
        # Top highlight bevel
        p.setPen(QPen(QColor(0xFF, 0xFF, 0xFF), 1))
        p.drawLine(4, 3, s-5, 3)
        p.drawLine(4, 3, 4, s-4)
        p.setPen(QPen(QColor(0x99, 0x99, 0x99), 1))
        p.drawLine(s-5, 3, s-5, s-4)
        p.drawLine(4, s-4, s-5, s-4)
        # Display — green LCD
        p.fillRect(6, 5, s-12, 9, QColor(0x77, 0xAA, 0x77))
        p.setPen(QPen(QColor(0x44, 0x77, 0x44), 1))
        p.drawRect(6, 5, s-13, 8)
        # "8" digit segments inside display
        p.setPen(QPen(QColor(0x00, 0x44, 0x00), 1))
        p.setFont(font_chicago(6, True))
        p.drawText(QRect(6, 5, s-12, 9), Qt.AlignRight | Qt.AlignVCenter, "0 ")
        # Button grid — 4 cols × 4 rows
        cols_b, rows_b = 4, 4
        bw = (s - 10) // cols_b
        bh = 4
        btn_colors = [
            QColor(0xCC, 0xCC, 0xCC),  # gray ops
            QColor(0xCC, 0xCC, 0xCC),
            QColor(0xCC, 0xCC, 0xCC),
            QColor(0xEE, 0xAA, 0x44),  # orange = ops
        ]
        for row_b in range(rows_b):
            for col_b in range(cols_b):
                bx2 = 5 + col_b * bw
                by2 = 16 + row_b * (bh + 2)
                col_fill = btn_colors[col_b] if row_b < 3 else QColor(0xBB, 0xBB, 0xBB)
                p.fillRect(bx2, by2, bw-1, bh, col_fill)
                p.setPen(QPen(QColor(0x77, 0x77, 0x77), 1))
                p.drawRect(bx2, by2, bw-2, bh-1)

    elif n == "alarm_clock":
        # Alarm clock icon
        p.setPen(QPen(bk, 1))
        p.setBrush(QBrush(lt))
        p.drawEllipse(4, 6, s-10, s-10)
        # clock hands
        mid2 = s//2
        p.drawLine(mid2, mid2, mid2, mid2-6)  # minute
        p.drawLine(mid2, mid2, mid2+4, mid2+2) # hour
        # bells top
        p.setPen(QPen(bk, 2))
        p.drawLine(4, 6, 2, 2)
        p.drawLine(s-6, 6, s-2, 2)
        # feet
        p.drawLine(6, s-5, 4, s-2)
        p.drawLine(s-6, s-5, s-4, s-2)

    elif n == "clock":
        # Round clock face with numerals
        # Shadow
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(0x88, 0x88, 0x88, 120)))
        p.drawEllipse(4, 5, s-6, s-6)
        # Face
        p.setBrush(QBrush(QColor(0xFF, 0xFF, 0xF8)))
        p.setPen(QPen(bk, 2))
        p.drawEllipse(2, 2, s-6, s-6)
        # Bezel highlight
        p.setPen(QPen(QColor(0xFF, 0xFF, 0xFF), 1))
        p.drawArc(3, 3, s-8, s-8, 45*16, 180*16)
        # Hour markers
        cx3, cy3 = s//2 - 1, s//2 - 1
        r_outer = (s-8)//2
        p.setPen(QPen(bk, 1))
        for i in range(12):
            ang = math.radians(i * 30 - 90)
            x1 = int(cx3 + (r_outer-2) * math.cos(ang))
            y1 = int(cy3 + (r_outer-2) * math.sin(ang))
            x2 = int(cx3 + (r_outer-4 if i % 3 != 0 else r_outer-5) * math.cos(ang))
            y2 = int(cy3 + (r_outer-4 if i % 3 != 0 else r_outer-5) * math.sin(ang))
            p.setPen(QPen(bk, 2 if i % 3 == 0 else 1))
            p.drawLine(x1, y1, x2, y2)
        # Hour hand (10:10 position)
        p.setPen(QPen(bk, 2))
        h_ang = math.radians(300 - 90)  # 10 o'clock
        p.drawLine(cx3, cy3, int(cx3 + r_outer*0.5*math.cos(h_ang)), int(cy3 + r_outer*0.5*math.sin(h_ang)))
        # Minute hand
        m_ang = math.radians(60 - 90)   # :10 minutes
        p.drawLine(cx3, cy3, int(cx3 + r_outer*0.7*math.cos(m_ang)), int(cy3 + r_outer*0.7*math.sin(m_ang)))
        # Center dot
        p.setBrush(QBrush(bk)); p.setPen(Qt.NoPen)
        p.drawEllipse(cx3-2, cy3-2, 4, 4)

    elif n == "chooser":
        bbox(2, 2, s-4, s-4, lt, bk, 1)
        p.setPen(QPen(bk, 1))
        # zones list on left
        p.fillRect(4, 8, (s-8)//2, s-12, wh)
        p.drawRect(4, 8, (s-8)//2-1, s-13)
        # device list on right
        rx = 4 + (s-8)//2 + 2
        p.fillRect(rx, 8, s-rx-3, s-12, wh)
        p.drawRect(rx, 8, s-rx-4, s-13)
        # small icons in right pane
        for i in range(3):
            draw_icon(p, "finder", rx+2, 10+i*8, 6)

    else:
        # Generic document with dog-ear
        bbox(4, 2, s-8, s-4, wh, bk, 1)
        p.fillRect(s-12, 2, 8, 8, gy)
        p.setPen(QPen(bk, 1))
        p.drawLine(s-12, 2, s-12, 10)
        p.drawLine(s-12, 10, s-4, 10)
        p.setPen(QPen(gy, 1))
        for row in range(4):
            p.drawLine(7, 14+row*5, s-8, 14+row*5)

    p.restore()


def draw_3d_box(p: QPainter, x, y, w, h):
    """System 7 bevelled 3D box (raised)."""
    # Light edge top+left
    p.setPen(QPen(C_WHITE, 1))
    p.drawLine(x, y, x+w-2, y)
    p.drawLine(x, y, x, y+h-2)
    # Shadow edge bottom+right
    p.setPen(QPen(C_BLACK, 1))
    p.drawLine(x+w-1, y, x+w-1, y+h-1)
    p.drawLine(x, y+h-1, x+w-1, y+h-1)
    # Inner shadow
    p.setPen(QPen(C_PLATINUM_DK, 1))
    p.drawLine(x+w-2, y+1, x+w-2, y+h-2)
    p.drawLine(x+1, y+h-2, x+w-2, y+h-2)
    # Fill
    p.fillRect(x+1, y+1, w-3, h-3, C_PLATINUM)


def draw_button(p: QPainter, x, y, w, h, text, pressed=False, default=False):
    """System 7 style push button."""
    if default:
        p.setPen(QPen(C_BLACK, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(x-3, y-3, w+6, h+6, 4, 4)

    if pressed:
        p.fillRect(x, y, w, h, C_PLATINUM_DK)
        p.setPen(QPen(C_BLACK, 1))
        p.drawLine(x, y, x+w-1, y)
        p.drawLine(x, y, x, y+h-1)
        p.setPen(QPen(C_WHITE, 1))
        p.drawLine(x+w-1, y, x+w-1, y+h-1)
        p.drawLine(x, y+h-1, x+w-1, y+h-1)
    else:
        draw_3d_box(p, x, y, w, h)

    p.setFont(font_chicago(11, default))
    p.setPen(C_BLACK)
    p.drawText(QRect(x, y, w, h), Qt.AlignCenter, text)


# ─────────────────────────────────────────────────────────────
#  VIRTUAL FILESYSTEM
# ─────────────────────────────────────────────────────────────
class VFS:
    def __init__(self):
        self.tree = {"/": {
            "System Folder": {
                "Preferences": {},
                "Fonts": {},
                "Extensions": {},
                "Control Panels": {},
            },
            "Applications": {
                "Calculator":  {"__type": "app", "__target": "calculator"},
                "Terminal":    {"__type": "app", "__target": "terminal"},
                "Browser":     {"__type": "app", "__target": "browser"},
                "Note Pad":    {"__type": "app", "__target": "notepad"},
                "Control Panels": {"__type": "app", "__target": "settings"},
                "Stickies":    {"__type": "app", "__target": "stickies"},
                "MacPaint":    {"__type": "app", "__target": "macpaint"},
                "Puzzle":      {"__type": "app", "__target": "puzzle"},
                "Scrapbook":   {"__type": "app", "__target": "scrapbook"},
                "Clock":       {"__type": "app", "__target": "clock"},
            },
            "Other": {
                "Calculator":  {"__type": "app", "__target": "calculator"},
                "Clock":       {"__type": "app", "__target": "clock"},
                "Note Pad":    {"__type": "app", "__target": "notepad"},
                "Terminal":    {"__type": "app", "__target": "terminal"},
                "MacPaint":    {"__type": "app", "__target": "macpaint"},
                "Scrapbook":   {"__type": "app", "__target": "scrapbook"},
                "Puzzle":      {"__type": "app", "__target": "puzzle"},
                "Control Panels": {"__type": "app", "__target": "settings"},
            },
            "Documents": {
                "Read Me.txt": {"__type": "file",
                    "__content": "Welcome to ClassicOS 7.5!\n\nThis is a Mac System 7.5 Platinum\nstyle desktop environment built\nwith Python and PyQt5.\n\nEnjoy the nostalgia!"},
                "Untitled.txt": {"__type": "file", "__content": ""},
            },
            "Trash": {},
        }}

    def resolve(self, path):
        parts = [p for p in path.strip("/").split("/") if p]
        node = self.tree["/"]
        for part in parts:
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return None
        return node

    def listdir(self, path):
        node = self.resolve(path) if path != "/" else self.tree["/"]
        if path == "/":
            node = self.tree["/"]
        if isinstance(node, dict):
            return [k for k in node if not k.startswith("__")]
        return []

    def read(self, path):
        node = self.resolve(path)
        if isinstance(node, dict):
            return node.get("__content", "")
        return ""

    def write(self, path, content):
        parts = path.strip("/").split("/")
        node = self.tree["/"]
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        fname = parts[-1]
        if fname in node and isinstance(node[fname], dict):
            node[fname]["__content"] = content
        else:
            node[fname] = {"__type": "file", "__content": content}

    def mkdir(self, path):
        parts = path.strip("/").split("/")
        node = self.tree["/"]
        for part in parts:
            node = node.setdefault(part, {})

    def isdir(self, path):
        if path == "/":
            return True
        node = self.resolve(path)
        return isinstance(node, dict) and "__type" not in node

    def isfile(self, path):
        node = self.resolve(path)
        return isinstance(node, dict) and node.get("__type") == "file"

    def isapp(self, path):
        node = self.resolve(path)
        return isinstance(node, dict) and node.get("__type") == "app"


VFS_INST = VFS()


# ─────────────────────────────────────────────────────────────
#  WINDOW MANAGER
# ─────────────────────────────────────────────────────────────
class WindowManager(QObject):
    changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.windows = []
        self._z = 100

    def register(self, w):
        self.windows.append(w)
        self._z += 1
        w._z = self._z
        self.changed.emit()

    def unregister(self, w):
        if w in self.windows:
            self.windows.remove(w)
        self.changed.emit()

    def raise_window(self, w):
        self._z += 1
        w._z = self._z
        w.raise_()
        for win in self.windows:
            win.set_active(win is w)

    def get_active(self):
        if not self.windows:
            return None
        return max(self.windows, key=lambda w: w._z)

    def tile(self, rect):
        vis = [w for w in self.windows if not w._minimized]
        if not vis:
            return
        cols = max(1, math.ceil(math.sqrt(len(vis))))
        rows = math.ceil(len(vis) / cols)
        ww = rect.width() // cols
        wh = rect.height() // rows
        for i, win in enumerate(vis):
            c, r = i % cols, i // cols
            win.move(rect.x() + c*ww + 2, rect.y() + r*wh + 2)
            win.resize(ww - 4, wh - 4)


WM = WindowManager()


# ─────────────────────────────────────────────────────────────
#  SYSTEM 7.5 WINDOW BASE
# ─────────────────────────────────────────────────────────────
class Mac75Window(QWidget):
    TITLE_H    = 22
    RESIZE_SZ  = 14
    SCROLL_W   = 16

    def __init__(self, parent, title: str, icon: str = "about",
                 has_scroll=False, has_resize=True, has_zoom=True):
        super().__init__(parent)
        self.title       = title
        self.icon_name   = icon
        self._active     = True
        self._z          = 0
        self._minimized  = False
        self._min_geom   = None
        self._drag_pos   = None
        self._rsz_mode   = False
        self._rsz_start  = None
        self._rsz_geom   = None
        self._wire_drag  = False
        self._wire_rect  = None
        self._close_pressed = False
        self._has_resize = has_resize
        self._has_zoom   = has_zoom
        self._zoomed     = False
        self._zoom_geom  = None
        self._anim       = None

        self.setWindowFlags(Qt.SubWindow)
        self.setAttribute(Qt.WA_StyledBackground, False)
        self.setMouseTracking(True)
        self.resize(480, 320)

        # Content widget (scrolled area)
        self._content = QWidget(self)
        self._content.setStyleSheet("background: white;")
        self._content.move(0, self.TITLE_H)
        self._content.resize(self.width(), self.height() - self.TITLE_H)

        self._skip_default_anim = False
        WM.register(self)
        # Animate open — deferred so open_window() can move() us first
        QTimer.singleShot(0, self._animate_open)
        self.show()

    # ── animation helpers ──────────────────────────────────────
    def _animate_open(self):
        if self._skip_default_anim:
            return
        g = self.geometry()
        self._final_geom = g
        cx, cy = g.center().x(), g.center().y()
        start = QRect(cx - 1, cy - 1, 2, 2)
        self.setGeometry(start)
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(180)
        self._anim.setStartValue(start)
        self._anim.setEndValue(g)
        self._anim.setEasingCurve(QEasingCurve.OutQuart)
        self._anim.start()

    def animate_open_from(self, from_rect):
        self._skip_default_anim = True
        if self._anim:
            self._anim.stop()
        g = self.geometry()
        self._final_geom = g
        start = QRect(from_rect.center().x() - 1, from_rect.center().y() - 1, 2, 2)
        self.setGeometry(start)
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(180)
        self._anim.setStartValue(start)
        self._anim.setEndValue(g)
        self._anim.setEasingCurve(QEasingCurve.OutQuart)
        self._anim.start()

    def _animate_close(self, callback):
        g = self.geometry()
        cx, cy = g.center().x(), g.center().y()
        end = QRect(cx - 1, cy - 1, 2, 2)
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(140)
        self._anim.setStartValue(g)
        self._anim.setEndValue(end)
        self._anim.setEasingCurve(QEasingCurve.InQuart)
        self._anim.finished.connect(callback)
        self._anim.start()

    def content_widget(self):
        return self._content

    def set_active(self, active: bool):
        self._active = active
        self.update()

    def close_window(self):
        desk = self.parent()
        win_geom = self._min_geom if self._minimized and self._min_geom else self.geometry()
        target_rect = self._find_icon_rect()
        if target_rect is None:
            target_rect = QRect(desk.width()//2 - 24, desk.height() - 24, 48, 48)
        WM.unregister(self)
        self.hide()
        if hasattr(desk, '_zoom_rects_close'):
            desk._zoom_rects_close(win_geom, target_rect)
        QTimer.singleShot(_ZoomRectsOverlay.DURATION_MS, self.deleteLater)

    def _find_icon_rect(self):
        """Find the desktop icon that corresponds to this window."""
        src = getattr(self, '_icon_src_rect', None)
        if src:
            return src
        desk = self.parent()
        if not hasattr(desk, 'findChildren'):
            return None
        # Prefer explicit target set by open_window
        my_target = getattr(self, "_icon_target", None)
        for ic in desk.findChildren(DesktopIcon75):
            if my_target and ic.target == my_target:
                return ic.geometry()
        # Fallback: fuzzy title match
        win_title = self.title.lower().replace(" ", "_")
        for ic in desk.findChildren(DesktopIcon75):
            tgt = ic.target.lower().replace(" ", "_")
            if tgt == win_title or tgt in win_title or win_title in tgt:
                return ic.geometry()
        return None

    def minimize(self):
        if self._minimized:
            return
        self._min_geom = self.geometry()
        self._minimized = True
        parent = self.parent()
        icon_rect = self._find_icon_rect()
        if icon_rect:
            target = icon_rect
        else:
            target = QRect(parent.width()//2 - 40, parent.height() - 40, 80, 80)
        self._icon_rect = target
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(200)
        self._anim.setStartValue(self.geometry())
        self._anim.setEndValue(target)
        self._anim.setEasingCurve(QEasingCurve.InQuart)
        self._anim.finished.connect(self.hide)
        self._anim.start()
        WM.changed.emit()

    def restore(self):
        if not self._minimized or not self._min_geom:
            return
        self._minimized = False
        start = getattr(self, "_icon_rect", None) or self._find_icon_rect()
        if start is None:
            parent = self.parent()
            start = QRect(parent.width()//2 - 40, parent.height() - 40, 80, 80)
        self.setGeometry(start)
        self.show()
        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(220)
        self._anim.setStartValue(start)
        self._anim.setEndValue(self._min_geom)
        self._anim.setEasingCurve(QEasingCurve.OutQuart)
        self._anim.start()
        WM.raise_window(self)
        WM.changed.emit()

    def zoom(self):
        """Zoom box — toggle between normal and maximised."""
        if not self._zoomed:
            self._zoom_geom = self.geometry()
            parent = self.parent()
            target = QRect(0, 22, parent.width() - 80, parent.height() - 44)
            self._anim = QPropertyAnimation(self, b"geometry")
            self._anim.setDuration(150)
            self._anim.setStartValue(self.geometry())
            self._anim.setEndValue(target)
            self._anim.setEasingCurve(QEasingCurve.OutQuart)
            self._anim.start()
            self._zoomed = True
        else:
            self._anim = QPropertyAnimation(self, b"geometry")
            self._anim.setDuration(150)
            self._anim.setStartValue(self.geometry())
            self._anim.setEndValue(self._zoom_geom)
            self._anim.setEasingCurve(QEasingCurve.OutQuart)
            self._anim.start()
            self._zoomed = False

    def resizeEvent(self, e):
        self._content.resize(self.width(), self.height() - self.TITLE_H)
        self._relayout()
        super().resizeEvent(e)

    def _relayout(self):
        pass

    # ── System 7.5 Platinum painting ──────────────────────────
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        W, H = self.width(), self.height()
        TH = self.TITLE_H

        # Drop shadow — solid black offset 2px right+down
        p.fillRect(2, 2, W - 1, H - 1, C_BLACK)

        # Outer border — 1px black on all four sides
        p.setPen(QPen(C_BLACK, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(0, 0, W - 3, H - 3)

        # Inner bevel: white top+left (raised), dark bottom+right
        p.setPen(QPen(C_WHITE, 1))
        p.drawLine(1, 1, W - 4, 1)
        p.drawLine(1, 1, 1, H - 4)
        p.setPen(QPen(C_PLATINUM_DK, 1))
        p.drawLine(W - 3, 1, W - 3, H - 3)
        p.drawLine(1, H - 3, W - 3, H - 3)

        # Title bar
        self._paint_titlebar(p, W - 2, TH)

        # Content background
        p.fillRect(2, TH, W - 5, H - TH - 4, C_WIN_BG)

        # Separator line below title
        p.setPen(QPen(C_BLACK, 1))
        p.drawLine(1, TH, W - 4, TH)

        # Resize grip
        if self._has_resize:
            self._paint_resize(p, W - 2, H - 2)

    def _paint_titlebar(self, p, W, TH):
        """Paint System 7.5 striped title bar."""
        # Background
        if self._active:
            p.fillRect(2, 2, W-4, TH-2, C_PLATINUM)
            # Horizontal stripes — the distinctive System 7 look
            for y in range(4, TH-2, 2):
                p.setPen(QPen(C_TITLE_STRIPE2, 1))
                p.drawLine(20, y, W-20, y)
                if y+1 < TH-2:
                    p.setPen(QPen(C_WHITE, 1))
                    p.drawLine(20, y+1, W-20, y+1)
        else:
            # Inactive: solid boring gray, no stripes at all
            p.fillRect(2, 2, W-4, TH-2, C_INACTIVE_TITLE)

        # Close box — only visible when active (plain square, no X, System 7 style)
        if self._active:
            cb_x, cb_y, cb_s = 6, 5, 12
            if self._close_pressed:
                p.fillRect(cb_x, cb_y, cb_s, cb_s, C_BLACK)
                p.setPen(QPen(C_WHITE, 1))
                p.drawRect(cb_x, cb_y, cb_s-1, cb_s-1)
                p.drawRect(cb_x+2, cb_y+2, cb_s-5, cb_s-5)
            else:
                p.fillRect(cb_x, cb_y, cb_s, cb_s, C_WHITE)
                p.setPen(QPen(C_BLACK, 1))
                p.drawRect(cb_x, cb_y, cb_s-1, cb_s-1)
                # Inner recessed square (the real System 7 close box look)
                p.drawRect(cb_x+2, cb_y+2, cb_s-5, cb_s-5)

        # Collapse/WindowShade box (left of zoom) — active only
        if self._has_zoom and self._active:
            cb_s = 12
            # Collapse box (windowshade) — second from right
            col_x = W - 36
            cb_y = 5
            p.fillRect(col_x, cb_y, cb_s, cb_s, C_WHITE)
            p.setPen(QPen(C_BLACK, 1))
            p.drawRect(col_x, cb_y, cb_s-1, cb_s-1)
            # Horizontal line in middle = collapse symbol
            p.drawLine(col_x+3, cb_y+5, col_x+8, cb_y+5)

        # Zoom box (right side) — active only
        if self._has_zoom and self._active:
            cb_s = 12
            zb_x = W - 19
            cb_y = 5
            p.fillRect(zb_x, cb_y, cb_s, cb_s, C_WHITE)
            p.setPen(QPen(C_BLACK, 1))
            p.drawRect(zb_x, cb_y, cb_s-1, cb_s-1)
            # Classic Mac zoom box: small rect inside + offset big rect
            p.drawRect(zb_x+1, cb_y+3, cb_s-5, cb_s-5)
            p.drawRect(zb_x+3, cb_y+1, cb_s-5, cb_s-5)

        # Title text
        p.setFont(font_chicago(11, True))
        p.setPen(C_BLACK if self._active else C_PLATINUM_DK)
        p.drawText(QRect(22, 2, W-50, TH-2), Qt.AlignCenter, self.title)

    def _paint_resize(self, p, W, H):
        """System 7 grow box (bottom-right corner) — visible resize handle."""
        sz = 16
        gx = W - sz - 2
        gy = H - sz - 2
        # Platinum fill
        p.fillRect(gx, gy, sz, sz, C_PLATINUM)
        # Black border
        p.setPen(QPen(C_BLACK, 1))
        p.drawRect(gx, gy, sz - 1, sz - 1)
        # White top+left bevel
        p.setPen(QPen(C_WHITE, 1))
        p.drawLine(gx + 1, gy + 1, gx + sz - 2, gy + 1)
        p.drawLine(gx + 1, gy + 1, gx + 1, gy + sz - 2)
        # Dark diagonal lines (classic Mac grow icon hatching)
        p.setPen(QPen(C_BLACK, 1))
        for offset in range(3, sz - 1, 4):
            p.drawLine(gx + offset,     gy + sz - 3,
                       gx + sz - 3,    gy + offset)
        # Tiny inner square (classic double-box grow icon)
        inner = 5
        p.drawRect(gx + sz - inner - 2, gy + sz - inner - 2, inner, inner)

    # ── mouse events ───────────────────────────────────────────
    def _close_rect(self):
        return QRect(6, 5, 12, 12)

    def _zoom_rect(self):
        return QRect(self.width()-19, 5, 12, 12)

    def _collapse_rect(self):
        return QRect(self.width()-36, 5, 12, 12)

    def _resize_rect(self):
        W, H = self.width(), self.height()
        sz = 16
        return QRect(W - sz - 4, H - sz - 4, sz + 4, sz + 4)

    def mousePressEvent(self, e):
        WM.raise_window(self)
        pos = e.pos()
        if e.button() != Qt.LeftButton:
            return
        if self._close_rect().contains(pos):
            self._close_pressed = True
            self.update()
            return
        if self._has_zoom and self._collapse_rect().contains(pos):
            self._windowshade()
            return
        if self._has_zoom and self._zoom_rect().contains(pos):
            self.zoom()
            return
        if self._has_resize and self._resize_rect().contains(pos):
            self._rsz_mode = True
            self._rsz_start = e.globalPos()
            self._rsz_geom = self.geometry()
            return
        if pos.y() < self.TITLE_H:
            # Wireframe drag: record start position, don't move yet
            self._drag_pos   = e.globalPos() - self.frameGeometry().topLeft()
            self._wire_rect  = self.geometry()   # current window rect in parent coords
            self._wire_drag  = True
            # Tell desktop to show wireframe
            desk = self.parent()
            if hasattr(desk, '_set_wireframe'):
                desk._set_wireframe(self._wire_rect)
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() & Qt.LeftButton and self._wire_drag:
            # Update wireframe rect on desktop — don't move actual window
            new_pos = e.globalPos() - self._drag_pos
            # Convert global → parent-local
            desk = self.parent()
            local = desk.mapFromGlobal(new_pos)
            self._wire_rect = QRect(local, self.size())
            if hasattr(desk, '_set_wireframe'):
                desk._set_wireframe(self._wire_rect)
            return
        if self._rsz_mode and e.buttons() & Qt.LeftButton:
            d = e.globalPos() - self._rsz_start
            g = self._rsz_geom
            self.resize(max(200, g.width()+d.x()), max(100, g.height()+d.y()))
            return
        # cursor hints
        if self._has_resize and self._resize_rect().contains(e.pos()):
            self.setCursor(Qt.SizeFDiagCursor)
        elif e.pos().y() < self.TITLE_H:
            self.setCursor(Qt.SizeAllCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, e):
        if self._close_pressed:
            self._close_pressed = False
            self.update()
            if self._close_rect().contains(e.pos()):
                self.close_window()
            return
        if self._wire_drag and self._wire_rect:
            # Teleport window to wireframe position
            self.move(self._wire_rect.topLeft())
        self._drag_pos  = None
        self._rsz_mode  = False
        self._wire_drag = False
        self._wire_rect = None
        desk = self.parent()
        if hasattr(desk, '_clear_wireframe'):
            desk._clear_wireframe()

    def mouseDoubleClickEvent(self, e):
        if e.pos().y() < self.TITLE_H:
            self._windowshade()

    def _windowshade(self):
        """WindowShade: collapse/restore window to just its title bar."""
        if not self._minimized:
            # Collapse — save full geometry, shrink to title bar height only
            self._min_geom = self.geometry()
            self._minimized = True
            target = QRect(self.x(), self.y(), self.width(), self.TITLE_H + 2)
            self._anim = QPropertyAnimation(self, b"geometry")
            self._anim.setDuration(120)
            self._anim.setStartValue(self.geometry())
            self._anim.setEndValue(target)
            self._anim.setEasingCurve(QEasingCurve.InCubic)
            self._anim.start()
            WM.changed.emit()
        else:
            # Restore to full size
            self._minimized = False
            if self._min_geom:
                self._anim = QPropertyAnimation(self, b"geometry")
                self._anim.setDuration(140)
                self._anim.setStartValue(self.geometry())
                self._anim.setEndValue(self._min_geom)
                self._anim.setEasingCurve(QEasingCurve.OutCubic)
                self._anim.start()
            WM.raise_window(self)
            WM.changed.emit()


# ─────────────────────────────────────────────────────────────
#  SYSTEM 7.5 SCROLLBAR  (drawn widget)
# ─────────────────────────────────────────────────────────────
class Mac75ScrollBar(QScrollBar):
    """QScrollBar with System 7.5 platinum painting override."""
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setStyleSheet("")  # remove Qt default styling

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        W, H = self.width(), self.height()
        vert = self.orientation() == Qt.Vertical

        # --- Dithered track background (2x2 checkerboard, white+gray) ---
        arrow_sz = 16
        if vert:
            track_top = arrow_sz
            track_h = H - 2 * arrow_sz
            tx, ty, tw, th = 0, track_top, W, track_h
        else:
            track_left = arrow_sz
            track_w = W - 2 * arrow_sz
            tx, ty, tw, th = track_left, 0, track_w, H

        # Fill dither pattern pixel by pixel via QImage for performance
        img = QImage(tw, th, QImage.Format_RGB32)
        for iy in range(th):
            for ix in range(tw):
                if (ix + iy) % 2 == 0:
                    img.setPixel(ix, iy, 0xFFFFFF)
                else:
                    img.setPixel(ix, iy, 0xAAAAAA)
        p.drawImage(tx, ty, img)

        # --- Arrow buttons ---
        p.setPen(QPen(C_BLACK, 1))
        if vert:
            mid = W // 2
            # Up arrow button
            draw_3d_box(p, 0, 0, W, arrow_sz)
            # Up triangle (pointing up)
            pts_up = QPolygon([QPoint(mid, 4), QPoint(mid-4, 11), QPoint(mid+4, 11)])
            p.setBrush(QBrush(C_BLACK))
            p.drawPolygon(pts_up)
            # Down arrow button
            draw_3d_box(p, 0, H - arrow_sz, W, arrow_sz)
            # Down triangle (pointing down)
            pts_dn = QPolygon([QPoint(mid, H-4), QPoint(mid-4, H-11), QPoint(mid+4, H-11)])
            p.drawPolygon(pts_dn)
            # Thumb
            if self.maximum() > 0:
                ratio = (self.value() - self.minimum()) / (self.maximum() - self.minimum())
                thumb_h = max(20, int(track_h * self.pageStep() / max(1, self.maximum() + self.pageStep())))
                thumb_y = track_top + int((track_h - thumb_h) * ratio)
                # Thumb body with raised bevel
                draw_3d_box(p, 1, thumb_y, W - 2, thumb_h)
                # Textured horizontal ribbing on thumb
                p.setPen(QPen(C_PLATINUM_DK, 1))
                for rib in range(thumb_y + 4, thumb_y + thumb_h - 3, 3):
                    p.drawLine(3, rib, W - 4, rib)
                p.setPen(QPen(C_WHITE, 1))
                for rib in range(thumb_y + 5, thumb_y + thumb_h - 3, 3):
                    p.drawLine(3, rib, W - 4, rib)
        else:
            mid = H // 2
            # Left arrow button
            draw_3d_box(p, 0, 0, arrow_sz, H)
            pts_lft = QPolygon([QPoint(4, mid), QPoint(11, mid - 4), QPoint(11, mid + 4)])
            p.setBrush(QBrush(C_BLACK))
            p.drawPolygon(pts_lft)
            # Right arrow button
            draw_3d_box(p, W - arrow_sz, 0, arrow_sz, H)
            pts_rt = QPolygon([QPoint(W - 4, mid), QPoint(W - 11, mid - 4), QPoint(W - 11, mid + 4)])
            p.drawPolygon(pts_rt)
            # Thumb
            if self.maximum() > 0:
                ratio = (self.value() - self.minimum()) / (self.maximum() - self.minimum())
                thumb_w = max(20, int(track_w * self.pageStep() / max(1, self.maximum() + self.pageStep())))
                thumb_x = track_left + int((track_w - thumb_w) * ratio)
                draw_3d_box(p, thumb_x, 1, thumb_w, H - 2)
                p.setPen(QPen(C_PLATINUM_DK, 1))
                for rib in range(thumb_x + 4, thumb_x + thumb_w - 3, 3):
                    p.drawLine(rib, 3, rib, H - 4)
                p.setPen(QPen(C_WHITE, 1))
                for rib in range(thumb_x + 5, thumb_x + thumb_w - 3, 3):
                    p.drawLine(rib, 3, rib, H - 4)


# ─────────────────────────────────────────────────────────────
#  SYSTEM 7.5 BUTTON WIDGET
# ─────────────────────────────────────────────────────────────
class Mac75Button(QAbstractButton):
    def __init__(self, text, parent=None, default=False, small=False):
        super().__init__(parent)
        self.setText(text)
        self._default = default
        self._small = small
        sz = 9 if small else 11
        self.setFont(font_chicago(sz, default))
        h = 18 if small else 22
        self.setFixedHeight(h)
        fm = QFontMetrics(self.font())
        self.setMinimumWidth(fm.horizontalAdvance(text) + 20)

    def paintEvent(self, e):
        p = QPainter(self)
        draw_button(p, 0, 0, self.width(), self.height(),
                    self.text(), self.isDown(), self._default)

    def sizeHint(self):
        fm = QFontMetrics(self.font())
        return QSize(fm.horizontalAdvance(self.text()) + 20,
                     18 if self._small else 22)


# ─────────────────────────────────────────────────────────────
#  SYSTEM 7.5 PUSH BUTTON  (convenience QPushButton skin)
# ─────────────────────────────────────────────────────────────
def make_toolbar_btn(text, small=True):
    b = QPushButton(text)
    b.setFont(font_chicago(9 if small else 11))
    h = 18 if small else 20
    b.setFixedHeight(h)
    b.setStyleSheet(
        "QPushButton{"
        f"  background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        f"    stop:0 #EEEEEE, stop:1 #AAAAAA);"
        "  border: 1px solid #000;"
        "  padding: 0 6px;"
        "}"
        "QPushButton:pressed{"
        "  background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
        "    stop:0 #AAAAAA, stop:1 #EEEEEE);"
        "}"
    )
    return b


# ─────────────────────────────────────────────────────────────
#  SYSTEM 7.5 DIALOG
# ─────────────────────────────────────────────────────────────
class Mac75Dialog(QDialog):
    def __init__(self, parent, title="", message="", buttons=None, icon_kind="info"):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(True)
        self._result = None

        # outer shadow border
        self.setStyleSheet("background: #CCCCCC;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(2, 2, 2, 2)
        outer.setSpacing(0)

        # Raised border
        frame = QWidget()
        frame.setStyleSheet(
            "background:#CCCCCC;"
            "border:1px solid #000;"
        )
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(12, 10, 12, 10)
        fl.setSpacing(10)
        outer.addWidget(frame)

        # Icon + text row
        row = QHBoxLayout()
        row.setSpacing(12)

        icon_w = _IconWidget(icon_kind)
        row.addWidget(icon_w, 0, Qt.AlignTop)

        msg_lbl = QLabel(message)
        msg_lbl.setFont(font_chicago(12))
        msg_lbl.setWordWrap(True)
        msg_lbl.setMinimumWidth(220)
        msg_lbl.setStyleSheet("background: transparent;")
        row.addWidget(msg_lbl, 1)
        fl.addLayout(row)

        # Separator
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:#000;")
        fl.addWidget(sep)

        # Buttons
        btns = buttons or [("OK", True)]
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        for label, is_default in btns:
            b = Mac75Button(label, default=is_default)
            b.clicked.connect(lambda _, l=label: self._click(l))
            btn_row.addWidget(b)
        fl.addLayout(btn_row)

        self.adjustSize()
        self.setFixedSize(max(300, self.width()), self.height())
        if parent:
            pg = parent.rect()
            self.move(parent.mapToGlobal(pg.center()) - self.rect().center())

    def _click(self, label):
        self._result = label
        self.accept()

    @staticmethod
    def info(parent, title, msg):
        Mac75Dialog(parent, title, msg, [("OK", True)], "info").exec_()

    @staticmethod
    def warning(parent, title, msg):
        Mac75Dialog(parent, title, msg, [("OK", True)], "stop").exec_()

    @staticmethod
    def question(parent, title, msg):
        d = Mac75Dialog(parent, title, msg, [("No", False), ("Yes", True)], "question")
        d.exec_()
        return d._result == "Yes"

    @staticmethod
    def get_text(parent, title, label):
        d = Mac75Dialog(parent, title, label, [("Cancel", False), ("OK", True)], "info")
        inp = QLineEdit()
        inp.setFont(font_chicago(12))
        inp.setStyleSheet("border: 2px inset #888; background:white; padding:2px;")
        for lay in d.findChildren(QVBoxLayout):
            if lay.count() >= 3:
                lay.insertWidget(lay.count()-1, inp)
                break
        d.adjustSize()
        d.setFixedSize(max(300, d.width()), d.height())
        if d.exec_() and d._result == "OK":
            return inp.text(), True
        return "", False


class _IconWidget(QWidget):
    def __init__(self, kind):
        super().__init__()
        self.kind = kind
        self.setFixedSize(40, 40)
        self.setStyleSheet("background:transparent;")

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(C_BLACK, 2))
        p.setBrush(QBrush(C_WHITE))
        p.drawEllipse(2, 2, 36, 36)
        p.setFont(font_chicago(18, True))
        p.setPen(C_BLACK)
        sym = {"info": "i", "stop": "✕", "question": "?"}
        p.drawText(QRect(0, 0, 40, 40), Qt.AlignCenter, sym.get(self.kind, "i"))


# ─────────────────────────────────────────────────────────────
#  ABOUT WINDOW
# ─────────────────────────────────────────────────────────────
class AboutWindow(Mac75Window):
    def __init__(self, parent):
        super().__init__(parent, "About This ClassicOS", "about",
                         has_resize=False, has_zoom=False)
        self.resize(360, 230)
        c = self.content_widget()
        lay = QVBoxLayout(c)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(8)

        class FaceW(QWidget):
            def __init__(self):
                super().__init__()
                self.setFixedSize(64, 64)
            def paintEvent(self, ev):
                p = QPainter(self)
                draw_icon(p, "finder", 0, 0, 64)

        lay.addWidget(FaceW(), alignment=Qt.AlignCenter)
        for txt, bold, sz in [
            ("System 7.5", True, 16),
            ("ClassicOS 1.1 Simulator", False, 12),
            ("", False, 9),
            ("Built with Python + PyQt5", False, 11),
            ("© 2026 ClassicOS Systems", False, 10),
        ]:
            lbl = QLabel(txt)
            lbl.setFont(font_chicago(sz, bold))
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("background: transparent;")
            lay.addWidget(lbl)


# ─────────────────────────────────────────────────────────────
#  NOTE PAD WINDOW
# ─────────────────────────────────────────────────────────────
class NotePadWindow(Mac75Window):
    def __init__(self, parent, path=None, content=""):
        title = Path(path).name if path else "Note Pad"
        super().__init__(parent, title, "notepad")
        self.resize(480, 340)
        self._path = path
        self._dirty = False

        c = self.content_widget()
        lay = QVBoxLayout(c)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Toolbar
        tb = QWidget()
        tb.setFixedHeight(24)
        tb.setStyleSheet("background:#DDDDDD; border-bottom:1px solid #000;")
        tl = QHBoxLayout(tb)
        tl.setContentsMargins(4, 2, 4, 2)
        tl.setSpacing(4)
        for lbl, fn in [("New", self._new), ("Open…", self._open),
                        ("Save", self._save), ("Save As…", self._save_as)]:
            b = make_toolbar_btn(lbl)
            b.clicked.connect(fn)
            tl.addWidget(b)
        tl.addStretch()

        # Editor — lined paper look
        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("Courier New", 12))
        self.editor.setStyleSheet(
            "QPlainTextEdit{"
            "  background: white;"
            "  border: none;"
            "  color: #000;"
            "}"
        )
        if path:
            self.editor.setPlainText(VFS_INST.read(path))
        elif content:
            self.editor.setPlainText(content)
        self.editor.textChanged.connect(lambda: setattr(self, '_dirty', True))

        # Status
        self.stat = QLabel("Ready")
        self.stat.setFont(font_chicago(9))
        self.stat.setFixedHeight(16)
        self.stat.setStyleSheet("background:#DDDDDD; border-top:1px solid #000; padding:0 4px;")

        lay.addWidget(tb)
        lay.addWidget(self.editor, 1)
        lay.addWidget(self.stat)

    def _new(self):
        self.editor.clear()
        self._path = None
        self.title = "Note Pad"
        self._dirty = False
        self.update()

    def _open(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open", str(Path.home()),
                                               "Text (*.txt);;All (*)")
        if path:
            with open(path, encoding="utf-8", errors="replace") as f:
                self.editor.setPlainText(f.read())
            self._path = path
            self.title = Path(path).name
            self.update()

    def _save(self):
        if not self._path:
            return self._save_as()
        with open(self._path, "w", encoding="utf-8") as f:
            f.write(self.editor.toPlainText())
        self.stat.setText(f"Saved: {self._path}")
        self._dirty = False

    def _save_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save As", str(Path.home()),
                                               "Text (*.txt);;All (*)")
        if path:
            self._path = path
            self.title = Path(path).name
            self._save()
            self.update()


# ─────────────────────────────────────────────────────────────
#  TERMINAL WINDOW
# ─────────────────────────────────────────────────────────────
class TerminalWindow(Mac75Window):
    _out_sig = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent, "Terminal", "terminal")
        self.resize(580, 380)
        self._out_sig.connect(self._append)

        c = self.content_widget()
        lay = QVBoxLayout(c)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.out = QPlainTextEdit()
        self.out.setReadOnly(True)
        self.out.setFont(QFont("Courier New", 11))
        self.out.setStyleSheet(
            "QPlainTextEdit{background:#000; color:#00FF41; border:none; "
            "selection-background-color:#00FF41; selection-color:#000;}")

        inp_row = QWidget()
        inp_row.setStyleSheet("background:#000;")
        ir = QHBoxLayout(inp_row)
        ir.setContentsMargins(4, 2, 4, 2)
        ir.setSpacing(4)

        self.prompt = QLabel("% ")
        self.prompt.setFont(QFont("Courier New", 11))
        self.prompt.setStyleSheet("color:#00FF41; background:transparent;")

        self.inp = QLineEdit()
        self.inp.setFont(QFont("Courier New", 11))
        self.inp.setStyleSheet(
            "background:transparent; color:#00FF41; border:none; "
            "selection-background-color:#00FF41;")
        self.inp.returnPressed.connect(self._run)

        ir.addWidget(self.prompt)
        ir.addWidget(self.inp)
        lay.addWidget(self.out, 1)
        lay.addWidget(inp_row)

        self._hist = []
        self._hi = -1
        self._locals = {"vfs": VFS_INST}
        self._mode = "shell"
        self._cwd = "/"

        self._print("ClassicOS 7.5 Terminal")
        self._print(f"Python {sys.version.split()[0]} — type 'help' for commands\n")

    def _print(self, t):
        self.out.appendPlainText(t)
        self.out.verticalScrollBar().setValue(self.out.verticalScrollBar().maximum())

    @pyqtSlot(str)
    def _append(self, t):
        self._print(t)

    def _run(self):
        cmd = self.inp.text().strip()
        self.inp.clear()
        if not cmd:
            return
        self._hist.insert(0, cmd)
        self._hi = -1
        prompt_str = f"{self._cwd} % " if self._mode == "shell" else ">>> "
        self._print(prompt_str + cmd)

        if cmd == "python":
            self._mode = "python"
            self.prompt.setText(">>> ")
            return
        if cmd == "shell":
            self._mode = "shell"
            self.prompt.setText(f"{self._cwd} % ")
            return
        if cmd == "clear":
            self.out.clear()
            return

        if self._mode == "python":
            self._run_python(cmd)
        else:
            self._run_shell(cmd)

    def _run_python(self, cmd):
        buf_o, buf_e = io.StringIO(), io.StringIO()
        old_o, old_e = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = buf_o, buf_e
        try:
            try:
                r = eval(compile(cmd, "<in>", "eval"), self._locals)
                if r is not None:
                    self._print(repr(r))
            except SyntaxError:
                exec(compile(cmd, "<in>", "exec"), self._locals)
        except Exception as ex:
            self._print(f"Error: {ex}")
        finally:
            sys.stdout, sys.stderr = old_o, old_e
            o, e = buf_o.getvalue(), buf_e.getvalue()
            if o: self._print(o.rstrip())
            if e: self._print(e.rstrip())

    def _run_shell(self, cmd):
        parts = cmd.split()
        if not parts:
            return
        c0 = parts[0]
        if c0 == "ls":
            path = parts[1] if len(parts) > 1 else self._cwd
            ents = VFS_INST.listdir(path)
            self._print("  ".join(ents) if ents else "(empty)")
        elif c0 == "cd":
            path = parts[1] if len(parts) > 1 else "/"
            if not path.startswith("/"):
                path = self._cwd.rstrip("/") + "/" + path
            if VFS_INST.isdir(path):
                self._cwd = path
                self.prompt.setText(f"{self._cwd} % ")
            else:
                self._print(f"cd: {path}: not found")
        elif c0 == "cat":
            path = parts[1] if len(parts) > 1 else ""
            if not path.startswith("/"):
                path = self._cwd.rstrip("/") + "/" + path
            if VFS_INST.isfile(path):
                self._print(VFS_INST.read(path))
            else:
                self._print(f"cat: {path}: not found")
        elif c0 == "mkdir":
            path = parts[1] if len(parts) > 1 else ""
            if not path.startswith("/"):
                path = self._cwd.rstrip("/") + "/" + path
            VFS_INST.mkdir(path)
            self._print(f"mkdir: {path}")
        elif c0 == "pwd":
            self._print(self._cwd)
        elif c0 == "echo":
            self._print(" ".join(parts[1:]))
        elif c0 == "date":
            self._print(datetime.now().strftime("%A, %B %d, %Y  %I:%M %p"))
        elif c0 == "help":
            self._print("ls  cd  cat  mkdir  pwd  echo  date  clear  python")
        elif c0 == "python":
            self._mode = "python"
            self.prompt.setText(">>> ")
        else:
            try:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=5)
                if r.stdout: self._print(r.stdout.rstrip())
                if r.stderr: self._print(r.stderr.rstrip())
            except Exception:
                self._print(f"{c0}: command not found")

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Up and self._hist:
            self._hi = min(self._hi+1, len(self._hist)-1)
            self.inp.setText(self._hist[self._hi])
        elif e.key() == Qt.Key_Down:
            self._hi = max(self._hi-1, -1)
            self.inp.setText(self._hist[self._hi] if self._hi >= 0 else "")
        else:
            super().keyPressEvent(e)


# ─────────────────────────────────────────────────────────────
#  BROWSER WINDOW
# ─────────────────────────────────────────────────────────────
class BrowserWindow(Mac75Window):
    _loaded = pyqtSignal(str, str)

    def __init__(self, parent):
        super().__init__(parent, "Browser", "browser")
        self.resize(680, 460)
        self._loaded.connect(self._show_page)

        c = self.content_widget()
        lay = QVBoxLayout(c)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Toolbar
        tb = QWidget()
        tb.setFixedHeight(26)
        tb.setStyleSheet("background:#DDDDDD; border-bottom:1px solid #000;")
        tl = QHBoxLayout(tb)
        tl.setContentsMargins(4, 3, 4, 3)
        tl.setSpacing(4)

        self.btn_back = make_toolbar_btn("◀")
        self.btn_fwd  = make_toolbar_btn("▶")
        self.btn_go   = make_toolbar_btn("Go")
        self.btn_stop = make_toolbar_btn("Stop")
        self.url_bar = QLineEdit("http://example.com")
        self.url_bar.setFont(font_chicago(10))
        self.url_bar.setStyleSheet(
            "border: 2px inset #888; background:white; padding: 1px 4px;")
        self.url_bar.returnPressed.connect(self._navigate)
        self.btn_back.clicked.connect(self._back)
        self.btn_fwd.clicked.connect(self._fwd)
        self.btn_go.clicked.connect(self._navigate)
        self.btn_stop.clicked.connect(self._stop)

        tl.addWidget(self.btn_back)
        tl.addWidget(self.btn_fwd)
        tl.addWidget(self.url_bar, 1)
        tl.addWidget(self.btn_go)
        tl.addWidget(self.btn_stop)

        # Content
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setFont(QFont("Courier New", 11))
        self.view.setStyleSheet("border:none; background:white;")

        # Status
        self.status = QLabel("Ready")
        self.status.setFont(font_chicago(9))
        self.status.setFixedHeight(16)
        self.status.setStyleSheet("background:#DDDDDD; border-top:1px solid #000; padding:0 4px;")

        lay.addWidget(tb)
        lay.addWidget(self.view, 1)
        lay.addWidget(self.status)

        self._hist = []
        self._fwd_stk = []
        self._nav("http://example.com")

    def _navigate(self):
        url = self.url_bar.text().strip()
        if url:
            self._nav(url)

    def _nav(self, url):
        if not url.startswith("http"):
            url = "http://" + url
        self.url_bar.setText(url)
        self._hist.append(url)
        self._fwd_stk.clear()
        self._fetch(url)

    def _back(self):
        if len(self._hist) > 1:
            self._fwd_stk.append(self._hist.pop())
            self._fetch(self._hist[-1])
            self.url_bar.setText(self._hist[-1])

    def _fwd(self):
        if self._fwd_stk:
            url = self._fwd_stk.pop()
            self._hist.append(url)
            self.url_bar.setText(url)
            self._fetch(url)

    def _stop(self):
        self.status.setText("Stopped.")

    def _fetch(self, url):
        self.status.setText(f"Loading {url}…")
        self.view.setPlainText("Loading…")

        def worker():
            if not HAS_REQUESTS:
                self._loaded.emit(url, "[requests not installed]\npip install requests")
                return
            try:
                r = requests.get(url, timeout=10,
                                  headers={"User-Agent": "ClassicOS/7.5 text-browser"})
                txt = re.sub(r'<style[^>]*>.*?</style>', '', r.text, flags=re.DOTALL|re.I)
                txt = re.sub(r'<script[^>]*>.*?</script>', '', txt, flags=re.DOTALL|re.I)
                txt = re.sub(r'<[^>]+>', '', txt)
                txt = re.sub(r'\n{3,}', '\n\n', txt).strip()
                self._loaded.emit(url, txt[:50000])
            except Exception as ex:
                self._loaded.emit(url, f"Error: {ex}")

        threading.Thread(target=worker, daemon=True).start()

    @pyqtSlot(str, str)
    def _show_page(self, url, content):
        self.view.setPlainText(content)
        self.status.setText(f"Done — {url}")


# ─────────────────────────────────────────────────────────────
#  FINDER WINDOW
# ─────────────────────────────────────────────────────────────
class FinderWindow(Mac75Window):
    def __init__(self, parent, path="/"):
        super().__init__(parent, path, "folder", has_zoom=False)
        self.resize(480, 320)
        self._path = path
        self._desk = parent
        c = self.content_widget()
        c.setAttribute(Qt.WA_StyledBackground, True)
        c.setStyleSheet("background:#CCCCCC;")
        # Inset manually; resizeEvent will keep it correct
        TH = self.TITLE_H
        c.setGeometry(2, TH + 1, 480 - 6, 320 - TH - 5)
        lay = QVBoxLayout(c)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Toolbar
        tb = QWidget()
        tb.setFixedHeight(24)
        tb.setStyleSheet("background:#CCCCCC; border-bottom:1px solid #000;")
        tl = QHBoxLayout(tb)
        tl.setContentsMargins(4, 2, 4, 2)
        tl.setSpacing(4)

        self.path_lbl = QLabel(path)
        self.path_lbl.setFont(font_chicago(10, True))
        self.path_lbl.setStyleSheet("background:transparent;")
        btn_up = make_toolbar_btn("↑ Up")
        btn_up.clicked.connect(self._go_up)
        btn_nf = make_toolbar_btn("New Folder")
        btn_nf.clicked.connect(self._new_folder)

        tl.addWidget(self.path_lbl, 1)
        tl.addWidget(btn_up)
        tl.addWidget(btn_nf)

        # Icon view — solid platinum bg, no scroll area border
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet(
            "QScrollArea { border:none; background:#FFFFFF; }"
            "QScrollArea > QWidget > QWidget { background:#FFFFFF; }"
        )
        self.scroll.viewport().setStyleSheet("background:#FFFFFF;")

        self.grid_w = QWidget()
        self.grid_w.setStyleSheet("background:#FFFFFF;")
        self.grid_w.setAcceptDrops(True)
        self.grid_w.dragEnterEvent = self._drag_enter
        self.grid_w.dragMoveEvent  = self._drag_move
        self.grid_w.dropEvent      = self._drop_event
        self.grid = QGridLayout(self.grid_w)
        self.grid.setContentsMargins(8, 8, 8, 8)
        self.grid.setSpacing(8)
        self.scroll.setWidget(self.grid_w)

        # Status bar
        self.stat = QLabel("")
        self.stat.setFont(font_chicago(9))
        self.stat.setFixedHeight(16)
        self.stat.setStyleSheet("background:#CCCCCC; border-top:1px solid #000; padding:0 4px;")

        lay.addWidget(tb)
        lay.addWidget(self.scroll, 1)
        lay.addWidget(self.stat)

        self._load(path)

    def resizeEvent(self, e):
        TH = self.TITLE_H
        c = self.content_widget()
        # Inset 2px inside the window border on left/right/bottom
        # Bypass Mac75Window.resizeEvent which would reset _content to full width
        c.setGeometry(2, TH + 1, self.width() - 6, self.height() - TH - 5)
        self._relayout()
        QWidget.resizeEvent(self, e)

    def paintEvent(self, e):
        """Override to paint 3D platinum gray content area instead of white."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        W, H = self.width(), self.height()
        TH = self.TITLE_H

        # Same window chrome as base class
        p.fillRect(2, 2, W - 1, H - 1, C_BLACK)
        p.setPen(QPen(C_BLACK, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(0, 0, W - 3, H - 3)
        p.setPen(QPen(C_WHITE, 1))
        p.drawLine(1, 1, W - 4, 1)
        p.drawLine(1, 1, 1, H - 4)
        p.setPen(QPen(C_PLATINUM_DK, 1))
        p.drawLine(W - 3, 1, W - 3, H - 3)
        p.drawLine(1, H - 3, W - 3, H - 3)

        self._paint_titlebar(p, W - 2, TH)

        # Fill content area platinum gray before child widgets render
        cx, cy = 2, TH + 1
        cw, ch = W - 6, H - TH - 5
        p.fillRect(cx, cy, cw, ch, C_PLATINUM)
        # Inset bevel (recessed look)
        p.setPen(QPen(QColor(0x88, 0x88, 0x88), 1))
        p.drawLine(cx, cy, cx + cw, cy)
        p.drawLine(cx, cy, cx, cy + ch)
        p.setPen(QPen(C_WHITE, 1))
        p.drawLine(cx + cw, cy, cx + cw, cy + ch)
        p.drawLine(cx, cy + ch, cx + cw, cy + ch)

        p.setPen(QPen(C_BLACK, 1))
        p.drawLine(1, TH, W - 4, TH)

        if self._has_resize:
            self._paint_resize(p, W - 2, H - 2)

    def _load(self, path):
        self._path = path
        self.title = path
        self.path_lbl.setText(path)
        self.update()

        # clear grid
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        entries = sorted(VFS_INST.listdir(path))
        cols = max(1, (self.width() - 30) // 80)
        for i, name in enumerate(entries):
            full = (path.rstrip("/") + "/" + name) if path != "/" else "/" + name
            node = VFS_INST.resolve(full) or {}
            if VFS_INST.isdir(full):
                icon = "folder"
            elif node.get("__type") == "app":
                tgt = node.get("__target", "about")
                # Map target to proper icon name
                _icon_map = {
                    "calculator": "calculator", "terminal": "terminal",
                    "browser": "browser", "notepad": "notepad",
                    "settings": "settings", "stickies": "stickies",
                    "macpaint": "macpaint", "puzzle": "puzzle",
                    "scrapbook": "scrapbook", "clock": "clock",
                    "finder": "finder", "about": "about",
                }
                icon = _icon_map.get(tgt, tgt)
            else:
                icon = "notepad"
            ic = _FinderIcon(name, icon, full, self)
            ic.double_clicked.connect(self._open_item)
            self.grid.addWidget(ic, i // cols, i % cols)

        self.stat.setText(f"{len(entries)} item{'s' if len(entries)!=1 else ''}  —  {path}")

    def _drag_enter(self, e):
        if e.mimeData().hasText():
            e.acceptProposedAction()

    def _drag_move(self, e):
        if e.mimeData().hasText():
            e.acceptProposedAction()

    def _drop_event(self, e):
        src_path = e.mimeData().text()
        if not src_path or src_path == self._path:
            return
        # Move the item into current folder in VFS
        name = src_path.rstrip("/").split("/")[-1]
        dst_path = (self._path.rstrip("/") + "/" + name) if self._path != "/" else "/" + name
        # Resolve source node
        src_node = VFS_INST.resolve(src_path)
        if src_node is None:
            return
        # Write to destination
        dst_parts = dst_path.strip("/").split("/")
        node = VFS_INST.tree["/"]
        for part in dst_parts[:-1]:
            node = node.setdefault(part, {})
        node[dst_parts[-1]] = src_node
        # Remove from source
        src_parts = src_path.strip("/").split("/")
        src_node2 = VFS_INST.tree["/"]
        for part in src_parts[:-1]:
            src_node2 = src_node2.get(part, {})
        src_node2.pop(src_parts[-1], None)
        e.acceptProposedAction()
        self._load(self._path)

    def _go_up(self):
        if self._path in ("/", ""):
            return
        parent = str(Path(self._path).parent)
        if not parent.startswith("/"):
            parent = "/"
        self._load(parent)

    def _new_folder(self):
        name, ok = Mac75Dialog.get_text(self, "New Folder", "Name of new folder:")
        if ok and name.strip():
            VFS_INST.mkdir(self._path.rstrip("/") + "/" + name.strip())
            self._load(self._path)

    def _open_item(self, full_path, icon_widget=None):
        node = VFS_INST.resolve(full_path) or {}
        desk = self._desk
        fr = None
        if icon_widget:
            fr = QRect(icon_widget.mapTo(desk, QPoint(0, 0)), icon_widget.size())
        if VFS_INST.isdir(full_path):
            new_win = FinderWindow(desk, full_path)
            new_win._icon_src_rect = fr
            if fr:
                new_win.setVisible(False)
                desk._zoom_rects_open(fr, new_win.geometry())
                QTimer.singleShot(_ZoomRectsOverlay.DURATION_MS,
                    lambda ww=new_win, frc=fr: (ww.setVisible(True), ww.animate_open_from(frc)))
            desk._menu.raise_()
            desk._wf_overlay.raise_()
        elif node.get("__type") == "app":
            desk.open_window(node.get("__target", ""), icon_widget)
        elif node.get("__type") == "file":
            new_win = NotePadWindow(desk, full_path)
            new_win._icon_src_rect = fr
            if fr:
                new_win.setVisible(False)
                desk._zoom_rects_open(fr, new_win.geometry())
                QTimer.singleShot(_ZoomRectsOverlay.DURATION_MS,
                    lambda ww=new_win, frc=fr: (ww.setVisible(True), ww.animate_open_from(frc)))
            desk._menu.raise_()
            desk._wf_overlay.raise_()


class _FinderIcon(QWidget):
    double_clicked = pyqtSignal(str, QWidget)

    def __init__(self, name, icon, path, finder_win=None):
        super().__init__()
        self.name = name
        self.icon = icon
        self.path = path
        self._finder = finder_win
        self._sel = False
        self._drag_start = None
        self.setFixedSize(72, 70)
        self.setMouseTracking(True)
        self.setAcceptDrops(False)   # icons don't accept drops (the grid widget does)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        if self._sel:
            p.fillRect(2, 2, 68, 40, C_SELECT)
        draw_icon(p, self.icon, 18, 2, 36)
        p.setFont(font_chicago(9))
        lrect = QRect(0, 42, 72, 26)
        if self._sel:
            p.fillRect(lrect, C_SELECT)
            p.setPen(C_SELECT_TEXT)
        else:
            p.setPen(C_BLACK)
        p.drawText(lrect, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, self.name)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_start = e.pos()
            self._sel = True
            if self.parent():
                for sib in self.parent().findChildren(_FinderIcon):
                    if sib is not self:
                        sib._sel = False
                        sib.update()
            self.update()

    def mouseMoveEvent(self, e):
        if not (e.buttons() & Qt.LeftButton) or self._drag_start is None:
            return
        if (e.pos() - self._drag_start).manhattanLength() < 8:
            return
        # Start a real Qt DnD
        drag = QDrag(self)
        mime = QMimeData()
        mime.setText(self.path)
        drag.setMimeData(mime)
        # Ghost pixmap
        pm = QPixmap(40, 40)
        pm.fill(Qt.transparent)
        pp = QPainter(pm)
        draw_icon(pp, self.icon, 0, 0, 40)
        pp.end()
        drag.setPixmap(pm)
        drag.setHotSpot(QPoint(20, 20))
        drag.exec_(Qt.MoveAction | Qt.CopyAction)

    def mouseDoubleClickEvent(self, e):
        self.double_clicked.emit(self.path, self)


# ─────────────────────────────────────────────────────────────
#  CONTROL PANELS (Settings)
# ─────────────────────────────────────────────────────────────
class ControlPanelWindow(Mac75Window):
    _BG_COLORS = {
        "Platinum Gray (default)":  "#888888",
        "Teal Green":               "#6B8E6B",
        "Dark Blue":                "#234567",
        "Forest Green":             "#345623",
        "Burgundy":                 "#671234",
        "Black":                    "#000000",
    }

    def __init__(self, parent):
        self._desk = parent
        super().__init__(parent, "Control Panels", "settings", has_resize=False)
        self.resize(380, 300)

        c = self.content_widget()
        lay = QVBoxLayout(c)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header strip
        hdr = QWidget()
        hdr.setFixedHeight(28)
        hdr.setStyleSheet("background:#DDDDDD; border-bottom:1px solid #000;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(8, 4, 8, 4)
        lbl = QLabel("Control Panels")
        lbl.setFont(font_chicago(13, True))
        hl.addWidget(lbl)
        lay.addWidget(hdr)

        # Main area
        main = QWidget()
        main.setStyleSheet("background:#CCCCCC;")
        ml = QVBoxLayout(main)
        ml.setContentsMargins(12, 10, 12, 10)
        ml.setSpacing(10)

        def row(label, widget):
            r = QWidget()
            r.setStyleSheet("background:transparent;")
            rl = QHBoxLayout(r)
            rl.setContentsMargins(0, 0, 0, 0)
            lb = QLabel(label)
            lb.setFont(font_chicago(11))
            lb.setFixedWidth(150)
            lb.setStyleSheet("background:transparent;")
            rl.addWidget(lb)
            rl.addWidget(widget)
            ml.addWidget(r)

        # Desktop pattern
        self.bg_combo = QComboBox()
        self.bg_combo.setFont(font_chicago(10))
        for k in self._BG_COLORS:
            self.bg_combo.addItem(k)
        self.bg_combo.setStyleSheet(
            "QComboBox{border:2px inset #888; background:white; padding:1px 4px;}")
        self.bg_combo.currentTextChanged.connect(
            lambda t: parent.setStyleSheet(f"background:{self._BG_COLORS[t]};"))
        row("Desktop Pattern:", self.bg_combo)

        # Highlight color
        self.hi_combo = QComboBox()
        self.hi_combo.setFont(font_chicago(10))
        self.hi_combo.addItems(["Blue (default)", "Red", "Green", "Purple", "Gold"])
        self.hi_combo.setStyleSheet(
            "QComboBox{border:2px inset #888; background:white; padding:1px 4px;}")
        row("Highlight Color:", self.hi_combo)

        # Clock
        self.clock_combo = QComboBox()
        self.clock_combo.setFont(font_chicago(10))
        self.clock_combo.addItems(["12-hour", "24-hour"])
        self.clock_combo.setStyleSheet(
            "QComboBox{border:2px inset #888; background:white; padding:1px 4px;}")
        self.clock_combo.currentIndexChanged.connect(
            lambda i: setattr(parent, "_clock_24h", i == 1))
        row("Clock Format:", self.clock_combo)

        # Menu font size
        self.font_spin = QSpinBox()
        self.font_spin.setFont(font_chicago(10))
        self.font_spin.setRange(9, 16)
        self.font_spin.setValue(12)
        self.font_spin.setStyleSheet("border:2px inset #888; background:white; padding:1px;")
        row("Menu Font Size:", self.font_spin)

        ml.addStretch()

        # Version info
        ver = QLabel("ClassicOS 7.5 — Control Panels v1.1")
        ver.setFont(font_chicago(9))
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet("color:#666; background:transparent;")
        ml.addWidget(ver)

        lay.addWidget(main, 1)


# ─────────────────────────────────────────────────────────────
#  CALCULATOR WINDOW  (classic System 7 Desk Accessory)
# ─────────────────────────────────────────────────────────────
class CalculatorWindow(Mac75Window):
    """System 7 Calculator desk accessory — fully functional."""

    BTNS = [
        ("7", "8", "9", "÷"),
        ("4", "5", "6", "×"),
        ("1", "2", "3", "−"),
        ("0", ".", "=", "+"),
        ("C", "±", "%", "⌫"),
    ]

    def __init__(self, parent):
        super().__init__(parent, "Calculator", "calculator", has_resize=False, has_zoom=False)
        self.resize(180, 230)
        self._expr     = ""
        self._display  = "0"
        self._new_num  = True
        self._op       = None
        self._acc      = None
        self._btn_objs = {}

        c = self.content_widget()
        c.setAttribute(Qt.WA_StyledBackground, True)
        c.setStyleSheet("background:#CCCCCC;")
        lay = QVBoxLayout(c)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)

        # LCD display
        self._disp_lbl = QLabel("0")
        self._disp_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._disp_lbl.setFixedHeight(28)
        self._disp_lbl.setFont(QFont("Courier New", 16, QFont.Bold))
        self._disp_lbl.setStyleSheet(
            "background:#AABBAA; border:2px inset #888;"
            " padding:0 4px; color:#001100;")
        lay.addWidget(self._disp_lbl)

        # Button grid
        for row in self.BTNS:
            row_w = QWidget()
            row_w.setStyleSheet("background:transparent;")
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(3)
            for label in row:
                btn = Mac75Button(label, row_w)
                btn.setFixedSize(34, 26)
                btn.setFont(font_chicago(11, label in ("=",)))
                btn.clicked.connect(lambda _, l=label: self._press(l))
                rl.addWidget(btn)
                self._btn_objs[label] = btn
            lay.addWidget(row_w)

    def _press(self, key):
        if key == "C":
            self._display = "0"; self._expr = ""; self._op = None
            self._acc = None; self._new_num = True
        elif key == "⌫":
            if not self._new_num and len(self._display) > 1:
                self._display = self._display[:-1]
            else:
                self._display = "0"; self._new_num = True
        elif key == "±":
            if self._display != "0":
                if self._display.startswith("-"):
                    self._display = self._display[1:]
                else:
                    self._display = "-" + self._display
        elif key == "%":
            try:
                self._display = self._fmt(float(self._display) / 100)
            except Exception:
                pass
        elif key in ("÷", "×", "−", "+"):
            self._apply_pending()
            self._op = key; self._new_num = True
        elif key == "=":
            self._apply_pending(); self._op = None
        elif key == ".":
            if self._new_num:
                self._display = "0."; self._new_num = False
            elif "." not in self._display:
                self._display += "."
        else:  # digit
            if self._new_num:
                self._display = key; self._new_num = False
            else:
                if self._display == "0":
                    self._display = key
                else:
                    self._display += key
        self._disp_lbl.setText(self._display)

    def _apply_pending(self):
        try:
            cur = float(self._display)
        except ValueError:
            return
        if self._op is None:
            self._acc = cur; return
        if self._acc is None:
            self._acc = cur; return
        ops = {"÷": lambda a,b: a/b if b else float("inf"),
               "×": lambda a,b: a*b,
               "−": lambda a,b: a-b,
               "+": lambda a,b: a+b}
        try:
            self._acc = ops[self._op](self._acc, cur)
        except Exception:
            self._acc = 0.0
        self._display = self._fmt(self._acc)
        self._new_num = True

    @staticmethod
    def _fmt(n):
        if n == int(n) and abs(n) < 1e12:
            return str(int(n))
        s = f"{n:.8g}"
        return s


# ─────────────────────────────────────────────────────────────
#  STICKIES WINDOW
# ─────────────────────────────────────────────────────────────
class StickiesWindow(Mac75Window):
    COLORS = [
        QColor(0xFF, 0xFF, 0x99),  # yellow
        QColor(0xCC, 0xFF, 0x99),  # green
        QColor(0xFF, 0xCC, 0x99),  # orange
        QColor(0x99, 0xCC, 0xFF),  # blue
        QColor(0xFF, 0x99, 0xCC),  # pink
    ]

    def __init__(self, parent):
        super().__init__(parent, "Stickies", "stickies",
                         has_resize=True, has_zoom=False)
        self.resize(240, 200)
        self._note_color = self.COLORS[0]

        c = self.content_widget()
        lay = QVBoxLayout(c)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Color bar
        cbar = QWidget()
        cbar.setFixedHeight(16)
        cbar_lay = QHBoxLayout(cbar)
        cbar_lay.setContentsMargins(2, 2, 2, 2)
        cbar_lay.setSpacing(3)
        for col in self.COLORS:
            btn = QLabel()
            btn.setFixedSize(10, 10)
            btn.setStyleSheet(f"background: {col.name()}; border: 1px solid #000;")
            btn.mousePressEvent = lambda e, c=col: self._set_color(c)
            cbar_lay.addWidget(btn)
        cbar_lay.addStretch()

        self.editor = QPlainTextEdit()
        self.editor.setFont(font_chicago(12))
        self.editor.setPlaceholderText("Type your note here…")

        lay.addWidget(cbar)
        lay.addWidget(self.editor, 1)
        self._apply_color()

    def _set_color(self, col):
        self._note_color = col
        self._apply_color()

    def _apply_color(self):
        c = self._note_color.name()
        self.content_widget().setStyleSheet(f"background:{c};")
        self.editor.setStyleSheet(f"background:{c}; border:none;")


# ─────────────────────────────────────────────────────────────
#  CLOCK WINDOW  (analog clock desk accessory)
# ─────────────────────────────────────────────────────────────
class ClockWindow(Mac75Window):
    """Analog clock desk accessory."""
    def __init__(self, parent):
        super().__init__(parent, "Clock", "clock", has_resize=False, has_zoom=False)
        self.resize(180, 200)
        self._clock_24h = getattr(parent, '_clock_24h', False)

        c = self.content_widget()
        c.setAttribute(Qt.WA_StyledBackground, True)
        c.setStyleSheet("background:#CCCCCC;")

        vlay = QVBoxLayout(c)
        vlay.setContentsMargins(4, 4, 4, 4)
        vlay.setSpacing(4)

        # Analog clock face widget
        self._face = _ClockFaceWidget()
        vlay.addWidget(self._face, 1)

        # Digital time label
        self._lbl = QLabel()
        self._lbl.setAlignment(Qt.AlignCenter)
        self._lbl.setFont(font_chicago(13, True))
        self._lbl.setStyleSheet("background:transparent; color:#000;")
        vlay.addWidget(self._lbl)

        # Date label
        self._date_lbl = QLabel()
        self._date_lbl.setAlignment(Qt.AlignCenter)
        self._date_lbl.setFont(font_chicago(9))
        self._date_lbl.setStyleSheet("background:transparent; color:#444;")
        vlay.addWidget(self._date_lbl)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._tick()

    def _tick(self):
        now = datetime.now()
        if self._clock_24h:
            self._lbl.setText(now.strftime("%H:%M:%S"))
        else:
            self._lbl.setText(now.strftime("%I:%M:%S %p"))
        self._date_lbl.setText(now.strftime("%A, %B %d"))
        self._face.set_time(now.hour, now.minute, now.second)


class _ClockFaceWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._h = 0; self._m = 0; self._s = 0
        self.setMinimumSize(120, 120)

    def set_time(self, h, m, s):
        self._h = h; self._m = m; self._s = s
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        W, H = self.width(), self.height()
        r = min(W, H) // 2 - 4
        cx, cy = W // 2, H // 2

        # Face gradient
        grad = QRadialGradient(cx, cy, r)
        grad.setColorAt(0, QColor(0xFF, 0xFF, 0xF8))
        grad.setColorAt(0.85, QColor(0xEE, 0xEE, 0xE8))
        grad.setColorAt(1, QColor(0xCC, 0xCC, 0xC4))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor(0x44, 0x44, 0x44), 2))
        p.drawEllipse(cx-r, cy-r, r*2, r*2)

        # Bezel ring highlight
        p.setPen(QPen(QColor(0xFF, 0xFF, 0xFF, 180), 1))
        p.setBrush(Qt.NoBrush)
        p.drawArc(cx-r+1, cy-r+1, r*2-2, r*2-2, 45*16, 180*16)

        # Hour markers
        for i in range(12):
            ang = math.radians(i * 30 - 90)
            is_qtr = (i % 3 == 0)
            r1 = r - 3 if is_qtr else r - 2
            r2 = r - 8 if is_qtr else r - 5
            x1 = int(cx + r1 * math.cos(ang))
            y1 = int(cy + r1 * math.sin(ang))
            x2 = int(cx + r2 * math.cos(ang))
            y2 = int(cy + r2 * math.sin(ang))
            p.setPen(QPen(QColor(0, 0, 0), 2 if is_qtr else 1))
            p.drawLine(x1, y1, x2, y2)

        # Second hand (red thin)
        s_ang = math.radians(self._s * 6 - 90)
        p.setPen(QPen(QColor(0xCC, 0x00, 0x00), 1))
        p.drawLine(cx - int(r*0.15*math.cos(s_ang)),
                   cy - int(r*0.15*math.sin(s_ang)),
                   int(cx + r*0.85*math.cos(s_ang)),
                   int(cy + r*0.85*math.sin(s_ang)))

        # Minute hand
        m_ang = math.radians((self._m * 6 + self._s * 0.1) - 90)
        p.setPen(QPen(QColor(0, 0, 0), 2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(cx, cy, int(cx + r*0.75*math.cos(m_ang)), int(cy + r*0.75*math.sin(m_ang)))

        # Hour hand
        h_ang = math.radians(((self._h % 12) * 30 + self._m * 0.5) - 90)
        p.setPen(QPen(QColor(0, 0, 0), 3, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(cx, cy, int(cx + r*0.5*math.cos(h_ang)), int(cy + r*0.5*math.sin(h_ang)))

        # Center dot
        p.setBrush(QBrush(QColor(0, 0, 0)))
        p.setPen(Qt.NoPen)
        p.drawEllipse(cx-3, cy-3, 6, 6)
        p.setBrush(QBrush(QColor(0xCC, 0x00, 0x00)))
        p.drawEllipse(cx-2, cy-2, 4, 4)


# ─────────────────────────────────────────────────────────────
#  TRASH WINDOW
# ─────────────────────────────────────────────────────────────
class TrashWindow(Mac75Window):
    def __init__(self, parent):
        super().__init__(parent, "Trash", "trash", has_zoom=False)
        self._desk = parent
        self.resize(420, 280)
        c = self.content_widget()
        c.setAttribute(Qt.WA_StyledBackground, True)
        c.setStyleSheet("background:#FFFFFF;")
        TH = self.TITLE_H
        c.setGeometry(2, TH + 1, 420 - 6, 280 - TH - 5)

        lay = QVBoxLayout(c)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Toolbar
        tb = QWidget()
        tb.setFixedHeight(24)
        tb.setStyleSheet("background:#CCCCCC; border-bottom:1px solid #000;")
        tl = QHBoxLayout(tb)
        tl.setContentsMargins(4, 2, 4, 2)
        tl.setSpacing(4)
        lbl = QLabel("Trash")
        lbl.setFont(font_chicago(10, True))
        lbl.setStyleSheet("background:transparent;")
        btn_empty = make_toolbar_btn("Empty Trash")
        btn_empty.clicked.connect(self._empty)
        tl.addWidget(lbl, 1)
        tl.addWidget(btn_empty)

        # Icon grid
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea{border:none; background:#FFFFFF;}")
        self.scroll.viewport().setStyleSheet("background:#FFFFFF;")
        self.grid_w = QWidget()
        self.grid_w.setStyleSheet("background:#FFFFFF;")
        self.grid = QGridLayout(self.grid_w)
        self.grid.setContentsMargins(8, 8, 8, 8)
        self.grid.setSpacing(8)
        self.scroll.setWidget(self.grid_w)

        self.stat = QLabel("")
        self.stat.setFont(font_chicago(9))
        self.stat.setFixedHeight(16)
        self.stat.setStyleSheet("background:#CCCCCC; border-top:1px solid #000; padding:0 4px;")

        lay.addWidget(tb)
        lay.addWidget(self.scroll, 1)
        lay.addWidget(self.stat)

        self._load()

    def _load(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        trash = VFS_INST.tree["/"].get("Trash", {})
        entries = [k for k in trash if not k.startswith("__")]
        cols = max(1, (self.width() - 30) // 80)
        for i, name in enumerate(entries):
            node = trash[name]
            icon = "folder" if isinstance(node, dict) and "__type" not in node else "notepad"
            ic = _FinderIcon(name, icon, "/Trash/" + name)
            self.grid.addWidget(ic, i // cols, i % cols)

        self.stat.setText(f"{len(entries)} item{'s' if len(entries)!=1 else ''}")

    def _empty(self):
        if Mac75Dialog.question(self, "Empty Trash",
                                "Permanently delete all items in the Trash?"):
            VFS_INST.tree["/"]["Trash"] = {}
            self._desk._update_trash_icon()
            self._load()


# ─────────────────────────────────────────────────────────────
#  DESKTOP ICON WIDGET
# ─────────────────────────────────────────────────────────────
class DesktopIcon75(QWidget):
    dbl_clicked = pyqtSignal(str, QWidget)

    GRID = 80   # snap grid size in pixels

    def __init__(self, parent, name, icon, x, y, target=None):
        super().__init__(parent)
        self.name = name
        self.icon = icon
        self.target = target or name.lower().replace(" ", "_")
        self._sel = False
        self._drag_off = None
        self._dragging = False
        self._blink_state = False
        self.setFixedSize(80, 80)
        self.move(x, y)
        self.setMouseTracking(True)
        # Trash icon accepts drops
        if self.target == "trash":
            self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if self.target == "trash" and e.mimeData().hasText():
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if self.target == "trash" and e.mimeData().hasText():
            e.acceptProposedAction()

    def dropEvent(self, e):
        src_path = e.mimeData().text()
        if not src_path:
            return
        name = src_path.rstrip("/").split("/")[-1]
        # Move to Trash in VFS
        src_node = VFS_INST.resolve(src_path)
        if src_node is not None:
            VFS_INST.tree["/"].setdefault("Trash", {})[name] = src_node
            # Remove from source
            parts = src_path.strip("/").split("/")
            parent_node = VFS_INST.tree["/"]
            for part in parts[:-1]:
                parent_node = parent_node.get(part, {})
            parent_node.pop(parts[-1], None)
        e.acceptProposedAction()
        # Update icon and refresh any open Finder windows
        desk = self.parent()
        if hasattr(desk, '_update_trash_icon'):
            desk._update_trash_icon()
        self.icon = "trash_full"
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)

        # Icon
        px = QPixmap(40, 40)
        px.fill(Qt.transparent)
        ip = QPainter(px)
        draw_icon(ip, self.icon, 0, 0, 40)
        ip.end()

        selected = self._sel or self._blink_state
        if selected:
            p.setCompositionMode(QPainter.RasterOp_SourceXorDestination)
            p.drawPixmap(20, 2, px)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        else:
            p.drawPixmap(20, 2, px)

        # Label
        p.setFont(font_chicago(9))
        trect = QRect(0, 44, 80, 34)
        if selected:
            p.fillRect(trect, C_SELECT)
            p.setPen(C_SELECT_TEXT)
        else:
            # white shadow then black text
            p.setPen(C_WHITE)
            p.drawText(trect.translated(1, 1),
                       Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, self.name)
            p.setPen(C_BLACK)
            p.drawText(trect, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, self.name)

    def _snap_pos(self, pos: QPoint) -> QPoint:
        """Snap position to nearest grid cell."""
        gx = round(pos.x() / self.GRID) * self.GRID
        gy = round(pos.y() / self.GRID) * self.GRID
        # Clamp to desktop area
        desk = self.parent()
        gx = max(0, min(gx, desk.width() - self.width()))
        gy = max(22, min(gy, desk.height() - 22 - self.height()))
        return QPoint(gx, gy)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._sel = True
            self._drag_off = e.pos()
            for sib in self.parent().findChildren(DesktopIcon75):
                if sib is not self:
                    sib._sel = False
                    sib.update()
            self.update()
            self.raise_()

    def mouseMoveEvent(self, e):
        if self._drag_off and e.buttons() & Qt.LeftButton:
            d = e.pos() - self._drag_off
            if not self._dragging and d.manhattanLength() > 5:
                self._dragging = True
            if self._dragging:
                np = self.pos() + d
                desk = self.parent()
                np.setX(max(0, min(np.x(), desk.width() - self.width())))
                np.setY(max(22, min(np.y(), desk.height() - 22 - self.height())))
                self.move(np)

    def mouseReleaseEvent(self, e):
        if self._dragging:
            # Snap-to-grid: animate to nearest grid cell (100ms)
            snapped = self._snap_pos(self.pos())
            anim = QPropertyAnimation(self, b"pos")
            anim.setDuration(100)
            anim.setStartValue(self.pos())
            anim.setEndValue(snapped)
            anim.setEasingCurve(QEasingCurve.OutQuad)
            anim.start(QAbstractAnimation.DeleteWhenStopped)
        self._dragging = False
        self._drag_off = None

    def mouseDoubleClickEvent(self, e):
        # Invert blink 2× before opening
        self._do_blink(2, lambda: self.dbl_clicked.emit(self.target, self))

    def _do_blink(self, count, callback):
        if count <= 0:
            self._blink_state = False
            self.update()
            callback()
            return
        self._blink_state = not self._blink_state
        self.update()
        QTimer.singleShot(80, lambda: self._do_blink(count - 1, callback))


# ─────────────────────────────────────────────────────────────
#  APPLE MENU BUTTON
# ─────────────────────────────────────────────────────────────
class AppleMenuBtn(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 22)
        self._pressed = False

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        fg = C_WHITE if self._pressed else C_BLACK
        if self._pressed:
            p.fillRect(self.rect(), C_BLACK)
        p.setBrush(QBrush(fg))
        p.setPen(Qt.NoPen)

        # Proper Apple silhouette — two overlapping lobes + bite + stem
        cx, cy = 14, 13
        apple = QPainterPath()
        # Left lobe
        apple.addEllipse(cx - 7, cy - 4, 8, 9)
        # Right lobe
        apple.addEllipse(cx - 1, cy - 4, 8, 9)
        # Flatten bottom into a rounded base
        base = QPainterPath()
        base.addRoundedRect(cx - 7, cy + 1, 14, 6, 3, 3)
        apple = apple.united(base)
        # Bite out of top-right
        bite = QPainterPath()
        bite.addEllipse(cx + 2, cy - 7, 6, 6)
        apple = apple.subtracted(bite)
        # Cleft between lobes (top center notch)
        notch = QPainterPath()
        notch.addEllipse(cx - 2, cy - 5, 4, 4)
        apple = apple.subtracted(notch)
        p.drawPath(apple)

        # Stem — curves up-right from top center
        p.setPen(QPen(fg, 1.5))
        p.setBrush(Qt.NoBrush)
        stem = QPainterPath()
        stem.moveTo(cx, cy - 4)
        stem.cubicTo(cx, cy - 9, cx + 4, cy - 10, cx + 3, cy - 7)
        p.drawPath(stem)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._pressed = True
            self.update()

    def mouseReleaseEvent(self, e):
        self._pressed = False
        self.update()
        if self.rect().contains(e.pos()):
            self.clicked.emit()


# ─────────────────────────────────────────────────────────────
#  MENU BAR
# ─────────────────────────────────────────────────────────────
class MenuBar75(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setFixedHeight(22)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(self.backgroundRole(), QColor(0xFF, 0xFF, 0xFF))
        self.setPalette(pal)
        self.setStyleSheet("MenuBar75 { background:#FFFFFF; border-bottom: 1px solid #000; }")
        self._desk = parent

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Apple logo button
        self.apple_btn = AppleMenuBtn(self)
        self.apple_btn.clicked.connect(self._show_apple)
        lay.addWidget(self.apple_btn)

        # Finder menus — always visible (Finder is always running in System 7)
        self._finder_menus = [
            ("File", [
                ("New Folder",           lambda: self._finder_action("new_folder")),
                ("Open",                 lambda: self._finder_action("open")),
                ("Print",                lambda: None),
                ("Close Window",         parent._close_active),
                None,
                ("Get Info",             lambda: None),
                ("Sharing…",             lambda: None),
                None,
                ("Duplicate",            lambda: None),
                ("Make Alias",           lambda: None),
                ("Put Away",             lambda: None),
                None,
                ("Find…",                lambda: parent.open_window("finder")),
                ("Find Again",           lambda: None),
                None,
                ("Page Setup…",          lambda: None),
                ("Print Window…",        lambda: None),
            ]),
            ("Edit", [
                ("Undo",                 lambda: None),
                None,
                ("Cut",                  lambda: None),
                ("Copy",                 lambda: None),
                ("Paste",                lambda: None),
                ("Clear",                lambda: None),
                ("Select All",           lambda: None),
                None,
                ("Show Clipboard",       lambda: None),
            ]),
            ("View", [
                ("by Small Icon",        lambda: None),
                ("by Icon",              lambda: None),
                ("by Name",              lambda: None),
                ("by Size",              lambda: None),
                ("by Kind",              lambda: None),
                ("by Label",             lambda: None),
                ("by Date",              lambda: None),
            ]),
            ("Label", [
                ("None",                 lambda: None),
                None,
                ("Hot",                  lambda: None),
                ("In Progress",          lambda: None),
                ("Cool",                 lambda: None),
                ("Personal",             lambda: None),
                ("Project 1",            lambda: None),
                ("Project 2",            lambda: None),
            ]),
            ("Special", [
                ("Clean Up",             lambda: None),
                ("Empty Trash…",         parent.empty_trash),
                ("Eject",                lambda: None),
                ("Erase Disk…",          lambda: None),
                None,
                ("Restart…",             parent.restart),
                ("Shut Down…",           parent.shut_down),
            ]),
        ]

        self._menu_btns = []
        for label, items in self._finder_menus:
            btn = QPushButton(label)
            btn.setFont(font_chicago(12))
            btn.setFlat(True)
            btn.setStyleSheet(
                "QPushButton{padding:2px 8px; border:none; background:transparent;}"
                "QPushButton:pressed,QPushButton:checked{background:#000; color:#fff;}")
            btn.setCheckable(True)
            menu = self._build_menu(items)
            btn.clicked.connect(lambda c=False, b=btn, m=menu: self._show(b, m))
            lay.addWidget(btn)
            self._menu_btns.append((btn, menu))

        lay.addStretch()

        # Clock (right side, before Application Menu)
        self.clock = QLabel()
        self.clock.setFont(font_chicago(11))
        self.clock.setStyleSheet("padding:0 6px; background:transparent;")
        lay.addWidget(self.clock)

        # Application Menu button (right side — app icon + app name)
        self._app_menu_btn = QPushButton("Finder")
        self._app_menu_btn.setFont(font_chicago(11, True))
        self._app_menu_btn.setFlat(True)
        self._app_menu_btn.setStyleSheet(
            "QPushButton{padding:2px 10px 2px 4px; border-left:1px solid #CCC;"
            " background:transparent;}"
            "QPushButton:pressed,QPushButton:checked{background:#000; color:#FFF;}")
        self._app_menu_btn.setCheckable(True)
        # Set initial Finder icon
        pm0 = QPixmap(16, 16)
        pm0.fill(Qt.transparent)
        pp0 = QPainter(pm0)
        draw_icon(pp0, "finder", 0, 0, 16)
        pp0.end()
        self._app_menu_btn.setIcon(QIcon(pm0))
        self._app_menu_btn.setIconSize(QSize(16, 16))
        self._app_menu_btn.clicked.connect(self._show_app_menu)
        lay.addWidget(self._app_menu_btn)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._tick()

        # Update app menu button when WM changes
        WM.changed.connect(self._refresh_app_menu)

    def _refresh_control_strip(self):
        if hasattr(self._desk, '_control_strip'):
            self._desk._control_strip.update()

    def _build_menu(self, items):
        m = QMenu(self)
        m.setFont(font_chicago(11))
        m.setStyleSheet(
            "QMenu{background:#FFF; border:1px solid #000; padding:2px 0;}"
            "QMenu::item{padding:3px 24px 3px 20px;}"
            "QMenu::item:selected{background:#000; color:#FFF;}"
            "QMenu::separator{height:1px; background:#888; margin:2px 4px;}")
        for item in items:
            if item is None:
                m.addSeparator()
            else:
                label, fn = item
                act = m.addAction(label)
                act.triggered.connect(fn)
        return m

    def _show(self, btn, menu):
        pos = btn.mapToGlobal(QPoint(0, btn.height()))
        menu.exec_(pos)
        btn.setChecked(False)

    def _show_apple(self):
        m = QMenu(self)
        m.setFont(font_chicago(11))
        m.setStyleSheet(
            "QMenu{background:#FFF; border:1px solid #000; padding:2px 0;}"
            "QMenu::item{padding:3px 24px 3px 20px;}"
            "QMenu::item:selected{background:#000; color:#FFF;}"
            "QMenu::separator{height:1px; background:#888; margin:2px 4px;}")
        m.addAction("About This Macintosh…").triggered.connect(
            lambda: self._desk.open_window("about"))
        m.addSeparator()
        # Apple Menu Items (classic System 7 items)
        for label, target in [
            ("Alarm Clock",    "clock"),
            ("Calculator",     "calculator"),
            ("Chooser",        None),
            ("Control Panels", "settings"),
            ("Find File",      "finder"),
            ("Note Pad",       "notepad"),
            ("Puzzle",         "puzzle"),
            ("Scrapbook",      "scrapbook"),
            ("Stickies",       "stickies"),
        ]:
            if target:
                act = m.addAction(label)
                act.triggered.connect(lambda _, t=target: self._desk.open_window(t))
            else:
                m.addAction(label).setEnabled(False)
        m.addSeparator()
        m.addAction("Shut Down…").triggered.connect(self._desk.shut_down)
        m.exec_(self.apple_btn.mapToGlobal(QPoint(0, 22)))

    def _show_app_menu(self):
        m = QMenu(self)
        m.setFont(font_chicago(11))
        m.setStyleSheet(
            "QMenu{background:#FFF; border:1px solid #000; padding:2px 0;}"
            "QMenu::item{padding:3px 28px 3px 6px;}"
            "QMenu::item:selected{background:#000; color:#FFF;}"
            "QMenu::separator{height:1px; background:#888; margin:2px 4px;}")

        def make_app_icon(icon_name, size=16):
            pm = QPixmap(size, size)
            pm.fill(Qt.transparent)
            pp = QPainter(pm)
            pp.setRenderHint(QPainter.Antialiasing, False)
            draw_icon(pp, icon_name, 0, 0, size)
            pp.end()
            return QIcon(pm)

        # Finder always top
        a_finder = m.addAction(make_app_icon("finder"), "Finder")
        a_finder.triggered.connect(lambda: self._desk.open_window("finder"))
        m.addSeparator()

        # Running windows — icon + title
        _icon_map = {
            "calculator": "calculator", "terminal": "terminal",
            "browser": "browser", "notepad": "notepad",
            "settings": "settings", "stickies": "stickies",
            "macpaint": "macpaint", "puzzle": "puzzle",
            "scrapbook": "scrapbook", "clock": "clock",
            "finder": "folder", "about": "about", "trash": "trash",
        }
        for win in WM.windows:
            tgt = getattr(win, '_icon_target', 'about')
            icon_nm = _icon_map.get(tgt, 'about')
            label = win.title[:24]
            if getattr(win, '_minimized', False):
                label = "  " + label + " (minimized)"
            act = m.addAction(make_app_icon(icon_nm), label)
            act.triggered.connect(lambda _, w=win: (
                WM.raise_window(w),
                w.restore() if getattr(w, '_minimized', False) else None
            ))

        m.addSeparator()
        m.addAction("Hide Others").triggered.connect(lambda: None)
        m.addAction("Show All").triggered.connect(
            lambda: [w.restore() if getattr(w, '_minimized', False) else None for w in WM.windows])
        pos = self._app_menu_btn.mapToGlobal(QPoint(0, self._app_menu_btn.height()))
        m.exec_(pos)
        self._app_menu_btn.setChecked(False)

    def _refresh_app_menu(self):
        active = WM.get_active()
        if active:
            name = active.title[:20]
            # Show icon in button too
            tgt = getattr(active, '_icon_target', 'about')
            _icon_map = {
                "calculator": "calculator", "terminal": "terminal",
                "browser": "browser", "notepad": "notepad",
                "settings": "settings", "stickies": "stickies",
                "macpaint": "macpaint", "puzzle": "puzzle",
                "scrapbook": "scrapbook", "clock": "clock",
                "finder": "folder", "about": "about", "trash": "trash",
            }
            icon_nm = _icon_map.get(tgt, 'about')
            pm = QPixmap(16, 16)
            pm.fill(Qt.transparent)
            pp = QPainter(pm)
            draw_icon(pp, icon_nm, 0, 0, 16)
            pp.end()
            self._app_menu_btn.setIcon(QIcon(pm))
            self._app_menu_btn.setIconSize(QSize(16, 16))
        else:
            name = "Finder"
            pm = QPixmap(16, 16)
            pm.fill(Qt.transparent)
            pp = QPainter(pm)
            draw_icon(pp, "finder", 0, 0, 16)
            pp.end()
            self._app_menu_btn.setIcon(QIcon(pm))
            self._app_menu_btn.setIconSize(QSize(16, 16))
        self._app_menu_btn.setText(name)

    def _finder_action(self, action):
        active = WM.get_active()
        if action == "new_folder" and isinstance(active, FinderWindow):
            active._new_folder()
        elif action == "open":
            self._desk.open_window("finder")

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(0, 0, self.width(), self.height(), QColor(0xFF, 0xFF, 0xFF))
        p.setPen(QPen(QColor(0x00, 0x00, 0x00), 1))
        p.drawLine(0, self.height() - 1, self.width(), self.height() - 1)

    def _tick(self):
        fmt = "%I:%M %p" if not getattr(self._desk, "_clock_24h", False) else "%H:%M:%S"
        self.clock.setText(datetime.now().strftime(fmt).lstrip("0"))


# ─────────────────────────────────────────────────────────────
#  APPLICATION SWITCHER (bottom taskbar – System 7.5 style)
# ─────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────
#  BOOT SCREEN (System 7.5 style)
# ─────────────────────────────────────────────────────────────
class BootScreen75(QWidget):
    done = pyqtSignal()

    # Card dimensions
    CARD_W = 340
    CARD_H = 240

    def __init__(self, parent):
        super().__init__(parent)
        self.setGeometry(parent.rect())
        self.raise_()
        self.show()

        self._stages = [
            (5,   "Checking memory…"),
            (18,  "Loading System…"),
            (32,  "Loading Finder…"),
            (48,  "Starting Extensions…"),
            (62,  "Mounting Macintosh HD…"),
            (75,  "Loading Control Panels…"),
            (88,  "Loading Preferences…"),
            (100, "Welcome to Macintosh!"),
        ]
        self._idx = 0
        self._pct = 0
        self._msg = "Starting up…"

        t = QTimer(self)
        t.timeout.connect(self._step)
        t.start(280)
        self._t = t

    # ── card rect centred on screen ──────────────────────────
    def _card_rect(self):
        cx = (self.width()  - self.CARD_W) // 2
        cy = (self.height() - self.CARD_H) // 2
        return QRect(cx, cy, self.CARD_W, self.CARD_H)

    # ── everything drawn by paintEvent — no child widgets ───
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)

        # ── background: classic Mac dither ──────────────────
        p.fillRect(self.rect(), dither_brush())

        cr = self._card_rect()
        cx, cy, cw, ch = cr.x(), cr.y(), cr.width(), cr.height()

        # ── drop shadow ─────────────────────────────────────
        p.fillRect(cx+4, cy+4, cw, ch, QColor(0, 0, 0, 120))

        # ── card background ──────────────────────────────────
        p.fillRect(cx, cy, cw, ch, QColor(0xEE, 0xEE, 0xEE))

        # ── card border: 2px black ───────────────────────────
        p.setPen(QPen(C_BLACK, 2))
        p.setBrush(Qt.NoBrush)
        p.drawRect(cx, cy, cw-1, ch-1)

        # ── inner white frame (the "welcome" panel inset) ────
        fx, fy, fw, fh = cx+12, cy+12, cw-24, 128
        p.fillRect(fx, fy, fw, fh, C_WHITE)
        p.setPen(QPen(C_BLACK, 1))
        p.drawRect(fx, fy, fw-1, fh-1)

        # ── Finder face inside the white panel ───────────────
        self._draw_finder_face(p, fx + (fw - 72)//2, fy + 8, 72)

        # ── "Mac OS" text below face ──────────────────────────
        p.setFont(font_chicago(18, True))
        p.setPen(C_BLACK)
        txt_y = fy + fh - 28
        # "Mac" in black, "OS" in blue (classic Mac OS 8 style)
        mac_r = QRect(fx, txt_y, fw//2 + 10, 24)
        os_r  = QRect(fx + fw//2 + 6, txt_y, fw//2 - 6, 24)
        p.setPen(C_BLACK)
        p.drawText(mac_r, Qt.AlignRight | Qt.AlignVCenter, "Mac")
        p.setPen(QColor(0x33, 0x66, 0xCC))
        p.setFont(font_chicago(18, True))
        p.drawText(os_r, Qt.AlignLeft | Qt.AlignVCenter, "OS")

        # ── status text ──────────────────────────────────────
        p.setFont(font_chicago(10))
        p.setPen(C_BLACK)
        msg_y = cy + 12 + 128 + 10
        p.drawText(QRect(cx, msg_y, cw, 18), Qt.AlignCenter, self._msg)

        # ── progress bar ─────────────────────────────────────
        BAR_W, BAR_H = 260, 16
        bx = cx + (cw - BAR_W) // 2
        by = cy + ch - 36
        # white bg
        p.fillRect(bx, by, BAR_W, BAR_H, C_WHITE)
        # blue fill
        fill_w = int((BAR_W - 4) * self._pct / 100)
        if fill_w > 0:
            grad = QLinearGradient(bx+2, by+2, bx+2, by+BAR_H-2)
            grad.setColorAt(0,   QColor(0x99, 0xBB, 0xEE))
            grad.setColorAt(0.4, QColor(0x44, 0x77, 0xCC))
            grad.setColorAt(1,   QColor(0x22, 0x44, 0x99))
            p.fillRect(bx+2, by+2, fill_w, BAR_H-4, QBrush(grad))
        # border: 2px black
        p.setPen(QPen(C_BLACK, 2))
        p.setBrush(Qt.NoBrush)
        p.drawRect(bx, by, BAR_W-1, BAR_H-1)

    def _draw_finder_face(self, p, x, y, size):
        """Draw the classic Mac Finder face icon pixel-perfectly."""
        s = size
        # outer border
        p.fillRect(x, y, s, s, C_BLACK)
        # left half — blue
        p.fillRect(x+1, y+1, s//2 - 1, s-2, QColor(0x73, 0x99, 0xCC))
        # right half — white
        p.fillRect(x + s//2, y+1, s//2 - 1, s-2, C_WHITE)
        # vertical divider
        p.fillRect(x + s//2 - 1, y+1, 2, s-2, C_BLACK)

        # LEFT eye: white rect
        ew, eh = s*20//72, s*18//72
        ex, ey = x + s*8//72, y + s*14//72
        p.fillRect(ex, ey, ew, eh, C_WHITE)
        # pupil
        pw, ph = s*10//72, s*9//72
        px2, py2 = ex + s*3//72, ey + s*3//72
        p.fillRect(px2, py2, pw, ph, C_BLACK)
        # highlight
        p.fillRect(px2, py2, s*3//72, s*3//72, C_WHITE)
        # lower left: lighter blue
        p.fillRect(x+1, y + s*42//72, s//2 - 2, s - 2 - s*42//72, QColor(0x99, 0xBB, 0xDD))

        # RIGHT eye: black rect
        rex, rey = x + s*47//72, y + s*17//72
        rew, reh = s*20//72, s*14//72
        p.fillRect(rex, rey, rew, reh, C_BLACK)
        # white
        p.fillRect(rex + s*2//72, rey + s*2//72, s*10//72, s*7//72, C_WHITE)
        # pupil
        p.fillRect(rex + s*2//72, rey + s*2//72, s*4//72, s*4//72, C_BLACK)

        # smile arc
        p.setPen(QPen(C_BLACK, max(1, s//24)))
        p.setBrush(Qt.NoBrush)
        arc_x = x + s*44//72
        arc_y = y + s*40//72
        arc_w = s*26//72
        arc_h = s*22//72
        p.drawArc(arc_x, arc_y, arc_w, arc_h, 0, -180*16)

    def _step(self):
        if self._idx >= len(self._stages):
            self._t.stop()
            anim = QPropertyAnimation(self, b"windowOpacity")
            anim.setDuration(400)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.finished.connect(self._finish)
            anim.start()
            self._fade_anim = anim
            return
        self._pct, self._msg = self._stages[self._idx]
        self._idx += 1
        self.update()

    def _finish(self):
        self.hide()
        self.done.emit()


# ─────────────────────────────────────────────────────────────
#  ZOOM RECTS ANIMATION  (System 7 window open/close effect)
# ─────────────────────────────────────────────────────────────
class _ZoomRectsOverlay(QWidget):
    """
    Authentic System 7 ZoomRects: fixed N wireframe rects drawn with XOR,
    marching from window rect toward close box in discrete steps.
    """
    STEPS       = 8     # number of discrete animation frames
    INTERVAL_MS = 28    # ~35 fps — fast but eye can catch the lines
    TUNNEL_N    = 4     # how many rects visible simultaneously (tunnel depth)
    DURATION_MS = STEPS * INTERVAL_MS

    def __init__(self, parent, from_rect: QRect, to_rect: QRect, opening=True):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(parent.rect())
        self._from    = from_rect
        self._to      = to_rect
        self._opening = opening
        self._step    = 0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(self.INTERVAL_MS)

    def _tick(self):
        self._step += 1
        self.update()
        if self._step > self.STEPS:
            self._timer.stop()
            self.hide()
            self.deleteLater()

    def _lerp_rect(self, t: float) -> QRect:
        """Linearly interpolate between from and to rect at position t ∈ [0,1]."""
        t = max(0.0, min(1.0, t))
        x = int(self._from.x() + (self._to.x() - self._from.x()) * t)
        y = int(self._from.y() + (self._to.y() - self._from.y()) * t)
        w = int(self._from.width()  + (self._to.width()  - self._from.width())  * t)
        h = int(self._from.height() + (self._to.height() - self._from.height()) * t)
        return QRect(x, y, w, h)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.setBrush(Qt.NoBrush)
        # XOR composition — invert whatever is under the 1px black lines,
        # exactly like the original 68k Toolbox RasterOp patXor
        p.setCompositionMode(QPainter.RasterOp_SourceXorDestination)

        # Draw TUNNEL_N simultaneous rects spaced evenly behind the leading edge
        # leading_t advances from 0→1 (open) or 0→1 (close, from=win to=closebox)
        leading_t = self._step / self.STEPS
        spacing   = 1.0 / self.STEPS  # gap between consecutive rects

        for i in range(self.TUNNEL_N):
            t = leading_t - i * spacing
            if t < 0:
                continue
            r = self._lerp_rect(t)
            if r.width() < 1 or r.height() < 1:
                continue
            p.setPen(QPen(Qt.white, 1, Qt.SolidLine))  # white XOR = inversion
            p.drawRect(r)


# ─────────────────────────────────────────────────────────────
#  MACPAINT WINDOW
# ─────────────────────────────────────────────────────────────
class MacPaintWindow(Mac75Window):
    """Simple pixel-art canvas à la MacPaint."""

    TOOLS = ["pencil", "eraser", "fill", "line", "rect", "oval"]
    TOOL_ICONS = {"pencil":"Pen", "eraser":"Eras", "fill":"Fill", "line":"Line", "rect":"Rect", "oval":"Oval"}
    COLORS = [
        QColor(0,0,0), QColor(255,255,255), QColor(128,128,128), QColor(192,192,192),
        QColor(255,0,0), QColor(0,255,0), QColor(0,0,255), QColor(255,255,0),
        QColor(255,128,0), QColor(128,0,255), QColor(0,255,255), QColor(255,0,255),
    ]
    PALETTE_W  = 56
    TOOLBAR_H  = 28

    def __init__(self, parent):
        super().__init__(parent, "MacPaint", "macpaint", has_zoom=True, has_resize=True)
        self.resize(560, 420)

        self._tool  = "pencil"
        self._color = QColor(0, 0, 0)
        self._bg    = QColor(255, 255, 255)
        self._sz    = 2          # brush size
        self._drawing = False
        self._last_pt = None
        self._line_start = None

        c = self.content_widget()
        c.setAttribute(Qt.WA_StyledBackground, True)
        c.setStyleSheet("background:#CCCCCC;")

        # Main layout: toolbar top, then [palette | canvas]
        vlay = QVBoxLayout(c)
        vlay.setContentsMargins(2, 2, 2, 2)
        vlay.setSpacing(2)

        # ── Toolbar ──
        tb = QWidget()
        tb.setFixedHeight(self.TOOLBAR_H)
        tb.setStyleSheet("background:#CCCCCC;")
        tb_lay = QHBoxLayout(tb)
        tb_lay.setContentsMargins(2, 2, 2, 2)
        tb_lay.setSpacing(3)

        for t in self.TOOLS:
            btn = Mac75Button(self.TOOL_ICONS[t], tb)
            btn.setFixedSize(36, 22)
            btn.setFont(font_chicago(9))
            btn.clicked.connect(lambda checked, tool=t: self._set_tool(tool))
            btn._tool_name = t
            tb_lay.addWidget(btn)
            setattr(self, f"_btn_{t}", btn)

        tb_lay.addStretch()
        # Brush size selector
        for sz, lbl in [(1,"·"),(2,"•"),(4,"●")]:
            btn = Mac75Button(lbl, tb)
            btn.setFixedSize(22, 22)
            btn.setFont(font_chicago(10))
            btn.clicked.connect(lambda checked, s=sz: setattr(self, "_sz", s))
            tb_lay.addWidget(btn)

        btn_clr = make_toolbar_btn("Clear")
        btn_clr.clicked.connect(self._clear_canvas)
        tb_lay.addWidget(btn_clr)
        vlay.addWidget(tb)

        # ── Middle: palette + canvas ──
        mid = QWidget()
        mid.setStyleSheet("background:#CCCCCC;")
        mid_lay = QHBoxLayout(mid)
        mid_lay.setContentsMargins(0, 0, 0, 0)
        mid_lay.setSpacing(2)

        # Color palette
        pal = _PaletteWidget(self.COLORS, self)
        pal.setFixedWidth(self.PALETTE_W)
        pal.color_picked.connect(self._pick_color)
        self._pal = pal
        mid_lay.addWidget(pal)

        # Canvas
        self._canvas = _CanvasWidget(self)
        mid_lay.addWidget(self._canvas, 1)
        vlay.addWidget(mid, 1)

        self._highlight_tool()

    def _set_tool(self, t):
        self._tool = t
        self._highlight_tool()

    def _highlight_tool(self):
        for t in self.TOOLS:
            btn = getattr(self, f"_btn_{t}", None)
            if btn:
                btn._pressed = (t == self._tool)
                btn.update()

    def _pick_color(self, c):
        self._color = c

    def _clear_canvas(self):
        self._canvas.clear_canvas()


class _PaletteWidget(QWidget):
    color_picked = pyqtSignal(QColor)

    def __init__(self, colors, paint_win):
        super().__init__()
        self._colors = colors
        self._pw = paint_win
        self._sel = 0

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        
        # current fg/bg swatches
        p.fillRect(4, 4, 22, 22, self._pw._bg)
        p.setPen(QPen(C_BLACK, 1)); p.setBrush(Qt.NoBrush)
        p.drawRect(4, 4, 21, 21)
        p.fillRect(14, 14, 22, 22, self._pw._color)
        p.setPen(QPen(C_BLACK, 1)); p.drawRect(14, 14, 21, 21)
        # grid of colors
        cols = 2
        sw = (self.width() - 6) // cols
        sh = 12
        for i, c in enumerate(self._colors):
            col = i % cols
            row = i // cols
            x = 3 + col * sw
            y = 40 + row * (sh + 2)
            p.fillRect(x, y, sw - 1, sh, c)
            if i == self._sel:
                p.setPen(QPen(C_WHITE, 1))
                p.drawRect(x, y, sw-2, sh-1)
            p.setPen(QPen(C_BLACK, 1))
            p.drawRect(x, y, sw-2, sh-1)

    def mousePressEvent(self, e):
        cols = 2
        sw = (self.width() - 6) // cols
        sh = 12
        for i in range(len(self._colors)):
            col = i % cols
            row = i // cols
            x = 3 + col * sw
            y = 40 + row * (sh + 2)
            if QRect(x, y, sw-1, sh).contains(e.pos()):
                self._sel = i
                if e.button() == Qt.LeftButton:
                    self._pw._color = self._colors[i]
                else:
                    self._pw._bg = self._colors[i]
                self.color_picked.emit(self._colors[i])
                self.update()
                break


class _CanvasWidget(QWidget):
    def __init__(self, paint_win):
        super().__init__()
        self._pw = paint_win
        self._pixmap = None
        self._tmp_pixmap = None  # for line/rect/oval preview
        self.setMouseTracking(True)

    def _ensure_pixmap(self):
        if self._pixmap is None or self._pixmap.size() != self.size():
            old = self._pixmap
            self._pixmap = QPixmap(self.size())
            self._pixmap.fill(Qt.white)
            if old and not old.isNull():
                p = QPainter(self._pixmap)
                p.drawPixmap(0, 0, old)
                p.end()

    def clear_canvas(self):
        self._ensure_pixmap()
        self._pixmap.fill(Qt.white)
        self.update()

    def resizeEvent(self, e):
        self._ensure_pixmap()
        super().resizeEvent(e)

    def paintEvent(self, e):
        self._ensure_pixmap()
        p = QPainter(self)
        p.drawPixmap(0, 0, self._pixmap)
        if self._tmp_pixmap:
            p.drawPixmap(0, 0, self._tmp_pixmap)
        # canvas border
        p.setPen(QPen(C_BLACK, 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(0, 0, self.width()-1, self.height()-1)

    def mousePressEvent(self, e):
        self._ensure_pixmap()
        self._pw._drawing = True
        pt = e.pos()
        col = self._pw._color if e.button() == Qt.LeftButton else self._pw._bg
        tool = self._pw._tool

        if tool == "fill":
            self._flood_fill(pt, col)
            self.update()
            return
        if tool in ("line", "rect", "oval"):
            self._pw._line_start = pt
            self._tmp_pixmap = QPixmap(self.size())
            self._tmp_pixmap.fill(Qt.transparent)
            return
        # pencil / eraser: draw dot
        p = QPainter(self._pixmap)
        p.setPen(Qt.NoPen)
        sz = self._pw._sz
        c = col if tool == "pencil" else self._pw._bg
        p.setBrush(QBrush(c))
        p.drawEllipse(pt.x()-sz//2, pt.y()-sz//2, sz, sz)
        p.end()
        self._pw._last_pt = pt
        self.update()

    def mouseMoveEvent(self, e):
        if not self._pw._drawing:
            return
        self._ensure_pixmap()
        pt = e.pos()
        col = self._pw._color
        tool = self._pw._tool
        sz = self._pw._sz

        if tool in ("pencil", "eraser"):
            lp = self._pw._last_pt or pt
            p = QPainter(self._pixmap)
            pen = QPen(col if tool=="pencil" else self._pw._bg, sz, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            p.setPen(pen)
            p.drawLine(lp, pt)
            p.end()
            self._pw._last_pt = pt
            self.update()
        elif tool in ("line","rect","oval") and self._pw._line_start:
            self._tmp_pixmap = QPixmap(self.size())
            self._tmp_pixmap.fill(Qt.transparent)
            p = QPainter(self._tmp_pixmap)
            pen = QPen(col, sz)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            s, e2 = self._pw._line_start, pt
            if tool == "line":
                p.drawLine(s, e2)
            elif tool == "rect":
                p.drawRect(QRect(s, e2).normalized())
            elif tool == "oval":
                p.drawEllipse(QRect(s, e2).normalized())
            p.end()
            self.update()

    def mouseReleaseEvent(self, e):
        if not self._pw._drawing:
            return
        self._ensure_pixmap()
        tool = self._pw._tool
        pt = e.pos()
        col = self._pw._color if e.button() == Qt.LeftButton else self._pw._bg
        sz = self._pw._sz

        if tool in ("line","rect","oval") and self._pw._line_start:
            p = QPainter(self._pixmap)
            pen = QPen(col, sz)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            s = self._pw._line_start
            if tool == "line":
                p.drawLine(s, pt)
            elif tool == "rect":
                p.drawRect(QRect(s, pt).normalized())
            elif tool == "oval":
                p.drawEllipse(QRect(s, pt).normalized())
            p.end()
            self._tmp_pixmap = None
        self._pw._drawing = False
        self._pw._last_pt = None
        self._pw._line_start = None
        self.update()

    def _flood_fill(self, pt, fill_color):
        img = self._pixmap.toImage().convertToFormat(QImage.Format_RGB32)
        W, H = img.width(), img.height()
        x0, y0 = pt.x(), pt.y()
        if not (0 <= x0 < W and 0 <= y0 < H):
            return
        target = img.pixel(x0, y0)
        fc = fill_color.rgb()
        if target == fc:
            return
        stack = [(x0, y0)]
        visited = set()
        while stack:
            x, y = stack.pop()
            if (x, y) in visited or not (0 <= x < W and 0 <= y < H):
                continue
            if img.pixel(x, y) != target:
                continue
            visited.add((x, y))
            img.setPixel(x, y, fc)
            stack += [(x+1,y),(x-1,y),(x,y+1),(x,y-1)]
        self._pixmap = QPixmap.fromImage(img)


# ─────────────────────────────────────────────────────────────
#  PUZZLE WINDOW  (15-puzzle classic desk accessory)
# ─────────────────────────────────────────────────────────────
class PuzzleWindow(Mac75Window):
    """Classic Mac 15-puzzle desk accessory."""
    GRID = 4
    TILE = 68

    def __init__(self, parent):
        super().__init__(parent, "Puzzle", "puzzle", has_resize=False, has_zoom=False)
        sz = self.GRID * self.TILE + 12
        self.resize(sz, sz + self.TITLE_H + 34)
        import random as _rand
        self._tiles = list(range(1, self.GRID*self.GRID)) + [0]
        # shuffle with 200 random valid moves
        for _ in range(400):
            blank = self._tiles.index(0)
            r, c = blank // self.GRID, blank % self.GRID
            moves = []
            for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                nr, nc = r+dr, c+dc
                if 0 <= nr < self.GRID and 0 <= nc < self.GRID:
                    moves.append(nr*self.GRID+nc)
            nb = _rand.choice(moves)
            self._tiles[blank], self._tiles[nb] = self._tiles[nb], self._tiles[blank]
        self._solved = False
        self._moves = 0

        c = self.content_widget()
        c.setAttribute(Qt.WA_StyledBackground, True)
        c.setStyleSheet("background:#CCCCCC;")
        vlay = QVBoxLayout(c)
        vlay.setContentsMargins(4, 4, 4, 4)
        vlay.setSpacing(4)

        self._canvas = QWidget()
        self._canvas.setFixedSize(self.GRID*self.TILE+4, self.GRID*self.TILE+4)
        self._canvas.setStyleSheet("background:#CCCCCC;")
        self._canvas.paintEvent = self._paint_puzzle
        self._canvas.mousePressEvent = self._click_tile
        vlay.addWidget(self._canvas, 0, Qt.AlignCenter)

        bar = QWidget()
        bar.setStyleSheet("background:transparent;")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(0, 0, 0, 0)
        self._stat_lbl = QLabel("Moves: 0")
        self._stat_lbl.setFont(font_chicago(10))
        self._stat_lbl.setStyleSheet("background:transparent;")
        btn_new = Mac75Button("New Game", bar)
        btn_new.clicked.connect(self._new_game)
        bl.addWidget(self._stat_lbl, 1)
        bl.addWidget(btn_new)
        vlay.addWidget(bar)

    def _paint_puzzle(self, e):
        p = QPainter(self._canvas)
        p.setRenderHint(QPainter.Antialiasing, False)
        T = self.TILE
        G = self.GRID
        for idx, val in enumerate(self._tiles):
            r, c = idx // G, idx % G
            x, y = 2 + c*T, 2 + r*T
            if val == 0:
                p.fillRect(x, y, T-2, T-2, QColor(0xBB, 0xBB, 0xBB))
                continue
            # tile face
            grad = QLinearGradient(x, y, x, y+T-2)
            grad.setColorAt(0, QColor(0xEE, 0xEE, 0xEE))
            grad.setColorAt(1, QColor(0xBB, 0xBB, 0xBB))
            p.fillRect(x, y, T-2, T-2, QBrush(grad))
            # bevel
            p.setPen(QPen(C_WHITE, 1))
            p.drawLine(x, y, x+T-3, y)
            p.drawLine(x, y, x, y+T-3)
            p.setPen(QPen(C_BLACK, 1))
            p.drawLine(x+T-2, y, x+T-2, y+T-2)
            p.drawLine(x, y+T-2, x+T-2, y+T-2)
            # number
            p.setFont(font_chicago(20, True))
            p.setPen(C_BLACK)
            p.drawText(QRect(x, y, T-2, T-2), Qt.AlignCenter, str(val))
        if self._solved:
            p.setFont(font_chicago(14, True))
            p.setPen(QColor(0x00, 0x00, 0x88))
            p.drawText(self._canvas.rect(), Qt.AlignCenter, "🎉 Solved!")

    def _click_tile(self, e):
        if self._solved:
            return
        T = self.TILE
        G = self.GRID
        c = (e.x() - 2) // T
        r = (e.y() - 2) // T
        if not (0 <= r < G and 0 <= c < G):
            return
        clicked = r*G + c
        blank = self._tiles.index(0)
        br, bc = blank // G, blank % G
        cr, cc = r, c
        # Check if adjacent
        if (abs(br - cr) == 1 and bc == cc) or (abs(bc - cc) == 1 and br == cr):
            self._tiles[blank], self._tiles[clicked] = self._tiles[clicked], self._tiles[blank]
            self._moves += 1
            self._stat_lbl.setText(f"Moves: {self._moves}")
            if self._tiles == list(range(1, G*G)) + [0]:
                self._solved = True
                self._stat_lbl.setText(f"Solved in {self._moves} moves! 🎉")
            self._canvas.update()

    def _new_game(self):
        import random as _rand
        G = self.GRID
        self._tiles = list(range(1, G*G)) + [0]
        for _ in range(400):
            blank = self._tiles.index(0)
            r, c = blank // G, blank % G
            moves = []
            for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                nr, nc = r+dr, c+dc
                if 0 <= nr < G and 0 <= nc < G:
                    moves.append(nr*G+nc)
            nb = _rand.choice(moves)
            self._tiles[blank], self._tiles[nb] = self._tiles[nb], self._tiles[blank]
        self._solved = False
        self._moves = 0
        self._stat_lbl.setText("Moves: 0")
        self._canvas.update()


# ─────────────────────────────────────────────────────────────
#  SCRAPBOOK WINDOW
# ─────────────────────────────────────────────────────────────
class ScrapbookWindow(Mac75Window):
    """System 7 Scrapbook desk accessory."""
    def __init__(self, parent):
        super().__init__(parent, "Scrapbook", "scrapbook", has_resize=True, has_zoom=False)
        self.resize(400, 320)
        self._pages = [
            ("Text", "Welcome to ClassicOS 7.5 Scrapbook!\n\nThis is page 1.\nYou can add text notes here."),
            ("Text", "Page 2 — Notes\n\nClassicOS 7.5 simulates System 7.5 Platinum.\nEnjoy the nostalgia!"),
            ("Text", "Page 3 — Ideas\n\n• Build cool apps\n• Explore the filesystem\n• Have fun!"),
        ]
        self._page = 0

        c = self.content_widget()
        c.setAttribute(Qt.WA_StyledBackground, True)
        c.setStyleSheet("background:#EEEEEE;")
        vlay = QVBoxLayout(c)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        # toolbar
        tb = QWidget(); tb.setFixedHeight(26)
        tb.setStyleSheet("background:#CCCCCC; border-bottom:1px solid #000;")
        tl = QHBoxLayout(tb); tl.setContentsMargins(4, 3, 4, 3); tl.setSpacing(4)
        self._prev_btn = Mac75Button("◀ Prev", tb)
        self._next_btn = Mac75Button("Next ▶", tb)
        self._add_btn  = Mac75Button("Add Page", tb)
        self._del_btn  = Mac75Button("Delete", tb)
        self._page_lbl = QLabel("1 / 3"); self._page_lbl.setFont(font_chicago(10))
        self._page_lbl.setStyleSheet("background:transparent;")
        self._prev_btn.clicked.connect(self._prev)
        self._next_btn.clicked.connect(self._next)
        self._add_btn.clicked.connect(self._add)
        self._del_btn.clicked.connect(self._delete)
        for w in [self._prev_btn, self._next_btn, self._page_lbl, self._add_btn, self._del_btn]:
            tl.addWidget(w)
        tl.addStretch()
        vlay.addWidget(tb)

        # content area
        self._editor = QPlainTextEdit()
        self._editor.setFont(QFont("Courier New", 12))
        self._editor.setStyleSheet("background:white; border:none; padding:8px;")
        self._editor.textChanged.connect(self._save_current)
        vlay.addWidget(self._editor, 1)

        # status
        self._stat = QLabel("Scrapbook — 3 pages")
        self._stat.setFont(font_chicago(9))
        self._stat.setFixedHeight(16)
        self._stat.setStyleSheet("background:#CCCCCC; border-top:1px solid #000; padding:0 4px;")
        vlay.addWidget(self._stat)
        self._load_page()

    def _load_page(self):
        self._editor.blockSignals(True)
        self._editor.setPlainText(self._pages[self._page][1])
        self._editor.blockSignals(False)
        total = len(self._pages)
        self._page_lbl.setText(f"{self._page+1} / {total}")
        self._stat.setText(f"Scrapbook — {total} page{'s' if total!=1 else ''}")

    def _save_current(self):
        kind, _ = self._pages[self._page]
        self._pages[self._page] = (kind, self._editor.toPlainText())

    def _prev(self):
        if self._page > 0:
            self._page -= 1; self._load_page()

    def _next(self):
        if self._page < len(self._pages) - 1:
            self._page += 1; self._load_page()

    def _add(self):
        self._pages.append(("Text", "New page…"))
        self._page = len(self._pages) - 1
        self._load_page()

    def _delete(self):
        if len(self._pages) <= 1:
            return
        self._pages.pop(self._page)
        self._page = min(self._page, len(self._pages)-1)
        self._load_page()


# ─────────────────────────────────────────────────────────────
#  ALARM CLOCK WINDOW
# ─────────────────────────────────────────────────────────────
class AlarmClockWindow(Mac75Window):
    """Classic Mac Alarm Clock desk accessory."""
    def __init__(self, parent):
        super().__init__(parent, "Alarm Clock", "alarm_clock", has_resize=False, has_zoom=False)
        self.resize(200, 160)
        self._alarm_time = None
        self._alarm_on = False
        self._show_seconds = True

        c = self.content_widget()
        c.setAttribute(Qt.WA_StyledBackground, True)
        c.setStyleSheet("background:#CCCCCC;")
        vlay = QVBoxLayout(c)
        vlay.setContentsMargins(8, 8, 8, 8)
        vlay.setSpacing(6)

        # Digital clock display
        self._time_lbl = QLabel("12:00:00 AM")
        self._time_lbl.setAlignment(Qt.AlignCenter)
        self._time_lbl.setFont(QFont("Courier New", 20, QFont.Bold))
        self._time_lbl.setStyleSheet(
            "background:#AABBAA; border:2px inset #888; padding:4px 8px; color:#001100;")
        vlay.addWidget(self._time_lbl)

        # Date display
        self._date_lbl = QLabel()
        self._date_lbl.setAlignment(Qt.AlignCenter)
        self._date_lbl.setFont(font_chicago(10))
        self._date_lbl.setStyleSheet("background:transparent;")
        vlay.addWidget(self._date_lbl)

        # Alarm row
        alarm_row = QWidget(); alarm_row.setStyleSheet("background:transparent;")
        al = QHBoxLayout(alarm_row); al.setContentsMargins(0, 0, 0, 0); al.setSpacing(4)
        alarm_lbl = QLabel("Alarm:"); alarm_lbl.setFont(font_chicago(10))
        alarm_lbl.setStyleSheet("background:transparent;")
        self._alarm_edit = QLineEdit("07:00 AM")
        self._alarm_edit.setFont(font_chicago(10))
        self._alarm_edit.setFixedWidth(80)
        self._alarm_edit.setStyleSheet("border:2px inset #888; background:white; padding:1px 3px;")
        self._alarm_chk_btn = Mac75Button("Set Alarm", alarm_row, small=True)
        self._alarm_chk_btn.clicked.connect(self._toggle_alarm)
        al.addWidget(alarm_lbl); al.addWidget(self._alarm_edit); al.addWidget(self._alarm_chk_btn)
        vlay.addWidget(alarm_row)

        self._alarm_status = QLabel("Alarm off")
        self._alarm_status.setFont(font_chicago(9))
        self._alarm_status.setAlignment(Qt.AlignCenter)
        self._alarm_status.setStyleSheet("background:transparent; color:#666;")
        vlay.addWidget(self._alarm_status)
        vlay.addStretch()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(500)
        self._tick()

    def _tick(self):
        now = datetime.now()
        self._time_lbl.setText(now.strftime("%I:%M:%S %p"))
        self._date_lbl.setText(now.strftime("%A, %B %d, %Y"))
        if self._alarm_on and self._alarm_time:
            t_str = now.strftime("%I:%M %p").lstrip("0")
            if self._alarm_time == now.strftime("%I:%M %p") or \
               self._alarm_time == now.strftime("%-I:%M %p"):
                Mac75Dialog.info(self.parent(), "Alarm Clock", f"⏰ ALARM! It's {t_str}")
                self._alarm_on = False
                self._alarm_status.setText("Alarm off")

    def _toggle_alarm(self):
        if self._alarm_on:
            self._alarm_on = False
            self._alarm_status.setText("Alarm off")
            self._alarm_chk_btn.setText("Set Alarm")
        else:
            t = self._alarm_edit.text().strip()
            self._alarm_time = t
            self._alarm_on = True
            self._alarm_status.setText(f"Alarm set: {t}")
            self._alarm_chk_btn.setText("Cancel")


# ─────────────────────────────────────────────────────────────
#  CHOOSER WINDOW
# ─────────────────────────────────────────────────────────────
class ChooserWindow(Mac75Window):
    """Classic Mac Chooser desk accessory."""
    def __init__(self, parent):
        super().__init__(parent, "Chooser", "chooser", has_resize=False, has_zoom=False)
        self.resize(340, 240)
        c = self.content_widget()
        c.setAttribute(Qt.WA_StyledBackground, True)
        c.setStyleSheet("background:#CCCCCC;")
        vlay = QVBoxLayout(c)
        vlay.setContentsMargins(8, 8, 8, 8)
        vlay.setSpacing(6)

        hlay = QHBoxLayout()
        # Left: device list
        left = QWidget(); left.setStyleSheet("background:white; border:2px inset #888;")
        ll = QVBoxLayout(left); ll.setContentsMargins(4, 4, 4, 4)
        lbl_dev = QLabel("AppleTalk Zones"); lbl_dev.setFont(font_chicago(10, True))
        lbl_dev.setStyleSheet("background:transparent;")
        self._zone_list = QListWidget()
        self._zone_list.setFont(font_chicago(10))
        self._zone_list.setStyleSheet("border:none; background:transparent;")
        for z in ["*", "LocalZone", "ClassicNet", "MacLAN"]:
            self._zone_list.addItem(z)
        self._zone_list.setCurrentRow(0)
        ll.addWidget(lbl_dev); ll.addWidget(self._zone_list)

        # Right: device icons
        right = QWidget(); right.setStyleSheet("background:white; border:2px inset #888;")
        rl = QVBoxLayout(right); rl.setContentsMargins(4, 4, 4, 4)
        lbl_dev2 = QLabel("Devices"); lbl_dev2.setFont(font_chicago(10, True))
        lbl_dev2.setStyleSheet("background:transparent;")
        self._dev_list = QListWidget()
        self._dev_list.setFont(font_chicago(10))
        self._dev_list.setStyleSheet("border:none; background:transparent;")
        for d in ["LaserWriter", "ImageWriter", "StyleWriter", "Network Printer"]:
            self._dev_list.addItem(d)
        rl.addWidget(lbl_dev2); rl.addWidget(self._dev_list)
        hlay.addWidget(left); hlay.addWidget(right)
        vlay.addLayout(hlay)

        # AppleTalk toggle
        at_row = QWidget(); at_row.setStyleSheet("background:transparent;")
        atl = QHBoxLayout(at_row); atl.setContentsMargins(0, 0, 0, 0)
        at_lbl = QLabel("AppleTalk:"); at_lbl.setFont(font_chicago(10))
        at_lbl.setStyleSheet("background:transparent;")
        self._at_btn = Mac75Button("Active", at_row, small=True)
        atl.addWidget(at_lbl); atl.addWidget(self._at_btn); atl.addStretch()
        vlay.addWidget(at_row)


# ─────────────────────────────────────────────────────────────
#  CONTROL STRIP (bottom-left System 7.5 floating panel)
# ─────────────────────────────────────────────────────────────
class ControlStrip(QWidget):
    """System 7.5 Control Strip — floating panel bottom.
    Left side: system controls (monitor, sound, brightness).
    Right side: app launcher icons for all apps."""

    ITEM_W = 28
    HEIGHT = 28

    def __init__(self, parent):
        super().__init__(parent)
        self._desk = parent
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background:#CCCCCC;")

        # System control items (left side)
        self._sys_items = [
            ("monitor_depth",  "Monitor Depth",   self._show_monitor_depth),
            ("monitor_res",    "Resolution",      self._show_monitor_res),
            ("sound",          "Sound Volume",    self._show_volume),
            ("brightness",     "Brightness",      self._show_brightness),
        ]

        # App launcher items (right side) — removed, icons are on desktop
        self._app_items = []

        self._pressed_sys = -1
        self._pressed_app = -1
        self._popup = None
        self.setMouseTracking(True)
        self._tooltip_txt = ""
        self._tooltip_timer = QTimer(self)
        self._tooltip_timer.setSingleShot(True)
        self._tooltip_timer.timeout.connect(self._show_tooltip)
        self._tooltip_pos = QPoint()
        self._collapsed = False
        self._update_size()

    def _update_size(self):
        if self._collapsed:
            self.setFixedSize(20, self.HEIGHT)
        else:
            n_sys = len(self._sys_items)
            n_app = len(self._app_items)
            # separator = 6px only if there are app items, 4px padding each side
            sep = 8 if n_app > 0 else 0
            w = 4 + n_sys * self.ITEM_W + sep + n_app * self.ITEM_W + 4
            self.setFixedSize(w, self.HEIGHT)

    def _sys_x(self, i):
        return 4 + i * self.ITEM_W

    def _app_x(self, i):
        n_sys = len(self._sys_items)
        return 4 + n_sys * self.ITEM_W + 8 + i * self.ITEM_W

    def _sep_x(self):
        return 4 + len(self._sys_items) * self.ITEM_W + 2

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        W, H = self.width(), self.height()

        # Background + raised bevel
        p.fillRect(0, 0, W, H, C_PLATINUM)
        p.setPen(QPen(C_WHITE, 1))
        p.drawLine(0, 0, W-1, 0)
        p.drawLine(0, 0, 0, H-1)
        p.setPen(QPen(C_BLACK, 1))
        p.drawLine(W-1, 0, W-1, H-1)
        p.drawLine(0, H-1, W-1, H-1)
        p.setPen(QPen(C_PLATINUM_DK, 1))
        p.drawLine(W-2, 1, W-2, H-2)
        p.drawLine(1, H-2, W-2, H-2)

        if self._collapsed:
            p.setPen(QPen(C_BLACK, 1))
            p.setBrush(QBrush(C_BLACK))
            pts = QPolygon([QPoint(6, 8), QPoint(6, 14), QPoint(14, 11)])
            p.drawPolygon(pts)
            return

        IH = H - 6  # icon height inside strip

        # Draw system control buttons
        for i, (icon_name, tooltip, _) in enumerate(self._sys_items):
            x = self._sys_x(i)
            pressed = (self._pressed_sys == i)
            bx, by, bw, bh = x, 2, self.ITEM_W - 2, IH
            if pressed:
                p.fillRect(bx, by, bw, bh, C_PLATINUM_DK)
                p.setPen(QPen(C_BLACK, 1))
            else:
                p.fillRect(bx, by, bw, bh, C_PLATINUM)
                p.setPen(QPen(C_WHITE, 1))
            p.drawLine(bx, by, bx+bw-1, by)
            p.drawLine(bx, by, bx, by+bh-1)
            p.setPen(QPen(C_PLATINUM_DK if not pressed else C_WHITE, 1))
            p.drawLine(bx+bw-1, by, bx+bw-1, by+bh-1)
            p.drawLine(bx, by+bh-1, bx+bw-1, by+bh-1)
            self._draw_strip_icon(p, icon_name, bx + bw//2 - 7, by + bh//2 - 7, 14)

        # Separator — only show if there are app items
        if self._app_items:
            sx = self._sep_x()
            p.setPen(QPen(C_PLATINUM_DK, 1))
            p.drawLine(sx, 3, sx, H-4)
            p.setPen(QPen(C_WHITE, 1))
            p.drawLine(sx+1, 3, sx+1, H-4)

        # Draw app launcher buttons
        for i, (icon_name, target, label) in enumerate(self._app_items):
            x = self._app_x(i)
            pressed = (self._pressed_app == i)
            # Check if app is running (window exists in WM)
            running = any(
                getattr(w, '_icon_target', '') == target
                for w in WM.windows
            )
            bx, by, bw, bh = x, 2, self.ITEM_W - 1, IH
            bg_col = QColor(0xBB, 0xBB, 0xBB) if pressed else (
                QColor(0xDD, 0xF0, 0xDD) if running else C_PLATINUM
            )
            p.fillRect(bx, by, bw, bh, bg_col)
            # Bevel
            p.setPen(QPen(C_WHITE if not pressed else C_PLATINUM_DK, 1))
            p.drawLine(bx, by, bx+bw-1, by)
            p.drawLine(bx, by, bx, by+bh-1)
            p.setPen(QPen(C_PLATINUM_DK if not pressed else C_WHITE, 1))
            p.drawLine(bx+bw-1, by, bx+bw-1, by+bh-1)
            p.drawLine(bx, by+bh-1, bx+bw-1, by+bh-1)
            # Draw icon using the global draw_icon function
            icon_size = min(IH - 2, 18)
            icon_ox = bx + (bw - icon_size) // 2
            icon_oy = by + (bh - icon_size) // 2
            draw_icon(p, icon_name, icon_ox, icon_oy, icon_size)
            # Running indicator — small dot below icon
            if running:
                p.setBrush(QBrush(QColor(0x00, 0x88, 0x00)))
                p.setPen(Qt.NoPen)
                p.drawEllipse(bx + bw//2 - 2, by + bh - 4, 4, 3)

    def _draw_strip_icon(self, p, name, x, y, size):
        """Draw tiny control strip system icons."""
        p.save()
        p.translate(x, y)
        s = size
        p.setPen(QPen(C_BLACK, 1))
        if name == "monitor_depth":
            p.fillRect(1, 0, s-3, s-4, QColor(0xCC, 0xDD, 0xFF))
            p.drawRect(1, 0, s-4, s-5)
            p.drawLine(s//2-2, s-4, s//2+2, s-4)
            p.drawLine(s//2, s-5, s//2, s-3)
            p.fillRect(2, 1, (s-6)//2, (s-6)//2, QColor(0xFF, 0x44, 0x44))
            p.fillRect(2+(s-6)//2, 1, (s-6)//2, (s-6)//2, QColor(0x44, 0xFF, 0x44))
            p.fillRect(2, 1+(s-6)//2, (s-6)//2, (s-6)//2, QColor(0x44, 0x44, 0xFF))
            p.fillRect(2+(s-6)//2, 1+(s-6)//2, (s-6)//2, (s-6)//2, QColor(0xFF, 0xFF, 0x44))
        elif name == "monitor_res":
            p.fillRect(1, 0, s-3, s-4, C_WHITE)
            p.drawRect(1, 0, s-4, s-5)
            p.drawLine(s//2-2, s-4, s//2+2, s-4)
            p.drawLine(s//2, s-5, s//2, s-3)
            p.setPen(QPen(C_BLACK, 1))
            for row2 in range(3):
                p.drawLine(3, 2+row2*3, s-4, 2+row2*3)
        elif name == "sound":
            pts = QPolygon([QPoint(1, s//2-3), QPoint(4, s//2-3),
                            QPoint(7, s//2-6), QPoint(7, s//2+6),
                            QPoint(4, s//2+3), QPoint(1, s//2+3)])
            p.setBrush(QBrush(C_BLACK))
            p.drawPolygon(pts)
            p.setBrush(Qt.NoBrush)
            p.drawArc(7, s//2-4, 4, 8, 90*16, -180*16)
            p.drawArc(7, s//2-6, 7, 12, 90*16, -180*16)
        elif name == "brightness":
            cx2, cy2 = s//2, s//2
            p.setBrush(QBrush(QColor(0xFF, 0xDD, 0x00)))
            p.drawEllipse(cx2-3, cy2-3, 6, 6)
            p.setPen(QPen(C_BLACK, 1))
            for angle in range(0, 360, 45):
                rad = math.radians(angle)
                p.drawLine(int(cx2 + 4*math.cos(rad)), int(cy2 + 4*math.sin(rad)),
                           int(cx2 + 6*math.cos(rad)), int(cy2 + 6*math.sin(rad)))
        p.restore()

    def mousePressEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        if self._collapsed:
            self._collapsed = False
            self._update_size()
            self._reposition()
            return
        x = e.x()
        # Check sys items
        for i in range(len(self._sys_items)):
            bx = self._sys_x(i)
            if bx <= x < bx + self.ITEM_W:
                self._pressed_sys = i
                self.update()
                return
        # Check app items
        for i in range(len(self._app_items)):
            bx = self._app_x(i)
            if bx <= x < bx + self.ITEM_W:
                self._pressed_app = i
                self.update()
                return

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton:
            return
        sys_idx = self._pressed_sys
        app_idx = self._pressed_app
        self._pressed_sys = -1
        self._pressed_app = -1
        self.update()

        if sys_idx >= 0:
            _, _, cb = self._sys_items[sys_idx]
            cb(self.mapToGlobal(QPoint(self._sys_x(sys_idx), self.height())))
        elif app_idx >= 0:
            icon_name, target, label = self._app_items[app_idx]
            # If window running, raise it; else open it
            for w in WM.windows:
                if getattr(w, '_icon_target', '') == target:
                    WM.raise_window(w)
                    if getattr(w, '_minimized', False):
                        w.restore()
                    self._desk._menu.raise_()
                    self._desk._wf_overlay.raise_()
                    self.update()
                    return
            self._desk.open_window(target)

    def mouseMoveEvent(self, e):
        if self._collapsed:
            return
        x = e.x()
        tip = ""
        for i, (_, tooltip, _) in enumerate(self._sys_items):
            bx = self._sys_x(i)
            if bx <= x < bx + self.ITEM_W:
                tip = tooltip
                break
        if not tip:
            for i, (_, target, label) in enumerate(self._app_items):
                bx = self._app_x(i)
                if bx <= x < bx + self.ITEM_W:
                    tip = label
                    break
        if tip:
            self._tooltip_txt = tip
            self._tooltip_pos = e.globalPos()
            self._tooltip_timer.start(500)
        else:
            self._tooltip_timer.stop()

    def _show_tooltip(self):
        QToolTip.showText(self._tooltip_pos, self._tooltip_txt)

    def _show_monitor_depth(self, pos):
        m = QMenu(self)
        m.setFont(font_chicago(10))
        m.setStyleSheet(
            "QMenu{background:#FFF; border:1px solid #000; padding:2px 0;}"
            "QMenu::item{padding:2px 20px 2px 20px;}"
            "QMenu::item:selected{background:#000; color:#FFF;}"
            "QMenu::separator{height:1px; background:#888; margin:2px 4px;}")
        title = m.addAction("Display")
        title.setEnabled(False)
        f = title.font(); f.setItalic(True); title.setFont(f)
        m.addSeparator()
        depths = [
            ("Black & White",       "bw"),
            ("4 Grays",             "gray4"),
            ("16 Grays",            "gray16"),
            ("256 Grays",           "gray256"),
            ("16 Colors",           "color16"),
            ("256 Colors",          "color256"),
            ("Thousands of Colors", "thousands"),
            ("Millions of Colors",  "millions"),
        ]
        current = getattr(self._desk, "_color_depth", "millions")
        for label, key in depths:
            act = m.addAction(label)
            act.setCheckable(True)
            act.setChecked(key == current)
            act.triggered.connect(lambda checked, k=key: self._apply_color_depth(k))
        m.exec_(pos)

    def _apply_color_depth(self, key):
        self._desk._color_depth = key
        desk = self._desk
        desk.setGraphicsEffect(None)
        if key == "millions":
            pass
        elif key == "thousands":
            eff = QGraphicsColorizeEffect(desk)
            eff.setColor(QColor(200, 200, 220)); eff.setStrength(0.08)
            desk.setGraphicsEffect(eff)
        elif key == "color256":
            eff = QGraphicsColorizeEffect(desk)
            eff.setColor(QColor(180, 180, 200)); eff.setStrength(0.15)
            desk.setGraphicsEffect(eff)
        elif key == "color16":
            eff = QGraphicsColorizeEffect(desk)
            eff.setColor(QColor(160, 160, 180)); eff.setStrength(0.35)
            desk.setGraphicsEffect(eff)
        elif key in ("gray256", "gray16", "gray4"):
            eff = QGraphicsColorizeEffect(desk)
            eff.setColor(QColor(128, 128, 128)); eff.setStrength(1.0)
            desk.setGraphicsEffect(eff)
        elif key == "bw":
            eff = QGraphicsColorizeEffect(desk)
            eff.setColor(Qt.white); eff.setStrength(1.0)
            desk.setGraphicsEffect(eff)

    def _show_monitor_res(self, pos):
        m = QMenu(self)
        m.setFont(font_chicago(10))
        m.setStyleSheet(
            "QMenu{background:#FFF; border:1px solid #000; padding:2px 0;}"
            "QMenu::item{padding:2px 20px 2px 20px;}"
            "QMenu::item:selected{background:#000; color:#FFF;}"
            "QMenu::separator{height:1px; background:#888; margin:2px 4px;}")
        title = m.addAction("Resolution")
        title.setEnabled(False)
        f = title.font(); f.setItalic(True); title.setFont(f)
        m.addSeparator()
        screen = QApplication.primaryScreen().availableGeometry()
        sw, sh = screen.width(), screen.height()
        resos = [(sw, sh), (1920, 1080), (1440, 900), (1280, 800),
                 (1024, 768), (800, 600), (640, 480)]
        seen = set()
        filtered = []
        for rw, rh in resos:
            if (rw, rh) not in seen and rw <= sw and rh <= sh:
                seen.add((rw, rh)); filtered.append((rw, rh))
        cur_w = getattr(self._desk, "_virt_w", sw)
        cur_h = getattr(self._desk, "_virt_h", sh)
        for rw, rh in filtered:
            act = m.addAction(f"{rw} \u00d7 {rh}")
            act.setCheckable(True)
            act.setChecked(rw == cur_w and rh == cur_h)
            act.triggered.connect(lambda checked, rw=rw, rh=rh: self._apply_resolution(rw, rh))
        m.exec_(pos)

    def _apply_resolution(self, rw, rh):
        desk = self._desk
        screen = QApplication.primaryScreen().availableGeometry()
        sw, sh = screen.width(), screen.height()
        desk._virt_w = rw
        desk._virt_h = rh
        if rw == sw and rh == sh:
            desk.setGeometry(screen)
        else:
            desk.setGeometry(
                screen.x() + (sw - rw) // 2,
                screen.y() + (sh - rh) // 2,
                rw, rh)
        desk._desk_rect = QRect(0, 22, desk.width(), desk.height() - 22)
        desk._menu.setGeometry(0, 0, desk.width(), 22)
        if hasattr(desk, "_control_strip"):
            desk._control_strip._reposition()

    def _show_volume(self, pos):
        m = QMenu(self)
        m.setFont(font_chicago(10))
        m.setStyleSheet(
            "QMenu{background:#FFF; border:1px solid #000; padding:2px 0;}"
            "QMenu::item{padding:2px 20px 2px 20px;}"
            "QMenu::item:selected{background:#000; color:#FFF;}")
        title = m.addAction("Sound Volume")
        title.setEnabled(False)
        f = title.font(); f.setItalic(True); title.setFont(f)
        m.addSeparator()
        for i in range(7, -1, -1):
            bar = "\u2588" * i + "\u2591" * (7-i)
            act = m.addAction(f" {bar} {i}")
            act.setCheckable(True)
            if i == 5:
                act.setChecked(True)
        m.exec_(pos)

    def _show_brightness(self, pos):
        m = QMenu(self)
        m.setFont(font_chicago(10))
        m.setStyleSheet(
            "QMenu{background:#FFF; border:1px solid #000; padding:2px 0;}"
            "QMenu::item{padding:2px 20px 2px 20px;}"
            "QMenu::item:selected{background:#000; color:#FFF;}")
        title = m.addAction("Brightness")
        title.setEnabled(False)
        f = title.font(); f.setItalic(True); title.setFont(f)
        m.addSeparator()
        current = getattr(self._desk, "_brightness", 6)
        for i in range(7, -1, -1):
            bar = "\u2593" * i + "\u2591" * (7-i)
            act = m.addAction(f" {bar} {i}")
            act.setCheckable(True)
            act.setChecked(i == current)
            act.triggered.connect(lambda checked, v=i: self._apply_brightness(v))
        m.exec_(pos)

    def _apply_brightness(self, level):
        self._desk._brightness = level
        desk = self._desk
        if not hasattr(desk, "_brightness_overlay"):
            overlay = QWidget(desk)
            overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
            overlay.setAttribute(Qt.WA_NoSystemBackground)
            desk._brightness_overlay = overlay
        overlay = desk._brightness_overlay
        overlay.setGeometry(desk.rect())
        if level >= 7:
            overlay.hide()
            return
        alpha = int((7 - level) * 30)
        overlay.setStyleSheet(f"background: rgba(0,0,0,{alpha});")
        overlay.show()
        overlay.raise_()

    def _reposition(self):
        desk = self._desk
        x = 2
        y = desk.height() - self.HEIGHT - 4
        self.move(x, y)
        self.raise_()



# ─────────────────────────────────────────────────────────────
#  WIREFRAME DRAG OVERLAY  (always on top of all windows)
# ─────────────────────────────────────────────────────────────
class _WireframeOverlay(QWidget):
    """Transparent full-screen overlay that draws the drag wireframe on top of everything."""
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._rect = None
        self.hide()

    def set_rect(self, rect):
        self._rect = rect
        self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()
        self.update()

    def clear(self):
        self._rect = None
        self.hide()

    def paintEvent(self, e):
        if not self._rect:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        pen = QPen(C_BLACK, 1, Qt.DashLine)
        pen.setDashPattern([4, 3])
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRect(self._rect.adjusted(0, 0, -2, -2))


# ─────────────────────────────────────────────────────────────
#  MAIN DESKTOP
# ─────────────────────────────────────────────────────────────
class Desktop75(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ClassicOS 7.5")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("background: #888888;")  # Classic Platinum Gray
        self._clock_24h = False

        # Menu bar
        self._menu = MenuBar75(self)
        self._menu.setGeometry(0, 0, self.width(), 22)
        self._menu.hide()

        # No bottom app switcher — System 7 uses Application Menu in menubar
        self._wf_overlay = _WireframeOverlay(self)

        # Control Strip — bottom-left floating panel (System 7.5)
        self._control_strip = ControlStrip(self)
        WM.changed.connect(lambda: self._control_strip.update())

        self._desk_rect = QRect(0, 22, self.width(), self.height()-22)

        # RIGHT-side desktop icons — System 7 style, column from top-right
        # In real System 7: HD top-right, then other volumes, Trash bottom-right
        # Icons snap to right edge with 8px margin, spaced 80px apart vertically
        icons_def = [
            ("Macintosh HD", "macintosh_hd", "finder"),
            ("The Outside World", "browser",  "browser"),
            ("Stickies",     "stickies",    "stickies"),
        ]
        self._icons = []
        ICON_W, ICON_H, MARGIN = 80, 80, 8
        for i, (name, icon, target) in enumerate(icons_def):
            rx = -(ICON_W + MARGIN)          # offset from right edge
            ry_from_top = 30 + i * (ICON_H + 4)  # from top (below menubar)
            x = 0   # placeholder, set in resizeEvent
            y = 0
            ic = DesktopIcon75(self, name, icon, x, y, target)
            ic._rx = rx
            ic._ry = ry_from_top
            ic._ry_from_bottom = False
            ic.dbl_clicked.connect(lambda t, ic_w, d=self: d.open_window(t, ic_w))
            ic.hide()
            ic.setWindowOpacity(0.0)
            self._icons.append(ic)

        # Trash — always bottom-right
        trash_ic = DesktopIcon75(self, "Trash", "trash", 0, 0, "trash")
        trash_ic._rx = -(ICON_W + MARGIN)
        trash_ic._ry = -(ICON_H + 30)      # offset from bottom
        trash_ic._ry_from_bottom = True
        trash_ic.dbl_clicked.connect(lambda t, ic_w, d=self: d.open_window(t, ic_w))
        trash_ic.hide()
        trash_ic.setWindowOpacity(0.0)
        self._icons.append(trash_ic)

        # "Apps" folder — above Trash, contains Clock, Calculator, all other apps
        apps_ic = DesktopIcon75(self, "Apps", "folder", 0, 0, "other_folder")
        apps_ic._rx = -(ICON_W + MARGIN)
        apps_ic._ry = -(ICON_H * 2 + 50)   # above Trash
        apps_ic._ry_from_bottom = True
        apps_ic.dbl_clicked.connect(lambda t, ic_w, d=self: d._open_other_folder(ic_w))
        apps_ic.hide()
        apps_ic.setWindowOpacity(0.0)
        self._icons.append(apps_ic)

        # Rubber-band selection — custom dashed 1px, not system rubber band
        self._sel_start = None
        self._sel_rect  = QRect()
        self._rubber_active = False

        # Shortcuts
        for key, target in [("Ctrl+T", "terminal"), ("Ctrl+B", "browser"),
                             ("Ctrl+N", "notepad"), ("Ctrl+F", "finder"),
                             ("Ctrl+,", "settings"), ("Ctrl+W", None)]:
            if target:
                QShortcut(QKeySequence(key), self, lambda t=target: self.open_window(t))
            else:
                QShortcut(QKeySequence(key), self, self._close_active)
        QShortcut(QKeySequence("Alt+F4"), self, self.shut_down)
        QShortcut(QKeySequence("Ctrl+M"), self, self.minimize_all)

        self.showFullScreen()

        # Boot screen — defer so fullscreen geometry is applied first
        QTimer.singleShot(50, self._start_boot)

    def _start_boot(self):
        self._desk_rect = QRect(0, 22, self.width(), self.height()-22)
        self._reposition_icons()
        self._boot = BootScreen75(self)
        self._boot.done.connect(self._boot_done)

    def _boot_done(self):
        """After boot: fade in menubar, then icons one by one, then open Finder."""
        self._menu.show()

        # Fade in menubar (use QGraphicsOpacityEffect — windowOpacity only works on top-level windows)
        _effect = QGraphicsOpacityEffect(self._menu)
        self._menu.setGraphicsEffect(_effect)
        anim_menu = QPropertyAnimation(_effect, b"opacity", self)
        anim_menu.setDuration(300)
        anim_menu.setStartValue(0.0)
        anim_menu.setEndValue(1.0)
        anim_menu.finished.connect(lambda: self._menu.setGraphicsEffect(None))
        anim_menu.start(QAbstractAnimation.DeleteWhenStopped)

        # Icons appear one by one with 80ms stagger (right column, top to bottom)
        icons = list(self._icons)
        def _show_icon(idx):
            if idx >= len(icons):
                # All done — show control strip, open Finder window
                self._control_strip._reposition()
                self._control_strip.show()
                self._control_strip.raise_()
                QTimer.singleShot(200, lambda: self.open_window("finder"))
                return
            ic = icons[idx]
            ic.show()
            anim = QPropertyAnimation(ic, b"windowOpacity", self)
            anim.setDuration(180)
            anim.setStartValue(0.0); anim.setEndValue(1.0)
            anim.start(QAbstractAnimation.DeleteWhenStopped)
            QTimer.singleShot(80, lambda: _show_icon(idx + 1))
        QTimer.singleShot(100, lambda: _show_icon(0))

    def _reposition_icons(self):
        for ic in self._icons:
            x = self.width() + ic._rx
            if ic._ry_from_bottom:
                y = self.height() + ic._ry
            else:
                y = 22 + ic._ry
            ic.move(x, y)

    def resizeEvent(self, e):
        self._menu.setGeometry(0, 0, self.width(), 22)
        self._desk_rect = QRect(0, 22, self.width(), self.height()-22)
        self._reposition_icons()
        if hasattr(self, '_control_strip'):
            self._control_strip._reposition()
            self._control_strip.raise_()
        super().resizeEvent(e)

    def _open_other_folder(self, icon_widget=None):
        """Open the /Other folder in Finder with zoom animation."""
        w = FinderWindow(self, "/Other")
        w._icon_target = "other_folder"
        import random
        margin = 40
        desk_w = self._desk_rect.width()
        desk_h = self._desk_rect.height()
        win_w, win_h = w.width(), w.height()
        max_x = max(margin, desk_w - win_w - margin)
        max_y = max(margin, desk_h - win_h - margin)
        rx = random.randint(margin, max_x) if max_x > margin else margin
        ry = self._desk_rect.y() + random.randint(30, max(31, max_y)) if max_y > 30 else self._desk_rect.y() + 30
        w.move(rx, ry)
        WM.raise_window(w)
        from_rect = self._desk_rect.center()
        from_rect = QRect(self._desk_rect.center().x() - 20, self._desk_rect.center().y() - 20, 40, 40)
        if icon_widget is not None:
            from_rect = icon_widget.geometry()
        w.setVisible(False)
        self._zoom_rects_open(from_rect, w.geometry())
        QTimer.singleShot(_ZoomRectsOverlay.DURATION_MS, lambda ww=w, fr=from_rect: (
            ww.setVisible(True), ww.animate_open_from(fr)
        ))
        self._menu.raise_()
        self._wf_overlay.raise_()

    def open_window(self, name: str, icon_widget=None):
        name = name.lower().replace(" ", "_")
        w = None
        if name == "finder":
            w = FinderWindow(self)
        elif name == "calculator":
            w = CalculatorWindow(self)
        elif name == "terminal":
            w = TerminalWindow(self)
        elif name == "browser":
            w = BrowserWindow(self)
        elif name == "notepad":
            w = NotePadWindow(self)
        elif name == "settings":
            w = ControlPanelWindow(self)
        elif name == "about":
            w = AboutWindow(self)
        elif name == "stickies":
            w = StickiesWindow(self)
        elif name == "macpaint":
            w = MacPaintWindow(self)
        elif name == "puzzle":
            w = PuzzleWindow(self)
        elif name == "scrapbook":
            w = ScrapbookWindow(self)
        elif name == "clock":
            w = ClockWindow(self)
        elif name == "trash":
            w = TrashWindow(self)
            w._icon_target = "trash"
        else:
            return
        if w:
            w._icon_target = name  # used by close/minimize to find the icon
            import random
            margin = 40
            desk_w = self._desk_rect.width()
            desk_h = self._desk_rect.height()
            win_w, win_h = w.width(), w.height()
            max_x = max(margin, desk_w - win_w - margin)
            max_y = max(margin, desk_h - win_h - margin)
            rx = random.randint(margin, max_x) if max_x > margin else margin
            ry = self._desk_rect.y() + random.randint(30, max(31, max_y)) if max_y > 30 else self._desk_rect.y() + 30
            w.move(rx, ry)
            WM.raise_window(w)
            from_rect = QRect(self._desk_rect.center().x() - 20,
                              self._desk_rect.center().y() - 20, 40, 40)
            if icon_widget is not None:
                ic_topleft = icon_widget.mapTo(self, QPoint(0, 0))
                from_rect = QRect(ic_topleft, icon_widget.size())
            else:
                for ic in self.findChildren(DesktopIcon75):
                    if ic.target == name:
                        from_rect = ic.geometry()
                        break
            w._icon_src_rect = from_rect
            w.setVisible(False)
            self._zoom_rects_open(from_rect, w.geometry())
            QTimer.singleShot(_ZoomRectsOverlay.DURATION_MS, lambda ww=w, fr=from_rect: (
                ww.setVisible(True), ww.animate_open_from(fr)
            ))
            self._menu.raise_()
            self._wf_overlay.raise_()

    def _close_active(self):
        a = WM.get_active()
        if a:
            a.close_window()

    def tile_windows(self):
        WM.tile(self._desk_rect)

    def minimize_all(self):
        for w in WM.windows:
            w.minimize()

    def empty_trash(self):
        VFS_INST.tree["/"]["Trash"] = {}
        self._update_trash_icon()
        Mac75Dialog.info(self, "Trash", "The Trash has been emptied.")

    def _update_trash_icon(self):
        trash_node = VFS_INST.tree["/"].get("Trash", {})
        has_items = any(not k.startswith("__") for k in trash_node)
        for ic in self._icons:
            if ic.target == "trash":
                ic.icon = "trash_full" if has_items else "trash"
                ic.update()
                break

    def restart(self):
        if Mac75Dialog.question(self, "Restart", "Are you sure you want to restart?"):
            for w in list(WM.windows):
                WM.unregister(w)
                w.deleteLater()
            self._boot = BootScreen75(self)
            self._boot.done.connect(self._boot_done)

    def shut_down(self):
        if Mac75Dialog.question(self, "Shut Down", "Are you sure you want to quit?"):
            QApplication.quit()

    def _set_wireframe(self, rect: QRect):
        self._wf_overlay.set_rect(rect)
        self._wf_overlay.raise_()

    def _clear_wireframe(self):
        self._wf_overlay.clear()

    def _zoom_rects_open(self, from_rect: QRect, to_rect: QRect):
        """ZoomRects animation: expanding frames from icon to window position."""
        self._zr_anim = _ZoomRectsOverlay(self, from_rect, to_rect, opening=True)
        self._zr_anim.show()
        self._zr_anim.raise_()

    def _zoom_rects_close(self, from_rect: QRect, to_rect: QRect):
        """ZoomRects animation: contracting frames from window to close box."""
        overlay = _ZoomRectsOverlay(self, from_rect, to_rect, opening=False)
        overlay.show()
        # Raise after Qt processes the window hide/redraw so overlay stays on top
        QTimer.singleShot(0, overlay.raise_)
        self._zr_anim = overlay

    # Desktop painting — dot grid like System 7
    def paintEvent(self, e):
        p = QPainter(self)
        p.setPen(QPen(QColor(0, 0, 0, 50), 1))
        for x in range(0, self.width(), 8):
            for y in range(22, self.height(), 8):
                p.drawPoint(x, y)
        # Custom rubber-band: 1px dashed alternating black/white (System 7 marching ants)
        if self._rubber_active and not self._sel_rect.isNull():
            pen = QPen(C_BLACK, 1, Qt.DotLine)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRect(self._sel_rect.adjusted(0, 0, -1, -1))

    # Rubber-band selection
    def mousePressEvent(self, e):
        if e.y() < 22 or e.y() > self.height():
            return
        for ic in self.findChildren(DesktopIcon75):
            ic._sel = False
            ic.update()
        self._sel_start = e.pos()
        self._sel_rect  = QRect(self._sel_start, QSize())
        self._rubber_active = True
        self.update()

    def mouseMoveEvent(self, e):
        if self._rubber_active and self._sel_start:
            self._sel_rect = QRect(self._sel_start, e.pos()).normalized()
            # Live selection: icons invert as soon as rubber band touches them
            for ic in self.findChildren(DesktopIcon75):
                hit = self._sel_rect.intersects(ic.geometry())
                if ic._sel != hit:
                    ic._sel = hit
                    ic.update()
            self.update()

    def mouseReleaseEvent(self, e):
        if self._rubber_active:
            r = QRect(self._sel_start, e.pos()).normalized()
            for ic in self.findChildren(DesktopIcon75):
                ic._sel = r.intersects(ic.geometry())
                ic.update()
            self._rubber_active = False
            self._sel_rect = QRect()
            self._sel_start = None
            self.update()


# ─────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ClassicOS 7.5")
    app.setStyle("Fusion")
    pal = app.palette()
    pal.setColor(QPalette.Window,     QColor("#CCCCCC"))
    pal.setColor(QPalette.WindowText, QColor("#000000"))
    pal.setColor(QPalette.Button,     QColor("#CCCCCC"))
    pal.setColor(QPalette.ButtonText, QColor("#000000"))
    pal.setColor(QPalette.Highlight,  QColor("#000077"))
    pal.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(pal)

    desk = Desktop75()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
