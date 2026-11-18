"""Sonda CPython de sólo lectura: observa llamadas/retornos reales, no sustituye funciones."""
from pathlib import Path

import numpy as np

from medidas import sha


def peak(x):
    return float(np.max(np.abs(x)))


class Observer:
    def __init__(self, mod, block, extra):
        self.block, self.extra = block, extra
        self.globals = mod.__dict__
        self.probe = (mod.apply_mask if block == 'A' else mod.CandidateMetrics.update_freq).__code__
        self.masks, self.chunks, self.guide_inputs, self.scale, self.errors = [], [], [], [], []
        self.energy = self.weighted = 0.
        self.raw = {}

    def __call__(self, frame, event, arg):
        if event not in ('call','return') or frame.f_globals is not self.globals:
            return
        code = frame.f_code
        try:
            if self.block == 'A':
                if event == 'return' and code is self.probe and arg is not None:
                    loc = frame.f_locals
                    raw = loc['mv'] / (loc['mv'] + loc['mi'] + loc['eps'])
                    check = raw if loc['mask_mode'] == 'per_channel' else raw.mean(axis=0, keepdims=True)
                    self.observe(loc['m'], loc['mix_stft'], arg[0], arg[1], loc['Vc'], loc['Ic'],
                                 dict(branch=loc['branch'], mask_mode=loc['mask_mode'],
                                      pre_share_formula_max_error=peak(loc['m']-check)), frame.f_back.f_locals['f0'])
            elif event == 'call' and code is self.probe:
                parent = frame.f_back.f_locals
                opt = parent['opt']
                if parent['runner'].mask_source == ('consensus', opt.consensus_default):
                    loc = frame.f_locals
                    self.observe(parent['mv_c'], loc['mix_stft'], loc['sdv_stft'], loc['sdi_stft'],
                                 parent['V_stft'], parent['I_stft'],
                                 dict(mask_mode=getattr(opt, 'mask_mode', None),
                                      consensus_order=getattr(opt, 'consensus_order', None),
                                      use_physical_residuals=getattr(opt, 'use_physical_residuals', None)), parent['f0'])
            elif event == 'call' and code.co_name == 'stft_span_frames':
                self.observe_guide(frame.f_locals['x2d'], frame.f_back.f_locals)
            elif self.block == 'C' and event == 'return' and code.co_name == 'analyze_guide_scale' and arg:
                self.scale.append(dict(pair_id=arg[0]['pair_id'], factors=arg[1],
                                       raw_ls={k:arg[0][k]['raw_g_ls'] for k in ('vocal','instrumental')}))
            elif self.block == 'C' and self.extra and event == 'return' and code.co_name == 'read_span' and arg is not None:
                self.raw[Path(frame.f_locals['handle'].name).resolve()] = arg.copy()
        except Exception as exc:
            # Una falla de observación no modifica ni interrumpe el motor.
            err = f'{code.co_name}: {type(exc).__name__}: {exc}'
            if err not in self.errors:
                self.errors.append(err)

    def observe_guide(self, x, parent):
        for key, role in [('v','vocal'), ('i','instrumental')]:
            span = parent.get(key+'_span')
            mono = parent.get(key+'_mono')
            if span is None or mono is None:
                continue
            stereo = x is span
            if not stereo and not np.shares_memory(x, mono):
                continue
            pair = parent['p']
            expected = span if stereo else span.mean(axis=1, keepdims=True)
            entry = dict(f0=parent['f0'], pair=pair.pair_id, role=role, guide_shape=list(span.shape),
                         stft_input_shape=list(x.shape), relation='stereo' if stereo else '(L+R)/2',
                         relation_max_error=peak(x-expected), input_peak=peak(x), stereo_span_peak=peak(span))
            if self.block == 'C' and self.extra:
                raw = self.raw[Path(getattr(pair, role+'_path')).resolve()]
                sign = parent['scale_factors'][pair.pair_id][role+'_polarity']
                entry.update(sign=sign, span_minus_sign_times_read_max=peak(span-sign*raw),
                             span_minus_unmodified_read_max=peak(span-raw))
            self.guide_inputs.append(entry)
            return

    def observe(self, m, x, v, i, vg, ig, config, f0):
        self.masks.append(m.copy())
        eff = m[None, :, :] if m.ndim == 2 else m
        if eff.shape[0] == 2:
            delta2 = (eff[0]-eff[1])**2
            energy = (np.abs(x)**2).sum(axis=0)
            self.weighted += float((energy * delta2).sum())
            self.energy += float(energy.sum())
        self.chunks.append(dict(f0=f0, config=config, mask_shape=list(m.shape), mix_stft_shape=list(x.shape),
                                V_stft_shape=list(vg.shape), I_stft_shape=list(ig.shape),
                                SDV_stft_shape=list(v.shape), SDI_stft_shape=list(i.shape),
                                max_abs_SDV_minus_XM=peak(v-x*eff),
                                max_abs_SDI_minus_X1mM=peak(i-x*(1.-eff))))

    def finish(self, path):
        result = dict(chunks=self.chunks, guide_inputs=self.guide_inputs, polarity=self.scale, errors=self.errors)
        if not self.masks:
            return result
        m = np.concatenate(self.masks, axis=-1)
        np.save(path, m, allow_pickle=False)  # valores reales y forma nativa, sin cast ni promediado
        a = m[None, :, :] if m.ndim == 2 else m
        shared = a.shape[0] == 1
        delta = np.zeros_like(a[0]) if shared else a[0]-a[1]
        result.update(shape=list(m.shape), dtype=str(m.dtype), shared=shared,
                      nonfinite=int((~np.isfinite(m)).sum()), mask_npy_sha256=sha(path.read_bytes()),
                      stats=[dict(min=float(ch.min()), max=float(ch.max()), mean=float(ch.mean()), std=float(ch.std())) for ch in a],
                      lr_max=peak(delta), lr_rms=float(np.sqrt(np.mean(delta**2))),
                      lr_mix_energy_weighted_rms=float(np.sqrt(self.weighted/self.energy)) if self.energy else 0.)
        return result
