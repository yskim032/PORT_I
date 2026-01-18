import sys
import copy
import json
from collections import defaultdict
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
                             QHeaderView, QLabel, QSplitter, QGraphicsView, QGraphicsScene,
                             QGraphicsRectItem, QGraphicsTextItem, QGraphicsItem, QGraphicsLineItem,
                             QDialog, QTabWidget, QCheckBox, QGroupBox, QScrollArea, QFrame,
                             QFileDialog, QHeaderView, QTextEdit, QColorDialog)
from PyQt5.QtGui import QColor, QFont, QBrush, QPen, QPainter, QWheelEvent, QPolygonF, QPainterPath
from PyQt5.QtCore import Qt, QRectF, pyqtSignal, QObject, QTimer, QLineF, QPointF
import math
import random


# pyinstaller -w -F port_i.py


# --- Utilities ---
def parse_date(date_str):
    try:
        return datetime.strptime(date_str.strip(), "%Y/%m/%d %H:%M")
    except:
        return datetime.now()

def format_date(dt):
    return dt.strftime("%Y/%m/%d %H:%M")

def format_short_dt(dt):
    return dt.strftime("%m/%d %H:%M")

def format_time_delta(td):
    # td is a timedelta object
    total_seconds = int(td.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    total_seconds = abs(total_seconds)
    
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    
    parts = []
    if days > 0:
        parts.append(f"{days}D")
    if hours > 0 or not parts:
        parts.append(f"{hours}H")
        
    return f"{sign}{' '.join(parts)}"

def get_display_voyage(voyage_str):
    if not voyage_str: return ""
    if "/" in voyage_str:
        return voyage_str.split("/")[-1].strip()
    return voyage_str.strip()

import os

CONFIG_FILE = "port_i_config.json"

def save_last_mapping_path(path):
    try:
        data = {}
        if os.path.exists(CONFIG_FILE):
             with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                 data = json.load(f)
                 
        data['last_mapping_path'] = path
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Error saving config: {e}")

def get_last_mapping_path():
    if not os.path.exists(CONFIG_FILE): return None
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('last_mapping_path')
    except:
        return None

def save_last_memo_path(path):
    try:
        data = {}
        if os.path.exists(CONFIG_FILE):
             with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                 data = json.load(f)
                 
        data['last_memo_path'] = path
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"Error saving config: {e}")

def get_last_memo_path():
    if not os.path.exists(CONFIG_FILE): return None
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('last_memo_path')
    except:
        return None

class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.zoom_factor = 1.15

    def wheelEvent(self, event):
        # Zoom Logic (Simple relative scaling)
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor
        
        if event.angleDelta().y() > 0:
            self.scale(zoom_in_factor, zoom_in_factor)
        else:
            self.scale(zoom_out_factor, zoom_out_factor)

    def drawForeground(self, painter, rect):
        super().drawForeground(painter, rect)
        
        # Get Reference to Data
        if not hasattr(self.scene(), 'parent_view'): return
        parent = self.scene().parent_view
        terminal_list = parent.terminal_list
        row_height = parent.row_height
        
        # Setup Painter
        painter.setPen(QColor("#c0caf5"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        
        # Draw Labels
        # rect is the visible scene rect (or dirty rect).
        # We MUST use the Viewport's top-left mapped to scene to be truly "fixed".
        # rect.left() gives the dirty rect's left, which causes ghosting on small updates.
        
        visible_left = self.mapToScene(0, 0).x()
        
        # Color Palette for terminals
        # Using a fixed map or cycle based on terminal name prefix
        t_base_colors = ["#2e7d32", "#e65100", "#1565c0", "#6a1b9a", "#00695c", "#c2185b", "#f9a825"]
        terminal_color_map = {}
        
        for i, term in enumerate(terminal_list):
            y = i * row_height
            
            # Determine Color based on terminal name (prefix before '-')
            t_name = term.split('-')[0]
            if t_name not in terminal_color_map:
                terminal_color_map[t_name] = QColor(t_base_colors[len(terminal_color_map) % len(t_base_colors)])
            
            bg_color = QColor(terminal_color_map[t_name])
            bg_color.setAlpha(180) # Semi-transparent
            
            # Background
            bg_rect = QRectF(visible_left, y, 150, row_height)
            painter.fillRect(bg_rect, bg_color)
            
            # Text
            # Improve text contrast - White text usually works well on these dark/translucent colors
            painter.setPen(QColor(Qt.white))
            
            # Handle display name (e.g., PNC-1 -> PNC (1))
            display_name = term.replace('-', ' (') + ')' if '-' in term else term
            
            painter.drawText(QRectF(visible_left + 10, y, 130, row_height), Qt.AlignVCenter | Qt.AlignLeft, display_name)
            
            # Bottom Line
            painter.setPen(QColor("#414868"))
            painter.drawLine(QLineF(visible_left, y + row_height, visible_left + 150, y + row_height))
            painter.setPen(QColor("#c0caf5")) # Reset text color

class TickerLabel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.segments = [] # List of (text, color)
        self.offset = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_offset)
        self.timer.start(30) # ~33 FPS
        self.setFixedHeight(30)
        self.total_text_width = 0
        
    def set_text_segments(self, segments):
        if segments != self.segments:
            self.segments = segments
            # Calculate total width
            fm = self.fontMetrics()
            spacer_width = fm.horizontalAdvance("    ★    ")
            self.total_text_width = 0
            for i, (text, color) in enumerate(self.segments):
                self.total_text_width += fm.horizontalAdvance(text)
                if i < len(self.segments) - 1:
                    self.total_text_width += spacer_width
            
            # Reset offset if needed
            if self.offset > self.total_text_width:
                self.offset = 0
            self.update()
            
    def set_text(self, text):
        # Legacy support
        self.set_text_segments([(text, QColor("#50fa7b"))])
            
    def update_offset(self):
        if not self.segments or self.total_text_width == 0: return
        self.offset += 1
        
        # Loop logic: Reset when the first set has scrolled past
        # We draw the sequence twice to make it seamless.
        # But we only need to reset when we've moved by total_text_width + spacer
        fm = self.fontMetrics()
        spacer_width = fm.horizontalAdvance("    ★    ")
        cycle_width = self.total_text_width + spacer_width
        
        if self.offset >= cycle_width:
            self.offset = 0
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0)) # Black background
        
        if not self.segments: return
        
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        fm = painter.fontMetrics()
        spacer = "    ★    "
        spacer_width = fm.horizontalAdvance(spacer)
        y = (self.height() + fm.ascent() - fm.descent()) / 2
        
        # Loop logic: Draw the content twice to ensure no gaps
        # Position: Starts from width and moves left
        start_x = self.width() - self.offset
        
        def draw_sequence(current_x):
            for i, (text, color) in enumerate(self.segments):
                painter.setPen(color)
                painter.drawText(int(current_x), int(y), text)
                current_x += fm.horizontalAdvance(text)
                
                # Draw spacer
                if i < len(self.segments) - 1 or True: # Always draw spacer for looping
                    painter.setPen(QColor("#a9b1d6")) # Greyish spacer
                    painter.drawText(int(current_x), int(y), spacer)
                    current_x += spacer_width
            return current_x

        # Draw first sequence
        next_x = draw_sequence(start_x)
        
        # Draw second sequence immediately after the first to fill the gap during loop
        if next_x < self.width() + self.total_text_width:
            draw_sequence(next_x)

# --- Graphic Items ---
class ArrowItem(QGraphicsLineItem):
    def __init__(self, start_pos, end_pos, color, parent=None):
        super().__init__(QLineF(start_pos, end_pos), parent)
        self.color = color
        self.setPen(QPen(color, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.setZValue(100)
        self.setData(0, "ARROW")
        self.arrow_head = QPolygonF()
        self.update_head()

    def update_head(self):
        line = self.line()
        
        arrow_size = 7.5 # Reduced by 50% from 15
        arrow_angle = math.pi / 6 # 30 degrees
        
        # Calculate angle of the line
        angle = math.atan2(line.y1() - line.y2(), line.x1() - line.x2())

        p1 = line.p2() + QPointF(math.cos(angle + arrow_angle) * arrow_size,
                                 math.sin(angle + arrow_angle) * arrow_size)
        p2 = line.p2() + QPointF(math.cos(angle - arrow_angle) * arrow_size,
                                 math.sin(angle - arrow_angle) * arrow_size)
                                 
        self.arrow_head = QPolygonF([line.p2(), p1, p2])

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        painter.setBrush(QBrush(self.color))
        painter.drawPolygon(self.arrow_head)

class ConnectionLineItem(QGraphicsLineItem):
    """Pink line connecting original vessel's ETD to copy vessel's ETA with time gap label"""
    def __init__(self, original_vessel, copy_vessel, parent=None):
        super().__init__(parent)
        self.original_vessel = original_vessel
        self.copy_vessel = copy_vessel
        self.setPen(QPen(QColor("#ff69b4"), 3, Qt.SolidLine))  # Pink line
        self.setZValue(50)  # Above vessels but below arrows
        
        # Text label for time gap
        self.label = QGraphicsTextItem("", self)
        self.label.setDefaultTextColor(QColor("#ff0000")) # Red text for time gap
        self.label.setFont(QFont("Segoe UI", 18, QFont.Bold))  # 2x larger font
        
        self.update_line()
    
    def update_line(self):
        """Update line position and time gap label"""
        # Get ETD point of original (right edge, center)
        orig_rect = self.original_vessel.rect()
        orig_pos = self.original_vessel.pos()
        etd_point = QPointF(
            orig_pos.x() + orig_rect.width(),
            orig_pos.y() + orig_rect.height() / 2
        )
        
        # Get ETA point of copy (left edge, center)
        copy_rect = self.copy_vessel.rect()
        copy_pos = self.copy_vessel.pos()
        eta_point = QPointF(
            copy_pos.x(),
            copy_pos.y() + copy_rect.height() / 2
        )
        
        # Update line
        self.setLine(QLineF(etd_point, eta_point))
        
        # Calculate time gap
        time_gap = self.copy_vessel.data['eta'] - self.original_vessel.data['etd']
        gap_str = format_time_delta(time_gap)
        
        # Update label position (midpoint of line)
        mid_x = (etd_point.x() + eta_point.x()) / 2
        mid_y = (etd_point.y() + eta_point.y()) / 2
        
        self.label.setPlainText(gap_str)
        label_rect = self.label.boundingRect()
        # Position label to the LEFT of the line to avoid overlap
        self.label.setPos(mid_x - label_rect.width() - 10, mid_y - label_rect.height() / 2)

class VesselItem(QGraphicsRectItem):
    def __init__(self, data, x_pos, y_pos, width, height, color):
        super().__init__(0, 0, width, height)
        self.data = data 
        self.setPos(x_pos, y_pos)
        self.setBrush(QBrush(color))
        self.setPos(x_pos, y_pos)
        self.setBrush(QBrush(color))
        self.default_pen = QPen(Qt.white, 1)
        self.setPen(self.default_pen)
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.resize_margin = 10
        self.resizing = None
        
        # Copy Mode indicators
        self.copy_label = None  # None, "1st", or "2nd"
        self.copy_border_color = None  # None, QColor for border
        self.linked_vessel = None  # Reference to paired vessel (for copy feature)
        self.connection_line = None  # Reference to ConnectionLineItem
        self.is_dragging_for_connection = False  # Flag to prevent itemChange updates during drag
        
        # Highlight Mode
        self.is_highlighted = False
        self.neon_timer = QTimer()
        self.neon_timer.timeout.connect(self.update_neon)
        self.neon_hue = 0
        
        # Connect Mode
        self.temp_line = None
        
        # MEMO & Heart Icon
        self.has_memo = False
        self.heart_rotation = 0
        
        # SEARCH Flag
        self.is_searched = False
        self.is_search_focused = False # New state for RED/2x checkmark
        
        # IN PORT Highlight
        self.is_in_port = False
        
        # Main Text Label: 
        # Line 1: Vessel Name, Voyage
        # Line 2: (Shipping Line)
        voyage = get_display_voyage(data['선사항차'])
        label_text = f"{data['모선명']} - {voyage}\n{data.get('선사', '')}, {data.get('항로', '')}"
        self.text = QGraphicsTextItem(label_text, self)
        self.text.setDefaultTextColor(Qt.black)
        self.text.setFont(QFont("Segoe UI", 7, QFont.Bold))
        t_rect = self.text.boundingRect()
        self.text.setPos((width - t_rect.width()) / 2, (height - t_rect.height()) / 2)

        # Arrival Hour (Left Bottom)
        self.eta_text = QGraphicsTextItem(str(data['eta'].hour), self)
        self.eta_text.setDefaultTextColor(QColor("#a11"))
        self.eta_text.setFont(QFont("Segoe UI", 7, QFont.Bold))
        self.eta_text.setPos(2, height - 15)

        # Departure Hour (Right Bottom)
        self.etd_text = QGraphicsTextItem(str(data['etd'].hour), self)
        self.etd_text.setDefaultTextColor(QColor("#11a"))
        self.etd_text.setFont(QFont("Segoe UI", 7, QFont.Bold))
        etd_w = self.etd_text.boundingRect().width()
        self.etd_text.setPos(width - etd_w - 2, height - 15)
    
    def paint(self, painter, option, widget=None):
        # Draw custom border if copy mode
        if self.copy_border_color:
            painter.setPen(QPen(self.copy_border_color, 3))
            painter.setBrush(self.brush())
            painter.drawRect(self.rect())
        elif self.is_in_port:
            # Current time line is inside this vessel - Draw Thin Red Outline
            painter.setPen(QPen(Qt.red, 3))
            painter.setBrush(self.brush())
            painter.drawRect(self.rect())
        else:
            super().paint(painter, option, widget)
        
        # Draw copy label if set (yellow text on purple background)
        if self.copy_label:
            # Draw purple background rectangle
            bg_rect = QRectF(3, 3, 35, 18)
            painter.fillRect(bg_rect, QColor("#9b59b6"))  # Purple background
            
            # Draw yellow text
            painter.setPen(QColor("#ffff00"))  # Yellow text
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.drawText(bg_rect, Qt.AlignCenter, self.copy_label)

        # Draw Rainbow Circle Icon if has memo
        if self.has_memo:
            painter.save()
            # Position: Top Left (offset slightly)
            cx = 15
            cy = 15
            painter.translate(cx, cy)
            
            # Rotation removed for Circle (unless we want it, but user asked for color change)
            # painter.rotate(self.heart_rotation) 
            
            # Size: Half of Star. Star was 5.0x. So 2.5x.
            painter.scale(2.5, 2.5) 
            painter.translate(-cx, -cy)
            
            # Rainbow Circle Shape
            painter.setPen(Qt.NoPen)
            
            # Get Hue from Parent View
            hue = 0
            if hasattr(self.scene(), 'parent_view'):
                hue = self.scene().parent_view.rainbow_hue
                
            color = QColor.fromHsv(int(hue), 255, 255)
            painter.setBrush(color) # Rainbow Color
            
            # Simple Circle
            # Radius ~5 (base size before scale)
            painter.drawEllipse(QPointF(cx, cy), 5, 5)
            
            painter.drawEllipse(QPointF(cx, cy), 5, 5)
            
            painter.restore()

        # Draw SEARCH Checkmark
        if self.is_searched:
            painter.save()
            
            # Request: Checkmark on TOP-RIGHT, slightly outside box allowed.
            # Normal: Green, 1.5x
            # Focused: Red, 2x
            
            # Base position: Top-Right corner
            # Translate to (Width, 0)
            painter.translate(self.rect().width(), 0)
            
            check_path = QPainterPath()
            color = QColor("#00ff00")
            scale = 1.5
            pen_width = 5
            
            if self.is_search_focused:
                color = QColor("#ff0000") # Red
                scale = 2.0
                pen_width = 6
                
            # Base Checkmark Path (Standard Size ~10x10 box)
            # (2,8) -> (6,12) -> (14,2)
            # We want it "slightly outside" or just top right.
            # Let's center it around (0,0) relative to Top-Right?
            # Or just shifted slightly left so it hangs off the corner?
            # Let's start path at (-5, 5) roughly.
            
            # Define path at origin (0,0) being the corner
            # A checkmark shape
            check_path.moveTo(-8 * scale, 4 * scale)      # Left point
            check_path.lineTo(-4 * scale, 8 * scale)      # Bottom point
            check_path.lineTo(8 * scale, -8 * scale)      # Top Right point (outside)
            
            pen = QPen(color, pen_width) 
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(check_path)
            
            painter.restore()

    def update_time_labels(self):
        self.eta_text.setPlainText(str(self.data['eta'].hour))
        self.etd_text.setPlainText(str(self.data['etd'].hour))
        etd_w = self.etd_text.boundingRect().width()
        self.etd_text.setPos(self.rect().width() - etd_w - 2, self.rect().height() - 15)
        
        # Center the main text again
        t_rect = self.text.boundingRect()
        self.text.setPos((self.rect().width() - t_rect.width()) / 2, (self.rect().height() - t_rect.height()) / 2)

    def update_neon(self):
        self.neon_hue = (self.neon_hue + 10) % 360
        color = QColor.fromHsv(self.neon_hue, 255, 255)
        pen = QPen(color, 4)
        self.setPen(pen)

    def toggle_highlight_effect(self):
        if self.is_highlighted:
            self.neon_timer.stop()
            self.setPen(self.default_pen)
            self.is_highlighted = False
        else:
            self.neon_timer.start(50) # 50ms update
            self.is_highlighted = True

    def hoverMoveEvent(self, event):
        scene = self.scene()
        if hasattr(scene, 'parent_view') and scene.parent_view.current_view_mode != "NORMAL":
             self.setCursor(Qt.ArrowCursor) # No resize cursor in special modes
             return

        pos = event.pos()
        width = self.rect().width()
        if pos.x() < self.resize_margin or pos.x() > width - self.resize_margin:
            self.setCursor(Qt.SizeHorCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event):
        scene = self.scene()
        
        # Check for Memo Mode via MainWindow
        views = scene.views()
        if views:
            # Assuming the view's window is BerthMonitor
            mw = views[0].window()
            if hasattr(mw, 'is_memo_mode') and mw.is_memo_mode:
                 if event.button() == Qt.LeftButton:
                     mw.open_memo_for_vessel(self.data)
                     event.accept()
                     return
        
        mode = "NORMAL"
        if hasattr(scene, 'parent_view'):
            mode = scene.parent_view.current_view_mode
            
        if mode == "HIGHLIGHT":
            self.toggle_highlight_effect()
            return # Block move
        
        if mode == "COPY":
            # Create a duplicate vessel
            import copy
            new_data = copy.deepcopy(self.data)
            
            # Find the rightmost vessel in the same berth
            same_berth_vessels = []
            if hasattr(self.scene(), 'parent_view'):
                same_berth_vessels = [
                    v for v in self.scene().parent_view.vessel_items 
                    if v.data['full_berth'] == self.data['full_berth']
                ]
            
            # Calculate position: rightmost end of same berth
            if same_berth_vessels:
                rightmost_x = max(v.pos().x() + v.rect().width() for v in same_berth_vessels)
                new_x = rightmost_x + 10  # Small gap after rightmost vessel
            else:
                new_x = self.pos().x()
            
            # Y position: same as original (same berth)
            new_y = self.pos().y()
            
            # Create new vessel item at calculated position
            new_vessel = VesselItem(
                new_data,
                new_x,
                new_y,
                self.rect().width(),
                self.rect().height(),
                QColor(self.brush().color())
            )
            
            # CRITICAL FIX: Update new_data to match the visual position (new_x)
            # Calculate time offset from start
            parent_view = self.scene().parent_view
            if parent_view:
                hours_from_start = new_x / parent_view.pixels_per_hour
                new_start_time = parent_view.start_time + timedelta(hours=hours_from_start)
                duration = new_data['etd'] - new_data['eta']
                
                new_data['eta'] = new_start_time
                new_data['etd'] = new_start_time + duration
                new_data['접안예정일시'] = format_date(new_data['eta'])
                new_data['출항예정일시'] = format_date(new_data['etd'])
                
                # Also update texts on the item itself so it shows correct times initially
                new_vessel.update_time_labels()
            
            # Set z-value slightly higher so copy is visible on top
            new_vessel.setZValue(self.zValue() + 1)
            
            # Mark original as 1st (red border)
            self.copy_label = "1st"
            self.copy_border_color = QColor("#ff0000")
            self.update()
            
            # Mark copy as 2nd (blue border)
            new_vessel.copy_label = "2nd"
            new_vessel.copy_border_color = QColor("#0088ff")
            new_vessel.is_just_copied = True
            
            # Establish bidirectional link
            self.linked_vessel = new_vessel
            new_vessel.linked_vessel = self
            
            # Create connection line
            connection = ConnectionLineItem(self, new_vessel)
            self.connection_line = connection
            new_vessel.connection_line = connection
            
            # Add to scene and data list
            self.scene().addItem(new_vessel)
            self.scene().addItem(connection)
            if hasattr(self.scene(), 'parent_view'):
                self.scene().parent_view.vessel_items.append(new_vessel)
                self.scene().parent_view.vessel_data_list.append(new_data)
            
            return # Block move
            
        if mode == "CONNECT":
            self.start_pos = self.mapToScene(self.rect().center())
            self.temp_line = QGraphicsLineItem(QLineF(self.start_pos, self.mapToScene(event.pos())))
            self.temp_line.setPen(QPen(Qt.white, 2, Qt.DashLine))
            self.scene().addItem(self.temp_line)
            return # Block move

        # NORMAL MODE logic
        pos = event.pos()
        width = self.rect().width()
        if pos.x() < self.resize_margin:
            self.resizing = 'left'
            self.initial_resize_pos = event.scenePos().x()
            self.initial_rect_width = width
            self.initial_x = self.pos().x()
        elif pos.x() > width - self.resize_margin:
            self.resizing = 'right'
            self.initial_resize_pos = event.scenePos().x()
            self.initial_rect_width = width
        else:
            self.resizing = None
            self.has_moved_during_drag = False # Reset drag tracker
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        scene = self.scene()
        mode = "NORMAL"
        if hasattr(scene, 'parent_view'):
            mode = scene.parent_view.current_view_mode
            
        if mode == "HIGHLIGHT":
            return
            
        if mode == "CONNECT":
            if self.temp_line:
                self.temp_line.setLine(QLineF(self.start_pos, self.mapToScene(event.pos())))
            return

        if self.resizing:
            current_x = event.scenePos().x()
            diff = current_x - self.initial_resize_pos
            
            if self.resizing == 'right':
                new_width = max(self.resize_margin * 2, self.initial_rect_width + diff)
                self.setRect(0, 0, new_width, self.rect().height())
                
            elif self.resizing == 'left':
                new_width = max(self.resize_margin * 2, self.initial_rect_width - diff)
                if new_width != self.initial_rect_width:
                     new_x = self.initial_x + diff
                     self.setPos(new_x, self.pos().y())
                     self.setRect(0, 0, new_width, self.rect().height())
            
            self.update_time_labels()
        else:
            self.has_moved_during_drag = True # Mark as dragged
            
            # UPDATE: Temporarily update ETA during drag for real-time connection line
            if hasattr(scene, 'parent_view'):
                parent_view = scene.parent_view
                # Use scene position for more accurate calculation
                current_scene_x = event.scenePos().x()
                hours_from_start = current_scene_x / parent_view.pixels_per_hour
                temp_eta = parent_view.start_time + timedelta(hours=hours_from_start)
                
                # Set flag to prevent itemChange from updating
                self.is_dragging_for_connection = True
                
                # Temporarily update data for connection line calculation
                # Don't restore it - let it stay until after itemChange
                self.data['eta'] = temp_eta
                
                # Update connection line if it exists
                if self.connection_line:
                    self.connection_line.update_line()
                    # Explicitly trigger repaint
                    self.connection_line.update()
                    self.connection_line.label.update()
            
            super().mouseMoveEvent(event)
            
            # Reset flag AFTER super() completes
            if hasattr(scene, 'parent_view') and self.connection_line:
                self.is_dragging_for_connection = False

    def mouseReleaseEvent(self, event):
        scene = self.scene()
        mode = "NORMAL"
        if hasattr(scene, 'parent_view'):
            mode = scene.parent_view.current_view_mode
            
        if mode == "HIGHLIGHT":
            return
            
        if mode == "CONNECT":
            if self.temp_line:
                self.scene().removeItem(self.temp_line)
                self.temp_line = None
                
                # Check drop target
                end_pos = self.mapToScene(event.pos())
                items = self.scene().items(end_pos)
                target = None
                for item in items:
                    if isinstance(item, VesselItem) and item != self:
                        target = item
                        break
                
                if target:
                    # Logic for Color
                    # A = self (Source), B = target (Dest)
                    a_eta = self.data['eta']
                    a_etd = self.data['etd']
                    b_eta = target.data['eta']
                    b_etd = target.data['etd']
                    
                    arrow_color = QColor("#ff0000") # Default Red
                    
                    # 1. A's ETA or ETD is within B's window -> Green
                    if (b_eta <= a_eta <= b_etd) or (b_eta <= a_etd <= b_etd):
                        arrow_color = QColor("#00ff00") # Green
                    # 2. A left before B arrived -> Blue
                    elif a_etd < b_eta:
                        arrow_color = QColor("#0088ff") # Blue
                    # 3. A arrived after B left -> Red
                    elif a_eta > b_etd:
                        arrow_color = QColor("#ff0000") # Red
                    
                    # Draw permanent arrow
                    p1 = self.mapToScene(self.rect().center())
                    p2 = target.mapToScene(target.rect().center())
                    arrow = ArrowItem(p1, p2, arrow_color)
                    self.scene().addItem(arrow)
                    
                    # Add to TS Table
                    # Drop Target = LOAD VESSEL, Self = DISCH VESSEL
                    if hasattr(self.scene(), 'parent_view'):
                        self.scene().parent_view.add_ts_connection(target, self, arrow_color)
            return

        if self.resizing:
            self.resizing = None
            if hasattr(self.scene(), 'parent_view'):
                self.scene().parent_view.handle_vessel_move(self)
        else:
            super().mouseReleaseEvent(event)
            if hasattr(self.scene(), 'parent_view'):
                self.scene().parent_view.handle_vessel_move(self)
    
    def itemChange(self, change, value):
        """Override to update connection line when vessel moves"""
        if change == QGraphicsItem.ItemPositionHasChanged:
            # Update connection line if it exists (but not during drag)
            if self.connection_line and not self.is_dragging_for_connection:
                self.connection_line.update_line()
        return super().itemChange(change, value)

# --- Port Data Structure ---
class PortData:
    def __init__(self, code, name):
        self.code = code
        self.name = name
        self.vessel_data_list = []
        self.original_vessel_data = [] 
        self.terminal_list = []
        self.ts_connections = {} 
        
        # Log Data (to repopulate tables)
        # Master Log: List of tuples/dicts matching table columns
        self.master_log_data = [] 
        # Slave Log
        self.slave_log_data = []
        
# --- Main App ---
class BerthMonitor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Berth Simulation System Pro")
        
        self.headers = [
            "번호", "터미널", "선석", "모선명", "모선항차", 
            "항차년도", "선사항차", "선사", "항로", 
            "접안방향", "접안예정일시", "출항예정일시"
        ]
        
        # Multi-Port Setup
        self.ports = {
            'KRPUS': PortData('KRPUS', 'Busan'),
            'KRKAN': PortData('KRKAN', 'Gwangyang'),
            'KRINC': PortData('KRINC', 'Incheon')
        }
        self.active_port_code = 'KRPUS'
        
        # Helper References (pointers to active port's data)
        self.vessel_data_list = self.ports['KRPUS'].vessel_data_list
        self.original_vessel_data = self.ports['KRPUS'].original_vessel_data
        self.terminal_list = self.ports['KRPUS'].terminal_list
        self.ts_connections = self.ports['KRPUS'].ts_connections
        
        self.pixels_per_hour = 5  
        self.row_height = 70      
        self.safety_gap_h = 2
        
        self.line_colors = {}
        self.base_colors = [
            "#ffadad", "#ffd6a5", "#fdffb6", "#caffbf", 
            "#9bf6ff", "#a0c4ff", "#bdb2ff", "#ffc6ff"
        ]
        
        # Filtering
        self.allowed_pairs = set() 
        self.filter_widgets = {} 
        
        # Memo Data (Global)
        self.memo_data = {} 
        self.is_memo_mode = False
        
        # Port-Specific Header Mapping
        # Maps external column names to internal standard names
        self.port_header_maps = {
            'KRPUS': {},  # Busan uses standard headers (no mapping needed)
            'KRKAN': {  # Gwangyang mapping
                '선박명': '모선명',
                '모선항차': ['모선항차', '항차년도', '선사항차'],  # Multiple targets
                '접안': '접안방향',
                '입항 일시': '접안예정일시',
                '출항 일시': '출항예정일시'
            },
            'KRINC': {  # Incheon mapping (same as Gwangyang)
                '선박명': '모선명',
                '모선항차': ['모선항차', '항차년도', '선사항차'],
                '접안': '접안방향',
                '입항 일시': '접안예정일시',
                '출항 일시': '출항예정일시'
            }
        }
        
        # Animation Timer
        self.heart_angle = 0
        self.rainbow_hue = 0
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.update_animation)
        self.anim_timer.start(50) 
        
        # Current Time Display Components
        self.current_time_text = None  # QGraphicsTextItem
        self.current_time_box = None   # QGraphicsRectItem
        self.current_time_line = None  # QGraphicsLineItem (vertical line)
        self.vessel_items = []         # QGraphicsRectItem list (VesselItem)
        
        # Current Time Update Timer (1 second)
        self.time_update_timer = QTimer()
        self.time_update_timer.timeout.connect(self.update_current_time_display)
        self.time_update_timer.start(1000)  # Update every 1 second
        
        # Ticker Update Timer (1 second)
        self.ticker_timer = QTimer()
        self.ticker_timer.timeout.connect(self.update_ticker_content)
        self.ticker_timer.start(1000)
        
        self.is_dark_mode = True # Default to Dark Mode
        
        self.initUI()
        self.apply_styles()
        
        # Auto-load last mapping if exists
        last_map = get_last_mapping_path()
        if last_map and os.path.exists(last_map):
             self.load_mappings(last_map)
             print(f"Auto-loaded mapping from: {last_map}")
             
        self.current_view_mode = "NORMAL"

    def initUI(self):
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        header_layout = QHBoxLayout()
        title_label = QLabel("BERTH SIMULATION MONITOR PRO / Port-I Fork ")
        title_label.setObjectName("titleLabel")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        # New Interactive Buttons
        
        # MEMO Button (Left of Copy)
        self.btn_memo = QPushButton()
        self.btn_memo.setText("MEMO\noff")
        self.btn_memo.setFixedSize(160, 45)
        self.btn_memo.setCheckable(True)
        self.btn_memo.clicked.connect(self.toggle_memo_mode)
        header_layout.addWidget(self.btn_memo)

        self.copy_btn = QPushButton()
        self.copy_btn.setText("Vessel Copy\noff")
        self.copy_btn.setFixedSize(160, 45)
        self.copy_btn.setCheckable(True)
        self.copy_btn.clicked.connect(self.toggle_copy_mode)
        header_layout.addWidget(self.copy_btn)
        
        self.highlight_btn = QPushButton()
        self.highlight_btn.setText("Highlight Mode\noff")
        self.highlight_btn.setFixedSize(160, 45)
        self.highlight_btn.setCheckable(True)
        self.highlight_btn.clicked.connect(self.toggle_highlight_mode)
        header_layout.addWidget(self.highlight_btn)

        self.connect_btn = QPushButton()
        self.connect_btn.setText("Connect Mode\noff")
        self.connect_btn.setFixedSize(160, 45)
        self.connect_btn.setCheckable(True)
        self.connect_btn.clicked.connect(self.toggle_connect_mode)
        header_layout.addWidget(self.connect_btn)

        self.reset_btn = QPushButton("🔄 Reset Current")
        self.reset_btn.setFixedSize(160, 45)
        self.reset_btn.clicked.connect(self.reset_data)
        self.reset_btn.setEnabled(False)
        header_layout.addWidget(self.reset_btn)

        # SPLIT PASTE BUTTONS
        btn_paste_krpus = QPushButton("Paste KRPUS")
        btn_paste_krpus.setFixedSize(110, 45)
        btn_paste_krpus.clicked.connect(lambda: self.paste_data('KRPUS'))
        btn_paste_krpus.setStyleSheet("background-color: #bb9af7; color: black; font-weight: bold;")
        header_layout.addWidget(btn_paste_krpus)

        btn_paste_krkan = QPushButton("Paste KRKAN")
        btn_paste_krkan.setFixedSize(110, 45)
        btn_paste_krkan.clicked.connect(lambda: self.paste_data('KRKAN'))
        btn_paste_krkan.setStyleSheet("background-color: #7dcfff; color: black; font-weight: bold;")
        header_layout.addWidget(btn_paste_krkan)

        btn_paste_krinc = QPushButton("Paste KRINC")
        btn_paste_krinc.setFixedSize(110, 45)
        btn_paste_krinc.clicked.connect(lambda: self.paste_data('KRINC'))
        btn_paste_krinc.setStyleSheet("background-color: #9ece6a; color: black; font-weight: bold;")
        header_layout.addWidget(btn_paste_krinc)
        
        main_layout.addLayout(header_layout)
        
        self.splitter = QSplitter(Qt.Vertical)
        
        # Upper area: Graphic View + Sidebar with Horizontal Splitter
        self.upper_splitter = QSplitter(Qt.Horizontal)
        
        # --- PORT TABS (GRAPHIC AREA) ---
        self.graphic_container = QWidget()
        gc_layout = QVBoxLayout(self.graphic_container)
        gc_layout.setContentsMargins(0,0,0,0)
        
        self.port_tabs = QTabWidget()
        self.port_tabs.setObjectName("portTabs")
        self.port_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #414868; background: #1f2335; }
            QTabBar::tab { background: #1a1b26; color: #a9b1d6; padding: 10px 15px; border: 1px solid #414868; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; font-weight: bold; }
            QTabBar::tab:selected { background: #7aa2f7; color: #1a1b26; }
        """)
        
        self.port_views = {}
        for code, name in [('KRPUS', 'Busan'), ('KRKAN', 'Gwangyang'), ('KRINC', 'Incheon')]:
             scene = QGraphicsScene()
             scene.parent_view = self
             view = ZoomableGraphicsView(scene)
             self.port_views[code] = (view, scene)
             self.port_tabs.addTab(view, name)
             
        self.port_tabs.currentChanged.connect(self.switch_port)

        # Minimize and Shutdown Buttons for Port Tabs
        self.port_corner_container = QWidget()
        pc_layout = QHBoxLayout(self.port_corner_container)
        pc_layout.setContentsMargins(0, 0, 5, 5) # Right/Bottom margin for alignment
        pc_layout.setSpacing(10)
        
        # News Ticker
        self.ticker = TickerLabel()
        self.ticker.setMinimumWidth(900)
        pc_layout.addWidget(self.ticker)
        
        self.btn_minimize_port = QPushButton("―")
        self.btn_minimize_port.setFixedSize(30, 30)
        self.btn_minimize_port.clicked.connect(self.showMinimized)
        self.btn_minimize_port.setStyleSheet("background-color: #414868; color: white;")
        pc_layout.addWidget(self.btn_minimize_port)
        
        self.btn_shutdown_port = QPushButton("✕")
        self.btn_shutdown_port.setFixedSize(30, 30)
        self.btn_shutdown_port.clicked.connect(self.shutdown_app)
        self.btn_shutdown_port.setStyleSheet("background-color: #f7768e; color: white;") 
        pc_layout.addWidget(self.btn_shutdown_port)
        
        self.port_tabs.setCornerWidget(self.port_corner_container, Qt.TopRightCorner)

        
        gc_layout.addWidget(self.port_tabs)
        self.upper_splitter.addWidget(self.graphic_container)
        
        self.sidebar = QWidget()
        self.sidebar.setMinimumWidth(380) # Increased width for tabs
        self.sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(self.sidebar)
        
        # --- TAB WIDGET ---
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #414868; background: #1f2335; }
            QTabBar::tab { background: #1a1b26; color: #a9b1d6; padding: 8px 12px; border: 1px solid #414868; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: #7aa2f7; color: #1a1b26; font-weight: bold; }
            QTabBar::tab:hover { background: #24283b; }
        """)
        
        # --- TAB 1: LOGS ---
        self.tab_logs = QWidget()
        logs_layout = QVBoxLayout(self.tab_logs)
        logs_layout.setContentsMargins(5, 5, 5, 5)
        
        # MASTER CHANGE
        master_header = QHBoxLayout()
        master_header.addWidget(QLabel("<b>[ MASTER CHANGE ]</b>"))
        master_header.addStretch()
        self.btn_pop_master = QPushButton("↗")
        self.btn_pop_master.setFixedSize(30, 25)
        self.btn_pop_master.clicked.connect(lambda: self.open_table_popup("MASTER CHANGE", self.master_table))
        master_header.addWidget(self.btn_pop_master)
        logs_layout.addLayout(master_header)
        
        self.master_table = QTableWidget()
        self.master_table.setColumnCount(4)
        self.master_table.setHorizontalHeaderLabels(["Vessel", "FROM", "TO", "Shift"])
        # Set column resize modes
        self.master_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)  # Vessel - takes remaining space
        self.master_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)  # FROM
        self.master_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)  # TO
        self.master_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Shift - minimal width
        # Set explicit widths for FROM and TO columns
        self.master_table.setColumnWidth(1, 130)  # FROM
        self.master_table.setColumnWidth(2, 130)  # TO
        self.master_table.setMinimumHeight(200)
        logs_layout.addWidget(self.master_table)
        
        # SLAVE CHANGES
        slave_header = QHBoxLayout()
        slave_header.addWidget(QLabel("<br><b>[ SLAVE CHANGES ]</b>"))
        slave_header.addStretch()
        self.btn_pop_slave = QPushButton("↗")
        self.btn_pop_slave.setFixedSize(30, 25)
        self.btn_pop_slave.clicked.connect(lambda: self.open_table_popup("SLAVE CHANGES", self.slave_table))
        slave_header.addWidget(self.btn_pop_slave)
        logs_layout.addLayout(slave_header)

        self.slave_table = QTableWidget()
        self.slave_table.setColumnCount(4)
        self.slave_table.setHorizontalHeaderLabels(["Vessel", "FROM", "TO", "Shift"])
        # Set column resize modes
        self.slave_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)  # Vessel - takes remaining space
        self.slave_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)  # FROM
        self.slave_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)  # TO
        self.slave_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Shift - minimal width
        # Set explicit widths for FROM and TO columns
        self.slave_table.setColumnWidth(1, 130)  # FROM
        self.slave_table.setColumnWidth(2, 130)  # TO
        self.slave_table.setObjectName("changeTable") 
        self.slave_table.setMinimumHeight(200)
        logs_layout.addWidget(self.slave_table)
        
        # TS CONNECT LOG
        ts_header = QHBoxLayout()
        ts_header.addWidget(QLabel("<br><b>[ TS CONNECT LOG ]</b>"))
        ts_header.addStretch()
        self.btn_pop_ts = QPushButton("↗")
        self.btn_pop_ts.setFixedSize(30, 25)
        self.btn_pop_ts.clicked.connect(lambda: self.open_table_popup("TS CONNECT LOG", self.ts_table))
        ts_header.addWidget(self.btn_pop_ts)
        logs_layout.addLayout(ts_header)

        self.ts_table = QTableWidget()
        self.ts_table.setColumnCount(2)
        self.ts_table.setHorizontalHeaderLabels(["LOAD VESSEL", "DISCH VESSEL (0)"])
        self.ts_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.ts_table.setMinimumHeight(200)
        logs_layout.addWidget(self.ts_table)
        
        logs_layout.addStretch()
        
        
        # --- TAB 2: FILTERS ---
        self.create_filter_tab()
        
        # --- TAB 3: MAPPING ---
        self.create_mapping_tab()
        
        # --- TAB 4: MEMO ---
        self.create_memo_tab()
        
        # Add Tabs to Sidebar
        self.tabs.addTab(self.tab_logs, "LOGS")
        self.tabs.addTab(self.tab_filters, "FILTERS")
        self.tabs.addTab(self.tab_mapping, "MAPPING")
        self.tabs.addTab(self.tab_memo, "MEMO")
        
        # --- TAB 5: SEARCH ---
        self.create_search_tab()
        self.tabs.addTab(self.tab_search, "SEARCH")
        
        # --- Theme Toggle Button (Corner Widget) ---
        self.theme_container = QWidget()
        theme_layout = QHBoxLayout(self.theme_container)
        theme_layout.setContentsMargins(50, 0, 20, 35) # Increased bottom margin to move button up
        theme_layout.setSpacing(0)
        
        self.btn_theme = QPushButton(" 🌙 ") # Initial: Dark Mode icon
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.setFixedSize(30, 30) # Slightly smaller to fit better
        self.btn_theme.setStyleSheet("border: none; background: transparent; font-size: 16px;")
        self.btn_theme.clicked.connect(self.toggle_theme)
        
        theme_layout.addWidget(self.btn_theme)
        
        self.tabs.setCornerWidget(self.theme_container, Qt.TopRightCorner)
        
        sidebar_layout.addWidget(self.tabs)
        
        self.upper_splitter.addWidget(self.sidebar)
        
        # Set initial sizes for upper splitter: 70% (Graphic) / 30% (Sidebar)
        # Using setSizes with large values to set proportions
        self.upper_splitter.setSizes([7000, 3000])
        
        self.splitter.addWidget(self.upper_splitter)
        
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.splitter.addWidget(self.table)
        
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 1)
        main_layout.addWidget(self.splitter)
        
        # Set initial refs for KRPUS (Default Tab 0 aka Active)
        self.gv, self.scene = self.port_views['KRPUS']

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.apply_styles()

    def apply_styles(self):
        if self.is_dark_mode:
            # --- DARK MODE COLORS ---
            bg_main = "#1a1b26"
            bg_sidebar = "#1f2335"
            bg_widget = "#16161e"
            bg_table = "#24283b"
            bg_header = "#1f2335"
            text_main = "#a9b1d6"
            text_header = "#7aa2f7"
            accent = "#7aa2f7"
            border = "#414868"
            btn_bg = "#7aa2f7"
            btn_text = "#1a1b26"
            btn_hover = "#89ddff"
            btn_disabled_bg = "#414868"
            btn_disabled_text = "#565f89"
            
            self.btn_theme.setText(" 🌙 ")
            self.btn_theme.setStyleSheet("border: none; background: transparent; font-size: 20px; color: #a9b1d6;")
            
            search_input_style = f"background-color: {bg_table}; color: {text_main}; border: 1px solid {border};"
            
        else:
            # --- LIGHT MODE COLORS ---
            bg_main = "#f0f2f5"
            bg_sidebar = "#ffffff"
            bg_widget = "#ffffff"
            bg_table = "#ffffff"
            bg_header = "#e4e4e7"
            text_main = "#333333"
            text_header = "#2563eb" # Blue-600
            accent = "#2563eb"
            border = "#d1d5db"
            btn_bg = "#3b82f6" # Blue-500
            btn_text = "#ffffff"
            btn_hover = "#60a5fa"
            btn_disabled_bg = "#e5e7eb"
            btn_disabled_text = "#9ca3af"
            
            self.btn_theme.setText(" ☀️ ")
            self.btn_theme.setStyleSheet("border: none; background: transparent; font-size: 20px; color: #f59e0b;") # Orange sun
            
            search_input_style = f"background-color: {bg_widget}; color: {text_main}; border: 1px solid {border};"

        # MAIN STYLESHEET
        self.setStyleSheet(f"""
            QMainWindow, QWidget#centralWidget {{ background-color: {bg_main}; }}
            QWidget {{ color: {text_main}; font-family: 'Segoe UI', sans-serif; }}
            #titleLabel {{ font-size: 20px; font-weight: bold; color: {accent}; margin: 10px; }}
            QPushButton {{ background-color: {btn_bg}; color: {btn_text}; border-radius: 8px; font-weight: bold; font-size: 14px; }}
            QPushButton:hover {{ background-color: {btn_hover}; }}
            QPushButton:disabled {{ background-color: {btn_disabled_bg}; color: {btn_disabled_text}; }}
            QGraphicsView {{ background-color: {bg_widget}; border: 1px solid {border}; border-radius: 10px; }}
            QTableWidget {{ background-color: {bg_table}; gridline-color: {border}; color: {text_main}; border: none; }}
            QHeaderView::section {{ background-color: {bg_header}; color: {text_header}; padding: 8px; border: 1px solid {border}; font-weight: bold; font-size: 11px; }}
            QTableCornerButton::section {{ background-color: {bg_header}; border: 1px solid {border}; }}
            QScrollBar:vertical {{ border: none; background: {bg_widget}; width: 14px; margin: 0px 0px 0px 0px; }}
            QScrollBar::handle:vertical {{ background: {border}; min-height: 30px; border-radius: 7px; }}
            QScrollBar::handle:vertical:hover {{ background: {btn_disabled_text}; }}
            QScrollBar::sub-line:vertical {{ border: none; background: none; height: 0px; }}
            QScrollBar::add-line:vertical {{ border: none; background: none; height: 0px; }}
            QScrollBar:horizontal {{ border: none; background: {bg_widget}; height: 14px; margin: 0px 0px 0px 0px; }}
            QScrollBar::handle:horizontal {{ background: {border}; min-width: 30px; border-radius: 7px; }}
            QScrollBar::handle:horizontal:hover {{ background: {btn_disabled_text}; }}
            QScrollBar::sub-line:horizontal {{ border: none; background: none; width: 0px; }}
            QScrollBar::add-line:horizontal {{ border: none; background: none; width: 0px; }}
            #sidebar {{ background-color: {bg_sidebar}; border-left: 2px solid {border}; padding: 5px; }}
            QDialog {{ background-color: {bg_main}; }}
            QCheckBox {{ spacing: 5px; color: {text_main}; }}
            QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 3px; border: 1px solid {btn_disabled_text}; background: {bg_widget}; }}
            QCheckBox::indicator:checked {{ background: {accent}; border: 1px solid {accent}; image: url(:/qt-project.org/styles/commonstyle/images/standardbutton-apply-16.png); }}
            QGroupBox {{ border: 1px solid {border}; border-radius: 5px; margin-top: 20px; font-weight: bold; color: {accent}; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}
        """)

        # TAB STYLES
        tab_stylesheet = f"""
            QTabWidget::pane {{ border: 1px solid {border}; background: {bg_sidebar}; }}
            QTabBar::tab {{ background: {bg_main}; color: {text_main}; padding: 10px 15px; border: 1px solid {border}; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; font-weight: bold; }}
            QTabBar::tab:selected {{ background: {accent}; color: {btn_text}; }}
            QTabBar::tab:hover {{ background: {bg_header}; }}
        """
        
        if hasattr(self, 'port_tabs'): self.port_tabs.setStyleSheet(tab_stylesheet)
        if hasattr(self, 'tabs'): self.tabs.setStyleSheet(tab_stylesheet)
        
        # Search Input Style
        if hasattr(self, 'search_input'): self.search_input.setStyleSheet(search_input_style)

    def switch_port(self, index):
        active_code = list(self.port_views.keys())[index] # Tabs added in order KRPUS, KRKAN, KRINC
        # Assuming order of keys matches tab order. Let's strictly rely on list order.
        codes = ['KRPUS', 'KRKAN', 'KRINC']
        if index < 0 or index >= len(codes): return
        active_code = codes[index]

        if self.active_port_code == active_code: return
        
        # 1. Update Active Code
        self.active_port_code = active_code
        port = self.ports[active_code]
        
        # 2. Update Data References
        self.vessel_data_list = port.vessel_data_list
        self.original_vessel_data = port.original_vessel_data
        self.terminal_list = port.terminal_list
        self.ts_connections = port.ts_connections
        
        # 3. Update View/Scene References
        self.gv, self.scene = self.port_views[active_code]
        
        # 4. Refresh UI
        self.reset_btn.setEnabled(len(self.original_vessel_data) > 0)
        self.repopulate_logs()
        self.update_filters()
        self.populate_mapping_tables()
        self.populate_memo_table()
        self.refresh_ts_table() # Refresh TS Table from active dict
        self.update_table()
        self.draw_graphic()

    def repopulate_logs(self):
        # Master Log
        self.master_table.setRowCount(0)
        port = self.ports[self.active_port_code]
        for entry in port.master_log_data:
            self.add_master_log_row(entry)
            
        # Slave Log
        self.slave_table.setRowCount(0)
        for entry in port.slave_log_data:
            self.add_slave_log_row(entry)

    def add_master_log_row(self, entry):
        row = self.master_table.rowCount()
        self.master_table.insertRow(row)
        
        # Col 0: Vessel (Widget or Item)
        if entry.get('vessel_widget_text'):
             lbl = QLabel(entry['vessel_widget_text'])
             lbl.setAlignment(Qt.AlignCenter)
             lbl.setStyleSheet(entry['vessel_widget_style'])
             self.master_table.setCellWidget(row, 0, lbl)
        else:
             self.master_table.setItem(row, 0, QTableWidgetItem(entry['vessel_text']))
             
        self.master_table.setItem(row, 1, QTableWidgetItem(entry['from']))
        
        # Col 2: To (Widget or Item)
        if entry.get('to_widget_text'):
             lbl = QLabel(entry['to_widget_text'])
             lbl.setAlignment(Qt.AlignCenter)
             lbl.setStyleSheet(entry['to_widget_style'])
             self.master_table.setCellWidget(row, 2, lbl)
        else:
             self.master_table.setItem(row, 2, QTableWidgetItem(entry['to_text']))
             
        # Col 3: Shift
        delta_item = QTableWidgetItem(entry['shift_text'])
        delta_item.setTextAlignment(Qt.AlignCenter)
        if entry.get('shift_color'):
            delta_item.setForeground(QColor(entry['shift_color']))
        self.master_table.setItem(row, 3, delta_item)
        
        self.master_table.scrollToBottom()

    def add_slave_log_row(self, entry):
        row = self.slave_table.rowCount()
        self.slave_table.insertRow(row)
        self.slave_table.setItem(row, 0, QTableWidgetItem(entry['name']))
        self.slave_table.setItem(row, 1, QTableWidgetItem(entry['old_eta']))
        self.slave_table.setItem(row, 2, QTableWidgetItem(entry['new_eta']))
        
        delta_item = QTableWidgetItem(entry['delta_str'])
        delta_item.setTextAlignment(Qt.AlignCenter)
        delta_item.setForeground(QColor("#ffb86c"))
        self.slave_table.setItem(row, 3, delta_item)
        self.slave_table.scrollToBottom()

    def create_filter_tab(self):
        self.tab_filters = QWidget()
        layout = QVBoxLayout(self.tab_filters)
        layout.setContentsMargins(5,5,5,5)
        
        # Global Controls
        global_btn_layout = QHBoxLayout()
        btn_all = QPushButton("Select All")
        btn_all.clicked.connect(lambda: self.set_global_toggle(True))
        btn_none = QPushButton("Select None")
        btn_none.clicked.connect(lambda: self.set_global_toggle(False))
        global_btn_layout.addWidget(btn_all)
        global_btn_layout.addWidget(btn_none)
        layout.addLayout(global_btn_layout)
        
        # Scroll Area for Hierarchy
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        # Light Theme for Filters
        scroll_content.setStyleSheet("""
            QWidget { background-color: #ffffff; color: #000000; }
            QCheckBox { color: #000000; spacing: 5px; }
            QCheckBox::indicator { border: 1px solid #888888; background: #f0f0f0; }
            QCheckBox::indicator:checked { background: #7aa2f7; border: 1px solid #7aa2f7; }
            QPushButton { background-color: #e0e0e0; color: black; border: 1px solid #cccccc; border-radius: 3px; padding: 4px; }
            QPushButton:hover { background-color: #d0d0d0; }
        """)
        self.filter_layout = QVBoxLayout(scroll_content)
        self.filter_layout.setSpacing(10)
        self.filter_layout.addStretch() # Ensure top align
        
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def set_global_toggle(self, state):
        # Toggle ALL Line Checkboxes
        for line_cb, _ in self.filter_widgets.values():
            line_cb.setChecked(state)
        # Note: line_cb.setChecked triggers toggle_routes via signal, 
        # which triggers on_filter_change, updating the graph.
        # Ideally we'd block signals and do one update, but for now this is functional.

    def update_filters(self):
        # 1. Build Hierarchy: Line -> Routes
        line_routes = defaultdict(set)
        for d in self.vessel_data_list:
            line = d.get('선사', 'Unknown')
            route = d.get('항로', 'Unknown')
            line_routes[line].add(route)
            
        # 2. Clear UI
        # Remove all items from filter_layout except stretch (last item)
        while self.filter_layout.count() > 1:
            item = self.filter_layout.takeAt(0)
            if item.widget(): item.widget().setParent(None)
            
        self.filter_widgets = {}
        
        # 3. Sort Lines (MSC Top, then Alpha)
        sorted_lines = sorted(line_routes.keys())
        msc_lines = [l for l in sorted_lines if "MSC" in l.upper()]
        other_lines = [l for l in sorted_lines if "MSC" not in l.upper()]
        final_lines = msc_lines + other_lines
        
        # 4. Create UI Elements
        for line in final_lines:
            # Container
            group = QGroupBox()
            # Light border for group
            group.setStyleSheet("QGroupBox { border: 1px solid #cccccc; border-radius: 5px; margin-top: 5px; font-weight: bold; }")
            group_layout = QVBoxLayout(group)
            group_layout.setContentsMargins(2, 2, 2, 2)
            group_layout.setSpacing(2)
            
            # Header: Line Checkbox
            line_cb = QCheckBox(f"{line} ({len(line_routes[line])})")
            line_cb.setChecked(True)
            if "MSC" in line.upper():
                line_cb.setStyleSheet("background-color: #ffd700; color: black; font-weight: bold; padding: 4px; border-radius: 4px;")
            else:
                # Inherit black color, just add padding/weight
                line_cb.setStyleSheet("font-weight: bold; padding: 4px;")
                
            group_layout.addWidget(line_cb)
            
            # Content: Route Checkboxes (Indented)
            route_cbs = []
            routes_frame = QWidget()
            routes_layout = QVBoxLayout(routes_frame)
            routes_layout.setContentsMargins(15, 0, 0, 0) # Indent
            routes_layout.setSpacing(2)
            
            for route in sorted(list(line_routes[line])):
                r_cb = QCheckBox(route)
                r_cb.setChecked(True)
                r_cb.stateChanged.connect(self.on_filter_change)
                routes_layout.addWidget(r_cb)
                route_cbs.append(r_cb)
                
            group_layout.addWidget(routes_frame)
            self.filter_layout.insertWidget(self.filter_layout.count()-1, group)
            
            # Store refs
            self.filter_widgets[line] = (line_cb, route_cbs)
            
            # Connect Line CB to toggle Children
            # Use closure default arg to capture current route_cbs
            line_cb.stateChanged.connect(lambda state, cbs=route_cbs: self.toggle_routes(state, cbs))
            
        self.on_filter_change() # Init state

    def toggle_routes(self, state, route_cbs):
        for cb in route_cbs:
            cb.blockSignals(True)
            cb.setChecked(state == Qt.Checked)
            cb.blockSignals(False)
        self.on_filter_change()

    def on_filter_change(self):
        self.allowed_pairs = set()
        
        for line, (line_cb, route_cbs) in self.filter_widgets.items():
            # Check routes regardless of parent line_cb state
            for i, r_cb in enumerate(route_cbs):
                if r_cb.isChecked():
                    # We need the route name back. 
                    # Option A: Store name in CB object
                    # Option B: Re-derive from CB text
                    route_name = r_cb.text()
                    self.allowed_pairs.add((line, route_name))
        
        self.draw_graphic()

    def create_mapping_tab(self):
        self.tab_mapping = QWidget()
        layout = QVBoxLayout(self.tab_mapping)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Helper to create table
        def create_map_table(title, headers=["Original", "New"]):
            lbl = QLabel(title)
            lbl.setStyleSheet("font-weight: bold; color: #7aa2f7; margin-top: 10px;")
            layout.addWidget(lbl)
            
            table = QTableWidget()
            table.setColumnCount(len(headers))
            table.setHorizontalHeaderLabels(headers)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            layout.addWidget(table)
            return table

        self.map_line_table = create_map_table("Line Mapping", ["Original", "New", "Color"])
        self.map_route_table = create_map_table("Route Mapping", ["Original", "New"])
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        btn_load = QPushButton("Load JSON")
        btn_load.clicked.connect(self.load_mappings)
        btn_layout.addWidget(btn_load)
        
        btn_save = QPushButton("Save JSON")
        btn_save.clicked.connect(self.save_mappings)
        btn_layout.addWidget(btn_save)
        
        layout.addLayout(btn_layout)
        
        btn_apply = QPushButton("Apply Mapping")
        btn_apply.setStyleSheet("background-color: #f7768e; color: black; font-weight: bold;")
        btn_apply.clicked.connect(self.apply_mappings)
        layout.addWidget(btn_apply)

    def populate_mapping_tables(self):
        # Extract unique Lines and Routes from CURRENT data
        unique_lines = sorted(list(set(d.get('선사', '') for d in self.vessel_data_list)))
        unique_routes = sorted(list(set(d.get('항로', '') for d in self.vessel_data_list)))
        
        def fill_table(table, items, is_line_table=False):
            table.setRowCount(len(items))
            for r, item in enumerate(items):
                # Col 0: Original (Read-onlyish)
                item_orig = QTableWidgetItem(item)
                item_orig.setFlags(item_orig.flags() ^ Qt.ItemIsEditable) # Make Read-only
                table.setItem(r, 0, item_orig)
                
                # Col 1: New (Editable, default empty)
                table.setItem(r, 1, QTableWidgetItem(""))
                
                # Col 2: Color (for Lines)
                if is_line_table and table.columnCount() > 2:
                    btn_color = QPushButton()
                    btn_color.setFixedSize(60, 20)
                    
                    # Use get_color to ensure we get either the saved color OR a consistent random color
                    # .name() ensures we get the hex string from the QColor object
                    initial_color = self.get_color(item).name()
                        
                    btn_color.setStyleSheet(f"background-color: {initial_color}; border: 1px solid #555;")
                    btn_color.clicked.connect(self.pick_color)
                    table.setCellWidget(r, 2, btn_color)
            
        fill_table(self.map_line_table, unique_lines, is_line_table=True)
        fill_table(self.map_route_table, unique_routes, is_line_table=False)

    def apply_mappings(self):
        # 1. Read Tables
        line_map = {}
        for r in range(self.map_line_table.rowCount()):
            orig = self.map_line_table.item(r, 0).text()
            new = self.map_line_table.item(r, 1).text().strip()
            if new: line_map[orig] = new
            
        route_map = {}
        for r in range(self.map_route_table.rowCount()):
            orig = self.map_route_table.item(r, 0).text()
            new = self.map_route_table.item(r, 1).text().strip()
            if new: route_map[orig] = new
            
        if not line_map and not route_map: return

        # 2. Apply to Data
        for d in self.vessel_data_list:
            if d.get('선사') in line_map:
                d['선사'] = line_map[d['선사']]
            if d.get('항로') in route_map:
                d['항로'] = route_map[d['항로']]
                
        # 3. Refresh UI
        self.update_filters() # Re-populate filters with new names
        self.update_table() # Update main table
        self.draw_graphic() # Redraw graph
        
        # 4. Optional: Refresh Mapping tables to reflect new state as "Original"?
        # Actually better to keep them as is so user knows what they mapped from?
        # But if we re-populate, 'Original' becomes the NEW name.
        # Let's re-populate to confirm the change state.
        # self.populate_mapping_tables() # REMOVED: Keep input values for saving
        
    def pick_color(self):
        btn = self.sender()
        if not btn: return
        
        color = QColorDialog.getColor()
        if color.isValid():
            hex_color = color.name()
            btn.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #555;")
            
            # Find which line this is
            line_name = None
            for r in range(self.map_line_table.rowCount()):
                if self.map_line_table.cellWidget(r, 2) == btn:
                    line_name = self.map_line_table.item(r, 0).text()
                    break
            
            if line_name:
                self.line_colors[line_name] = QColor(hex_color)
                self.draw_graphic() # Instant update
            
    def save_mappings(self):
        default_name = f"mapping_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.json"
        filename, _ = QFileDialog.getSaveFileName(self, "Save Mapping", default_name, "JSON Files (*.json)")
        if filename:
            self.perform_save_mapping(filename)

    def perform_save_mapping(self, filename):
        data = {
            'lines': {},
            'routes': {},
            'line_colors': {}
        }
        for r in range(self.map_line_table.rowCount()):
            orig = self.map_line_table.item(r, 0).text()
            new = self.map_line_table.item(r, 1).text().strip()
            if new: data['lines'][orig] = new
            
            btn_color = self.map_line_table.cellWidget(r, 2)
            if btn_color:
                 style = btn_color.styleSheet()
                 if "background-color:" in style:
                     try:
                         hex_code = style.split("background-color:")[1].split(";")[0].strip()
                         data['line_colors'][orig] = hex_code
                     except: pass
            
        for r in range(self.map_route_table.rowCount()):
            orig = self.map_route_table.item(r, 0).text()
            new = self.map_route_table.item(r, 1).text().strip()
            if new: data['routes'][orig] = new
            
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            save_last_mapping_path(filename)
        except Exception as e:
            print(f"Error saving mapping: {e}")

    def auto_save_mappings(self):
        # Auto-save to a temporary file or a designated auto-save location
        # For simplicity, let's save to a file named with timestamp in the current directory
        filename = f"auto_mapping_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.json"
        self.perform_save_mapping(filename)


    def load_mappings(self, file_path=None):
        if file_path:
            filename = file_path
        else:
            filename, _ = QFileDialog.getOpenFileName(self, "Load Mapping", "", "JSON Files (*.json)")
            
        if not filename: return
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Apply to Tables
            loaded_lines = data.get('lines', {})
            loaded_routes = data.get('routes', {})
            loaded_colors = data.get('line_colors', {}) # New: Load Colors
            
            # Convert loaded hex strings to QColor objects
            converted_colors = {}
            for line, hex_str in loaded_colors.items():
                converted_colors[line] = QColor(hex_str)
            
            self.line_colors = converted_colors # Update internal dict with QColor objects
            
            def match_table(table, map_data, color_data=None):
                if color_data is None:
                    color_data = {} # Default empty dict if not provided
                for r in range(table.rowCount()):
                    orig = table.item(r, 0).text()
                    if orig in map_data:
                        table.setItem(r, 1, QTableWidgetItem(map_data[orig]))
                    
                    # Handle Color Button (Column 2) if this is the Line Table
                    if table.columnCount() > 2: # Check if the table has a 3rd column
                        btn_color = QPushButton()
                        btn_color.setFixedSize(60, 20)
                        
                        # Set initial color logic
                        initial_color = "#ffffff" # Default
                        if orig in color_data:
                            initial_color = color_data[orig]
                        
                        btn_color.setStyleSheet(f"background-color: {initial_color}; border: 1px solid #555;")
                        btn_color.clicked.connect(self.pick_color)
                        table.setCellWidget(r, 2, btn_color)
            
            match_table(self.map_line_table, loaded_lines, loaded_colors)
            match_table(self.map_route_table, loaded_routes)
            
            # Save for next time (if manual load or first time)
            if not file_path:
                save_last_mapping_path(filename)
            
        except Exception as e:
            print(f"Error loading: {e}")

    def create_memo_tab(self):
        self.tab_memo = QWidget()
        layout = QVBoxLayout(self.tab_memo)
        layout.setContentsMargins(5,5,5,5)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_load = QPushButton("Load Memos")
        btn_load.clicked.connect(self.load_memos)
        btn_save = QPushButton("Save Memos")
        btn_save.clicked.connect(self.save_memos)
        btn_layout.addWidget(btn_load)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)
        
        # Table
        # Table
        self.memo_table = QTableWidget()
        self.memo_table.setColumnCount(3)
        self.memo_table.setHorizontalHeaderLabels(["Vessel Info", "Memo", "Action"])
        self.memo_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.memo_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.memo_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.memo_table.cellChanged.connect(self.on_memo_changed)
        layout.addWidget(self.memo_table)
        
    def create_search_tab(self):
        self.tab_search = QWidget()
        layout = QVBoxLayout(self.tab_search)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Input Area (Label + TextEdit)
        lbl_instruction = QLabel("Paste Excel Data (Vessel Name + Voyage):")
        lbl_instruction.setStyleSheet("font-weight: bold; color: #7aa2f7;")
        layout.addWidget(lbl_instruction)
        
        self.search_input = QTextEdit()
        self.search_input.setPlaceholderText("Example:\nSUNNY 001\nMOON 002W\n...")
        self.search_input.setMaximumHeight(100)
        # Style for input
        self.search_input.setStyleSheet("background-color: #24283b; color: #a9b1d6; border: 1px solid #414868;")
        layout.addWidget(self.search_input)
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_search = QPushButton("🔍 SEARCH")
        btn_search.setStyleSheet("background-color: #7dcfff; color: black; font-weight: bold;")
        btn_search.clicked.connect(self.perform_search)
        
        btn_clear = QPushButton("❌ CLEAR")
        btn_clear.setStyleSheet("background-color: #f7768e; color: black; font-weight: bold;")
        btn_clear.clicked.connect(self.clear_search)
        
        btn_layout.addWidget(btn_search)
        btn_layout.addWidget(btn_clear)
        layout.addLayout(btn_layout)
        
        # Results Table
        self.search_table = QTableWidget()
        self.search_table.setColumnCount(5)
        headers = ["Terminal", "Route", "Vessel", "Berth", "Depart"]
        self.search_table.setHorizontalHeaderLabels(headers)
        self.search_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.search_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch) # Vessel Name stretches
        self.search_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.search_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.search_table.cellClicked.connect(self.focus_searched_vessel)
        
        layout.addWidget(QLabel("<b>Search Results:</b>"))
        layout.addWidget(self.search_table)

    def perform_search(self):
        # 1. Reset Previous
        self.clear_search(clear_input=False)
        
        text = self.search_input.toPlainText().strip()
        if not text: return
        
        # 2. Parse Lines
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        found_count = 0
        
        # 3. Search Logic
        # We need to match AGAINST the active port's data
        # Token-based matching: Input "SUNNY 002" -> Tokens ["SUNNY", "002"]
        # Match if ALL tokens appear in (VesselName + Voyage) string.
        
        matching_vessels = []
        
        for search_line in lines:
            tokens = search_line.lower().split()
            if not tokens: continue
            
            # Search in current vessel list
            for vessel_item in self.scene.items():
                if not isinstance(vessel_item, VesselItem): continue
                
                data = vessel_item.data
                # Construct searchable string
                v_name = data.get('모선명', '').lower()
                v_voy = str(data.get('모선항차', '')).lower()
                
                # Combined string for searching
                target_str = f"{v_name} {v_voy}"
                
                # Check ALL tokens
                if all(token in target_str for token in tokens):
                    # MATCH FOUND
                    matching_vessels.append(vessel_item)
                    vessel_item.is_searched = True
                    # Start Rainbow Animation (reuses Highlight logic)
                    if not vessel_item.is_highlighted:
                        vessel_item.neon_timer.start(50)
                    vessel_item.update() # Trigger repaint for Checkmark
        
        # 4. Populate Table
        self.search_table.setRowCount(len(matching_vessels))
        for i, v_item in enumerate(matching_vessels):
            d = v_item.data
            
            # Terminal
            self.search_table.setItem(i, 0, QTableWidgetItem(d.get('터미널', '')))
            # Route
            self.search_table.setItem(i, 1, QTableWidgetItem(d.get('항로', '')))
            # Vessel + Carrier Voyage (선사항차)
            # Request: "VESSEL에는 선명과 선사항차를 보여줘"
            v_str = f"{d.get('모선명','')} {d.get('선사항차','')}"
            item_v = QTableWidgetItem(v_str)
            item_v.setData(Qt.UserRole, v_item) # Store Reference
            self.search_table.setItem(i, 2, item_v)
            
            # Dates
            self.search_table.setItem(i, 3, QTableWidgetItem(format_short_dt(d['eta'])))
            self.search_table.setItem(i, 4, QTableWidgetItem(format_short_dt(d['etd'])))
            
        if matching_vessels:
            # Force update scene
            self.scene.update()

    def clear_search(self, clear_input=True):
        if clear_input:
            self.search_input.clear()
        
        self.search_table.setRowCount(0)
        
        # Clear flags on ALL items in scene
        for item in self.scene.items():
            if isinstance(item, VesselItem):
                if item.is_searched:
                    item.is_searched = False
                    # Stop Rainbow Animation (if not otherwise highlighted)
                    # For simplicity, we stop it. 
                    # If the user HAD Highlight Mode on separately, this might stop it,
                    # but usually search is transient.
                    if not item.is_highlighted: # Only stop if it wasn't manually highlighted
                         # Actually `is_highlighted` is the toggle flag.
                         # If we reused neon timer, we should check if we should stop it.
                         # But wait, `is_highlighted` is set by the toggle button logic?
                         # Let's just stop it to be safe, or check status.
                         # The simplest way: toggle_highlight sets `is_highlighted` = True.
                         # If we manipulate timer directly, `is_highlighted` might mismatch.
                         # Let's just stop timer.
                        item.neon_timer.stop()
                        item.setPen(item.default_pen)
                        
                    item.update()
        
        self.scene.update()

    def focus_searched_vessel(self, row, col):
        # Get VesselItem from UserRole in Col 2 (Vessel column)
        item_v = self.search_table.item(row, 2)
        if not item_v: return
        
        v_item = item_v.data(Qt.UserRole)
        if v_item:
            # 1. Reset Focus on all OTHERs (or just clear global tracker if we had one)
            # Efficient way: Iterate scene or keep list? 
            # We can iterate scene items, or just iterate `matching_vessels` if we stored them,
            # but simpler is scene iteration or accept slight perf cost.
            # actually we can just iterate scene items check type.
            for item in self.scene.items():
                if isinstance(item, VesselItem) and item.is_search_focused:
                    item.is_search_focused = False
                    item.update()
            
            # 2. Set Focus
            v_item.is_search_focused = True
            v_item.update()
            
            self.gv.centerOn(v_item)
            
            self.scene.clearSelection()
            v_item.setSelected(True)


    def toggle_memo_mode(self):
        self.is_memo_mode = self.btn_memo.isChecked()
        if self.is_memo_mode:
            # Turn off Copy Mode if on
            if self.copy_btn.isChecked():
                self.copy_btn.setChecked(False)
                self.toggle_copy_mode()
            self.tabs.setCurrentWidget(self.tab_memo)
            # ON state: complementary color (cyan) with ON text below
            self.btn_memo.setStyleSheet("background-color: #00ffff; color: black;")
            self.btn_memo.setText("MEMO\non")
        else:
            # OFF state: original color with OFF text below
            self.btn_memo.setStyleSheet("")
            self.btn_memo.setText("MEMO\noff")

    def on_memo_changed(self, row, col):
        if col == 1: # Memo Content changed
            key_item = self.memo_table.item(row, 0)
            if not key_item: return
            key = key_item.data(Qt.UserRole)
            text = self.memo_table.item(row, 1).text()
            
            if text.strip():
                self.memo_data[key] = text
            else:
                if key in self.memo_data:
                    del self.memo_data[key]
            
            # Redraw graph to show/hide hearts
            self.draw_graphic()
            
            # Auto-Save
            self.auto_save_memos()

    def auto_save_memos(self):
        # Try to save to last known path, or default
        path = get_last_memo_path()
        if not path:
             # Default to a local file if not set
             path = "port_i_memos.json"
             # Optionally set it as default? Yes.
             save_last_memo_path(path)
             
        try:
             with open(path, 'w', encoding='utf-8') as f:
                 json.dump(self.memo_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
             print(f"Auto-save failed: {e}")

    def update_animation(self):
        # 5 seconds period. 50ms interval.
        # Spining: 360 deg / 100 steps = 3.6 deg per step.
        self.heart_angle = (self.heart_angle + 3.6) % 360
        
        # Rainbow Color Cycle: 
        # Period: Let's say 2 seconds for full spectrum? 
        # 2000ms / 50ms = 40 steps. 360 / 40 = 9 deg per step.
        # Or faster/slower as needed. Let's try 5 sec like rotation.
        self.rainbow_hue = (self.rainbow_hue + 3.6) % 360
        
        self.scene.update() # Trigger repaint call

    def open_memo_for_vessel(self, v_data):
        self.tabs.setCurrentWidget(self.tab_memo)
        
        key = f"{v_data['모선명']}|{v_data['선사항차']}"
        
        # Find row or Add
        found_row = -1
        for r in range(self.memo_table.rowCount()):
            item = self.memo_table.item(r, 0)
            if item.data(Qt.UserRole) == key:
                found_row = r
                break
        
        if found_row == -1:
            # Add new row (Should strictly happen during population, but dynamic add is fine)
            r = self.memo_table.rowCount()
            self.memo_table.insertRow(r)
            
            # Info
            # Format: Name Voyage \n Route
            info_str = f"{v_data['모선명']} {get_display_voyage(v_data['선사항차'])}\n{v_data.get('항로','')}"
            item_info = QTableWidgetItem(info_str)
            item_info.setData(Qt.UserRole, key)
            item_info.setFlags(item_info.flags() ^ Qt.ItemIsEditable)
            self.memo_table.setItem(r, 0, item_info)
            
            # Ensure height accommodates 2 lines
            self.memo_table.setRowHeight(r, 50)
            
            # Memo
            item_memo = QTableWidgetItem(self.memo_data.get(key, ""))
            self.memo_table.setItem(r, 1, item_memo)
            
            # Delete Button
            btn_del = QPushButton("Del")
            btn_del.setStyleSheet("background-color: #ff5555; color: white; font-weight: bold;")
            btn_del.clicked.connect(lambda _, k=key: self.delete_memo(k))
            self.memo_table.setCellWidget(r, 2, btn_del)
            
            found_row = r
            
        self.memo_table.selectRow(found_row)
        self.memo_table.scrollToItem(self.memo_table.item(found_row, 0))

    def save_memos(self):
        default_name = f"memo_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.json"
        filename, _ = QFileDialog.getSaveFileName(self, "Save Memos", default_name, "JSON Files (*.json)")
        if filename:
            self.perform_save_memo(filename)

    def perform_save_memo(self, filename):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.memo_data, f, indent=4, ensure_ascii=False)
            save_last_memo_path(filename)
        except Exception as e:
            print(f"Error saving memos: {e}")

    def auto_save_memos(self):
        filename = f"memo_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}.json"
        self.perform_save_memo(filename)

    def shutdown_app(self):
        # Auto-save everything
        self.auto_save_mappings()
        self.auto_save_memos()
        QApplication.quit()


    def load_memos(self, file_path=None):
        if file_path:
            filename = file_path
        else:
            filename, _ = QFileDialog.getOpenFileName(self, "Load Memos", "", "JSON Files (*.json)")
            
        if not filename: return
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                self.memo_data = json.load(f)
            
            # Refresh Table if populated
            self.populate_memo_table()
            self.draw_graphic()
            
            if not file_path:
                save_last_memo_path(filename)
                
        except Exception as e:
            print(f"Error loading memos: {e}")

    def populate_memo_table(self):
        # Populate table with ONLY vessels that have memos
        self.memo_table.setRowCount(0)
        self.memo_table.blockSignals(True)
        
        for d in self.vessel_data_list:
            key = f"{d['모선명']}|{d['선사항차']}"
            
            # Only add if exists in memo_data
            if key not in self.memo_data: continue
            
            r = self.memo_table.rowCount()
            self.memo_table.insertRow(r)
            
            # Info
            # Format: Name Voyage \n Route
            # User wants "Service Name" on 2nd line. Assuming '항로' == Service.
            info_str = f"{d['모선명']} {get_display_voyage(d['선사항차'])}\n{d.get('항로','')}"
            item_info = QTableWidgetItem(info_str)
            item_info.setData(Qt.UserRole, key)
            item_info.setFlags(item_info.flags() ^ Qt.ItemIsEditable)
            self.memo_table.setItem(r, 0, item_info)
            
            # Ensure height accommodates 2 lines
            self.memo_table.setRowHeight(r, 50)
            
            # Memo
            val = self.memo_data.get(key, "")
            self.memo_table.setItem(r, 1, QTableWidgetItem(val))
            
            # Delete Button
            btn_del = QPushButton("Del")
            btn_del.setStyleSheet("background-color: #ff5555; color: white; font-weight: bold;")
            btn_del.clicked.connect(lambda _, k=key: self.delete_memo(k))
            self.memo_table.setCellWidget(r, 2, btn_del)
            
        self.memo_table.blockSignals(False)

    def delete_memo(self, key):
        if key in self.memo_data:
            del self.memo_data[key]
            
        # Refresh Table and Graph
        self.populate_memo_table()
        self.draw_graphic()

    def get_color(self, line):
        if line not in self.line_colors or not self.line_colors[line].isValid():
            # Generate Random Pastel Color
            hue = random.randint(0, 359)
            saturation = random.randint(90, 160) # Low saturation for pastel
            value = random.randint(200, 255)     # High value for brightness
            
            color = QColor.fromHsv(hue, saturation, value)
            self.line_colors[line] = color
            
        return self.line_colors[line]

    def toggle_copy_mode(self):
        if self.copy_btn.isChecked():
            self.current_view_mode = "COPY"
            self.highlight_btn.setChecked(False)
            self.connect_btn.setChecked(False)
            # ON state: complementary color (orange) with ON text below
            self.copy_btn.setStyleSheet("background-color: #ff8c00; color: black;")
            self.copy_btn.setText("Vessel Copy\non")
        else:
            self.current_view_mode = "NORMAL"
            self.copy_btn.setStyleSheet("")
            self.copy_btn.setText("Vessel Copy\noff")

    def toggle_highlight_mode(self):
        if self.highlight_btn.isChecked():
            self.current_view_mode = "HIGHLIGHT"
            self.copy_btn.setChecked(False)
            self.connect_btn.setChecked(False)
            # ON state: complementary color (lime green) with ON text below
            self.highlight_btn.setStyleSheet("background-color: #32cd32; color: black;")
            self.highlight_btn.setText("Highlight Mode\non")
        else:
            self.current_view_mode = "NORMAL"
            self.highlight_btn.setStyleSheet("")
            self.highlight_btn.setText("Highlight Mode\noff")
            self.clear_analysis_artifacts()
 
    def toggle_connect_mode(self):
        if self.connect_btn.isChecked():
            self.current_view_mode = "CONNECT"
            self.copy_btn.setChecked(False)
            self.highlight_btn.setChecked(False)
            # ON state: complementary color (blue) with ON text below
            self.connect_btn.setStyleSheet("background-color: #1e90ff; color: black;")
            self.connect_btn.setText("Connect Mode\non")
        else:
            self.current_view_mode = "NORMAL"
            self.connect_btn.setStyleSheet("")
            self.connect_btn.setText("Connect Mode\noff")
            self.clear_analysis_artifacts()

    def clear_analysis_artifacts(self):
        # 1. Stop Neon
        for item in self.scene.items():
            if isinstance(item, VesselItem) and item.is_highlighted:
                item.toggle_highlight_effect()
                
        # 2. Remove Arrows
        items_to_remove = [item for item in self.scene.items() 
                           if isinstance(item, QGraphicsLineItem) and item.data(0) == "ARROW"]
        for item in items_to_remove:
            self.scene.removeItem(item)
            
        # 3. Clear TS Table
        self.ts_table.setRowCount(0)
        self.ts_table.clearSpans()
        self.ts_connections = {}

    def add_ts_connection(self, load_vessel, disch_vessel, color):
        if load_vessel not in self.ts_connections:
            self.ts_connections[load_vessel] = []
        
        # Check if already exists to prevent dupes if logic allows multiple arrows (though mouseRelease blocks self)
        # Assuming one arrow per pair for now.
        # But we simply append for the view.
        self.ts_connections[load_vessel].append((disch_vessel, color))
        self.refresh_ts_table()

    def refresh_ts_table(self):
        self.ts_table.setRowCount(0)
        self.ts_table.clearSpans()
        
        # Sorting Priority: Red (#ff0000) -> Green (#00ff00) -> Blue (#0088ff)
        def get_color_priority(color):
            nm = color.name().lower()
            if nm == "#ff0000": return 0
            if nm == "#00ff00": return 1
            if nm == "#0088ff": return 2
            return 3

        current_row = 0
        
        for load_vessel, disch_list in self.ts_connections.items():
            # Sort discharge vessels
            disch_list.sort(key=lambda x: get_color_priority(x[1]))
            
            count = len(disch_list)
            if count == 0: continue
            
            start_row = current_row
            
            # Add Rows
            for i in range(count):
                self.ts_table.insertRow(current_row + i)
                
            # Populate LOAD VESSEL (Merged)
            load_voy = get_display_voyage(load_vessel.data['선사항차'])
            load_display = f"{load_vessel.data['모선명']} ({load_voy})"
            
            load_item = QTableWidgetItem(load_display)
            load_item.setTextAlignment(Qt.AlignCenter)
            self.ts_table.setItem(start_row, 0, load_item)
            
            if count > 1:
                self.ts_table.setSpan(start_row, 0, count, 1)
                
            # Populate DISCH VESSELS
            for i, (disch_vessel, color) in enumerate(disch_list):
                r = start_row + i
                disch_voy = get_display_voyage(disch_vessel.data['선사항차'])
                disch_display = f"{disch_vessel.data['모선명']} ({disch_voy})"
                
                container = QWidget()
                layout = QHBoxLayout(container)
                layout.setContentsMargins(2, 2, 2, 2)
                lbl = QLabel(disch_display)
                lbl.setAlignment(Qt.AlignCenter)
                
                # Convert QColor to hex string
                color_hex = color.name()
                lbl.setStyleSheet(f"border: 2px solid {color_hex}; color: {color_hex}; font-weight: bold; background: #282a36; border-radius: 4px;")
                
                layout.addWidget(lbl)
                self.ts_table.setCellWidget(r, 1, container)
                
            current_row += count
            

            
        # Update Header Count
        total_disch = sum(len(v) for v in self.ts_connections.values())
        self.ts_table.setHorizontalHeaderItem(1, QTableWidgetItem(f"DISCH VESSEL ({total_disch})"))
        
        self.ts_table.scrollToBottom()

    def open_table_popup(self, title, source_table):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(600, 400)
        layout = QVBoxLayout(dialog)
        
        # Clone Table
        new_table = QTableWidget()
        new_table.setColumnCount(source_table.columnCount())
        new_table.setRowCount(source_table.rowCount())
        
        # Headers
        headers = []
        for c in range(source_table.columnCount()):
            item = source_table.horizontalHeaderItem(c)
            headers.append(item.text() if item else "")
        new_table.setHorizontalHeaderLabels(headers)
        new_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # Content
        for r in range(source_table.rowCount()):
            # Copy items
            for c in range(source_table.columnCount()):
                item = source_table.item(r, c)
                if item:
                    new_table.setItem(r, c, QTableWidgetItem(item))
            
            # Copy Cell Widgets (must be recreated)
            # This is tricky for cell widgets. We will just simplify for popup:
            # If it's a TS table, the Text is inside the label.
            # We'll just grab text if possible, or recreate basic widget.
            # For simplicity in this iteration: If cell widget exists (colored box), 
            # we try to extract text and color.
            w = source_table.cellWidget(r, 1) # Primarily Col 1 in TS Table has widgets. Also Col 2 in Master.
            if w:
                # TS Table Logic
                labels = w.findChildren(QLabel)
                if labels:
                    lbl = labels[0]
                    text = lbl.text()
                    style = lbl.styleSheet()
                    
                    container = QWidget()
                    l = QHBoxLayout(container); l.setContentsMargins(2,2,2,2)
                    new_lbl = QLabel(text)
                    new_lbl.setAlignment(Qt.AlignCenter)
                    new_lbl.setStyleSheet(style)
                    l.addWidget(new_lbl)
                    new_table.setCellWidget(r, 1, container)
                else: 
                     # Master Table Logic (direct QLabel)
                     if isinstance(w, QLabel):
                         text = w.text()
                         style = w.styleSheet()
                         new_lbl = QLabel(text)
                         new_lbl.setAlignment(Qt.AlignCenter)
                         new_lbl.setStyleSheet(style)
                         new_table.setCellWidget(r, 1, new_lbl) # Col 1? Master is Col 2/3
                     
            # Master Table Widgets are at Col 2, TS at Col 1.
            # Checking cellWidget at every cell is safe.
            for c in range(source_table.columnCount()):
                if c == 1 and w: continue # Handled above (assuming TS logic focus)
                w_cell = source_table.cellWidget(r, c)
                if w_cell and isinstance(w_cell, QLabel):
                         text = w_cell.text()
                         style = w_cell.styleSheet()
                         new_lbl = QLabel(text)
                         new_lbl.setAlignment(Qt.AlignCenter)
                         new_lbl.setStyleSheet(style)
                         new_table.setCellWidget(r, c, new_lbl)

        # Copy Spans (Row Merging)
        # We iterate specifically to find spans and apply them.
        # Assuming spans are mostly on Column 0 (Load Vessel) or others.
        for c in range(source_table.columnCount()):
            r = 0
            while r < source_table.rowCount():
                row_span = source_table.rowSpan(r, c)
                col_span = source_table.columnSpan(r, c)
                if row_span > 1 or col_span > 1:
                    new_table.setSpan(r, c, row_span, col_span)
                    r += row_span # Skip covered rows
                else:
                    r += 1

        # Style
        new_table.setStyleSheet(source_table.styleSheet())
        layout.addWidget(new_table)
        dialog.exec_()

    def reset_data(self):
        if not self.original_vessel_data: return
        self.clear_analysis_artifacts() # Clear visual effects
        self.current_view_mode = "NORMAL"
        self.highlight_btn.setChecked(False); self.highlight_btn.setStyleSheet("")
        self.highlight_btn.setText("✨ Highlight Mode\noff")
        self.connect_btn.setChecked(False); self.connect_btn.setStyleSheet("")
        self.connect_btn.setText("🔗 Connect Mode\noff")
        self.copy_btn.setChecked(False); self.copy_btn.setStyleSheet("")
        self.copy_btn.setText("📋 Vessel Copy\noff")
        
        # Reset ACTIVE port data
        port = self.ports[self.active_port_code]
        port.vessel_data_list = copy.deepcopy(port.original_vessel_data)
        
        # Update Refs
        self.vessel_data_list = port.vessel_data_list
        
        # Clear Logs
        port.master_log_data = []
        port.slave_log_data = []
        port.ts_connections = {}
        
        self.repopulate_logs()
        self.refresh_ts_table()
        
        self.update_table()
        self.draw_graphic()

    def paste_data(self, target_port_code=None):
        text = QApplication.clipboard().text()
        if not text.strip(): return
        
        # Target Port
        code = target_port_code if target_port_code else self.active_port_code
        port = self.ports[code]
        
        lines = text.strip().split('\n')
        if len(lines) < 2: return  # Need at least header + 1 data row
        
        # Parse header row
        header_row = lines[0].split('\t')
        
        # Get port-specific mapping
        port_map = self.port_header_maps.get(code, {})
        
        # Create reverse mapping: external_header -> internal_header(s)
        # For KRPUS (Busan), no mapping needed - use headers as-is
        if not port_map:
            # Standard Busan format
            new_list = []
            berths = set()
            
            for line in lines[1:]:
                row = line.split('\t')
                if len(row) < 12 or "번호" in line: continue
                
                d = {self.headers[i]: row[i] for i in range(min(len(self.headers), len(row)))}
                d['eta'] = parse_date(d.get('접안예정일시', ''))
                d['etd'] = parse_date(d.get('출항예정일시', ''))
                d['full_berth'] = f"{d.get('터미널', '')}-{d.get('선석', '')}"
                new_list.append(d)
                berths.add(d['full_berth'])
        else:
            # KRKAN/KRINC format - apply mapping
            new_list = []
            berths = set()
            
            for line in lines[1:]:
                row = line.split('\t')
                if len(row) < len(header_row) or "번호" in line: continue
                
                # Create dict with external headers
                external_data = {header_row[i]: row[i] for i in range(min(len(header_row), len(row)))}
                
                # Map to internal format
                d = {}
                
                # Apply mappings
                for ext_header, int_header in port_map.items():
                    if ext_header in external_data:
                        value = external_data[ext_header]
                        
                        # Handle multiple target fields (e.g., 모선항차 -> [모선항차, 항차년도, 선사항차])
                        if isinstance(int_header, list):
                            for target in int_header:
                                d[target] = value
                        else:
                            d[int_header] = value
                
                # Copy unmapped fields that match standard headers
                for header in self.headers:
                    if header not in d and header in external_data:
                        d[header] = external_data[header]
                
                # Set fixed values for KRKAN/KRINC
                if code in ['KRKAN', 'KRINC']:
                    d['터미널'] = 'GWCT'
                
                # Ensure required fields exist
                if '선석' not in d and '선석' in external_data:
                    d['선석'] = external_data['선석']
                if '선사' not in d and '선사' in external_data:
                    d['선사'] = external_data['선사']
                if '항로' not in d and '항로' in external_data:
                    d['항로'] = external_data['항로']
                
                # Fill missing standard fields with empty strings
                for header in self.headers:
                    if header not in d:
                        d[header] = ''
                
                # Parse dates
                d['eta'] = parse_date(d.get('접안예정일시', ''))
                d['etd'] = parse_date(d.get('출항예정일시', ''))
                d['full_berth'] = f"{d.get('터미널', '')}-{d.get('선석', '')}"
                
                new_list.append(d)
                berths.add(d['full_berth'])
            
        # Update SPECIFIC Port Data
        port.vessel_data_list = new_list
        port.terminal_list = sorted(list(berths))
        port.original_vessel_data = copy.deepcopy(new_list)
        
        # Reset Logs for that port
        port.master_log_data = []
        port.slave_log_data = []
        port.ts_connections = {}
        
        # If updating ACTIVE port, refresh UI
        if code == self.active_port_code:
            self.vessel_data_list = port.vessel_data_list
            self.original_vessel_data = port.original_vessel_data
            self.terminal_list = port.terminal_list
            self.ts_connections = port.ts_connections
            
            self.update_filters() 
            self.populate_mapping_tables() 
            
            # AUTO-LOAD MAPPING
            last_map = get_last_mapping_path()
            if last_map and os.path.exists(last_map):
                self.load_mappings(file_path=last_map)
                self.apply_mappings()
                
            # AUTO-LOAD MEMOS
            last_memo = get_last_memo_path()
            if last_memo and os.path.exists(last_memo):
                self.load_memos(file_path=last_memo)
            else:
                self.populate_memo_table()
            
            self.reset_btn.setEnabled(True)
            self.repopulate_logs()
            self.update_table()
            self.draw_graphic()
        else:
            print(f"Pasted data to {code} (Background)")

    def update_table(self):
        self.table.setRowCount(len(self.vessel_data_list))
        for r, d in enumerate(self.vessel_data_list):
            for c, h in enumerate(self.headers):
                self.table.setItem(r, c, QTableWidgetItem(str(d[h])))

    def draw_graphic(self):
        self.scene.clear()
        # Reset tracking variables as items are deleted
        self.current_time_text = None
        self.current_time_box = None
        self.current_time_line = None
        if not self.vessel_data_list: return
        
        min_eta = min(d['eta'] for d in self.vessel_data_list) - timedelta(days=2)
        max_etd = max(d['etd'] for d in self.vessel_data_list) + timedelta(days=2)
        min_eta = min_eta.replace(hour=0, minute=0, second=0)
        self.start_time = min_eta
        
        total_hours = int((max_etd - min_eta).total_seconds() / 3600)
        canvas_width = total_hours * self.pixels_per_hour
        canvas_height = len(self.terminal_list) * self.row_height
        
        # Terminals (Y-axis) -> Now Berths
        terminal_colors = {}
        # Vibrant colors for different terminals (Green, Orange, Blue, Purple, Teal)
        t_base_colors = ["#2e7d32", "#e65100", "#1565c0", "#6a1b9a", "#00695c"] 
        
        last_terminal = None
        for i, term in enumerate(self.terminal_list):
            y = i * self.row_height
            parts = term.split('-', 1)
            t_name = parts[0]
            
            if t_name not in terminal_colors:
                terminal_colors[t_name] = QColor(t_base_colors[len(terminal_colors) % len(t_base_colors)])
            

            
            # 2. Row Background (Simulation Area: 0 to canvas_width) - Subtle shade
            sim_bg_color = QColor(terminal_colors[t_name])
            sim_bg_color.setAlpha(30) # Very transparent for grid visibility
            sim_bg = self.scene.addRect(0, y, canvas_width, self.row_height, 
                                        QPen(Qt.NoPen), QBrush(sim_bg_color))
            sim_bg.setZValue(-11)
            
            # Split Terminal-Berth for better display
            pen_color = QColor("#414868")
            pen_width = 1
            
            if last_terminal is not None and t_name != last_terminal:
                # Terminal Boundary: Thicker and brighter
                pen_color = QColor("#7aa2f7")
                pen_width = 3
            elif i == 0:
                pen_width = 2
                
            self.scene.addLine(0, y, canvas_width, y, QPen(pen_color, pen_width))
            last_terminal = t_name
        
        # Final Bottom Line
        self.scene.addLine(0, canvas_height, canvas_width, canvas_height, QPen(QColor("#7aa2f7"), 3))

        # Time Grid (X-axis)
        day_width = 24 * self.pixels_per_hour
        for h in range(total_hours + 1):
            x = h * self.pixels_per_hour
            curr_time = min_eta + timedelta(hours=h)
            pen = QPen(QColor("#24283b"))
            is_header_safe = False
            
            if curr_time.hour == 0: # Day break (24h)
                pen.setWidth(3); pen.setColor(QColor("#7aa2f7"))
                is_header_safe = True
                
                # Weekend Highlight
                is_weekend = curr_time.weekday() in [5, 6] # Sat, Sun
                if is_weekend:
                    # Draw red column for the header
                    weekend_bg = self.scene.addRect(x, -70, day_width, 20, 
                                                   QPen(Qt.NoPen), QBrush(QColor("#f7768e")))
                    weekend_bg.setZValue(-5)
                
                # Date Label (Centered)
                date_str = curr_time.strftime("%m / %d (%a)")
                d_label = self.scene.addText(date_str, QFont("Segoe UI", 9, QFont.Bold))
                
                if is_weekend:
                    d_label.setDefaultTextColor(Qt.white)
                else:
                    d_label.setDefaultTextColor(QColor("#7aa2f7"))
                
                label_w = d_label.boundingRect().width()
                d_label.setPos(x + (day_width/2) - (label_w/2), -70)
            elif h % 12 == 0: # 12h
                pen.setWidth(2); pen.setColor(QColor("#444b6a"))
                is_header_safe = False 
            elif h % 2 == 0: # 2h
                pen.setStyle(Qt.SolidLine)
                pen.setColor(QColor("#24283b"))
            else: # 1h
                pen.setStyle(Qt.DotLine)
                pen.setColor(QColor("#1f2335"))

            # Grid line drawing
            self.scene.addLine(x, -60 if is_header_safe else 0, x, canvas_height, pen)
            
            # Specific Labels (6, 12, 18)
            if curr_time.hour in [6, 12, 18]:
                t_str = str(curr_time.hour) # Simplified to natural number
                t_label = self.scene.addText(t_str, QFont("Segoe UI", 8))
                t_label.setDefaultTextColor(QColor("#565f89"))
                # Center text horizontally on the grid line
                label_w = t_label.boundingRect().width()
                t_label.setPos(x - (label_w / 2), -30)

        # Vessels
        self.vessel_items = []
        # Vessels
        self.vessel_items = []
        for d in self.vessel_data_list:
            # FILTER CHECK (Hierarchical)
            if (d.get('선사'), d.get('항로')) not in self.allowed_pairs: continue
            
            term_idx = self.terminal_list.index(d['full_berth'])
            y = term_idx * self.row_height + 10
            x_start = (d['eta'] - min_eta).total_seconds() / 3600 * self.pixels_per_hour
            width = (d['etd'] - d['eta']).total_seconds() / 3600 * self.pixels_per_hour
            
            item = VesselItem(d, x_start, y, width, self.row_height - 20, self.get_color(d['선사']))
            
            # MEMO CHECK
            memo_key = f"{d['모선명']}|{d['선사항차']}"
            if memo_key in self.memo_data:
                item.has_memo = True
                
            self.scene.addItem(item)
            self.vessel_items.append(item)

        # Current Time Display
        self.update_current_time_display()


    def update_current_time_display(self):
        """Update current time display and vertical line position"""
        from datetime import datetime
        
        # Remove old components if they exist
        if self.current_time_text:
            self.scene.removeItem(self.current_time_text)
        if self.current_time_box:
            self.scene.removeItem(self.current_time_box)
        if self.current_time_line:
            self.scene.removeItem(self.current_time_line)
        
        # Get current time
        now = datetime.now()
        
        # 1. Calculate X Position first
        line_x = 0
        if hasattr(self, 'start_time') and self.start_time:
            time_diff = (now - self.start_time).total_seconds() / 3600  # hours
            line_x = time_diff * self.pixels_per_hour
        
        # 2. Format Time Text
        time_str = now.strftime("%Y/%b/%d %H:%M:%S").upper()
        
        # Create text item
        self.current_time_text = QGraphicsTextItem(time_str)
        self.current_time_text.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.current_time_text.setDefaultTextColor(QColor("#50fa7b"))  # Bright green
        self.current_time_text.setZValue(1000)
        
        # 3. Position Text relative to Line
        text_rect = self.current_time_text.boundingRect()
        # Center text horizontally on the line
        text_x = line_x - (text_rect.width() / 2)
        text_y = -120  # Above the date headers
        self.current_time_text.setPos(text_x, text_y)
        
        # 4. Create Box around Text
        padding = 8
        self.current_time_box = QGraphicsRectItem(
            text_x - padding,
            text_y - padding,
            text_rect.width() + padding * 2,
            text_rect.height() + padding * 2
        )
        self.current_time_box.setPen(QPen(QColor("#50fa7b"), 2))
        self.current_time_box.setBrush(QBrush(QColor(30, 30, 30, 200)))
        self.current_time_box.setZValue(999)
        
        # 5. Draw Vertical Line
        if hasattr(self, 'terminal_list') and self.terminal_list:
            # Line starts right below the box
            line_start_y = text_y + text_rect.height() + padding
            line_end_y = len(self.terminal_list) * self.row_height + 20
            
            self.current_time_line = QGraphicsLineItem(line_x, line_start_y, line_x, line_end_y)
            self.current_time_line.setPen(QPen(QColor("#50fa7b"), 2))
            self.current_time_line.setZValue(500)
            self.scene.addItem(self.current_time_line)
            
        # 6. Highlight Vessels currently in port (where line_x is inside vessel rect)
        if hasattr(self, 'vessel_items') and self.vessel_items:
            for v_item in self.vessel_items:
                # Check if current time is between ETA and ETD
                if v_item.data['eta'] <= now <= v_item.data['etd']:
                    if not v_item.is_in_port:
                        v_item.is_in_port = True
                        v_item.update()
                else:
                    if v_item.is_in_port:
                        v_item.is_in_port = False
                        v_item.update()
        
        # Add to scene
        self.scene.addItem(self.current_time_box)
        self.scene.addItem(self.current_time_text)

    def update_ticker_content(self):
        """Gather and format data for the scrolling news ticker with colored segments"""
        now = datetime.now()
        segments = [] # List of (text, color)
        
        # 1. Off-work countdown (6 PM) and Weekend info - Bright Pink (#ff69b4)
        pink_color = QColor("#ff69b4")
        green_color = QColor("#50fa7b")
        
        # Off-work countdown
        off_work_time = now.replace(hour=18, minute=0, second=0, microsecond=0)
        if now < off_work_time:
            diff = off_work_time - now
            h = diff.seconds // 3600
            m = (diff.seconds % 3600) // 60
            s = diff.seconds % 60
            segments.append((f"⏰ 퇴근까지 남은 시간: {h:02d}:{m:02d}:{s:02d}", pink_color))
        else:
            segments.append(("🎉 퇴근 시간이 지났습니다! 고생하셨습니다!", pink_color))
            
        # Weekend info (Days until Saturday)
        # Weekday: Mon=0, ..., Fri=4, Sat=5, Sun=6
        current_weekday = now.weekday()
        if current_weekday < 5: # Mon-Fri
            days_to_weekend = 5 - current_weekday
            segments.append((f"📅 주말까지 {days_to_weekend}일 남았습니다!", pink_color))
        elif current_weekday == 5:
            segments.append(("💃 오늘은 즐거운 토요일입니다!", pink_color))
        else:
            segments.append(("🛌 오늘은 편안한 일요일입니다!", pink_color))

        # 2. In-Port Vessels (Red Outline) - Bright Green (#50fa7b)
        connected_vessels = []
        if hasattr(self, 'vessel_items') and self.vessel_items:
            for v in self.vessel_items:
                if v.is_in_port:
                    remaining = v.data['etd'] - now
                    hours = remaining.total_seconds() / 3600
                    if hours < 0: hours = 0 
                    v_name = v.data.get('모선명', 'Unknown')
                    connected_vessels.append(f"🚢 [{v_name}] IN PORT - {hours:.1f}H Left")
        
        if connected_vessels:
            segments.append((" | ".join(connected_vessels), green_color))
            
        # 3. Memos - Bright Green (#50fa7b)
        memo_messages = []
        for key, text in self.memo_data.items():
            if text.strip():
                v_name = key.split('|')[0] if '|' in key else key
                memo_messages.append(f"📝 {v_name}: {text}")
        
        if memo_messages:
            segments.append((" | ".join(memo_messages), green_color))
            
        if not segments:
            segments.append(("WELCOME TO BERTH SIMULATION MONITOR ... NO ACTIVE EVENTS ...", green_color))
            
        self.ticker.set_text_segments(segments)

    def get_original_data(self, current_data):
        key_name = current_data['모선명']
        key_voy = current_data['선사항차']
        
        # Search in original_vessel_data
        for orig in self.original_vessel_data:
            if orig['모선명'] == key_name and orig['선사항차'] == key_voy:
                return orig
        return None

    def update_log_entry(self, log_list, entry_key, new_entry):
        # Entry Key: Unique Key (e.g. "VesselName|Voyage")
        
        # Add key to new_entry if provided (helper)
        if new_entry:
             new_entry['log_key'] = entry_key
        
        # Extract vessel name and voyage from the key for backward compatibility
        # entry_key format: "Name|Voyage"
        if '|' in entry_key:
            vessel_name, vessel_voyage = entry_key.split('|', 1)
            # Construct the display text that would appear in legacy entries
            # Format: "Name (DisplayVoyage)"
            vessel_display = f"{vessel_name} ({get_display_voyage(vessel_voyage)})"
        else:
            vessel_display = entry_key
        
        # Strategy: Find ALL indices with this key (to handle legacy dupes)
        indices = []
        for i, log in enumerate(log_list):
            # Match using multiple criteria:
            # 1. New style: log_key field
            # 2. Old style master: vessel_text field
            # 3. Old style slave: name field
            if (log.get('log_key') == entry_key or 
                log.get('vessel_text') == vessel_display or 
                log.get('name') == vessel_display):
                indices.append(i)
        
        # Determine insertion point (first found index or end)
        insert_idx = indices[0] if indices else len(log_list)
        
        # Remove ALL existing entries for this key (reverse order to keep indices valid)
        for i in sorted(indices, reverse=True):
            log_list.pop(i)
            
        # Re-Insert if new_entry exists
        if new_entry:
            # Check range
            if insert_idx > len(log_list): insert_idx = len(log_list)
            log_list.insert(insert_idx, new_entry)

    def handle_vessel_move(self, master_item):
        new_y = master_item.pos().y()
        term_idx = max(0, min(round(new_y / self.row_height), len(self.terminal_list) - 1))
        snapped_y = term_idx * self.row_height + 10
        
        new_x = master_item.pos().x()
        hours_from_start = round(new_x / self.pixels_per_hour)
        snapped_x = hours_from_start * self.pixels_per_hour
        
        master_item.setPos(snapped_x, snapped_y)
        
        # Snap Width as well
        current_width = master_item.rect().width()
        duration_hours = max(1, round(current_width / self.pixels_per_hour)) # Min 1 hour
        snapped_width = duration_hours * self.pixels_per_hour
        master_item.setRect(0, 0, snapped_width, master_item.rect().height())
        master_item.update_time_labels()
        
        old_eta = master_item.data['eta']
        old_term = master_item.data['full_berth']
        
        new_eta = self.start_time + timedelta(hours=hours_from_start)
        new_term = self.terminal_list[term_idx]
        
        # Calculate new etd based on width
        new_duration = timedelta(hours=duration_hours)
        new_etd = new_eta + new_duration
        
        # Update Data
        master_item.data['eta'] = new_eta
        master_item.data['etd'] = new_etd
        master_item.data['full_berth'] = new_term
        # Split back to terminal and berth if needed for table
        parts = new_term.split('-', 1)
        master_item.data['터미널'] = parts[0]
        master_item.data['선석'] = parts[1] if len(parts) > 1 else ""
        
        master_item.data['접안예정일시'] = format_date(new_eta)
        master_item.data['출항예정일시'] = format_date(new_etd)
        
        master_item.update_time_labels()

        # Update Change Sidebar TABLE (MASTER)
        # 1. Get Original Data
        orig_data = self.get_original_data(master_item.data)
        
        if orig_data:
            # 2. Compare Current vs Original
            orig_term = orig_data['full_berth']
            orig_eta = orig_data['eta']
            
            curr_term = master_item.data['full_berth']
            curr_eta = master_item.data['eta']
            
            # Check for ANY change
            if orig_term != curr_term or orig_eta != curr_eta:
                # Construct Log Entry
                # Use strict key for identification
                log_key = f"{master_item.data['모선명']}|{master_item.data['선사항차']}"
                vessel_display = master_item.data['모선명'] + " (" + get_display_voyage(master_item.data['선사항차']) + ")"
                
                vessel_widget_text = None
                vessel_widget_style = None
                
                if hasattr(master_item, 'copy_label'):
                    if master_item.copy_label == "1st":
                         vessel_widget_text = vessel_display + " 1ST"
                         vessel_widget_style = "border: 2px solid #ff0000; color: #ffffff; font-weight: bold; background: #ff0000; border-radius: 4px;"
                    elif master_item.copy_label == "2nd":
                         vessel_widget_text = vessel_display + " 2ND"
                         vessel_widget_style = "border: 2px solid #0088ff; color: #ffffff; font-weight: bold; background: #0088ff; border-radius: 4px;"
                
                orig_str = f"{orig_term.replace('-', '(') + ')'} {format_short_dt(orig_eta)}"
                curr_str = f"{curr_term.replace('-', '(') + ')'} {format_short_dt(curr_eta)}"
                
                to_widget_text = None
                to_widget_style = None
                
                old_t_name = orig_term.split('-')[0]
                new_t_name = curr_term.split('-')[0]
                
                color_code = None
                if old_t_name != new_t_name:
                    color_code = "#ff5555" # Red (Process Change)
                elif orig_term != curr_term:
                    color_code = "#50fa7b" # Green (Berth Change)
                
                # Check Time Change
                delta = curr_eta - orig_eta
                delta_str = format_time_delta(delta)
                shift_color = None
                
                if delta.total_seconds() != 0:
                    shift_color = "#ffb86c" # Orange (Time Change)
                
                # Highlight logic for TO column if terminal changed
                if color_code:
                    to_widget_text = curr_str
                    to_widget_style = f"border: 2px solid {color_code}; color: {color_code}; font-weight: bold; background: #282a36;"
                
                entry = {
                    'vessel_text': vessel_display,
                    'vessel_widget_text': vessel_widget_text,
                    'vessel_widget_style': vessel_widget_style,
                    'from': orig_str,
                    'to_text': curr_str,
                    'to_widget_text': to_widget_text,
                    'to_widget_style': to_widget_style,
                    'shift_text': delta_str,
                    'shift_color': shift_color
                }
                
                
                # Update Log List (Unique by Key)
                self.update_log_entry(self.ports[self.active_port_code].master_log_data, log_key, entry)
            else:
                # No difference from Original -> Remove if exists
                log_key = f"{master_item.data['모선명']}|{master_item.data['선사항차']}"
                self.update_log_entry(self.ports[self.active_port_code].master_log_data, log_key, None)
                
            # Repopulate Table
            self.repopulate_logs()
        
        # Check if this is the first move after copy
        if hasattr(master_item, 'is_just_copied') and master_item.is_just_copied:
             if hasattr(master_item, 'has_moved_during_drag') and master_item.has_moved_during_drag:
                 master_item.is_just_copied = False
                 print("DEBUG: Flag consumed (moved).")
             else:
                 print("DEBUG: Flag KEPT (not moved).")
        else:
             self.resolve_collisions(master_item)
             
        self.update_table()

    def resolve_collisions(self, master_item):
        slave_changes = []
        terminal_vessels = [v for v in self.vessel_items if v.data['full_berth'] == master_item.data['full_berth']]
        terminal_vessels.sort(key=lambda x: x.data['eta'])
        
        # Capture Initial State for Slave Logging
        initial_state = {}
        for v in terminal_vessels:
            if v == master_item: continue
            initial_state[v] = v.data['eta']
            
        changed = True
        loop = 0
        
        while changed and loop < 50:
            changed = False; loop += 1
            for i in range(len(terminal_vessels) - 1):
                v1, v2 = terminal_vessels[i], terminal_vessels[i+1]
                safe_eta = v1.data['etd'] + timedelta(hours=self.safety_gap_h)
                if v2.data['eta'] < safe_eta:
                    delta = safe_eta - v2.data['eta']
                    # old_eta = v2.data['eta'] # No longer needed for logging inside loop
                    v2.data['eta'] += delta
                    v2.data['etd'] += delta
                    v2.data['접안예정일시'] = format_date(v2.data['eta'])
                    v2.data['출항예정일시'] = format_date(v2.data['etd'])
                    v2.setPos((v2.data['eta'] - self.start_time).total_seconds()/3600 * self.pixels_per_hour, v2.pos().y())
                    v2.update_time_labels()
                    
                    changed = True

        # Generate Logs based on Total Shift (Original vs Current) - SLAVE
        # Compare against ORIGINAL data for cumulative log
        
        current_slave_logs = self.ports[self.active_port_code].slave_log_data
        
        for v in terminal_vessels:
            if v == master_item: continue # Skip Master (logged separately)
            
            orig = self.get_original_data(v.data)
            if not orig: continue
            
            total_delta = v.data['eta'] - orig['eta']
            
            log_key = f"{v.data['모선명']}|{v.data['선사항차']}"
            v_name = v.data['모선명'] + " (" + get_display_voyage(v.data['선사항차']) + ")"
            
            # If changed significantly (> 1 hr)
            entry = None
            if abs(total_delta.total_seconds()) >= 3600:
                entry = {
                     'vessel': v,
                     'name': v_name,
                     'old_eta': format_short_dt(orig['eta']),
                     'new_eta': format_short_dt(v.data['eta']),
                     'delta': total_delta,
                     'delta_str': format_time_delta(total_delta)
                }
            
            
            # Update Log (Unique by log_key)
            self.update_log_entry(current_slave_logs, log_key, entry)

        # Repopulate Logs (Both Master and Slave might have updated)
        # Repopulate Logs (Both Master and Slave might have updated)
        self.repopulate_logs()
        self.slave_table.scrollToBottom()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BerthMonitor()
    window.showFullScreen()
    sys.exit(app.exec_())
