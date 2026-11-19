"""Construye las copias 6F de los tres motores desde la entrega congelada 6E.

Sólo sustituye bloques de diagnóstico: importación del módulo 6F, agregado por
canal, análisis de alineación y compuerta de continuación en la CLI. No toca
STFT, máscaras, ganancias, polaridad, shifts ni procesamiento de muestras.

Uso:
    python -B scripts/construir_motores_6f.py [--check]

`--check` sólo verifica que las copias publicadas coincidan con lo que produce
el constructor (no escribe).
"""
import difflib
import os
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parent
SEIS_E = ROOT / 'ETAPA_6E_CORRECCION_ATRIBUCION_INTEGRIDAD' / 'motores'
OUT = HERE / 'motores'

IMPORT_OLD = 'from atribucion_6e import measure, verify_wave'
IMPORT_NEW = ('from atribucion_6f import (measure, verify_wave, alignment_gate,\n'
              '                        analyze_files as _analyze_files_6f,\n'
              '                        combine_channels as _combine_6f)')

COMBINE_NEW = '''def _combine(records, clocks=False):
    """6F: agregado por canal delegado al módulo compartido (sólo diagnóstico)."""
    if isinstance(records, list):
        records = {str(i): r for i, r in enumerate(records)}
    return _combine_6f(records, _decision, _severity)


'''

ALIGN_NEW_COMMON = '''    return _analyze_files_6f(mix_info, guide_info, REQUIRED_SAMPLE_RATE,
                             ALIGN_SEARCH_SECONDS, _decision, _severity,
                             ALIGNED_TOL_SAMPLES, MISALIGNED_TOL_MS)


'''

GATE_OLD_CLASSIC = """    if any(r['classification']=='ERROR' for r in misaligned) or (misaligned and not opt.allow_misaligned):
        log('[ABORT] Alineación no validada. ERROR es incondicional; los demás vetos requieren --allow-misaligned.')
        return EXIT_VALIDATION, None"""

GATE_NEW_CLASSIC = """    gate = alignment_gate(alignment_records, misaligned, opt.allow_misaligned, log)
    ctx["alignment_gate"] = gate
    for _r in misaligned:
        _r['continuation_permission'] = gate['permission']
    if not gate['allowed']:
        return EXIT_VALIDATION, None"""

GATE_OLD_MQR = """    if any(r['classification']=='ERROR' for r in misaligned):
        log('[ABORT] Error de alineación; no admite excepción operativa.')
        return EXIT_VALIDATION, ctx
    if misaligned:
        permission = 'cli_allow_misaligned' if opt.allow_misaligned else None
        if not permission:
            log('[ABORT] Guías sin validación de reloj. Sólo --allow-misaligned permite continuar sin shift.')
            return EXIT_VALIDATION, ctx
        ctx['misalignment_user_authorized'] = True
        ctx['alignment_permission'] = permission
        log('Continuación explícita sin corrección: '+permission)"""

GATE_NEW_MQR = """    gate = alignment_gate(alignment_records, misaligned, opt.allow_misaligned, log)
    ctx['alignment_gate'] = gate
    for _r in misaligned:
        _r['continuation_permission'] = gate['permission']
    if not gate['allowed']:
        return EXIT_VALIDATION, ctx
    if gate['permission']:
        ctx['misalignment_user_authorized'] = True
        ctx['alignment_permission'] = gate['permission']"""

REPORT_OLD = '        "alignment_analysis": ctx.get("alignment", []),'
REPORT_NEW = ('        "alignment_analysis": ctx.get("alignment", []),\n'
              '        "alignment_gate": ctx.get("alignment_gate", {}),')

MQRR_OLD = """    if ctx.get('misalignment_user_authorized'):
        check('misalignment_user_authorized','recorded',source=ctx.get('alignment_permission'))"""
MQRR_NEW = """    if ctx.get('misalignment_user_authorized'):
        check('misalignment_user_authorized','recorded',source=ctx.get('alignment_permission'))
    gate = ctx.get('alignment_gate')
    if gate:
        check('alignment_gate', 'pass' if gate.get('allowed') else 'fail',
              verdict=gate.get('verdict'), permission=gate.get('permission'),
              blocking=gate.get('blocking'))"""


def replace_block(text, start_marker, end_marker, new):
    i = text.index(start_marker)
    j = text.index(end_marker, i)
    return text[:i] + new + text[j:]


def patch(path, kind):
    src = path.read_text(encoding='utf-8')
    if IMPORT_OLD not in src:
        raise SystemExit(f'{path.name}: no se encontró el import 6E')
    src = src.replace(IMPORT_OLD, IMPORT_NEW, 1)
    src = replace_block(src, 'def _combine(records, clocks=False):',
                        'def _alignment_spans(', COMBINE_NEW)
    signature = ('def analyze_alignment(mix_info, guide_info, mix_mono_cache=None):'
                 if kind == 'mqr' else
                 'def analyze_alignment(mix_info: FileInfo, guide_info: FileInfo) -> dict:')
    body = signature + '\n    """6F: validación y lectura desde el mismo descriptor; sin corrección."""\n' + ALIGN_NEW_COMMON
    src = replace_block(src, signature, 'def _attribution_state(', body)
    if kind == 'mqr':
        if GATE_OLD_MQR not in src:
            raise SystemExit(f'{path.name}: compuerta MQR no encontrada')
        src = src.replace(GATE_OLD_MQR, GATE_NEW_MQR, 1)
        src = src.replace(MQRR_OLD, MQRR_NEW, 1)
    else:
        if GATE_OLD_CLASSIC not in src:
            raise SystemExit(f'{path.name}: compuerta no encontrada')
        src = src.replace(GATE_OLD_CLASSIC, GATE_NEW_CLASSIC, 1)
        src = src.replace(REPORT_OLD, REPORT_NEW, 1)
    return src


FILES = [('MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py', 'classic'),
         ('MOTOR_SEP_SDV-SDI_EVO.py', 'classic'),
         ('sdv_sdi_mqr_engine.py', 'mqr')]


def main(check=False):
    OUT.mkdir(parents=True, exist_ok=True)
    report = {}
    for name, kind in FILES:
        new = patch(SEIS_E / name, kind)
        old = (SEIS_E / name).read_text(encoding='utf-8')
        diff = [l for l in difflib.unified_diff(old.splitlines(), new.splitlines(), n=0)
                if l.startswith(('+', '-')) and not l.startswith(('+++', '---'))]
        report[name] = len(diff)
        dest = OUT / name
        if check:
            if not dest.exists() or dest.read_text(encoding='utf-8') != new:
                raise SystemExit(f'{name}: la copia publicada difiere del constructor')
        else:
            dest.write_text(new, encoding='utf-8')
        print(f'{name}: {len(diff)} líneas de diff respecto de 6E')
    return report


if __name__ == '__main__':
    import sys
    main(check='--check' in sys.argv)
