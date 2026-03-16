"""
NetDog Network Diagnostics GUI - Headless Background Version
Fixed console popup issue when running as EXE
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
import statistics
if platform.system() == 'Windows':
    import winreg

# Hide console window on Windows when running as EXE
if platform.system() == 'Windows' and getattr(sys, 'frozen', False):
    import ctypes
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

# ── Design tokens ─────────────────────────────────────────────────────────────
BG        = '#0d1117'
BG_PANEL  = '#161b22'
BG_CARD   = '#1c2128'
BORDER    = '#30363d'
TEXT      = '#e6edf3'
TEXT_DIM  = '#8b949e'
TEXT_MUTED= '#484f58'
ACCENT    = '#00d4ff'
GOOD      = '#3fb950'
WARN      = '#d29922'
BAD       = '#f85149'
DL_CLR    = '#00d4ff'
UL_CLR    = '#7ee787'

F_MONO    = ('Consolas', 10)
F_MONO_LG = ('Consolas', 12, 'bold')
F_MONO_SM = ('Consolas', 9)
F_UI      = ('Segoe UI', 9)
F_UI_SM   = ('Segoe UI', 8)
F_UI_BOLD = ('Segoe UI', 9, 'bold')
F_LABEL   = ('Segoe UI', 7)
F_TITLE   = ('Segoe UI', 8, 'bold')


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
        self.root.title("NetDog")
        self.root.geometry("300x400")
        self.root.configure(bg=BG)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.9)

        # Set the window icon properly
        self.set_window_icon()

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

    def set_window_icon(self):
        """Set the window icon for NetDog"""
        try:
            # Get the icon file path
            icon_path = self.get_resource_path('NetDog_icon_highres.ico')

            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
                print(f"✅ Icon set successfully: {icon_path}")
            else:
                print(f"❌ Icon file not found: {icon_path}")
                # Try fallback locations
                fallback_paths = [
                    'NetDog_icon_highres.ico',
                    os.path.join(os.path.dirname(__file__), 'NetDog_icon_highres.ico'),
                    os.path.join(os.getcwd(), 'NetDog_icon_highres.ico')
                ]

                icon_found = False
                for fallback in fallback_paths:
                    if os.path.exists(fallback):
                        self.root.iconbitmap(fallback)
                        print(f"✅ Using fallback icon: {fallback}")
                        icon_found = True
                        break

                if not icon_found:
                    print("⚠️  No icon file found - using default")
                    # Try to remove the default Python icon
                    try:
                        self.root.iconbitmap(default='')
                    except:
                        pass

        except Exception as e:
            print(f"❌ Failed to set icon: {e}")
            # Try to remove the default Python icon as fallback
            try:
                self.root.iconbitmap(default='')
            except:
                pass

    def get_resource_path(self, relative_path):
        """Get absolute path to resource, works for dev and for PyInstaller"""
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)

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
            'view_mode': 'compact',
            'speed_test_interval': 60,  # minutes
        }

        # Historical data (24 hours)
        self.history = {
            'timestamps': [],
            'ping_values': [],
            'signal_values': []
        }

        self.drag_start_x = 0
        self.drag_start_y = 0

        # Caches
        self._netsh_cache = None
        self._netsh_cache_time = 0
        self._packet_loss_pct = 0

        # Speed test state
        self._speed_testing = False
        self.speedtest_time_var = tk.StringVar(value="Speed test: never run")

    def _mk_btn(self, parent, text, command):
        """Create a flat dark button"""
        b = tk.Button(parent, text=text, command=command,
                      fg=TEXT_DIM, bg=BG_PANEL, font=F_UI_SM,
                      relief='flat', bd=0, cursor='hand2',
                      activebackground=BORDER, activeforeground=TEXT,
                      padx=10, pady=5)
        b.bind('<Enter>', lambda e: b.config(fg=TEXT, bg=BG_CARD))
        b.bind('<Leave>', lambda e: b.config(fg=TEXT_DIM, bg=BG_PANEL))
        return b

    def setup_ui(self):
        """Create the user interface"""
        self.main_frame = tk.Frame(self.root, bg=BG)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # ── Header bar (hidden in minimal mode) ────────────────────────────
        self.title_frame = tk.Frame(self.main_frame, bg=BG_PANEL)

        # Accent top stripe
        tk.Frame(self.title_frame, bg=ACCENT, height=2).pack(fill=tk.X)

        header_inner = tk.Frame(self.title_frame, bg=BG_PANEL)
        header_inner.pack(fill=tk.X, padx=10, pady=(5, 6))

        # Status dot + status text
        self.status_canvas = tk.Canvas(header_inner, width=10, height=10,
                                       bg=BG_PANEL, highlightthickness=0)
        self.status_canvas.pack(side=tk.LEFT, pady=2)
        self.status_indicator = self.status_canvas.create_oval(1, 1, 9, 9,
                                                               fill=TEXT_MUTED, outline='')
        self.status_label = tk.Label(header_inner, text="INITIALIZING",
                                     fg=TEXT_DIM, bg=BG_PANEL, font=F_LABEL)
        self.status_label.pack(side=tk.LEFT, padx=(6, 0))

        # App name (center)
        tk.Label(header_inner, text="NETDOG", fg=ACCENT, bg=BG_PANEL,
                 font=F_TITLE).pack(side=tk.LEFT, expand=True)

        # Toggle button
        self.toggle_btn = tk.Label(header_inner, text="▾", fg=TEXT_DIM,
                                   bg=BG_PANEL, font=('Segoe UI', 13),
                                   cursor='hand2', padx=4)
        self.toggle_btn.pack(side=tk.RIGHT)
        self.toggle_btn.bind('<Button-1>', lambda e: self.cycle_view_mode())
        self.toggle_btn.bind('<Enter>', lambda e: self.toggle_btn.config(fg=ACCENT))
        self.toggle_btn.bind('<Leave>', lambda e: self.toggle_btn.config(fg=TEXT_DIM))

        # Kept as empty frame for layout compat (status_frame is merged into title_frame)
        self.status_frame = tk.Frame(self.main_frame, bg=BG, height=0)

        # ── View frames ────────────────────────────────────────────────────
        self.minimal_frame = tk.Frame(self.main_frame, bg='black')
        self.create_minimal_view()

        self.compact_frame = tk.Frame(self.main_frame, bg=BG)
        self.create_compact_view()

        self.detailed_frame = tk.Frame(self.main_frame, bg=BG)
        self.create_detailed_view()

        # ── Controls bar ───────────────────────────────────────────────────
        self.controls_frame = tk.Frame(self.main_frame, bg=BG_PANEL)
        tk.Frame(self.controls_frame, bg=BORDER, height=1).pack(fill=tk.X)

        btn_row = tk.Frame(self.controls_frame, bg=BG_PANEL)
        btn_row.pack(fill=tk.X)

        self._mk_btn(btn_row, "Refresh", self.manual_refresh).pack(side=tk.LEFT)
        self._mk_btn(btn_row, "Config", self.show_config).pack(side=tk.LEFT)
        self.speedtest_btn = self._mk_btn(btn_row, "Speed Test", self.run_speed_test)
        self.speedtest_btn.pack(side=tk.LEFT)
        self._mk_btn(btn_row, "Exit", self.on_closing).pack(side=tk.RIGHT)

        self.view_mode.set(self.config.get('view_mode', 'compact'))
        self.update_view_mode()

        self.create_context_menu()
        self.root.bind('<Button-3>', self.show_context_menu)

    def create_minimal_view(self):
        """Minimal HUD pill — dot · ping · dl↓ ul↑ · expand"""
        PILL_BG = '#0a0e14'
        self.minimal_container = tk.Frame(self.minimal_frame, bg=PILL_BG,
                                          padx=10, pady=5,
                                          highlightbackground='#1e2a38',
                                          highlightthickness=1)
        self.minimal_container.pack()

        row = tk.Frame(self.minimal_container, bg=PILL_BG)
        row.pack()

        # Status dot
        self.minimal_dot_canvas = tk.Canvas(row, width=10, height=10,
                                            bg=PILL_BG, highlightthickness=0)
        self.minimal_dot_canvas.pack(side=tk.LEFT, padx=(0, 8))
        self.minimal_dot = self.minimal_dot_canvas.create_oval(1, 1, 9, 9,
                                                               fill=TEXT_MUTED, outline='')

        # Ping
        self.minimal_ping_label = tk.Label(row, text="-- ms",
                                           fg=TEXT, bg=PILL_BG,
                                           font=F_MONO_LG)
        self.minimal_ping_label.pack(side=tk.LEFT)

        # Divider
        tk.Label(row, text="·", fg='#2a3a4a', bg=PILL_BG,
                 font=('Segoe UI', 13)).pack(side=tk.LEFT, padx=(8, 8))

        # Download
        self.minimal_dl_label = tk.Label(row, text="--↓",
                                         fg=DL_CLR, bg=PILL_BG,
                                         font=F_MONO_SM)
        self.minimal_dl_label.pack(side=tk.LEFT)

        # Upload
        self.minimal_ul_label = tk.Label(row, text="  --↑",
                                         fg=UL_CLR, bg=PILL_BG,
                                         font=F_MONO_SM)
        self.minimal_ul_label.pack(side=tk.LEFT)

        # Expand chevron
        self.minimal_expand_btn = tk.Label(row, text="›",
                                           fg='#2a3a4a', bg=PILL_BG,
                                           font=('Segoe UI', 15, 'bold'),
                                           cursor='hand2', padx=6)
        self.minimal_expand_btn.pack(side=tk.LEFT, padx=(8, 0))
        self.minimal_expand_btn.bind('<Button-1>', lambda e: self.cycle_view_mode())
        self.minimal_expand_btn.bind('<Enter>',
                                     lambda e: self.minimal_expand_btn.config(fg=ACCENT))
        self.minimal_expand_btn.bind('<Leave>',
                                     lambda e: self.minimal_expand_btn.config(fg='#2a3a4a'))

    def _section_header(self, parent, text):
        """Thin section header: colored label + horizontal rule"""
        f = tk.Frame(parent, bg=BG)
        f.pack(fill=tk.X, padx=12, pady=(10, 4))
        tk.Label(f, text=text, fg=ACCENT, bg=BG,
                 font=('Segoe UI', 7, 'bold')).pack(side=tk.LEFT)
        tk.Frame(f, bg=BORDER, height=1).pack(side=tk.LEFT, fill=tk.X,
                                              expand=True, padx=(6, 0), pady=3)

    def _metric_row(self, parent, label_text, var=None, label_ref=None):
        """Single label + value row, returns value widget"""
        row = tk.Frame(parent, bg=BG)
        row.pack(fill=tk.X, padx=14, pady=1)
        tk.Label(row, text=label_text.upper(), fg=TEXT_MUTED, bg=BG,
                 font=F_LABEL, width=12, anchor='w').pack(side=tk.LEFT)
        if var:
            w = tk.Label(row, textvariable=var, fg=TEXT, bg=BG, font=F_MONO,
                         anchor='e')
        else:
            w = tk.Label(row, text="—", fg=TEXT, bg=BG, font=F_MONO, anchor='e')
        w.pack(side=tk.RIGHT)
        return w

    def create_compact_view(self):
        """Compact dark card view"""
        self._section_header(self.compact_frame, "CONNECTION")

        conn = tk.Frame(self.compact_frame, bg=BG)
        conn.pack(fill=tk.X, padx=14, pady=1)
        tk.Label(conn, text="TYPE", fg=TEXT_MUTED, bg=BG,
                 font=F_LABEL, width=12, anchor='w').pack(side=tk.LEFT)
        tk.Label(conn, textvariable=self.connection_type, fg=TEXT, bg=BG,
                 font=F_MONO, anchor='e').pack(side=tk.RIGHT)

        net = tk.Frame(self.compact_frame, bg=BG)
        net.pack(fill=tk.X, padx=14, pady=1)
        tk.Label(net, text="NETWORK", fg=TEXT_MUTED, bg=BG,
                 font=F_LABEL, width=12, anchor='w').pack(side=tk.LEFT)
        tk.Label(net, textvariable=self.network_name, fg=TEXT, bg=BG,
                 font=F_MONO, anchor='e').pack(side=tk.RIGHT)

        self._section_header(self.compact_frame, "PERFORMANCE")

        self.ping_label = self._metric_row(self.compact_frame, "Ping",
                                           self.ping_latency)
        self.packet_loss_label_compact = self._metric_row(self.compact_frame,
                                                          "Packet Loss",
                                                          self.packet_loss)
        self.signal_label = self._metric_row(self.compact_frame, "Signal",
                                             self.signal_strength)

        self._section_header(self.compact_frame, "SPEED TEST")
        self._metric_row(self.compact_frame, "Download", self.download_speed)
        self._metric_row(self.compact_frame, "Upload", self.upload_speed)

    def create_detailed_view(self):
        """Detailed dark card view with graph"""
        self._section_header(self.detailed_frame, "NETWORK")
        self._metric_row(self.detailed_frame, "Type", self.connection_type)
        self._metric_row(self.detailed_frame, "Network", self.network_name)
        self._metric_row(self.detailed_frame, "Local IP", self.local_ip)
        self._metric_row(self.detailed_frame, "Public IP", self.public_ip)

        self._section_header(self.detailed_frame, "PERFORMANCE")
        self.ping_label_detailed = self._metric_row(self.detailed_frame, "Ping",
                                                    self.ping_latency)
        self._metric_row(self.detailed_frame, "Download", self.download_speed)
        self._metric_row(self.detailed_frame, "Upload", self.upload_speed)
        self._metric_row(self.detailed_frame, "Packet Loss", self.packet_loss)
        self.signal_label_detailed = self._metric_row(self.detailed_frame, "Signal",
                                                       self.signal_strength)

        # Speed test timestamp
        ts_row = tk.Frame(self.detailed_frame, bg=BG)
        ts_row.pack(fill=tk.X, padx=14, pady=(4, 0))
        tk.Label(ts_row, textvariable=self.speedtest_time_var,
                 fg=TEXT_MUTED, bg=BG, font=F_LABEL).pack(side=tk.LEFT)

        # Trend graph
        self._section_header(self.detailed_frame, "PING TREND")
        graph_wrap = tk.Frame(self.detailed_frame, bg=BG_CARD,
                              highlightbackground=BORDER, highlightthickness=1)
        graph_wrap.pack(fill=tk.X, padx=12, pady=(0, 8))
        self.trend_canvas = tk.Canvas(graph_wrap, height=56, bg=BG_CARD,
                                      highlightthickness=0)
        self.trend_canvas.pack(fill=tk.X, padx=2, pady=2)

    def create_context_menu(self):
        """Create right-click context menu"""
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Refresh Now", command=self.manual_refresh)
        self.context_menu.add_command(label="Speed Test", command=self.run_speed_test)
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

        self.minimal_frame.pack_forget()
        self.compact_frame.pack_forget()
        self.detailed_frame.pack_forget()
        self.title_frame.pack_forget()
        self.status_frame.pack_forget()
        self.controls_frame.pack_forget()

        if mode == "minimal":
            self.minimal_frame.pack(fill=tk.BOTH, expand=True)
            self.root.update_idletasks()
            w = self.minimal_container.winfo_reqwidth()
            h = self.minimal_container.winfo_reqheight()
            self.root.geometry(f"{w}x{h}")
            self.root.overrideredirect(True)

        elif mode == "compact":
            self.root.overrideredirect(False)
            self.title_frame.pack(fill=tk.X)
            self.compact_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
            self.controls_frame.pack(fill=tk.X)
            self.root.geometry("300x270")
            self.toggle_btn.config(text="▾")

        else:  # detailed
            self.root.overrideredirect(False)
            self.title_frame.pack(fill=tk.X)
            self.detailed_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
            self.controls_frame.pack(fill=tk.X)
            self.root.geometry("300x510")
            self.toggle_btn.config(text="▴")

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

        # Start watchdog to restart monitoring thread if it dies
        self.root.after(10000, self._watchdog)

        # Auto speed test every 15 minutes
        self.root.after(self.config.get('speed_test_interval', 60) * 60 * 1000, self._auto_speed_test)

    def _watchdog(self):
        """Restart monitoring thread if it has died unexpectedly"""
        if self.is_monitoring and (self.monitoring_thread is None or not self.monitoring_thread.is_alive()):
            self.monitoring_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
            self.monitoring_thread.start()
        if self.is_monitoring:
            self.root.after(10000, self._watchdog)

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

    def _get_netsh_data(self):
        """Return cached netsh wlan output, refreshing every 10 seconds."""
        now = time.time()
        if self._netsh_cache is not None and now - self._netsh_cache_time < 10:
            return self._netsh_cache
        try:
            if platform.system() == 'Windows':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                result = subprocess.run(
                    ['netsh', 'wlan', 'show', 'interfaces'],
                    capture_output=True, text=True, timeout=5,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if result.returncode == 0:
                    self._netsh_cache = result.stdout
                    self._netsh_cache_time = now
                    return self._netsh_cache
        except Exception:
            pass
        return self._netsh_cache or ""

    def get_wifi_ssid(self):
        """Get current WiFi SSID using cached netsh data"""
        try:
            output = self._get_netsh_data()
            for line in output.split('\n'):
                if 'SSID' in line and 'BSSID' not in line:
                    return line.split(':', 1)[1].strip()
            return "WiFi Network"
        except Exception:
            return "WiFi Network"

    def get_ping_latency(self):
        """Ping each target 3x, return median latency. Tracks packet loss."""
        ping_times = []
        total_attempts = 0

        for target in self.config['ping_targets']:
            for _ in range(3):
                total_attempts += 1
                try:
                    if platform.system() == 'Windows':
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                        startupinfo.wShowWindow = subprocess.SW_HIDE

                        result = subprocess.run(
                            ['ping', '-n', '1', '-w', str(self.config['ping_timeout'] * 1000), target],
                            capture_output=True, text=True, timeout=self.config['ping_timeout'] + 1,
                            startupinfo=startupinfo,
                            creationflags=subprocess.CREATE_NO_WINDOW
                        )
                        if result.returncode == 0:
                            for line in result.stdout.split('\n'):
                                if 'time=' in line.lower():
                                    time_part = line.split('time=')[1].split('ms')[0]
                                    ping_times.append(float(time_part))
                                    break
                    else:
                        result = subprocess.run(
                            ['ping', '-c', '1', '-W', str(self.config['ping_timeout']), target],
                            capture_output=True, text=True, timeout=self.config['ping_timeout'] + 1
                        )
                        if result.returncode == 0:
                            for line in result.stdout.split('\n'):
                                if 'time=' in line:
                                    ping_times.append(float(line.split('time=')[1].split(' ')[0]))
                                    break
                except Exception:
                    pass

        # Update packet loss
        if total_attempts > 0:
            lost = total_attempts - len(ping_times)
            self._packet_loss_pct = round((lost / total_attempts) * 100)
        else:
            self._packet_loss_pct = 0

        if ping_times:
            return round(statistics.median(ping_times), 1)
        return None

    def get_signal_strength(self):
        """Get WiFi signal strength using cached netsh data"""
        try:
            output = self._get_netsh_data()
            for line in output.split('\n'):
                if 'Signal' in line:
                    signal = line.split(':')[1].strip().replace('%', '')
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

        # Update packet loss
        loss = self._packet_loss_pct
        self.packet_loss.set(f"{loss} %")
        if hasattr(self, 'packet_loss_label_compact'):
            self.packet_loss_label_compact.config(fg=BAD if loss > 0 else GOOD)

        # Update ping with color coding
        if 'ping' in data and data['ping'] is not None:
            ping_val = data['ping']
            ping_text = f"{ping_val} ms"
            self.ping_latency.set(ping_text)

            # Color coding for ping
            color = GOOD
            dot_color = GOOD
            if ping_val > 100:
                color = BAD
                dot_color = BAD
            elif ping_val > 50:
                color = WARN
                dot_color = WARN

            # Apply color to labels
            if hasattr(self, 'ping_label'):
                self.ping_label.config(fg=color)
            if hasattr(self, 'ping_label_detailed'):
                self.ping_label_detailed.config(fg=color)

            # Update minimal view
            if hasattr(self, 'minimal_ping_label'):
                self.minimal_ping_label.config(text=f"{ping_val}ms", fg='white')
            if hasattr(self, 'minimal_dot_canvas'):
                self.minimal_dot_canvas.itemconfig(self.minimal_dot, fill=dot_color)

        else:
            ping_text = "Timeout"
            self.ping_latency.set(ping_text)
            if hasattr(self, 'ping_label'):
                self.ping_label.config(fg=BAD)
            if hasattr(self, 'ping_label_detailed'):
                self.ping_label_detailed.config(fg=BAD)

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
            color = GOOD
            if signal_val < -70:
                color = BAD
            elif signal_val < -50:
                color = WARN

            if hasattr(self, 'signal_label'):
                self.signal_label.config(fg=color)
            if hasattr(self, 'signal_label_detailed'):
                self.signal_label_detailed.config(fg=color)
        else:
            if data.get('connection_type') == 'WiFi':
                self.signal_strength.set("No signal data")
            else:
                self.signal_strength.set("Not WiFi")

        # Update status indicator
        overall_status = self.calculate_overall_status(data)
        status_colors = {'good': GOOD, 'fair': WARN, 'poor': BAD}
        dot_color = status_colors.get(overall_status, TEXT_MUTED)
        self.status_canvas.itemconfig(self.status_indicator, fill=dot_color)
        self.status_label.config(text=overall_status.upper(),
                                 fg=dot_color)

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

        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width <= 1:
            return

        if len(self.history['ping_values']) < 2:
            canvas.create_text(width // 2, height // 2,
                               text="collecting data…", fill=TEXT_MUTED,
                               font=F_LABEL)
            return

        ping_data = [(i, v) for i, v in enumerate(self.history['ping_values'])
                     if v is not None]
        if len(ping_data) < 2:
            return

        max_ping = max(v for _, v in ping_data)
        min_ping = min(v for _, v in ping_data)
        if max_ping == min_ping:
            max_ping += 1

        PAD = 18

        # Faint horizontal grid lines
        for frac in (0.25, 0.5, 0.75):
            y = PAD + frac * (height - PAD * 2)
            canvas.create_line(PAD, y, width - 4, y,
                               fill=BORDER, width=1, dash=(2, 4))

        # Filled area under the line
        area_pts = [PAD, height - 4]
        for i, (_, v) in enumerate(ping_data):
            x = PAD + (i / (len(ping_data) - 1)) * (width - PAD - 4)
            y = (height - PAD) - ((v - min_ping) / (max_ping - min_ping)) * (height - PAD * 2)
            area_pts.extend([x, y])
        area_pts.extend([width - 4, height - 4])
        canvas.create_polygon(area_pts, fill='#00334a', outline='')

        # Trend line
        pts = []
        for i, (_, v) in enumerate(ping_data):
            x = PAD + (i / (len(ping_data) - 1)) * (width - PAD - 4)
            y = (height - PAD) - ((v - min_ping) / (max_ping - min_ping)) * (height - PAD * 2)
            pts.extend([x, y])
        canvas.create_line(pts, fill=ACCENT, width=1, smooth=True)

        # Y-axis labels
        canvas.create_text(PAD - 2, height - PAD, text=f"{min_ping:.0f}",
                           fill=TEXT_MUTED, font=F_LABEL, anchor='e')
        canvas.create_text(PAD - 2, PAD, text=f"{max_ping:.0f}",
                           fill=TEXT_MUTED, font=F_LABEL, anchor='e')

    def manual_refresh(self):
        """Manually trigger a refresh"""
        self.status_label.config(text="Refreshing...")
        threading.Thread(target=self._manual_refresh_worker, daemon=True).start()

    def _manual_refresh_worker(self):
        """Worker for manual refresh"""
        data = self.collect_network_data()
        self.data_queue.put(data)

    def _update_minimal_speed(self, dl_text, ul_text):
        """Update download/upload labels in minimal view"""
        if hasattr(self, 'minimal_dl_label'):
            self.minimal_dl_label.config(text=dl_text)
        if hasattr(self, 'minimal_ul_label'):
            self.minimal_ul_label.config(text=ul_text)

    def _auto_speed_test(self):
        """Scheduled auto speed test at the configured interval"""
        self.run_speed_test()
        ms = self.config.get('speed_test_interval', 60) * 60 * 1000
        self.root.after(ms, self._auto_speed_test)

    def run_speed_test(self):
        """Start a speed test in a background thread"""
        if self._speed_testing:
            return
        self._speed_testing = True
        self.download_speed.set("Testing...")
        self.upload_speed.set("Testing...")
        if hasattr(self, 'speedtest_btn'):
            self.speedtest_btn.config(state='disabled')
        threading.Thread(target=self._speed_test_worker, daemon=True).start()

    def _speed_test_worker(self):
        """Download and upload speed test using timed HTTP transfers"""
        try:
            # --- Download test: fetch 5MB from Cloudflare speed test ---
            dl_url = "https://speed.cloudflare.com/__down?bytes=5000000"
            start = time.time()
            resp = requests.get(dl_url, timeout=30, stream=True)
            downloaded = 0
            for chunk in resp.iter_content(chunk_size=65536):
                downloaded += len(chunk)
            elapsed = time.time() - start
            dl_mbps = round((downloaded * 8) / (elapsed * 1_000_000), 1) if elapsed > 0 else 0

            # --- Upload test: POST 1MB to Cloudflare speed test ---
            ul_url = "https://speed.cloudflare.com/__up"
            payload = b'0' * 1_000_000
            start = time.time()
            requests.post(ul_url, data=payload, timeout=30)
            elapsed = time.time() - start
            ul_mbps = round((len(payload) * 8) / (elapsed * 1_000_000), 1) if elapsed > 0 else 0

            stamp = datetime.now().strftime("%H:%M")
            self.root.after(0, lambda: self.download_speed.set(f"{dl_mbps} Mbps"))
            self.root.after(0, lambda: self.upload_speed.set(f"{ul_mbps} Mbps"))
            self.root.after(0, lambda: self.speedtest_time_var.set(f"Speed test: last run {stamp}"))
            self.root.after(0, lambda: self._update_minimal_speed(f"{dl_mbps}↓", f" {ul_mbps}↑"))

        except Exception as e:
            self.root.after(0, lambda: self.download_speed.set("Failed"))
            self.root.after(0, lambda: self.upload_speed.set("Failed"))
            self.root.after(0, lambda: self.speedtest_time_var.set("Speed test: failed"))
            self.root.after(0, lambda: self._update_minimal_speed("Err↓", " Err↑"))
        finally:
            self._speed_testing = False
            if hasattr(self, 'speedtest_btn'):
                self.root.after(0, lambda: self.speedtest_btn.config(state='normal'))

    def show_config(self):
        """Show configuration dialog"""
        ConfigDialog(self.root, self.config, self.apply_config)

    def apply_autostart(self, enabled):
        """Add or remove NetDog from Windows startup registry key"""
        if platform.system() != 'Windows':
            return
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "NetDog"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path,
                                 0, winreg.KEY_SET_VALUE)
            if enabled:
                # Use the running EXE path when frozen, else skip
                exe_path = sys.executable if getattr(sys, 'frozen', False) else None
                if exe_path:
                    winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, f'"{exe_path}"')
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Auto-start error: {e}")

    def apply_config(self, new_config):
        """Apply new configuration"""
        prev_autostart = self.config.get('auto_start', False)
        self.config.update(new_config)
        self.save_config()

        # Update window opacity
        self.root.attributes('-alpha', self.config['opacity'])

        # Apply auto-start if the setting changed
        if self.config['auto_start'] != prev_autostart:
            self.apply_autostart(self.config['auto_start'])

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

        # Re-apply auto-start in case the EXE path changed (e.g. after a reinstall)
        if self.config.get('auto_start') and getattr(sys, 'frozen', False):
            self.apply_autostart(True)

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
                f.write("NetDog Network Diagnostics Export\n")
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
        self.parent = parent

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("NetDog — Configuration")
        self.dialog.geometry("420x520")
        self.dialog.minsize(380, 300)
        self.dialog.configure(bg=BG)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 210
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 260
        self.dialog.geometry(f"+{x}+{y}")

        self.create_widgets()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _section(self, parent, title):
        """Dark section header with rule"""
        f = tk.Frame(parent, bg=BG)
        f.pack(fill=tk.X, padx=12, pady=(12, 4))
        tk.Label(f, text=title, fg=ACCENT, bg=BG,
                 font=('Segoe UI', 7, 'bold')).pack(side=tk.LEFT)
        tk.Frame(f, bg=BORDER, height=1).pack(side=tk.LEFT, fill=tk.X,
                                              expand=True, padx=(6, 0), pady=3)

    def _label(self, parent, text):
        return tk.Label(parent, text=text, fg=TEXT_DIM, bg=BG, font=F_UI_SM,
                        anchor='w')

    def _slider(self, parent, from_, to, var, command=None):
        s = tk.Scale(parent, from_=from_, to=to, variable=var,
                     orient=tk.HORIZONTAL, length=260,
                     bg=BG, fg=TEXT, troughcolor=BG_CARD,
                     highlightthickness=0, bd=0,
                     activebackground=ACCENT, sliderrelief='flat',
                     command=command)
        return s

    # ── layout ───────────────────────────────────────────────────────────────

    def create_widgets(self):
        # ── Fixed button bar at bottom ─────────────────────────────────────
        btn_bar = tk.Frame(self.dialog, bg=BG_PANEL)
        btn_bar.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Frame(btn_bar, bg=BORDER, height=1).pack(fill=tk.X)
        btn_inner = tk.Frame(btn_bar, bg=BG_PANEL)
        btn_inner.pack(fill=tk.X, padx=8, pady=6)

        def _btn(parent, text, cmd):
            b = tk.Button(parent, text=text, command=cmd,
                          fg=TEXT_DIM, bg=BG_PANEL, font=F_UI_SM,
                          relief='flat', bd=0, cursor='hand2',
                          activebackground=BORDER, activeforeground=TEXT,
                          padx=12, pady=4)
            b.bind('<Enter>', lambda e: b.config(fg=TEXT, bg=BG_CARD))
            b.bind('<Leave>', lambda e: b.config(fg=TEXT_DIM, bg=BG_PANEL))
            return b

        _btn(btn_inner, "Reset Defaults", self.reset_defaults).pack(side=tk.LEFT)
        _btn(btn_inner, "Cancel", self.cancel_clicked).pack(side=tk.RIGHT)
        _btn(btn_inner, "Save", self.ok_clicked).pack(side=tk.RIGHT, padx=(0, 4))

        # ── Scrollable content area ────────────────────────────────────────
        container = tk.Frame(self.dialog, bg=BG)
        container.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(container, bg=BG, highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(container, orient='vertical',
                                 command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=BG)
        inner_id = canvas.create_window((0, 0), window=inner, anchor='nw')

        def on_resize(e):
            canvas.itemconfig(inner_id, width=e.width)
        canvas.bind('<Configure>', on_resize)

        def on_frame_configure(e):
            canvas.configure(scrollregion=canvas.bbox('all'))
        inner.bind('<Configure>', on_frame_configure)

        # Mouse wheel scrolling
        def on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), 'units')
        canvas.bind_all('<MouseWheel>', on_mousewheel)
        self.dialog.bind('<Destroy>', lambda e: canvas.unbind_all('<MouseWheel>'))

        # ── NETWORK ───────────────────────────────────────────────────────
        self._section(inner, "NETWORK")

        self._label(inner, "Ping targets (one per line):").pack(anchor='w', padx=14)
        self.ping_targets_text = tk.Text(inner, height=3, width=36,
                                         bg=BG_CARD, fg=TEXT, font=F_MONO_SM,
                                         insertbackground=TEXT, relief='flat',
                                         highlightbackground=BORDER,
                                         highlightthickness=1)
        self.ping_targets_text.pack(fill=tk.X, padx=14, pady=(4, 0))
        self.ping_targets_text.insert(tk.END, '\n'.join(self.config['ping_targets']))

        self._label(inner, "Ping timeout (seconds):").pack(anchor='w', padx=14, pady=(8, 0))
        self.ping_timeout_var = tk.StringVar(value=str(self.config['ping_timeout']))
        tk.Entry(inner, textvariable=self.ping_timeout_var, width=8,
                 bg=BG_CARD, fg=TEXT, font=F_MONO_SM, relief='flat',
                 insertbackground=TEXT,
                 highlightbackground=BORDER, highlightthickness=1
                 ).pack(anchor='w', padx=14, pady=(4, 0))

        # ── UPDATE ────────────────────────────────────────────────────────
        self._section(inner, "UPDATE INTERVALS")

        self._label(inner, "Ping refresh (seconds):").pack(anchor='w', padx=14)
        self.refresh_var = tk.IntVar(value=int(self.config['refresh_interval']))
        refresh_val_lbl = tk.Label(inner, text="", fg=ACCENT, bg=BG, font=F_MONO_SM)
        refresh_val_lbl.pack(anchor='w', padx=14)

        def on_refresh(v):
            refresh_val_lbl.config(text=f"{int(float(v))} sec")
        self._slider(inner, 1, 60, self.refresh_var, on_refresh).pack(
            anchor='w', padx=14, pady=(2, 0))
        on_refresh(self.refresh_var.get())

        self._label(inner, "Auto speed test (minutes):").pack(
            anchor='w', padx=14, pady=(10, 0))
        self.speed_interval_var = tk.IntVar(
            value=self.config.get('speed_test_interval', 60))
        speed_val_lbl = tk.Label(inner, text="", fg=ACCENT, bg=BG, font=F_MONO_SM)
        speed_val_lbl.pack(anchor='w', padx=14)

        def on_speed(v):
            mins = int(float(v))
            mb = int((1440 / mins) * 6)
            speed_val_lbl.config(text=f"{mins} min  (~{mb} MB/day)")
        self._slider(inner, 15, 120, self.speed_interval_var, on_speed).pack(
            anchor='w', padx=14, pady=(2, 0))
        on_speed(self.speed_interval_var.get())

        # ── APPEARANCE ────────────────────────────────────────────────────
        self._section(inner, "APPEARANCE")

        self._label(inner, "Window opacity:").pack(anchor='w', padx=14)
        self.opacity_var = tk.DoubleVar(value=self.config['opacity'])
        opacity_val_lbl = tk.Label(inner, text="", fg=ACCENT, bg=BG, font=F_MONO_SM)
        opacity_val_lbl.pack(anchor='w', padx=14)

        def on_opacity(v):
            val = round(float(v), 2)
            opacity_val_lbl.config(text=f"{val:.0%}")
            try:
                self.parent.attributes('-alpha', max(0.1, val))
            except Exception:
                pass

        opacity_scale = self._slider(inner, 0.1, 1.0, self.opacity_var, on_opacity)
        opacity_scale.config(resolution=0.01, digits=3)
        opacity_scale.pack(anchor='w', padx=14, pady=(2, 0))
        on_opacity(self.opacity_var.get())

        # ── VIEW ──────────────────────────────────────────────────────────
        self._section(inner, "DEFAULT VIEW")

        self.view_mode_var = tk.StringVar(value=self.config['view_mode'])
        view_row = tk.Frame(inner, bg=BG)
        view_row.pack(anchor='w', padx=14, pady=(4, 0))
        for mode in ('minimal', 'compact', 'detailed'):
            tk.Radiobutton(view_row, text=mode.title(),
                           variable=self.view_mode_var, value=mode,
                           bg=BG, fg=TEXT_DIM, selectcolor=BG_CARD,
                           activebackground=BG, activeforeground=TEXT,
                           font=F_UI_SM).pack(side=tk.LEFT, padx=(0, 12))

        # ── STARTUP ───────────────────────────────────────────────────────
        self._section(inner, "STARTUP")

        self.autostart_var = tk.BooleanVar(value=self.config['auto_start'])
        tk.Checkbutton(inner, text="Start with Windows",
                       variable=self.autostart_var,
                       bg=BG, fg=TEXT_DIM, selectcolor=BG_CARD,
                       activebackground=BG, activeforeground=TEXT,
                       font=F_UI_SM).pack(anchor='w', padx=14, pady=(4, 12))

    def ok_clicked(self):
        """Handle OK button click"""
        try:
            targets = [t.strip() for t in
                       self.ping_targets_text.get('1.0', tk.END).strip().split('\n')
                       if t.strip()]
            self.config['ping_targets'] = targets or ['8.8.8.8', '1.1.1.1']
            self.config['ping_timeout'] = max(1, int(float(self.ping_timeout_var.get())))
            self.config['refresh_interval'] = max(1, int(self.refresh_var.get()))
            self.config['speed_test_interval'] = max(15, min(120, int(self.speed_interval_var.get())))
            self.config['opacity'] = round(max(0.1, min(1.0, float(self.opacity_var.get()))), 2)
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
            'speed_test_interval': 60,
            'theme': 'light',
            'opacity': 0.9,
            'auto_start': False,
            'view_mode': 'compact'
        }

        self.ping_targets_text.delete('1.0', tk.END)
        self.ping_targets_text.insert(tk.END, '\n'.join(defaults['ping_targets']))
        self.ping_timeout_var.set(str(defaults['ping_timeout']))
        self.refresh_var.set(defaults['refresh_interval'])
        self.speed_interval_var.set(defaults['speed_test_interval'])
        self.opacity_var.set(defaults['opacity'])
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