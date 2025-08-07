"""
Network Diagnostics GUI - A lightweight, always-visible network monitoring tool
Provides real-time network performance metrics in a compact GUI
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import subprocess
import platform
import psutil
import requests
import json
import os
from datetime import datetime, timedelta
import queue
import sys


class NetworkDiagnostics:
    def __init__(self):
        self.root = tk.Tk()
        self.setup_window()
        self.setup_variables()
        self.setup_ui()
        self.load_config()
        self.start_monitoring()

    def setup_window(self):
        """Configure the main window"""
        self.root.title("Network Diagnostics")
        self.root.geometry("300x400")
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.9)

        # Position in top-right corner
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = screen_width - width - 20
        y = 50
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        # Make window draggable
        self.root.bind('<Button-1>', self.start_drag)
        self.root.bind('<B1-Motion>', self.on_drag)

        # Bind dragging to all child widgets in minimal mode
        self.root.bind_all('<Button-1>', self.start_drag)
        self.root.bind_all('<B1-Motion>', self.on_drag)

        # Prevent window from going off-screen
        self.root.bind('<Configure>', self.on_configure)

    def setup_variables(self):
        """Initialize all variables and data structures"""
        self.view_mode = tk.StringVar(value="compact")  # "compact", "detailed", "minimal"
        self.is_monitoring = False
        self.monitoring_thread = None
        self.data_queue = queue.Queue()

        # Network metrics
        self.ping_latency = tk.StringVar(value="-- ms")
        self.signal_strength = tk.StringVar(value="-- dBm")
        self.connection_type = tk.StringVar(value="Unknown")
        self.network_name = tk.StringVar(value="Not connected")
        self.local_ip = tk.StringVar(value="--")
        self.public_ip = tk.StringVar(value="--")
        self.download_speed = tk.StringVar(value="-- Mbps")
        self.upload_speed = tk.StringVar(value="-- Mbps")
        self.packet_loss = tk.StringVar(value="-- %")

        # Configuration
        self.config = {
            'ping_targets': ['8.8.8.8', '1.1.1.1'],
            'refresh_interval': 5,
            'ping_timeout': 3,
            'theme': 'light',
            'opacity': 0.9,
            'auto_start': False,
            'view_mode': 'compact'
        }

        # Historical data (24 hours)
        self.history = {
            'timestamps': [],
            'ping_values': [],
            'signal_values': []
        }

        self.drag_start_x = 0
        self.drag_start_y = 0

    def setup_ui(self):
        """Create the user interface"""
        # Main frame
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Title bar (hidden in minimal mode)
        self.title_frame = ttk.Frame(self.main_frame)

        title_label = ttk.Label(self.title_frame, text="Network Diagnostics",
                                font=('Arial', 10, 'bold'))
        title_label.pack(side=tk.LEFT)

        # View toggle button
        self.toggle_btn = ttk.Button(self.title_frame, text="●", width=3,
                                     command=self.cycle_view_mode)
        self.toggle_btn.pack(side=tk.RIGHT)

        # Status indicator (hidden in minimal mode)
        self.status_frame = ttk.Frame(self.main_frame)

        self.status_canvas = tk.Canvas(self.status_frame, width=20, height=20)
        self.status_canvas.pack(side=tk.LEFT)
        self.status_indicator = self.status_canvas.create_oval(2, 2, 18, 18,
                                                               fill='gray', outline='')

        self.status_label = ttk.Label(self.status_frame, text="Initializing...")
        self.status_label.pack(side=tk.LEFT, padx=(10, 0))

        # Minimal view frame (League of Legends style)
        self.minimal_frame = ttk.Frame(self.main_frame)
        self.create_minimal_view()

        # Compact view frame
        self.compact_frame = ttk.Frame(self.main_frame)
        self.create_compact_view()

        # Detailed view frame
        self.detailed_frame = ttk.Frame(self.main_frame)
        self.create_detailed_view()

        # Control buttons frame (hidden in minimal mode)
        self.controls_frame = ttk.Frame(self.main_frame)

        ttk.Button(self.controls_frame, text="Refresh",
                   command=self.manual_refresh).pack(side=tk.LEFT)
        ttk.Button(self.controls_frame, text="Config",
                   command=self.show_config).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Button(self.controls_frame, text="Exit",
                   command=self.on_closing).pack(side=tk.RIGHT)

        # Set initial view
        self.view_mode.set(self.config.get('view_mode', 'compact'))
        self.update_view_mode()

        # Context menu
        self.create_context_menu()
        self.root.bind('<Button-3>', self.show_context_menu)

    def create_minimal_view(self):
        """Create the minimal League of Legends style view"""
        self.minimal_container = tk.Frame(self.minimal_frame, bg='black', padx=8, pady=4)
        self.minimal_container.pack()

        # Single frame to hold all elements in one line
        content_frame = tk.Frame(self.minimal_container, bg='black')
        content_frame.pack()

        # Status dot (left side)
        self.minimal_dot_canvas = tk.Canvas(content_frame, width=12, height=12,
                                            bg='black', highlightthickness=0)
        self.minimal_dot_canvas.pack(side=tk.LEFT, padx=(0, 6))
        self.minimal_dot = self.minimal_dot_canvas.create_oval(2, 2, 10, 10,
                                                               fill='gray', outline='white', width=1)

        # Ping text (middle)
        self.minimal_ping_label = tk.Label(content_frame, text="-- ms",
                                           fg='white', bg='black',
                                           font=('Arial', 11, 'bold'))
        self.minimal_ping_label.pack(side=tk.LEFT)

        # Triangle button to expand/cycle view (right side)
        self.minimal_expand_btn = tk.Label(
            content_frame,
            text="▸",  # Triangle pointing right
            font=("Arial", 14, "bold"),
            fg="white",
            bg="black",
            cursor="hand2",
            padx=6, pady=0
        )
        self.minimal_expand_btn.pack(side=tk.LEFT, padx=(4, 0))  # Small gap from ping text
        self.minimal_expand_btn.bind("<Button-1>", lambda e: self.cycle_view_mode())

    def create_compact_view(self):
        """Create the compact view with essential metrics"""
        # Connection info
        conn_frame = ttk.LabelFrame(self.compact_frame, text="Connection", padding="5")
        conn_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(conn_frame, text="Type:").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(conn_frame, textvariable=self.connection_type).grid(row=0, column=1, sticky=tk.W)

        ttk.Label(conn_frame, text="Network:").grid(row=1, column=0, sticky=tk.W)
        ttk.Label(conn_frame, textvariable=self.network_name).grid(row=1, column=1, sticky=tk.W)

        # Key metrics
        metrics_frame = ttk.LabelFrame(self.compact_frame, text="Metrics", padding="5")
        metrics_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(metrics_frame, text="Ping:").grid(row=0, column=0, sticky=tk.W)
        self.ping_label = ttk.Label(metrics_frame, textvariable=self.ping_latency)
        self.ping_label.grid(row=0, column=1, sticky=tk.W)

        ttk.Label(metrics_frame, text="Signal:").grid(row=1, column=0, sticky=tk.W)
        self.signal_label = ttk.Label(metrics_frame, textvariable=self.signal_strength)
        self.signal_label.grid(row=1, column=1, sticky=tk.W)

    def create_detailed_view(self):
        """Create the detailed view with all metrics"""
        # Network Information
        net_frame = ttk.LabelFrame(self.detailed_frame, text="Network Information", padding="5")
        net_frame.pack(fill=tk.X, pady=(0, 5))

        info_labels = [
            ("Type:", self.connection_type),
            ("Network:", self.network_name),
            ("Local IP:", self.local_ip),
            ("Public IP:", self.public_ip)
        ]

        for i, (label, var) in enumerate(info_labels):
            ttk.Label(net_frame, text=label).grid(row=i, column=0, sticky=tk.W)
            ttk.Label(net_frame, textvariable=var).grid(row=i, column=1, sticky=tk.W, padx=(10, 0))

        # Performance Metrics
        perf_frame = ttk.LabelFrame(self.detailed_frame, text="Performance", padding="5")
        perf_frame.pack(fill=tk.X, pady=(0, 5))

        perf_labels = [
            ("Ping:", self.ping_latency),
            ("Download:", self.download_speed),
            ("Upload:", self.upload_speed),
            ("Packet Loss:", self.packet_loss),
            ("Signal:", self.signal_strength)
        ]

        for i, (label, var) in enumerate(perf_labels):
            ttk.Label(perf_frame, text=label).grid(row=i, column=0, sticky=tk.W)
            label_widget = ttk.Label(perf_frame, textvariable=var)
            label_widget.grid(row=i, column=1, sticky=tk.W, padx=(10, 0))

            # Store references for color coding
            if label == "Ping:":
                self.ping_label_detailed = label_widget
            elif label == "Signal:":
                self.signal_label_detailed = label_widget

        # Mini graph placeholder
        graph_frame = ttk.LabelFrame(self.detailed_frame, text="Trend (Last Hour)", padding="5")
        graph_frame.pack(fill=tk.X, pady=(0, 5))

        self.trend_canvas = tk.Canvas(graph_frame, height=60, bg='white')
        self.trend_canvas.pack(fill=tk.X)

    def create_context_menu(self):
        """Create right-click context menu"""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Refresh Now", command=self.manual_refresh)
        self.context_menu.add_command(label="Reset Position", command=self.reset_position)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Minimal View", command=lambda: self.set_view_mode("minimal"))
        self.context_menu.add_command(label="Compact View", command=lambda: self.set_view_mode("compact"))
        self.context_menu.add_command(label="Detailed View", command=lambda: self.set_view_mode("detailed"))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Configuration", command=self.show_config)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Always on Top", command=self.toggle_topmost)
        self.context_menu.add_command(label="Export Data", command=self.export_data)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Exit", command=self.on_closing)

    def set_view_mode(self, mode):
        """Set specific view mode"""
        self.view_mode.set(mode)
        self.update_view_mode()

    def show_context_menu(self, event):
        """Show context menu"""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def cycle_view_mode(self):
        """Cycle through view modes: minimal -> compact -> detailed"""
        current_mode = self.view_mode.get()
        if current_mode == "minimal":
            self.view_mode.set("compact")
        elif current_mode == "compact":
            self.view_mode.set("detailed")
        else:
            self.view_mode.set("minimal")

        self.update_view_mode()

    def update_view_mode(self):
        """Update the display based on current view mode"""
        mode = self.view_mode.get()

        # Hide all frames first
        self.minimal_frame.pack_forget()
        self.compact_frame.pack_forget()
        self.detailed_frame.pack_forget()
        self.title_frame.pack_forget()
        self.status_frame.pack_forget()
        self.controls_frame.pack_forget()

        if mode == "minimal":
            # Minimal mode - just ping, dot, and tiny expand button
            self.minimal_frame.pack(fill=tk.BOTH, expand=True)
            self.root.update_idletasks()
            self.root.geometry(f"{self.minimal_container.winfo_reqwidth()}x{self.minimal_container.winfo_reqheight()}")
            self.toggle_btn.config(text="●")
            self.main_frame.config(padding="0")

            # Remove window decorations for true minimal look
            self.root.overrideredirect(True)

        elif mode == "compact":
            # Compact mode - essential info
            self.root.overrideredirect(False)  # Restore window decorations
            self.title_frame.pack(fill=tk.X, pady=(0, 10))
            self.status_frame.pack(fill=tk.X, pady=(0, 10))
            self.compact_frame.pack(fill=tk.BOTH, expand=True)
            self.controls_frame.pack(fill=tk.X, pady=(10, 0))
            self.root.geometry("300x200")
            self.toggle_btn.config(text="▼")
            self.main_frame.config(padding="10")

        else:  # detailed
            # Detailed mode - all information
            self.root.overrideredirect(False)  # Restore window decorations
            self.title_frame.pack(fill=tk.X, pady=(0, 10))
            self.status_frame.pack(fill=tk.X, pady=(0, 10))
            self.detailed_frame.pack(fill=tk.BOTH, expand=True)
            self.controls_frame.pack(fill=tk.X, pady=(10, 0))
            self.root.geometry("300x500")
            self.toggle_btn.config(text="▲")
            self.main_frame.config(padding="10")

        # Save preference
        self.config['view_mode'] = mode

    def toggle_view(self):
        """Legacy method for backward compatibility"""
        self.cycle_view_mode()

    def start_drag(self, event):
        if self.view_mode.get() == "minimal":
            if hasattr(self, 'minimal_expand_btn') and event.widget == self.minimal_expand_btn:
                return
        self.drag_start_x = event.x
        self.drag_start_y = event.y

    def on_drag(self, event):
        """Handle window dragging"""
        x = self.root.winfo_pointerx() - self.drag_start_x
        y = self.root.winfo_pointery() - self.drag_start_y
        self.root.geometry(f"+{x}+{y}")

    def on_configure(self, event):
        """Ensure window stays on screen"""
        if event.widget == self.root:
            x = self.root.winfo_x()
            y = self.root.winfo_y()
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()

            # Prevent window from going off-screen
            if x < 0:
                x = 0
            elif x + width > screen_width:
                x = screen_width - width

            if y < 0:
                y = 0
            elif y + height > screen_height:
                y = screen_height - height

            if x != self.root.winfo_x() or y != self.root.winfo_y():
                self.root.geometry(f"+{x}+{y}")

    def start_monitoring(self):
        """Start the network monitoring thread"""
        self.is_monitoring = True
        self.monitoring_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        self.monitoring_thread.start()

        # Start UI update loop
        self.root.after(100, self.update_ui)

    def monitoring_loop(self):
        """Main monitoring loop running in background thread"""
        while self.is_monitoring:
            try:
                # Collect network data
                data = self.collect_network_data()
                self.data_queue.put(data)

                # Wait for next refresh interval
                time.sleep(self.config['refresh_interval'])
            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(5)  # Wait before retrying

    def collect_network_data(self):
        """Collect all network diagnostic data"""
        data = {}

        try:
            # Get network interface info
            data.update(self.get_network_info())

            # Get ping latency
            data['ping'] = self.get_ping_latency()

            # Get signal strength (WiFi only)
            data['signal'] = self.get_signal_strength()

            # Get public IP (less frequent)
            if not hasattr(self, '_last_ip_check') or time.time() - self._last_ip_check > 300:
                data['public_ip'] = self.get_public_ip()
                self._last_ip_check = time.time()

            # Add timestamp
            data['timestamp'] = datetime.now()

        except Exception as e:
            print(f"Data collection error: {e}")
            data = {'error': str(e), 'timestamp': datetime.now()}

        return data

    def get_network_info(self):
        """Get basic network interface information"""
        info = {}

        try:
            # Get all network interfaces
            interfaces = psutil.net_if_addrs()
            stats = psutil.net_if_stats()

            # Find active interface
            active_interface = None
            for interface_name, interface_info in interfaces.items():
                if interface_name.lower() != 'loopback' and interface_name in stats:
                    if stats[interface_name].isup:
                        for addr in interface_info:
                            if addr.family == 2:  # IPv4
                                if not addr.address.startswith('169.254'):  # Not APIPA
                                    active_interface = interface_name
                                    info['local_ip'] = addr.address
                                    break

                if active_interface:
                    break

            if active_interface:
                # Determine connection type
                if 'wifi' in active_interface.lower() or 'wireless' in active_interface.lower():
                    info['connection_type'] = 'WiFi'
                    info['network_name'] = self.get_wifi_ssid()
                else:
                    info['connection_type'] = 'Ethernet'
                    info['network_name'] = active_interface
            else:
                info['connection_type'] = 'Disconnected'
                info['network_name'] = 'Not connected'
                info['local_ip'] = 'Not available'

        except Exception as e:
            print(f"Network info error: {e}")
            info = {
                'connection_type': 'Unknown',
                'network_name': 'Error getting info',
                'local_ip': 'Unknown'
            }

        return info

    def get_wifi_ssid(self):
        """Get current WiFi SSID"""
        try:
            if platform.system() == 'Windows':
                result = subprocess.run(['netsh', 'wlan', 'show', 'profile'],
                                        capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    # Parse current connection
                    result2 = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'],
                                             capture_output=True, text=True, timeout=5)
                    for line in result2.stdout.split('\n'):
                        if 'SSID' in line and 'BSSID' not in line:
                            return line.split(':', 1)[1].strip()
            return "WiFi Network"
        except Exception:
            return "WiFi Network"

    def get_ping_latency(self):
        """Get ping latency to configured targets"""
        try:
            total_time = 0
            successful_pings = 0

            for target in self.config['ping_targets']:
                try:
                    if platform.system() == 'Windows':
                        result = subprocess.run(
                            ['ping', '-n', '1', '-w', str(self.config['ping_timeout'] * 1000), target],
                            capture_output=True, text=True, timeout=self.config['ping_timeout'] + 1
                        )

                        if result.returncode == 0:
                            # Parse Windows ping output
                            for line in result.stdout.split('\n'):
                                if 'time=' in line.lower():
                                    time_part = line.split('time=')[1].split('ms')[0]
                                    if 'ms' in line:
                                        ping_time = float(time_part)
                                        total_time += ping_time
                                        successful_pings += 1
                                    break
                    else:
                        # Linux/Mac ping
                        result = subprocess.run(
                            ['ping', '-c', '1', '-W', str(self.config['ping_timeout']), target],
                            capture_output=True, text=True, timeout=self.config['ping_timeout'] + 1
                        )

                        if result.returncode == 0:
                            for line in result.stdout.split('\n'):
                                if 'time=' in line:
                                    time_part = line.split('time=')[1].split(' ')[0]
                                    ping_time = float(time_part)
                                    total_time += ping_time
                                    successful_pings += 1
                                    break

                except Exception as e:
                    print(f"Ping to {target} failed: {e}")
                    continue

            if successful_pings > 0:
                return round(total_time / successful_pings, 1)
            else:
                return None

        except Exception as e:
            print(f"Ping error: {e}")
            return None

    def get_signal_strength(self):
        """Get WiFi signal strength (Windows only for now)"""
        try:
            if platform.system() == 'Windows':
                result = subprocess.run(['netsh', 'wlan', 'show', 'interfaces'],
                                        capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'Signal' in line:
                            signal = line.split(':')[1].strip().replace('%', '')
                            # Convert percentage to approximate dBm
                            signal_pct = int(signal)
                            # Rough conversion: 100% = -30dBm, 0% = -100dBm
                            signal_dbm = -100 + (signal_pct * 0.7)
                            return round(signal_dbm)
            return None
        except Exception:
            return None

    def get_public_ip(self):
        """Get public IP address"""
        try:
            response = requests.get('https://api.ipify.org', timeout=5)
            if response.status_code == 200:
                return response.text.strip()
        except Exception:
            pass
        return None

    def update_ui(self):
        """Update UI with latest data from queue"""
        try:
            # Process all available data
            latest_data = None
            while not self.data_queue.empty():
                latest_data = self.data_queue.get_nowait()

            if latest_data:
                self.update_display(latest_data)
                self.update_history(latest_data)
                self.update_trend_graph()

        except Exception as e:
            print(f"UI update error: {e}")

        # Schedule next update
        self.root.after(500, self.update_ui)

    def update_display(self, data):
        """Update display with new data"""
        if 'error' in data:
            self.status_label.config(text="Error collecting data")
            self.status_canvas.itemconfig(self.status_indicator, fill='red')
            return

        # Update connection info
        if 'connection_type' in data:
            self.connection_type.set(data['connection_type'])
        if 'network_name' in data:
            self.network_name.set(data['network_name'])
        if 'local_ip' in data:
            self.local_ip.set(data['local_ip'])
        if 'public_ip' in data:
            self.public_ip.set(data['public_ip'])

        # Update ping with color coding
        if 'ping' in data and data['ping'] is not None:
            ping_val = data['ping']
            ping_text = f"{ping_val} ms"
            self.ping_latency.set(ping_text)

            # Color coding for ping
            color = 'green'
            dot_color = 'lime'
            if ping_val > 100:
                color = 'red'
                dot_color = 'red'
            elif ping_val > 50:
                color = 'orange'
                dot_color = 'yellow'

            # Apply color to labels
            if hasattr(self, 'ping_label'):
                self.ping_label.config(foreground=color)
            if hasattr(self, 'ping_label_detailed'):
                self.ping_label_detailed.config(foreground=color)

            # Update minimal view
            if hasattr(self, 'minimal_ping_label'):
                self.minimal_ping_label.config(text=f"{ping_val}ms", fg='white')
            if hasattr(self, 'minimal_dot_canvas'):
                self.minimal_dot_canvas.itemconfig(self.minimal_dot, fill=dot_color)

        else:
            ping_text = "Timeout"
            self.ping_latency.set(ping_text)
            if hasattr(self, 'ping_label'):
                self.ping_label.config(foreground='red')
            if hasattr(self, 'ping_label_detailed'):
                self.ping_label_detailed.config(foreground='red')

            # Update minimal view for timeout
            if hasattr(self, 'minimal_ping_label'):
                self.minimal_ping_label.config(text="Timeout", fg='red')
            if hasattr(self, 'minimal_dot_canvas'):
                self.minimal_dot_canvas.itemconfig(self.minimal_dot, fill='red')

        # Update signal strength
        if 'signal' in data and data['signal'] is not None:
            signal_val = data['signal']
            self.signal_strength.set(f"{signal_val} dBm")

            # Color coding for signal strength
            color = 'green'
            if signal_val < -70:
                color = 'red'
            elif signal_val < -50:
                color = 'orange'

            if hasattr(self, 'signal_label'):
                self.signal_label.config(foreground=color)
            if hasattr(self, 'signal_label_detailed'):
                self.signal_label_detailed.config(foreground=color)
        else:
            if data.get('connection_type') == 'WiFi':
                self.signal_strength.set("No signal data")
            else:
                self.signal_strength.set("Not WiFi")

        # Update status indicator
        overall_status = self.calculate_overall_status(data)
        status_colors = {'good': 'green', 'fair': 'orange', 'poor': 'red'}
        self.status_canvas.itemconfig(self.status_indicator,
                                      fill=status_colors.get(overall_status, 'gray'))
        self.status_label.config(text=f"Status: {overall_status.title()}")

    def calculate_overall_status(self, data):
        """Calculate overall network status"""
        if 'error' in data:
            return 'poor'

        ping = data.get('ping')
        signal = data.get('signal')

        poor_conditions = 0
        total_conditions = 0

        if ping is not None:
            total_conditions += 1
            if ping > 100:
                poor_conditions += 1

        if signal is not None:
            total_conditions += 1
            if signal < -70:
                poor_conditions += 1

        if total_conditions == 0:
            return 'fair'

        if poor_conditions == 0:
            return 'good'
        elif poor_conditions < total_conditions:
            return 'fair'
        else:
            return 'poor'

    def update_history(self, data):
        """Update historical data"""
        timestamp = data.get('timestamp', datetime.now())

        # Add new data point
        self.history['timestamps'].append(timestamp)
        self.history['ping_values'].append(data.get('ping'))
        self.history['signal_values'].append(data.get('signal'))

        # Keep only last 24 hours
        cutoff = datetime.now() - timedelta(hours=24)
        while (self.history['timestamps'] and
               self.history['timestamps'][0] < cutoff):
            self.history['timestamps'].pop(0)
            self.history['ping_values'].pop(0)
            self.history['signal_values'].pop(0)

    def update_trend_graph(self):
        """Update the mini trend graph"""
        if not hasattr(self, 'trend_canvas'):
            return

        canvas = self.trend_canvas
        canvas.delete("all")

        if len(self.history['ping_values']) < 2:
            canvas.create_text(canvas.winfo_width() // 2, 30,
                               text="Collecting data...", fill='gray')
            return

        # Filter out None values for ping
        ping_data = [(i, v) for i, v in enumerate(self.history['ping_values'])
                     if v is not None]

        if len(ping_data) < 2:
            return

        # Draw ping trend
        width = canvas.winfo_width()
        height = canvas.winfo_height()

        if width > 1 and height > 1:
            # Calculate scales
            max_ping = max(v for _, v in ping_data)
            min_ping = min(v for _, v in ping_data)

            if max_ping == min_ping:
                max_ping += 1

            # Draw trend line
            points = []
            for i, (idx, ping_val) in enumerate(ping_data):
                x = (i / (len(ping_data) - 1)) * (width - 20) + 10
                y = height - 10 - ((ping_val - min_ping) / (max_ping - min_ping)) * (height - 20)
                points.extend([x, y])

            if len(points) >= 4:
                canvas.create_line(points, fill='blue', width=2)

            # Add labels
            canvas.create_text(15, height - 5, text=f"{min_ping:.0f}",
                               fill='gray', font=('Arial', 8))
            canvas.create_text(15, 15, text=f"{max_ping:.0f}",
                               fill='gray', font=('Arial', 8))

    def manual_refresh(self):
        """Manually trigger a refresh"""
        self.status_label.config(text="Refreshing...")
        threading.Thread(target=self._manual_refresh_worker, daemon=True).start()

    def _manual_refresh_worker(self):
        """Worker for manual refresh"""
        data = self.collect_network_data()
        self.data_queue.put(data)

    def show_config(self):
        """Show configuration dialog"""
        ConfigDialog(self.root, self.config, self.apply_config)

    def apply_config(self, new_config):
        """Apply new configuration"""
        self.config.update(new_config)
        self.save_config()

        # Update window opacity
        self.root.attributes('-alpha', self.config['opacity'])

    def load_config(self):
        """Load configuration from file"""
        config_file = os.path.join(os.path.expanduser('~'), '.network_diagnostics_config.json')
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    saved_config = json.load(f)
                    self.config.update(saved_config)
        except Exception as e:
            print(f"Error loading config: {e}")

    def save_config(self):
        """Save configuration to file"""
        config_file = os.path.join(os.path.expanduser('~'), '.network_diagnostics_config.json')
        try:
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")

    def reset_position(self):
        """Reset window to top-right corner"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        screen_width = self.root.winfo_screenwidth()
        x = screen_width - width - 20
        y = 50
        self.root.geometry(f"+{x}+{y}")

    def toggle_topmost(self):
        """Toggle always on top"""
        current = self.root.attributes('-topmost')
        self.root.attributes('-topmost', not current)

    def export_data(self):
        """Export diagnostic data to file"""
        try:
            filename = f"network_diagnostics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = os.path.join(os.path.expanduser('~'), 'Desktop', filename)

            with open(filepath, 'w') as f:
                f.write("Network Diagnostics Export\n")
                f.write("=" * 40 + "\n")
                f.write(f"Export Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                # Current status
                f.write("Current Status:\n")
                f.write(f"Connection Type: {self.connection_type.get()}\n")
                f.write(f"Network Name: {self.network_name.get()}\n")
                f.write(f"Local IP: {self.local_ip.get()}\n")
                f.write(f"Public IP: {self.public_ip.get()}\n")
                f.write(f"Ping Latency: {self.ping_latency.get()}\n")
                f.write(f"Signal Strength: {self.signal_strength.get()}\n\n")

                # Historical data
                f.write("Historical Data (Last 24 Hours):\n")
                f.write("-" * 40 + "\n")
                for i, timestamp in enumerate(self.history['timestamps']):
                    ping = self.history['ping_values'][i]
                    signal = self.history['signal_values'][i]
                    f.write(f"{timestamp.strftime('%H:%M:%S')}: ")
                    f.write(f"Ping={ping}ms, Signal={signal}dBm\n")

            messagebox.showinfo("Export Complete", f"Data exported to:\n{filepath}")

        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export data:\n{str(e)}")

    def on_closing(self):
        """Handle application closing"""
        self.is_monitoring = False
        self.save_config()
        self.root.quit()
        self.root.destroy()

    def run(self):
        """Start the application"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()


class ConfigDialog:
    """Configuration dialog window"""

    def __init__(self, parent, config, callback):
        self.config = config.copy()
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Configuration")
        self.dialog.geometry("400x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center the dialog
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.dialog.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

        self.create_widgets()

    def create_widgets(self):
        """Create configuration widgets"""
        # Main frame with scrollbar
        main_frame = ttk.Frame(self.dialog, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Network Settings
        net_frame = ttk.LabelFrame(main_frame, text="Network Settings", padding="10")
        net_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(net_frame, text="Ping Targets (one per line):").pack(anchor=tk.W)
        self.ping_targets_text = tk.Text(net_frame, height=4, width=40)
        self.ping_targets_text.pack(fill=tk.X, pady=(5, 10))
        self.ping_targets_text.insert(tk.END, '\n'.join(self.config['ping_targets']))

        ttk.Label(net_frame, text="Ping Timeout (seconds):").pack(anchor=tk.W)
        self.ping_timeout_var = tk.StringVar(value=str(self.config['ping_timeout']))
        ttk.Entry(net_frame, textvariable=self.ping_timeout_var, width=10).pack(anchor=tk.W, pady=(5, 0))

        # Update Settings
        update_frame = ttk.LabelFrame(main_frame, text="Update Settings", padding="10")
        update_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(update_frame, text="Refresh Interval (seconds):").pack(anchor=tk.W)
        self.refresh_var = tk.StringVar(value=str(self.config['refresh_interval']))
        refresh_scale = ttk.Scale(update_frame, from_=1, to=60, variable=self.refresh_var,
                                  orient=tk.HORIZONTAL, length=200)
        refresh_scale.pack(anchor=tk.W, pady=(5, 0))

        refresh_label = ttk.Label(update_frame, textvariable=self.refresh_var)
        refresh_label.pack(anchor=tk.W)

        # Appearance Settings
        appear_frame = ttk.LabelFrame(main_frame, text="Appearance", padding="10")
        appear_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(appear_frame, text="Window Opacity:").pack(anchor=tk.W)
        self.opacity_var = tk.DoubleVar(value=self.config['opacity'])
        opacity_scale = ttk.Scale(appear_frame, from_=0.0, to=1.0, variable=self.opacity_var,
                                  orient=tk.HORIZONTAL, length=200)
        opacity_scale.pack(anchor=tk.W, pady=(5, 0))

        opacity_label = ttk.Label(appear_frame, text="")
        opacity_label.pack(anchor=tk.W)

        def update_opacity_label(*args):
            opacity_label.config(text=f"{self.opacity_var.get():.1f}")

        self.opacity_var.trace('w', update_opacity_label)
        update_opacity_label()

        # Theme selection
        ttk.Label(appear_frame, text="Theme:").pack(anchor=tk.W, pady=(10, 0))
        self.theme_var = tk.StringVar(value=self.config['theme'])
        theme_frame = ttk.Frame(appear_frame)
        theme_frame.pack(anchor=tk.W, pady=(5, 0))
        ttk.Radiobutton(theme_frame, text="Light", variable=self.theme_var,
                        value="light").pack(side=tk.LEFT)
        ttk.Radiobutton(theme_frame, text="Dark", variable=self.theme_var,
                        value="dark").pack(side=tk.LEFT, padx=(10, 0))

        # View Mode Settings
        view_frame = ttk.LabelFrame(main_frame, text="View Settings", padding="10")
        view_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(view_frame, text="Default View Mode:").pack(anchor=tk.W)
        self.view_mode_var = tk.StringVar(value=self.config['view_mode'])
        view_mode_frame = ttk.Frame(view_frame)
        view_mode_frame.pack(anchor=tk.W, pady=(5, 0))

        ttk.Radiobutton(view_mode_frame, text="Minimal", variable=self.view_mode_var,
                        value="minimal").pack(side=tk.LEFT)
        ttk.Radiobutton(view_mode_frame, text="Compact", variable=self.view_mode_var,
                        value="compact").pack(side=tk.LEFT, padx=(10, 0))
        ttk.Radiobutton(view_mode_frame, text="Detailed", variable=self.view_mode_var,
                        value="detailed").pack(side=tk.LEFT, padx=(10, 0))

        # Startup Settings
        startup_frame = ttk.LabelFrame(main_frame, text="Startup", padding="10")
        startup_frame.pack(fill=tk.X, pady=(0, 10))

        self.autostart_var = tk.BooleanVar(value=self.config['auto_start'])
        ttk.Checkbutton(startup_frame, text="Start with Windows",
                        variable=self.autostart_var).pack(anchor=tk.W)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(button_frame, text="OK", command=self.ok_clicked).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="Cancel", command=self.cancel_clicked).pack(side=tk.RIGHT, padx=(0, 10))
        ttk.Button(button_frame, text="Reset to Defaults", command=self.reset_defaults).pack(side=tk.LEFT)

    def ok_clicked(self):
        """Handle OK button click"""
        try:
            # Validate and save settings
            self.config['ping_targets'] = [target.strip() for target in
                                           self.ping_targets_text.get('1.0', tk.END).strip().split('\n')
                                           if target.strip()]

            if not self.config['ping_targets']:
                self.config['ping_targets'] = ['8.8.8.8', '1.1.1.1']

            self.config['ping_timeout'] = max(1, int(float(self.ping_timeout_var.get())))
            self.config['refresh_interval'] = max(1, int(float(self.refresh_var.get())))
            self.config['opacity'] = max(0.0, min(1.0, self.opacity_var.get()))
            self.config['theme'] = self.theme_var.get()
            self.config['auto_start'] = self.autostart_var.get()
            self.config['view_mode'] = self.view_mode_var.get()

            self.callback(self.config)
            self.dialog.destroy()

        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please check your input values:\n{str(e)}")

    def cancel_clicked(self):
        """Handle Cancel button click"""
        self.dialog.destroy()

    def reset_defaults(self):
        """Reset all settings to defaults"""
        defaults = {
            'ping_targets': ['8.8.8.8', '1.1.1.1'],
            'refresh_interval': 5,
            'ping_timeout': 3,
            'theme': 'light',
            'opacity': 0.9,
            'auto_start': False,
            'view_mode': 'compact'
        }

        self.ping_targets_text.delete('1.0', tk.END)
        self.ping_targets_text.insert(tk.END, '\n'.join(defaults['ping_targets']))
        self.ping_timeout_var.set(str(defaults['ping_timeout']))
        self.refresh_var.set(str(defaults['refresh_interval']))
        self.opacity_var.set(defaults['opacity'])
        self.theme_var.set(defaults['theme'])
        self.autostart_var.set(defaults['auto_start'])
        self.view_mode_var.set(defaults['view_mode'])


def main():
    """Main entry point"""
    try:
        # Check if required modules are available
        required_modules = ['psutil', 'requests']
        missing_modules = []

        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing_modules.append(module)

        if missing_modules:
            print("Missing required modules. Please install:")
            for module in missing_modules:
                print(f"  pip install {module}")
            return

        # Create and run the application
        app = NetworkDiagnostics()
        app.run()

    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
    except Exception as e:
        print(f"Application error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()