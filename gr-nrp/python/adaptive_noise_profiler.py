import numpy as np
from gnuradio import gr
import pmt

class adaptive_noise_profiler(gr.sync_block):
    """
    Adaptive Noise Profiler Block
    """
    def __init__(self, fft_size=512, rms_threshold=0.01, avg_alpha=0.95):
        gr.sync_block.__init__(
            self,
            name="Adaptive Noise Profiler",
            in_sig=[np.float32],
            out_sig=[np.float32]
        )

        self.fft_size = fft_size
        self.rms_threshold = rms_threshold
        self.avg_alpha = avg_alpha

        self.buffer = np.zeros(self.fft_size, dtype=np.float32)
        self.buf_idx = 0

        # FIX: rfft returns fft_size//2 + 1 bins
        self.noise_profile = np.zeros(self.fft_size // 2 + 1)

        # Register the message port so it actually works
        self.message_port_register_out(pmt.intern("noise_profile"))

    def work(self, input_items, output_items):
        inp = input_items[0]
        out = output_items[0]
        
        # Pass-through input to output
        out[:] = inp[:]
        
        for sample in inp:
            self.buffer[self.buf_idx] = sample
            self.buf_idx += 1
            
            if self.buf_idx >= self.fft_size:
                self.buf_idx = 0
                rms = np.sqrt(np.mean(self.buffer ** 2))
                
                if rms < self.rms_threshold:
                    # Apply Window
                    windowed_buf = self.buffer * np.hanning(self.fft_size)
                    fft = np.fft.rfft(windowed_buf)
                    mag = np.abs(fft)
                    
                    # Update average
                    self.noise_profile = (self.avg_alpha * self.noise_profile + 
                                        (1 - self.avg_alpha) * mag)
                    
                    # Publish Message
                    msg = pmt.init_f32vector(len(self.noise_profile), 
                                           self.noise_profile.astype(np.float32))
                    self.message_port_pub(pmt.intern("noise_profile"), msg)

        return len(out)
