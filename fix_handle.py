import sys

try:
    with open('e:/PORT_I/port_I.py', 'r', encoding='utf-8') as f:
        content = f.read()

    start_marker = "def handle_vessel_move(self, master_item):"
    end_marker = "self.update_table()"
    
    start_idx = content.find(start_marker)
    if start_idx == -1:
        print("Start marker not found")
        sys.exit(1)
        
    # Find update_table after start
    end_idx = content.find(end_marker, start_idx)
    if end_idx == -1:
        print("End marker not found")
        sys.exit(1)
        
    end_idx += len(end_marker) # Include the marker

    new_method = """    def handle_vessel_move(self, master_item):
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
        if old_term == new_term and old_eta == new_eta:
            pass
        else:
             # Construct Log Entry
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
            
            old_str = f"{old_term.replace('-', '(') + ')'} {format_short_dt(old_eta)}"
            new_str = f"{new_term.replace('-', '(') + ')'} {format_short_dt(new_eta)}"
            to_widget_text = None
            to_widget_style = None
            
            old_t_name = old_term.split('-')[0]
            new_t_name = new_term.split('-')[0]
            
            color_code = None
            if old_t_name != new_t_name:
                color_code = "#ff5555"
            elif old_term != new_term:
                color_code = "#50fa7b"
                
            if color_code:
                to_widget_text = new_str
                to_widget_style = f"border: 2px solid {color_code}; color: {color_code}; font-weight: bold; background: #282a36;"
            
            delta = new_eta - old_eta
            delta_str = format_time_delta(delta)
            shift_color = None
            if delta.total_seconds() != 0:
                shift_color = "#ffb86c"
                
            entry = {
                'vessel_text': vessel_display,
                'vessel_widget_text': vessel_widget_text,
                'vessel_widget_style': vessel_widget_style,
                'from': old_str,
                'to_text': new_str,
                'to_widget_text': to_widget_text,
                'to_widget_style': to_widget_style,
                'shift_text': delta_str,
                'shift_color': shift_color
            }
            
            self.ports[self.active_port_code].master_log_data.append(entry)
            self.add_master_log_row(entry)
        
        # Check if this is the first move after copy
        if hasattr(master_item, 'is_just_copied') and master_item.is_just_copied:
             if hasattr(master_item, 'has_moved_during_drag') and master_item.has_moved_during_drag:
                 master_item.is_just_copied = False
                 print("DEBUG: Flag consumed (moved).")
             else:
                 print("DEBUG: Flag KEPT (not moved).")
        else:
             self.resolve_collisions(master_item)
             
        self.update_table()"""

    new_content = content[:start_idx] + new_method + content[end_idx:]

    with open('e:/PORT_I/port_I.py', 'w', encoding='utf-8') as f:
        f.write(new_content)

    print("Successfully replaced method.")

except Exception as e:
    print(f"Error: {e}")
