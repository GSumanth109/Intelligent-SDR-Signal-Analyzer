#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2026 sumanth.
#
# SPDX-License-Identifier: GPL-3.0-or-later
#


import numpy
from gnuradio import gr

class adaptive_noise_profiler(gr.sync_block):
    """
    docstring for block adaptive_noise_profiler
    """
    def __init__(self, fft_size=512, rms_threshold=0.01, avg_alpha=0.95):
        gr.sync_block.__init__(self,
            name="adaptive_noise_profiler",
            in_sig=[<+numpy.float32+>, ],
            out_sig=[<+numpy.float32+>, ])


    def work(self, input_items, output_items):
        in0 = input_items[0]
        out = output_items[0]
        # <+signal processing here+>
        out[:] = in0
        return len(output_items[0])
