import tkinter as tk
from tkinter import ttk, scrolledtext, font, messagebox
import xmlrpc.client
import threading
import zmq
import numpy as np
import json
import sys
import time
import os
from scipy import signal

# --- CONFIGURATION ---
GRC_HOST = "http://127.0.0.1:8080"
ZMQ_AUDIO_PORT = "5555"
ZMQ_METRICS_PORT = "5557"
AI_RATE = 16000

# --- LIBRARY HANDLING ---
import ctypes
HAS_SCANNER = False
if sys.platform == "darwin":
    try:
        os.environ["DYLD_LIBRARY_PATH"] = "/opt/homebrew/lib:" + os.environ.get("DYLD_LIBRARY_PATH", "")
        ctypes.CDLL("/opt/homebrew/lib/librtlsdr.dylib")
    except: pass

try:
    from rtlsdr import RtlSdr
    HAS_SCANNER = True
except: HAS_SCANNER = False

# --- AI IMPORTS ---
try:
    import noisereduce as nr
    HAS_NOISEREDUCE = True
except: HAS_NOISEREDUCE = False

try:
    from vosk import Model, KaldiRecognizer, SetLogLevel
    from deep_translator import GoogleTranslator
    AI_ENABLED = True
    SetLogLevel(-1)
except: AI_ENABLED = False

class SmartCommander:
    def __init__(self, root):
        self.root = root
        self.root.title("TOKYO SIGINT v32 (Full Database)")
        self.root.geometry("580x980")
        self.root.configure(bg="#121212")
        
        self.is_running = True
        self.detected_stations = []
        self.gate_threshold = 0.02 # Default Squelch
        self.silence_timer = 0
        self.last_partial_time = 0

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background="#121212")
        style.configure("TProgressbar", thickness=10)
        
        # --- HEADER ---
        header = tk.Frame(root, bg="#121212", pady=15)
        header.pack(fill="x", padx=20)
        tk.Label(header, text="TOKYO SIGINT", font=("Helvetica", 20, "bold"), bg="#121212", fg="#e0e0e0").pack(anchor="w")
        self.lbl_status = tk.Label(header, text="System Online", font=("Helvetica", 10), bg="#121212", fg="#888")
        self.lbl_status.pack(anchor="w")

        # --- SIGNAL INTELLIGENCE PANEL ---
        metric_frame = tk.Frame(root, bg="#1e1e1e", pady=10, padx=15)
        metric_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        m_grid = tk.Frame(metric_frame, bg="#1e1e1e")
        m_grid.pack(fill="x")
        
        # SNR
        tk.Label(m_grid, text="SNR QUALITY:", font=("Arial", 8), bg="#1e1e1e", fg="#aaa").grid(row=0, column=0, sticky="w")
        self.lbl_snr = tk.Label(m_grid, text="0 dB", font=("Arial", 9, "bold"), bg="#1e1e1e", fg="white")
        self.lbl_snr.grid(row=0, column=1, sticky="e", padx=10)
        self.bar_snr = ttk.Progressbar(m_grid, orient="horizontal", length=200, mode="determinate")
        self.bar_snr.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        
        # Coherency
        tk.Label(m_grid, text="SIGNAL TYPE:", font=("Arial", 8), bg="#1e1e1e", fg="#aaa").grid(row=2, column=0, sticky="w")
        self.lbl_coh = tk.Label(m_grid, text="Unknown", font=("Arial", 9, "bold"), bg="#1e1e1e", fg="white")
        self.lbl_coh.grid(row=2, column=1, sticky="e", padx=10)
        self.bar_coh = ttk.Progressbar(m_grid, orient="horizontal", length=200, mode="determinate")
        self.bar_coh.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 15))

        # --- SQUELCH SLIDER ---
        tk.Label(m_grid, text="POWER SQUELCH (Gate):", font=("Arial", 8, "bold"), bg="#1e1e1e", fg="#03dac6").grid(row=4, column=0, sticky="w")
        self.sq_val_label = tk.Label(m_grid, text="0.020", font=("Courier", 9), bg="#1e1e1e", fg="#03dac6")
        self.sq_val_label.grid(row=4, column=1, sticky="e")
        
        self.sld_squelch = tk.Scale(m_grid, from_=0.001, to=0.5, resolution=0.001, orient="horizontal",
                                    bg="#1e1e1e", fg="#888", highlightthickness=0, troughcolor="#333",
                                    showvalue=0, command=self.update_squelch)
        self.sld_squelch.set(0.02)
        self.sld_squelch.grid(row=5, column=0, columnspan=2, sticky="ew")
        
        m_grid.columnconfigure(0, weight=1)

        # --- CONTROLS ---
        ctrl = tk.Frame(root, bg="#121212")
        ctrl.pack(fill="x", padx=20, pady=10)
        
        self.var_ai = tk.IntVar(value=1 if HAS_NOISEREDUCE else 0)
        tk.Checkbutton(ctrl, text="AI Denoise", variable=self.var_ai, bg="#121212", fg="#03dac6",
                       selectcolor="#121212", font=("Arial", 9, "bold")).pack(side="right")
        
        self.btn_scan = tk.Button(ctrl, text="SMART SCAN", command=self.start_scan_thread,
                                  bg="#333", fg="white", font=("Arial", 10, "bold"), relief="flat", padx=15)
        self.btn_scan.pack(side="left")

        # --- STATION LIST ---
        list_container = tk.LabelFrame(root, text="DETECTED STATIONS", bg="#121212", fg="#888", font=("Arial", 9, "bold"))
        list_container.pack(fill="x", padx=20, pady=5)
        self.canvas_list = tk.Canvas(list_container, bg="#121212", highlightthickness=0, height=140)
        self.scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.canvas_list.yview)
        self.scroll_frame = ttk.Frame(self.canvas_list, style="TFrame")
        self.scroll_frame.bind("<Configure>", lambda e: self.canvas_list.configure(scrollregion=self.canvas_list.bbox("all")))
        self.canvas_window = self.canvas_list.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        self.canvas_list.configure(yscrollcommand=self.scrollbar.set)
        self.canvas_list.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.scrollbar.pack(side="right", fill="y", pady=5)
        def _on_mousewheel(event): self.canvas_list.yview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas_list.bind_all("<MouseWheel>", _on_mousewheel)

        # --- TRANSCRIPT ---
        tk.Label(root, text="LIVE TRANSCRIPT", font=("Arial", 9, "bold"), bg="#121212", fg="#888").pack(pady=(10,0))
        self.txt_display = scrolledtext.ScrolledText(root, bg="black", fg="white", font=("Helvetica", 13), height=8)
        self.txt_display.pack(fill="both", expand=True, padx=20, pady=5)
        self.txt_display.tag_config("jp", foreground="#ffffff", font=("Hiragino Sans", 13, "bold"))
        self.txt_display.tag_config("en", foreground="#03dac6", font=("Helvetica", 11, "italic"))
        self.lbl_subtitle = tk.Label(root, text="Listening...", font=("Hiragino Sans", 14), bg="#222", fg="#888", height=2, wraplength=500)
        self.lbl_subtitle.pack(fill="x", side="bottom")

        self.connect_systems()
        if AI_ENABLED: threading.Thread(target=self.setup_vosk, daemon=True).start()

    def update_squelch(self, val):
        self.gate_threshold = float(val)
        self.sq_val_label.config(text=f"{self.gate_threshold:.3f}")

    def update_metrics(self, snr, coh):
        try:
            snr_clamped = max(0, min(snr, 30))
            self.bar_snr['value'] = (snr_clamped / 30) * 100
            self.lbl_snr.config(text=f"{snr:.1f} dB")
            self.bar_coh['value'] = coh * 100
            if coh < 0.3: state, color = "STATIC / NOISE", "#555"
            elif coh < 0.6: state, color = "WEAK / UNSTABLE", "orange"
            else: state, color = "VOICE / MUSIC", "#00ff00"
            self.lbl_coh.config(text=f"{state} ({coh:.2f})", fg=color)
        except: pass

    def listen_metrics(self):
        ctx = zmq.Context()
        sock = ctx.socket(zmq.SUB)
        sock.connect(f"tcp://127.0.0.1:{ZMQ_METRICS_PORT}")
        sock.setsockopt_string(zmq.SUBSCRIBE, "")
        while self.is_running:
            try:
                if sock.poll(50):
                    data = np.frombuffer(sock.recv(), dtype=np.float32)
                    if len(data) >= 2:
                        self.root.after(0, lambda s=np.mean(data[0::2]), c=np.mean(data[1::2]): self.update_metrics(s, c))
            except: pass

    def listen_audio(self):
        ctx = zmq.Context()
        sock = ctx.socket(zmq.SUB)
        sock.connect(f"tcp://127.0.0.1:{ZMQ_AUDIO_PORT}")
        sock.setsockopt_string(zmq.SUBSCRIBE, "")
        while self.is_running:
            try:
                if sock.poll(10):
                    audio_raw = np.frombuffer(sock.recv(), dtype=np.float32)
                    audio_16k = audio_raw[::3]
                    
                    if HAS_NOISEREDUCE and self.var_ai.get() == 1:
                        try: audio_16k = nr.reduce_noise(y=audio_16k, sr=16000, stationary=False)
                        except: pass
                    
                    vol = np.sqrt(np.mean(audio_16k**2))
                    if vol < self.gate_threshold:
                        self.silence_timer += 1
                        if self.silence_timer == 75 and AI_ENABLED:
                            try:
                                res = json.loads(self.rec.FinalResult())
                                if res['text']: self.handle_final(res['text'])
                            except: pass
                    else:
                        self.silence_timer = 0
                        if AI_ENABLED:
                            pcm = (np.clip(audio_16k * 3.0, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
                            if self.rec.AcceptWaveform(pcm):
                                res = json.loads(self.rec.Result())
                                if res['text']: self.handle_final(res['text'])
                            elif time.time() - self.last_partial_time > 0.3:
                                res = json.loads(self.rec.PartialResult())
                                if res['partial']:
                                    self.root.after(0, lambda t=res['partial']: self.lbl_subtitle.config(text=t, fg="#888"))
                                    self.last_partial_time = time.time()
            except: pass

    def start_scan_thread(self):
        self.btn_scan.config(state="disabled", bg="#555")
        threading.Thread(target=self.perform_scan, daemon=True).start()

    # --- FULL TOKYO SCANNER ---
    def perform_scan(self):
        if not HAS_SCANNER:
            messagebox.showerror("Scanner Error", "Librtlsdr not loaded.")
            return

        self.root.after(0, lambda: self.lbl_status.config(text="Scanning..."))
        detected = []
        try:
            sdr = RtlSdr()
            sdr.sample_rate = 2.4e6
            sdr.gain = 35
            
            freq_hz = 76.0 * 1e6
            stop_hz = 95.5 * 1e6 # Increased to cover Wide FM (95.0)
            step_size = 2e6

            while freq_hz < stop_hz:
                sdr.center_freq = freq_hz + (step_size/2)
                time.sleep(0.1)
                samples = sdr.read_samples(256*1024)
                
                if np.mean(np.abs(samples)) == 0:
                    raise ValueError("Device returning zeros.")

                # Welch Periodogram + FFT Shift Logic
                f, Pxx = signal.welch(samples, sdr.sample_rate, nperseg=2048)
                f = np.fft.fftshift(f)
                Pxx_db = 10 * np.log10(np.fft.fftshift(Pxx) + 1e-12)
                
                # Adaptive Threshold
                floor = np.median(Pxx_db)
                peaks, _ = signal.find_peaks(Pxx_db, height=floor+6, prominence=3, distance=50)
                
                for p in peaks:
                    mhz = round(((freq_hz + (step_size/2)) + f[p]) / 1e6, 1)
                    if 76.0 <= mhz <= 95.0: detected.append((mhz, Pxx_db[p]))
                
                freq_hz += step_size
            sdr.close()
            
            # De-Duplication
            unique = {}
            for f, p in detected:
                matched = False
                for ex_f in list(unique.keys()):
                    if abs(f - ex_f) <= 0.2:
                        matched = True
                        if p > unique[ex_f]: del unique[ex_f]; unique[f] = p
                        break
                if not matched: unique[f] = p
            
            # --- TOKYO RADIO DATABASE ---
            STATION_DB = {
                78.0: "bayfm (Chiba)",
                79.5: "NACK5 (Saitama)",
                80.0: "TOKYO FM",
                81.3: "J-WAVE",
                82.5: "NHK-FM",
                84.7: "FM Yokohama",
                89.7: "InterFM897",
                90.5: "TBS Radio (Wide FM)",
                91.6: "Bunka Hoso (Wide FM)",
                93.0: "Nippon Hoso (Wide FM)"
            }
            
            self.detected_stations = sorted([(f, STATION_DB.get(f, "Unknown"), p) for f, p in unique.items()])
            self.root.after(0, self.update_list)
            
        except Exception as e:
            print(f"Scan Error: {e}")
            if "busy" in str(e).lower():
                self.root.after(0, lambda: messagebox.showwarning("Device Busy", "Stop GNU Radio first!"))
        finally:
            self.root.after(0, lambda: self.lbl_status.config(text="Scan Complete"))
            self.root.after(0, lambda: self.btn_scan.config(state="normal", bg="#333"))

    def update_list(self):
        for w in self.scroll_frame.winfo_children(): w.destroy()
        if not self.detected_stations:
             tk.Label(self.scroll_frame, text="No Stations Found", bg="#121212", fg="#555").pack(pady=20)
             
        for f, n, p in self.detected_stations:
            card = tk.Frame(self.scroll_frame, bg="#1e1e1e", pady=10, padx=15)
            card.pack(fill="x", pady=2)
            tk.Label(card, text=f"{n}", font=("Arial", 11, "bold"), bg="#1e1e1e", fg="white").pack(side="left")
            tk.Label(card, text=f" {f} MHz", font=("Arial", 10), bg="#1e1e1e", fg="#03dac6").pack(side="left")
            tk.Label(card, text=f"({p:.0f}dB)", font=("Arial", 8), bg="#1e1e1e", fg="#555").pack(side="left", padx=5)
            tk.Button(card, text="TUNE", command=lambda freq=f: self.tune(freq), bg="#333", fg="white", font=("Arial", 8), relief="flat").pack(side="right")

    def tune(self, freq):
        try: self.radio_control.set_cent_freq(float(freq * 1e6)); self.lbl_status.config(text=f"RX: {freq} MHz")
        except: pass

    def handle_final(self, text):
        self.root.after(0, lambda: self.lbl_subtitle.config(text=text, fg="white"))
        threading.Thread(target=lambda: self.commit_to_log(text, self.translator.translate(text)), daemon=True).start()

    def commit_to_log(self, jp, en):
        self.txt_display.insert(tk.END, f"{jp}\n", "jp")
        self.txt_display.insert(tk.END, f"{en}\n\n", "en")
        self.txt_display.see(tk.END)

    def setup_vosk(self):
        try:
            if not os.path.exists("model"): return
            self.model = Model("model")
            self.rec = KaldiRecognizer(self.model, AI_RATE)
            self.translator = GoogleTranslator(source='ja', target='en')
            self.root.after(0, lambda: self.lbl_status.config(text="AI Engine Ready"))
        except: pass

    def connect_systems(self):
        try:
            self.radio_control = xmlrpc.client.ServerProxy(GRC_HOST)
            threading.Thread(target=self.listen_audio, daemon=True).start()
            threading.Thread(target=self.listen_metrics, daemon=True).start()
        except: pass

if __name__ == "__main__":
    root = tk.Tk()
    app = SmartCommander(root)
    root.mainloop()
