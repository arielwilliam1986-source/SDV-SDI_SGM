"""6F: atribución temporal conservadora, sin edición de audio ni corrección.

Cambios respecto de 6E (sólo diagnóstico):

* Ventanas solapadas en lugar de bloques contiguos, y mitades degeneradas
  (silencio/constante) descartadas en lugar de invalidar la ventana completa:
  recupera retardos uniformes cuyo borde contiene silencio (caso 567 de 6E).
* La réplica rival se contrasta con una prueba de hipótesis explícita
  (coeficiente de regresión y su error estándar, estadístico t) en vez de
  comparar una correlación normalizada contra un umbral derivado de un tamaño
  efectivo sesgado. La multiplicidad se cuenta sobre los picos examinados, no
  sobre todas las posiciones del barrido.
* Se publica la capacidad de detección del caso (`replica_detection_floor`,
  mínima amplitud relativa de réplica detectable) y se abstiene cuando esa
  capacidad es pobre; no se declara UNIQUE por defecto.
* Los lóbulos de la autocorrelación de la guía se tratan como ambigüedad
  estructural: nunca como réplica real ni como ruido.
* El agregado L/R informa desacuerdos entre canales y no los convierte en un
  retardo común.

Convención heredada: M[t] ~ G[t-k]; d = -k. Nunca se aplica shift.
"""
import math
import os
from statistics import NormalDist

import numpy as np
from scipy.signal import correlate

from wav_integridad_6f import WaveError, check_unchanged, verify_wave  # verify_wave: reexport 6F
from audio_integridad_6g import open_audio as open_validated

WINDOWS = 6
MIN_HALF = 2048
MIN_FIT = 512
SUPPORT_MIN_RHO = 0.20
SCREEN_RHO = 0.02
CAPABILITY_MAX_MDR = 0.35
ALPHA = 1e-3
PEAK_LIMIT = 6
STRUCTURAL_ACF = 0.50


def _r(x, nd=6):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if not math.isfinite(v) else round(v, nd)


def _curve(mix, tpl, s, radius):
    """rho(q) con q = índice de guía - índice de mix, en el rango pedido.

    Sólo posiciones con solape completo de la plantilla; la energía del mix se
    normaliza localmente, así que un lóbulo lateral pequeño no se amplifica.
    """
    na, nb = len(mix), len(tpl)
    if nb < 1 or na < nb:
        return None
    u_lo = max(0, s - radius)
    u_hi = min(na - nb, s + radius)
    if u_hi < u_lo:
        return None
    c = correlate(mix, tpl, mode='valid', method='fft')
    seg = c[u_lo:u_hi + 1]
    cs = np.r_[0.0, np.cumsum(mix * mix)]
    energy = cs[u_lo + nb:u_hi + 1 + nb] - cs[u_lo:u_hi + 1]
    den = np.sqrt(np.maximum(energy, 0.0) * float(np.dot(tpl, tpl)))
    rho = np.divide(seg, den, out=np.zeros_like(seg), where=den > 0)
    return (u_lo - s), np.clip(rho, -1.0, 1.0)


def _acf(tpl):
    x = tpl - tpl.mean()
    p = float(np.dot(x, x))
    if p <= 0:
        return None
    a = correlate(x, x, mode='full', method='fft')[len(x) - 1:]
    return a / p


def _peaks(rho, q0_index, floor, limit=PEAK_LIMIT):
    absr = np.abs(rho)
    if not len(absr):
        return []
    eligible = absr >= floor
    if not eligible.any():
        return []
    left = np.r_[True, absr[1:] >= absr[:-1]]
    right = np.r_[absr[:-1] >= absr[1:], True]
    idx = np.flatnonzero(eligible & left & right)
    order = idx[np.argsort(-absr[idx], kind='stable')]
    picked = []
    for i in order:
        if abs(int(i) - q0_index) <= 1:
            continue
        if all(abs(int(i) - j) > 1 for j in picked):
            picked.append(int(i))
        if len(picked) >= limit:
            break
    return picked


def _tstat(y, cols):
    n = len(y)
    k = len(cols) + 1
    if n < max(MIN_FIT, 8 * k):
        return None
    X = np.column_stack([np.ones(n)] + list(cols))
    try:
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ coef
        dof = n - k
        s2 = float(resid @ resid) / dof
        inv = np.linalg.pinv(X.T @ X)
        var = s2 * float(inv[-1, -1])
    except np.linalg.LinAlgError:
        return None
    if not np.isfinite(var) or var <= 0 or not np.isfinite(coef).all():
        return None
    se = math.sqrt(var)
    amp = abs(float(coef[-1]))
    return dict(t=float(coef[-1] / se), coefficient=amp, se=se,
                se_ratio=(se / amp if amp > 0 else None), dof=int(dof))


def _slice(y, guide, lo, hi, q):
    if lo < max(0, q) or hi > min(len(y), len(guide) + q):
        return None
    return y[lo:hi], guide[lo - q:hi - q]


def _test_pair(mix, guide, lo, hi, q0, q1, amp_ref):
    cut = _slice(mix, guide, lo, hi, q1)
    cut0 = _slice(mix, guide, lo, hi, q0)
    if cut is None or cut0 is None:
        return None
    y, c1 = cut
    _, c0 = cut0
    r = _tstat(y, [c0, c1])
    if r is None:
        return None
    return dict(kind='JOINT', t=r['t'], coefficient=r['coefficient'], se=r['se'],
                se_ratio=(r['se'] / amp_ref if amp_ref else None), dof=r['dof'])


def _test_single(mix, guide, lo, hi, q, amp_ref=None):
    cut = _slice(mix, guide, lo, hi, q)
    if cut is None:
        return None
    y, c = cut
    r = _tstat(y, [c])
    if r is None:
        return None
    amp = amp_ref or r['coefficient']
    return dict(kind='SINGLE', t=r['t'], coefficient=r['coefficient'], se=r['se'],
                se_ratio=(r['se'] / amp if amp else None), dof=r['dof'])


def _half_evidence(mix, guide, s, n, radius):
    tpl = np.asarray(guide[s:s + n], dtype='float64')
    rec = dict(span=[int(s), int(s + n)], usable=False)
    if n < MIN_HALF:
        rec.update(state='DEGENERATE', reason='HALF_TOO_SHORT')
        return rec
    if not np.isfinite(tpl).all():
        rec.update(state='ERROR', reason='NON_FINITE_TEMPLATE')
        return rec
    tpl = tpl - tpl.mean()
    if float(np.dot(tpl, tpl)) <= 0:
        rec.update(state='DEGENERATE', reason='CONSTANT_OR_SILENT')
        return rec
    curve = _curve(mix, tpl, s, radius)
    if curve is None:
        rec.update(state='DEGENERATE', reason='NO_VALID_OVERLAP')
        return rec
    q_lo, rho = curve
    best = int(np.argmax(np.abs(rho)))
    q_best = q_lo + best
    rec.update(usable=True, lag=int(q_best), rho=_r(rho[best]), abs_rho=_r(abs(rho[best])))
    if abs(float(rho[best])) < SUPPORT_MIN_RHO:
        rec.update(state='WEAK', reason='LOW_CORRELATION_SUPPORT')
        return rec
    acf = _acf(tpl)
    floor = max(SCREEN_RHO, 3.2 / math.sqrt(n))
    idx = _peaks(rho, best, floor)
    m_test = len(idx) + 1
    # Multiplicidad del barrido completo: el pico rival fue *seleccionado* entre
    # todas las posiciones examinadas, no entre las seis retenidas.
    z = NormalDist().inv_cdf(1.0 - ALPHA / (2.0 * max(len(rho), m_test)))
    support_floor = max(MIN_FIT, n // 4)
    # Null calibrado con los propios datos (robusto a señales dispersas y
    # correlacionadas): MAD de la curva, no 1/sqrt(n) teórico.
    sigma_rho = 1.4826 * float(np.median(np.abs(rho - np.median(rho))))
    crit_rho = sigma_rho * z
    tested, confirmed, structural = [], [], None
    max_t, blind, se_ratios, amp0 = 0.0, 0.0, [], None
    lo0 = max(0, s + q_best)
    hi0 = min(len(mix), s + q_best + n, len(guide) + q_best)
    fit0 = _test_single(mix, guide, lo0, hi0, q_best) if hi0 - lo0 >= support_floor else None
    if fit0 is not None:
        amp0 = fit0['coefficient']
    # Escala física del error estándar: amplitud relativa al Mix de la ventana.
    scale = None
    if hi0 - lo0 >= MIN_FIT:
        sy = float(np.std(mix[lo0:hi0]))
        if sy > 0:
            scale = float(np.std(tpl)) / sy
    for i in idx:
        q1 = q_lo + i
        delta = abs(q1 - q_best)
        entry = dict(lag=int(q1), delta=int(delta), abs_rho=_r(abs(rho[i])))
        if acf is not None and delta < len(acf) and abs(float(acf[delta])) >= STRUCTURAL_ACF:
            # Un hombro del lóbulo principal no es otra hipótesis: sólo hay
            # ambigüedad estructural si el candidato está igual de soportado.
            if abs(float(rho[i])) >= 0.5 * abs(float(rho[best])):
                entry.update(kind='STRUCTURAL_ACF')
                structural = dict(lag=int(q1), delta=int(delta),
                                  acf=_r(abs(float(acf[delta]))))
            else:
                entry.update(kind='MAIN_LOBE')
            tested.append(entry)
            continue
        lo = max(0, s + q_best, s + q1)
        hi = min(len(mix), s + q_best + n, s + q1 + n)
        test = (_test_pair(mix, guide, lo, hi, q_best, q1, amp0)
                if hi - lo >= support_floor else None)
        if test is None:
            lo1, hi1 = max(0, s + q1, q1), min(len(mix), s + q1 + n, len(guide) + q1)
            if hi1 - lo1 >= support_floor:
                test = _test_single(mix, guide, lo1, hi1, q1, amp0)
        if test is None:
            entry.update(kind='LOW_SUPPORT_NOT_TESTED')
            tested.append(entry)
            blind = max(blind, abs(float(rho[i])))
            continue
        entry.update(kind=test['kind'], t=_r(test['t'], 3), z=_r(z, 3),
                     coefficient=_r(test['coefficient']), se=_r(test['se']),
                     dof=test['dof'])
        if test['se_ratio'] is not None:
            ratio = test['se']
            if scale is not None:
                ratio *= scale
            se_ratios.append(ratio)
        max_t = max(max_t, abs(test['t']))
        entry['crit_rho'] = _r(crit_rho)
        if abs(test['t']) >= z and abs(float(rho[i])) >= crit_rho:
            entry['confirmed'] = True
            confirmed.append(entry)
        tested.append(entry)
    mdr = _r(z * max(se_ratios)) if se_ratios else None
    blind_ok = (mdr is not None and blind >= mdr) or blind >= crit_rho
    rec.update(state=('AMBIGUOUS' if (confirmed or structural or blind_ok) else 'MEASURED'),
               tested=tested, confirmed=confirmed,
               confirmed_lags=[e['lag'] for e in confirmed],
               mdr_basis='z*se*std(guide_window)/std(mix_window)',
               detection_scale=_r(scale),
               structural=structural, mdr=mdr, z=_r(z, 3), max_t=_r(max_t, 3),
               peaks_examined=m_test, untestable_max_abs_rho=_r(blind),
               sigma_rho=_r(sigma_rho), crit_rho=_r(crit_rho))
    if mdr is None and rec['state'] == 'MEASURED':
        rec.update(state='WEAK', reason='NO_CAPABILITY_ESTIMATE')
    return rec


def _window(mix, guide, span, radius):
    s, e = span
    n = e - s
    cuts = [(s, s + n // 2), (s + n // 2, e)]
    halves = [_half_evidence(mix, guide, a, b - a, radius) for a, b in cuts]
    w = dict(span=[int(s), int(e)], halves=halves)
    usable = [h for h in halves if h.get('usable')]
    if not usable:
        w.update(state='INSUFFICIENT_SIGNAL', reason='NO_USABLE_HALF')
        return w
    if any(h['state'] == 'ERROR' for h in halves):
        w.update(state='ERROR', reason='HALF_ERROR')
        return w
    if any(h['state'] == 'AMBIGUOUS' for h in halves):
        structural = [h['structural'] for h in halves if h.get('structural')]
        cones = [e for h in halves for e in h.get('confirmed', [])]
        # Una réplica real es estacionaria: debe corroborarse en dos mitades
        # con el mismo retardo (tolerancia de 1 muestra). Un único testimonio
        # se registra como evidencia no corroborada, no como ambigüedad probada.
        corroborated = any(
            abs(e1['lag'] - e2['lag']) <= 1
            for i, h1 in enumerate(halves)
            for h2 in halves[i + 1:]
            for e1 in h1.get('confirmed', []) for e2 in h2.get('confirmed', []))
        if structural or corroborated:
            w.update(state='AMBIGUOUS', reason='RIVAL_OR_STRUCTURAL_AMBIGUITY',
                     confirmed=cones, structural=structural, corroborated=corroborated)
        else:
            w.update(state='INSUFFICIENT_SIGNAL', reason='RIVAL_NOT_CORROBORATED',
                     confirmed=cones)
        return w
    measured = [h for h in halves if h['state'] == 'MEASURED']
    if not measured:
        w.update(state='INSUFFICIENT_SIGNAL', reason='WEAK_HALVES')
        return w
    lags = {h['lag'] for h in measured}
    if len(lags) > 1:
        w.update(state='AMBIGUOUS', reason='VARIABLE_CLOCK_WITHIN_WINDOW',
                 lags=sorted(lags))
        return w
    signs = {math.copysign(1.0, h['rho']) for h in measured}
    if len(signs) > 1:
        w.update(state='AMBIGUOUS', reason='POLARITY_CONFLICT_WITHIN_WINDOW')
        return w
    mdrs = [h['mdr'] for h in measured if h.get('mdr') is not None]
    w.update(state='UNIQUE', lag=int(lags.pop()),
             rho=_r(sum(h['rho'] for h in measured) / len(measured)),
             mdr=_r(max(mdrs)) if mdrs else None,
             max_t=_r(max(h.get('max_t') or 0.0 for h in measured)),
             z=_r(max(h.get('z') or 0.0 for h in measured)))
    return w


def _plan(n):
    if n < 2 * MIN_HALF:
        return [(0, n)]
    L = min(n, max(MIN_HALF, n // 4))
    stride = max(1, (n - L) // max(1, WINDOWS - 1))
    spans = {(min(i * stride, n - L), min(i * stride, n - L) + L) for i in range(WINDOWS)}
    return sorted(spans)


def measure(mix, guide, radius, rate, decision, severity, config=None):
    """Diagnóstico por canal. Devuelve (decision, ventanas); no altera muestras."""
    mix = np.asarray(mix, dtype='float64')
    guide = np.asarray(guide, dtype='float64')
    if not (np.isfinite(mix).all() and np.isfinite(guide).all()):
        raise ValueError('Muestras no finitas')
    if not len(guide) or not len(mix):
        return decision('NON_INFORMATIVE', 'EMPTY'), []
    if float(np.ptp(guide)) == 0 or float(np.ptp(mix)) == 0:
        return decision('NON_INFORMATIVE', 'EMPTY_OR_CONSTANT'), []
    windows = [_window(mix, guide, sp, radius) for sp in _plan(len(guide))]
    states = [w['state'] for w in windows]
    if 'ERROR' in states:
        return decision('ERROR', 'WINDOW_ERROR'), windows
    unique = [w for w in windows if w['state'] == 'UNIQUE']
    coverage = 0.0
    if unique:
        coverage = min(1.0, sum(e - s for s, e in (w['span'] for w in unique)) / float(len(guide)))
    if 'AMBIGUOUS' in states:
        reasons = sorted({w.get('reason', 'AMBIGUOUS') for w in windows if w['state'] == 'AMBIGUOUS'})
        d = decision('AMBIGUOUS', 'RIVAL_OR_STRUCTURAL_AMBIGUITY')
        d.update(ambiguity_detail=reasons, coverage=_r(coverage, 3),
                 rivals=[r for w in windows for r in (w.get('confirmed') or [])],
                 structural=[s for w in windows for s in (w.get('structural') or [])])
        return d, windows
    lags = {w['lag'] for w in unique}
    if len(lags) > 1:
        d = decision('AMBIGUOUS', 'VARIABLE_CLOCK_BETWEEN_WINDOWS')
        d.update(lags=sorted(lags), coverage=_r(coverage, 3))
        return d, windows
    if len(unique) < 2 or coverage < 0.5:
        d = decision('INSUFFICIENT_SIGNAL', 'INCOMPLETE_TEMPORAL_COVERAGE')
        d.update(coverage=_r(coverage, 3))
        return d, windows
    mdrs = [w['mdr'] for w in unique if w.get('mdr') is not None]
    mdr = max(mdrs) if mdrs else None
    if mdr is None or mdr > CAPABILITY_MAX_MDR:
        d = decision('INSUFFICIENT_SIGNAL', 'INSUFFICIENT_DETECTION_CAPABILITY')
        d.update(replica_detection_floor=_r(mdr), coverage=_r(coverage, 3))
        return d, windows
    k = unique[0]['lag']
    rho = sum(w['rho'] for w in unique) / len(unique)
    max_t = max((w.get('max_t') or 0.0) for w in unique)
    z = max((w.get('z') or 0.0) for w in unique)
    margin = max(0.0, 1.0 - (max_t / z)) if z else 0.0
    d = decision(severity(k), 'UNIQUE_WITHIN_REPLICA_TEST', k, rho, abs(rho) * margin)
    d.update(replica_detection_floor=_r(mdr), coverage=_r(coverage, 3),
             rival_margin=_r(margin, 3))
    return d, windows


def combine_channels(records, decision, severity):
    """Agregado L/R explícito: no promedia canales ni oculta desacuerdos."""
    if not records:
        return decision('INSUFFICIENT_SIGNAL', 'NO_CHANNELS')
    states = {r['classification'] for r in records.values()}
    if 'ERROR' in states:
        d = decision('ERROR', 'MEMBER_ERROR')
        d['channel_states'] = {n: r['classification'] for n, r in records.items()}
        return d
    names = list(records)
    measured = {n: r['estimated_offset_samples'] for n, r in records.items()
                if r.get('estimated_offset_samples') is not None}
    if len(records) == 1:
        n = names[0]
        r = records[n]
        d = decision(r['classification'], r['reason'], r.get('estimated_offset_samples'),
                     r.get('correlation_peak'), r.get('alignment_confidence'))
        d.update(channel_lags=measured, channel_states={n: r['classification']})
        return d
    if len(measured) == len(records):
        lags = set(measured.values())
        signs = {math.copysign(1.0, r['correlation_peak']) for r in records.values()
                 if r.get('correlation_peak') is not None}
        if len(lags) == 1 and len(signs) <= 1:
            k = measured[names[0]]
            weakest = min(records.values(), key=lambda r: r.get('alignment_confidence') or 0.0)
            d = decision(severity(k), 'MEASURED_AGREEMENT', k,
                         weakest.get('correlation_peak'), weakest.get('alignment_confidence'))
            d.update(channel_lags=measured,
                     channel_states={n: r['classification'] for n, r in records.items()})
            return d
        d = decision('AMBIGUOUS',
                     'CHANNEL_POLARITY_CONFLICT' if len(lags) == 1 else 'CHANNEL_DISAGREEMENT')
        d.update(channel_lags=measured,
                 channel_states={n: r['classification'] for n, r in records.items()})
        return d
    if 'AMBIGUOUS' in states:
        d = decision('AMBIGUOUS', 'MEMBER_AMBIGUITY_OR_CONFLICT')
        d.update(channel_lags=measured,
                 channel_states={n: r['classification'] for n, r in records.items()},
                 partial=dict(measured=sorted(measured),
                              not_measured=sorted(set(names) - set(measured))))
        return d
    if states == {'NON_INFORMATIVE'}:
        return decision('NON_INFORMATIVE', 'ALL_CHANNELS_NON_INFORMATIVE')
    d = decision('INSUFFICIENT_SIGNAL', 'INCOMPLETE_CHANNEL_EVIDENCE')
    d.update(channel_lags=measured,
             channel_states={n: r['classification'] for n, r in records.items()},
             partial=dict(measured=sorted(measured),
                          not_measured=sorted(set(names) - set(measured)),
                          note='un solo canal medido no define un reloj común'))
    return d


def analyze_files(mix_info, guide_info, rate, search_seconds, decision, severity,
                  aligned_tol, warning_ms):
    """Validación y lectura desde el mismo descriptor + diagnóstico por canal."""
    radius = int(search_seconds * rate)
    delta = guide_info.frames - mix_info.frames
    rec = dict(schema='alignment-6f/1', policy='detect_only_no_correction',
               guide=os.path.basename(guide_info.path),
               duration_difference_samples=delta,
               duration_difference_ms=1000.0 * delta / rate,
               convention='M[t] ~ G[t-k]; d=-k',
               search_window_seconds=search_seconds, search_window_samples=radius,
               tolerances=dict(aligned_max_samples=aligned_tol, warning_max_ms=warning_ms),
               channels={}, estimated_offset_ms=None, cross_correlation=None,
               guide_delay_R_minus_L=None, k_R_minus_L=None,
               action=dict(shift_authorized=False, applied_shift_samples=0,
                           polarity_changed=False),
               integrity={})
    names = (('L', 'R') if mix_info.channels == guide_info.channels == 2 else
             ('M',) if mix_info.channels == guide_info.channels == 1 else ())
    handles = []
    try:
        mx = open_validated(mix_info.path)
        handles.append(('mix', mx))
        gu = open_validated(guide_info.path)
        handles.append(('guide', gu))
        rec['integrity'] = {
            'same_descriptor_read': True,
            'mix': dict(sha256=mx.digest, identity=mx.identity, spec=mx.spec.as_dict()),
            'guide': dict(sha256=gu.digest, identity=gu.identity, spec=gu.spec.as_dict()),
        }
        for tag, vw, meta in (('mix', mx, mix_info), ('guide', gu, guide_info)):
            if (vw.spec.rate, vw.spec.channels, vw.spec.frames) != (rate, meta.channels, meta.frames):
                raise WaveError(f'{tag}: geometría inesperada '
                                f'({vw.spec.rate}/{vw.spec.channels}/{vw.spec.frames})')
            if meta.sha256 and meta.sha256 != vw.digest:
                raise WaveError(f'{tag}: sha256 distinto del sondeo (posible sustitución '
                                'entre validación y lectura)')
        if not names:
            d = decision('INSUFFICIENT_SIGNAL', 'NO_MATCHING_CHANNEL_LAYOUT')
            rec.update(d)
            rec['attribution'] = 'INSUFFICIENT_SIGNAL'
            return rec
        for i, name in enumerate(names):
            try:
                result, windows = measure(mx.samples[:, i], gu.samples[:, i], radius,
                                          rate, decision, severity)
                rec['channels'][name] = dict(result, windows=windows)
            except Exception as exc:  # noqa: BLE001 - se informa, no se oculta
                import traceback
                rec['channels'][name] = dict(decision('ERROR', 'CHANNEL_ERROR'), windows=[],
                                             error=type(exc).__name__ + ': ' + str(exc),
                                             traceback=traceback.format_exc())
        rec.update(combine_channels(rec['channels'], decision, severity))
        errors = [s['error'] for s in rec['channels'].values() if 'error' in s]
        if errors:
            rec['error'] = '; '.join(errors)
        k = rec.get('estimated_offset_samples')
        if k is not None:
            rec['estimated_offset_ms'] = 1000.0 * k / rate
            rec['cross_correlation'] = rec.get('correlation_peak')
        if names == ('L', 'R'):
            lags = rec.get('channel_lags') or {}
            if all(c in lags for c in ('L', 'R')):
                diff = lags['L'] - lags['R']
                rec.update(guide_delay_R_minus_L=-diff, k_R_minus_L=diff)
            elif len(lags) == 1:
                rec['channel_disagreement_note'] = 'un solo canal medido; no se infiere reloj común'
        rec['attribution'] = _attribution(rec)
        for ch in rec['channels'].values():
            ch['attribution'] = _attribution(ch)
    except Exception as exc:
        import traceback
        rec.update(decision('ERROR', 'READ_OR_FORMAT_ERROR'),
                   error=type(exc).__name__ + ': ' + str(exc),
                   traceback=traceback.format_exc())
        rec['channels'] = {ch: decision('ERROR', 'READ_OR_FORMAT_ERROR') for ch in names}
        rec['attribution'] = 'ERROR'
    finally:
        for tag, vw in handles:
            try:
                rec['integrity'][tag + '_unchanged_on_close'] = vw.unchanged_on_close
                rec['integrity'][tag + '_after'] = check_unchanged(vw)
            except Exception:
                pass
            vw.close()
    return rec


def _attribution(record):
    return ('UNIQUE' if record.get('estimated_offset_samples') is not None
            else record.get('classification', 'ERROR'))


def alignment_gate(records, blocking, allow, log=lambda *_: None):
    """Decisión de continuación explícita y registrable.

    Un permiso no sustituye validaciones físicas ni la comprobación de datos no
    finitos: ambos se ejecutan antes de esta compuerta y ERROR nunca se permite.
    """
    states = {}
    for rec in records:
        states[f"{rec.get('pair_id')}/{rec.get('role')}"] = rec.get('classification', 'ERROR')
    blocking = list(blocking or [])
    gate = dict(permission=None, allowed=True, states=states,
                blocking=[{ 'pair': r.get('pair_id'), 'role': r.get('role'),
                            'classification': r.get('classification'),
                            'attribution': r.get('attribution'),
                            'reason': r.get('reason'),
                            'channel_lags': r.get('channel_lags')} for r in blocking],
                does_not_bypass=['validacion_fisica_wav', 'datos_no_finitos',
                                 'integridad_identidad_archivo'],
                action=dict(shift_authorized=False, applied_shift_samples=0,
                            polarity_changed=False))
    if any(r.get('classification') == 'ERROR' for r in records):
        gate.update(allowed=False, permission=None, verdict='ABORT_ERROR')
        log('[ABORT] ERROR de alineación: no admite permiso explícito.')
        return gate
    if blocking and not allow:
        gate.update(allowed=False, verdict='ABORT_NO_PERMISSION')
        log('[ABORT] Diagnóstico no validado (%s). Se requiere --allow-misaligned para '
            'continuar sin corrección; el diagnóstico no cambia.'
            % ', '.join(sorted({r.get('classification', '?') for r in blocking})))
        return gate
    if blocking and allow:
        gate.update(allowed=True, verdict='ALLOWED_EXPLICIT', permission='cli_allow_misaligned',
                    scope='procesar_sin_corregir_alineacion',
                    note='el permiso no altera offsets, muestras ni polaridad')
        log('[PERMISO] continuación explícita: cli_allow_misaligned (diagnóstico intacto).')
        return gate
    gate.update(allowed=True, verdict='ALIGNED')
    return gate
