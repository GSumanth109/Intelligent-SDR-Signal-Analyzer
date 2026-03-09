import numpy as np
from gnuradio import gr

class signal_analyzer(gr.sync_block):
    """
    Analyzes Audio to extract SNR (dB) and Coherency (0-1).
    Output 0: SNR (Signal Quality)
    Output 1: Coherency (Signal Stability/Type)
    """
    def __init__(self, alpha=0.001):
        gr.sync_block.__init__(self,
            name="Signal Analyzer",
            in_sig=[np.float32],      # Input: Audio
            out_sig=[np.float32, np.float32]) # Outputs: [SNR, Coherency]

        self.alpha = alpha
        self.noise_floor = 0.001

    def work(self, input_items, output_items):
        in0 = input_items[0]
        out_snr = output_items[0]
        out_coh = output_items[1]

        # --- 1. SNR CALCULATION ---
        # Get magnitude of current audio chunk
        mags = np.abs(in0)
        current_avg = np.mean(mags)
        
        # Fast-Attack / Slow-Decay for Noise Floor Tracking
        if current_avg < self.noise_floor:
            self.noise_floor = current_avg # Found new silence
        else:
            self.noise_floor = self.noise_floor * (1.0 + self.alpha) # Drift up slowly

        # Avoid divide by zero
        if self.noise_floor < 1e-9: self.noise_floor = 1e-9
        
        # Calculate SNR in dB
        snr = 20 * np.log10(current_avg / self.noise_floor + 1e-9)

        # --- 2. COHERENCY (Auto-Correlation) ---
        # "Lag 1" Auto-correlation: compares sample[i] with sample[i-1]
        if len(in0) > 1:
            # Multiply signal by itself shifted by 1
            cross_prod = np.mean(in0[1:] * in0[:-1])
            # Normalize by power (variance)
            power = np.mean(in0**2) + 1e-12
            coherency = np.abs(cross_prod / power)
        else:
            coherency = 0.0

        # --- OUTPUT ---
        out_snr[:] = snr
        out_coh[:] = coherency 

        return len(in0)
