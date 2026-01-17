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
                             QFileDialog, QHeaderView)
from PyQt5.QtGui import QColor, QFont, QBrush, QPen, QPainter, QWheelEvent, QPolygonF, QPainterPath
from PyQt5.QtCore import Qt, QRectF, pyqtSignal, QObject, QTimer, QLineF, QPointF
import math


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
        
        # Highlight Mode
        self.is_highlighted = False
        self.neon_timer = QTimer()
        self.neon_timer.timeout.connect(self.update_neon)
        self.neon_hue = 0
        
        # Connect Mode
        self.temp_line = None
        
        # Flag for deferred shifting
        self.is_just_copied = False
        self.has_moved_during_drag = False  # Track if moved during current press sequence
        
        # MEMO & Heart Icon
        self.has_memo = False
        self.heart_rotation = 0
        
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
            super().mouseMoveEvent(event)

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
            # Update connection line if it exists
            if self.connection_line:
                self.connection_line.update_line()
        return super().itemChange(change, value)

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
        
        self.vessel_data_list = []
        self.original_vessel_data = [] # For Reset feature
        self.terminal_list = []
        self.pixels_per_hour = 5  
        self.row_height = 70      
        self.safety_gap_h = 2
        
        self.line_colors = {}
        self.base_colors = [
            "#ffadad", "#ffd6a5", "#fdffb6", "#caffbf", 
            "#9bf6ff", "#a0c4ff", "#bdb2ff", "#ffc6ff"
        ]
        
        self.ts_connections = {} # Key: LoadVesselItem, Value: List of (DischVesselItem, Color)
        
        # Filtering
        self.allowed_pairs = set() # Set of (line, route) tuples
        self.filter_widgets = {} # Map 'Line' -> (LineCheckBox, List of RouteCheckBoxes)
        
        # Memo Data
        self.memo_data = {} # Key: "VesselName|Voyage", Value: "Memo Content"
        self.is_memo_mode = False
        
        # Animation Timer (Heart Spin & Rainbow)
        self.heart_angle = 0
        self.rainbow_hue = 0
        self.anim_timer = QTimer()
        self.anim_timer.timeout.connect(self.update_animation)
        self.anim_timer.start(50) # 20fps
        
        self.initUI()
        self.apply_styles()
        self.current_view_mode = "NORMAL" # NORMAL, HIGHLIGHT, CONNECT

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
        self.btn_memo = QPushButton("❤ MEMO")
        self.btn_memo.setFixedSize(160, 45)
        self.btn_memo.setCheckable(True)
        self.btn_memo.clicked.connect(self.toggle_memo_mode)
        header_layout.addWidget(self.btn_memo)

        self.copy_btn = QPushButton("📋 Vessel Copy")
        self.copy_btn.setFixedSize(160, 45)
        self.copy_btn.setCheckable(True)
        self.copy_btn.clicked.connect(self.toggle_copy_mode)
        header_layout.addWidget(self.copy_btn)
        
        self.highlight_btn = QPushButton("✨ Highlight Mode")
        self.highlight_btn.setFixedSize(160, 45)
        self.highlight_btn.setCheckable(True)
        self.highlight_btn.clicked.connect(self.toggle_highlight_mode)
        header_layout.addWidget(self.highlight_btn)

        self.connect_btn = QPushButton("🔗 Connect Mode")
        self.connect_btn.setFixedSize(160, 45)
        self.connect_btn.setCheckable(True)
        self.connect_btn.clicked.connect(self.toggle_connect_mode)
        header_layout.addWidget(self.connect_btn)

        self.reset_btn = QPushButton("🔄 Reset to Original")
        self.reset_btn.setFixedSize(180, 45)
        self.reset_btn.clicked.connect(self.reset_data)
        self.reset_btn.setEnabled(False)
        header_layout.addWidget(self.reset_btn)

        self.paste_btn = QPushButton("📋 Paste & Parse Data")
        self.paste_btn.setFixedSize(220, 45)
        self.paste_btn.clicked.connect(self.paste_data)
        header_layout.addWidget(self.paste_btn)
        main_layout.addLayout(header_layout)
        
        self.splitter = QSplitter(Qt.Vertical)
        
        # Upper area: Graphic View + Sidebar with Horizontal Splitter
        self.upper_splitter = QSplitter(Qt.Horizontal)
        
        self.scene = QGraphicsScene()
        self.scene.parent_view = self
        self.gv = ZoomableGraphicsView(self.scene)
        self.upper_splitter.addWidget(self.gv)
        
        self.sidebar = QWidget()
        self.sidebar.setMinimumWidth(380) # Increased width for tabs
        self.sidebar.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(self.sidebar)
        
        # --- TAB WIDGET ---
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #414868; background: #1f2335; }
            QTabBar::tab { background: #1a1b26; color: #a9b1d6; padding: 8px 12px; border: 1px solid #414868; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; }
        # --- TAB 3: MAPPING ---
        self.create_mapping_tab()
        
        # --- TAB 4: MEMO ---
        self.create_memo_tab()
        
        # Add Tabs to Sidebar
        self.tabs.addTab(self.tab_logs, "LOGS")
        self.tabs.addTab(self.tab_filters, "FILTERS")
        self.tabs.addTab(self.tab_mapping, "MAPPING")
        self.tabs.addTab(self.tab_memo, "MEMO")
        
        sidebar_layout.addWidget(self.tabs)
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
        slave_header.addWidget(QLabel("<br><b>[ SLAVE CHANGES LOG ]</b>"))
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

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow, QWidget#centralWidget { background-color: #1a1b26; }
            QWidget { color: #a9b1d6; font-family: 'Segoe UI', sans-serif; }
            #titleLabel { font-size: 20px; font-weight: bold; color: #7aa2f7; margin: 10px; }
            QPushButton { background-color: #7aa2f7; color: #1a1b26; border-radius: 8px; font-weight: bold; font-size: 14px; }
            QPushButton:hover { background-color: #89ddff; }
            QPushButton:disabled { background-color: #414868; color: #565f89; }
            QGraphicsView { background-color: #16161e; border: 1px solid #24283b; border-radius: 10px; }
            QTableWidget { background-color: #24283b; gridline-color: #414868; color: #c0caf5; border: none; }
            QHeaderView::section { background-color: #1f2335; color: #7aa2f7; padding: 8px; border: 1px solid #414868; font-weight: bold; font-size: 11px; }
            QTableCornerButton::section { background-color: #1f2335; border: 1px solid #414868; }
            QScrollBar:vertical { border: none; background: #16161e; width: 14px; margin: 0px 0px 0px 0px; }
            QScrollBar::handle:vertical { background: #414868; min-height: 30px; border-radius: 7px; }
            QScrollBar::handle:vertical:hover { background: #565f89; }
            QScrollBar::sub-line:vertical { border: none; background: none; height: 0px; }
            QScrollBar::add-line:vertical { border: none; background: none; height: 0px; }
            QScrollBar:horizontal { border: none; background: #16161e; height: 14px; margin: 0px 0px 0px 0px; }
            QScrollBar::handle:horizontal { background: #414868; min-width: 30px; border-radius: 7px; }
            QScrollBar::handle:horizontal:hover { background: #565f89; }
            QScrollBar::sub-line:horizontal { border: none; background: none; width: 0px; }
            QScrollBar::add-line:horizontal { border: none; background: none; width: 0px; }
            #sidebar { background-color: #1f2335; border-left: 2px solid #24283b; padding: 5px; }
            QDialog { background-color: #1a1b26; }
            QCheckBox { spacing: 5px; color: #a9b1d6; }
            QCheckBox::indicator { width: 18px; height: 18px; border-radius: 3px; border: 1px solid #565f89; background: #16161e; }
            QCheckBox::indicator:checked { background: #7aa2f7; border: 1px solid #7aa2f7; image: url(:/qt-project.org/styles/commonstyle/images/standardbutton-apply-16.png); }
            QGroupBox { border: 1px solid #414868; border-radius: 5px; margin-top: 20px; font-weight: bold; color: #7aa2f7; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)

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
        def create_map_table(title):
            lbl = QLabel(title)
            lbl.setStyleSheet("font-weight: bold; color: #7aa2f7; margin-top: 10px;")
            layout.addWidget(lbl)
            
            table = QTableWidget()
            table.setColumnCount(2)
            table.setHorizontalHeaderLabels(["Original", "New"])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            layout.addWidget(table)
            return table

        self.map_line_table = create_map_table("Line Mapping")
        self.map_route_table = create_map_table("Route Mapping")
        
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
        
        # Preserving existing "New" values if reloading same data? 
        # For simplicity, we just rebuild. User can Save/Load JSON for persistence.
        
        def fill_table(table, items):
            table.setRowCount(len(items))
            for r, item in enumerate(items):
                # Col 0: Original (Read-onlyish)
                item_orig = QTableWidgetItem(item)
                item_orig.setFlags(item_orig.flags() ^ Qt.ItemIsEditable) # Make Read-only
                table.setItem(r, 0, item_orig)
                
                # Col 1: New (Editable, default empty)
                table.setItem(r, 1, QTableWidgetItem(""))
                
        fill_table(self.map_line_table, unique_lines)
        fill_table(self.map_route_table, unique_routes)

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
        self.populate_mapping_tables()
        
    def save_mappings(self):
        data = {
            'lines': {},
            'routes': {}
        }
        
        for r in range(self.map_line_table.rowCount()):
            orig = self.map_line_table.item(r, 0).text()
            new = self.map_line_table.item(r, 1).text().strip()
            if new: data['lines'][orig] = new
            
        for r in range(self.map_route_table.rowCount()):
            orig = self.map_route_table.item(r, 0).text()
            new = self.map_route_table.item(r, 1).text().strip()
            if new: data['routes'][orig] = new
            
        filename, _ = QFileDialog.getSaveFileName(self, "Save Mapping", "", "JSON Files (*.json)")
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f"Error saving: {e}")

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
            
            def match_table(table, map_data):
                for r in range(table.rowCount()):
                    orig = table.item(r, 0).text()
                    if orig in map_data:
                        table.setItem(r, 1, QTableWidgetItem(map_data[orig]))
            
            match_table(self.map_line_table, loaded_lines)
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
        
        # User requested 2x row height to show 2 lines
        self.memo_table.verticalHeader().setDefaultSectionSize(50) 
        
        self.memo_table.cellChanged.connect(self.on_memo_changed)
        layout.addWidget(self.memo_table)

    def toggle_memo_mode(self):
        self.is_memo_mode = self.btn_memo.isChecked()
        if self.is_memo_mode:
            # Turn off Copy Mode if on
            if self.copy_btn.isChecked():
                self.copy_btn.setChecked(False)
                self.toggle_copy_mode()
            self.tabs.setCurrentWidget(self.tab_memo)

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
        filename, _ = QFileDialog.getSaveFileName(self, "Save Memos", "", "JSON Files (*.json)")
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(self.memo_data, f, indent=4, ensure_ascii=False)
                save_last_memo_path(filename)
            except Exception as e:
                print(f"Error saving memos: {e}")

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
        if line not in self.line_colors:
            idx = len(self.line_colors) % len(self.base_colors)
            self.line_colors[line] = QColor(self.base_colors[idx])
        return self.line_colors[line]

    def toggle_copy_mode(self):
        if self.copy_btn.isChecked():
            self.current_view_mode = "COPY"
            self.highlight_btn.setChecked(False)
            self.connect_btn.setChecked(False)
            self.copy_btn.setStyleSheet("background-color: #8be9fd; color: black;")
        else:
            self.current_view_mode = "NORMAL"
            self.copy_btn.setStyleSheet("")

    def toggle_highlight_mode(self):
        if self.highlight_btn.isChecked():
            self.current_view_mode = "HIGHLIGHT"
            self.copy_btn.setChecked(False)
            self.connect_btn.setChecked(False)
            self.highlight_btn.setStyleSheet("background-color: #ff9cf9; color: black;")
        else:
            self.current_view_mode = "NORMAL"
            self.highlight_btn.setStyleSheet("")
            self.clear_analysis_artifacts()
 
    def toggle_connect_mode(self):
        if self.connect_btn.isChecked():
            self.current_view_mode = "CONNECT"
            self.copy_btn.setChecked(False)
            self.highlight_btn.setChecked(False)
            self.connect_btn.setStyleSheet("background-color: #f1fa8c; color: black;")
        else:
            self.current_view_mode = "NORMAL"
            self.connect_btn.setStyleSheet("")
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
        self.connect_btn.setChecked(False); self.connect_btn.setStyleSheet("")
        
        self.vessel_data_list = copy.deepcopy(self.original_vessel_data)
        self.master_table.setRowCount(0)
        self.slave_table.setRowCount(0)
        self.ts_table.setRowCount(0)
        self.update_table()
        self.draw_graphic()

    def paste_data(self):
        text = QApplication.clipboard().text()
        if not text.strip(): return
        
        lines = text.strip().split('\n')
        self.vessel_data_list = []
        berths = set()
        
        for line in lines:
            row = line.split('\t')
            if len(row) < 12 or "번호" in line: continue
            
            d = {self.headers[i]: row[i] for i in range(len(self.headers))}
            d['eta'] = parse_date(d['접안예정일시'])
            d['etd'] = parse_date(d['출항예정일시'])
            # Create a combined Terminal-Berth key
            d['full_berth'] = f"{d['터미널']}-{d['선석']}"
            self.vessel_data_list.append(d)
            berths.add(d['full_berth'])
            
        self.terminal_list = sorted(list(berths))
        self.original_vessel_data = copy.deepcopy(self.vessel_data_list)
        
        self.update_filters() # NEW: Populate Filters
        self.populate_mapping_tables() # NEW: Populate Mapping
        
        # AUTO-LOAD MAPPING
        last_map = get_last_mapping_path()
        if last_map and os.path.exists(last_map):
            print(f"Auto-loading mapping from: {last_map}")
            self.load_mappings(file_path=last_map)
            self.apply_mappings()
            
        # AUTO-LOAD MEMOS
        last_memo = get_last_memo_path()
        if last_memo and os.path.exists(last_memo):
            print(f"Auto-loading memos from: {last_memo}")
            self.load_memos(file_path=last_memo)
        else:
            # Just populate table empty
            self.populate_memo_table()
        
        self.reset_btn.setEnabled(True)
        self.update_table()
        self.draw_graphic()

    def update_table(self):
        self.table.setRowCount(len(self.vessel_data_list))
        for r, d in enumerate(self.vessel_data_list):
            for c, h in enumerate(self.headers):
                self.table.setItem(r, c, QTableWidgetItem(str(d[h])))

    def draw_graphic(self):
        self.scene.clear()
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

        # Update Change Sidebar TABLE
        # Skip logging if FROM and TO are the same
        if old_term == new_term and old_eta == new_eta:
            # No actual change, skip logging
            pass
        else:
            row = self.master_table.rowCount()
            self.master_table.insertRow(row)
            vessel_display = master_item.data['모선명'] + " (" + get_display_voyage(master_item.data['선사항차']) + ")"
            
            # Column 0: Vessel
            # Column 0: Vessel
            if master_item.copy_label == "1st":
                 vessel_display += " 1ST"
                 lbl = QLabel(vessel_display)
                 lbl.setAlignment(Qt.AlignCenter)
                 lbl.setStyleSheet("border: 2px solid #ff0000; color: #ffffff; font-weight: bold; background: #ff0000; border-radius: 4px;")
                 self.master_table.setCellWidget(row, 0, lbl)
            elif master_item.copy_label == "2nd":
                 vessel_display += " 2ND"
                 lbl = QLabel(vessel_display)
                 lbl.setAlignment(Qt.AlignCenter)
                 lbl.setStyleSheet("border: 2px solid #0088ff; color: #ffffff; font-weight: bold; background: #0088ff; border-radius: 4px;")
                 self.master_table.setCellWidget(row, 0, lbl)
            else:
                 self.master_table.setItem(row, 0, QTableWidgetItem(vessel_display))
            
            # Column 1: FROM {Berth} {Time}
            old_str = f"{old_term.replace('-', '(') + ')'} {format_short_dt(old_eta)}"
            self.master_table.setItem(row, 1, QTableWidgetItem(old_str))
            
            # Column 2: TO {Berth} {Time}
            new_str = f"{new_term.replace('-', '(') + ')'} {format_short_dt(new_eta)}"
            
            # Highlighting Logic
            old_t_name = old_term.split('-')[0]
            new_t_name = new_term.split('-')[0]
            
            color_code = None
            if old_t_name != new_t_name:
                # Terminal changed: Red highlighting
                color_code = "#ff5555" # Bright Red
            elif old_term != new_term:
                # Same terminal, different berth: Green highlighting
                color_code = "#50fa7b" # Bright Green
                
            if color_code:
                lbl = QLabel(new_str)
                lbl.setAlignment(Qt.AlignCenter)
                lbl.setStyleSheet(f"border: 2px solid {color_code}; color: {color_code}; font-weight: bold; background: #282a36;")
                self.master_table.setCellWidget(row, 2, lbl)
            else:
                self.master_table.setItem(row, 2, QTableWidgetItem(new_str))

            # Column 3: Shift
            delta = new_eta - old_eta
            delta_str = format_time_delta(delta)
            delta_item = QTableWidgetItem(delta_str)
            delta_item.setTextAlignment(Qt.AlignCenter)
            if delta.total_seconds() != 0:
                delta_item.setForeground(QColor("#ffb86c")) # Orange for shift
            self.master_table.setItem(row, 3, delta_item)

            self.master_table.scrollToBottom()
        
            self.master_table.scrollToBottom()
        
        # Check if this is the first move after copy
        # Check if this is the first move after copy
        if hasattr(master_item, 'is_just_copied') and master_item.is_just_copied:
            print(f"DEBUG: Skipping collision resolution for {master_item.data.get('모선명')}. is_just_copied=True")
            # Only reset flag if actually dragged (prevent click-consumption)
            if hasattr(master_item, 'has_moved_during_drag') and master_item.has_moved_during_drag:
                master_item.is_just_copied = False
                print("DEBUG: Flag consumed (moved).")
            else:
                print("DEBUG: Flag KEPT (not moved).")
        else:
            # print(f"DEBUG: Resolving collisions for {master_item.data.get('모선명')}. is_just_copied={getattr(master_item, 'is_just_copied', 'MISSING')}")
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

        # Generate Logs based on Total Shift
        pending_logs = []
        for v, old_eta in initial_state.items():
            new_eta = v.data['eta']
            total_delta = new_eta - old_eta
            
            # Only log if shift is at least 1 hour (3600 seconds)
            if abs(total_delta.total_seconds()) >= 3600:
                pending_logs.append({
                     'vessel': v,
                     'name': v.data['모선명'] + " (" + get_display_voyage(v.data['선사항차']) + ")",
                     'old_eta_str': format_short_dt(old_eta),
                     'new_eta_str': format_short_dt(new_eta),
                     'delta': total_delta,
                     'delta_str': format_time_delta(total_delta)
                 })

        # Sort logs by Shift (Descending)
        pending_logs.sort(key=lambda x: abs(x['delta'].total_seconds()), reverse=True)
        
        # Add to Table
        for log in pending_logs:
            row = self.slave_table.rowCount()
            self.slave_table.insertRow(row)
            self.slave_table.setItem(row, 0, QTableWidgetItem(log['name']))
            self.slave_table.setItem(row, 1, QTableWidgetItem(log['old_eta_str']))
            self.slave_table.setItem(row, 2, QTableWidgetItem(log['new_eta_str']))
            
            delta_item = QTableWidgetItem(log['delta_str'])
            delta_item.setTextAlignment(Qt.AlignCenter)
            delta_item.setForeground(QColor("#ffb86c"))
            self.slave_table.setItem(row, 3, delta_item)
            
        self.slave_table.scrollToBottom()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BerthMonitor()
    window.showFullScreen()
    sys.exit(app.exec_())
