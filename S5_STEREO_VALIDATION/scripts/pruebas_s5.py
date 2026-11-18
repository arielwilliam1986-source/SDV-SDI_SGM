"""Ejecuta bloques sobre copias inmutables. No reusa directorios de corrida."""
import argparse
import contextlib
import importlib.util
import inspect
import os
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf

from medidas import ROOT, WORK, SR, N, load, dump, sha, wav_stats, read, difference
from observador import Observer
from preparar_fuentes import ENGINES, verify

RESULTS = {'A':'s5_a_v3', 'B':'s5_b_hardened', 'C':'s5_c_evo', 'D':'s5_d_mqr'}


def jobs(block):
    modes = ['per_channel','mono'] if block != 'D' else ['shared']
    for n in range(1,8):
        for mode in modes:
            yield f'S{n}', mode, 'principal'
    for mode in modes:
        yield 'Ronly', mode, 'unilateral'
    if block == 'C':
        yield 'Ppos', 'per_channel', 'polaridad'
        yield 'Pneg', 'per_channel', 'polaridad'
        yield 'Ppos', 'per_channel', 'hybrid'


def import_engine(block):
    name = 's5_original_' + block
    spec = importlib.util.spec_from_file_location(name, ROOT / 'sources' / ENGINES[block])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def arguments(block, mask, series, manifest, out):
    argv = ['--manifest',str(manifest.relative_to(ROOT)), '--out',str(out.relative_to(ROOT)),
            '--n-fft','4096','--hop','1024','--chunk-frames','64']
    if block == 'A':
        return argv + ['--branch','identity','--consensus','magnitudes_first','--mask-mode',mask,
                       '--power','1.95','--epsilon','1e-12','--smoothing','none','--no-loo']
    argv += ['--mode','full_processing','--allow-misaligned','--consensus','confidence_weighted_mean']
    if block == 'D':
        return argv + ['--power','2','--epsilon','1e-9']
    return argv + ['--mask-mode',mask,'--consensus-order', 'hybrid_asymmetric' if series == 'hybrid' else 'magnitudes_first',
                   '--smoothing','none','--power','1.8','--epsilon','1e-12','--beta','1']


def v3(mod, args, run, record):
    # main() invoca audit_alignment incondicionalmente. Llamada soportada al núcleo,
    # sin reemplazar esa función, sin estimar desplazamientos ni ganancias.
    mix, pairs, cal, _ = mod.load_manifest(args.manifest)
    if cal or args.branch != 'identity' or mod.validate_numeric(args,args):
        raise ValueError('Configuración v3 no autorizada o no válida')
    info = mod.probe_file(mix,'mix')
    for p in pairs:
        for path in [p.vocal_path,p.instrumental_path]:
            mod.check_degeneration(mod.probe_file(path,'guide'))
    mod.check_degeneration(info)
    kw = dict(opt=args, mix_info=info, pairs=pairs, branch='identity', method=args.consensus,
              run_dir=str(run), write_wavs=True, ref_v=None, ref_i=None, shifts={}, gains={}, enable_loo=False)
    inspect.signature(mod.run_processing).bind(**kw)
    record['kernel_args'] = dict(branch='identity', method=args.consensus, run_dir=str(run.relative_to(ROOT)),
                                 write_wavs=True, ref_v=None, ref_i=None, shifts={}, gains={}, enable_loo=False,
                                 mix_info='probe_file(mix)', pairs='load_manifest(manifest)', opt='parsed_options')
    res = mod.run_processing(**kw)
    dump(run/'kernel_result.json',res)
    return 0


def check_inputs(manifest, catalog):
    spec = load(manifest)
    if spec.get('calibration_parameters'):
        raise ValueError('Manifiesto con overrides inesperados')
    files = {'Mix':spec['mix_original']}
    for p in spec['pairs']:
        for role, key in [('V','vocal'), ('I','instrumental')]:
            if p[key+'_path'] != p[key+'_guide']:
                raise ValueError('Claves no equivalentes')
            files[p['pair_id']+'/'+role] = p[key+'_path']
    refs = {}
    for role, name in files.items():
        path = (manifest.parent / name).resolve()
        info = sf.info(path)
        stored = catalog['audio'][str(path.relative_to(WORK/'inputs'))]
        digest = sha(path.read_bytes())
        if (info.samplerate, info.channels, info.frames, info.subtype, digest) != (SR,2,N,'FLOAT',stored['sha256']):
            raise ValueError(f'La entrada no coincide con el diseño estéreo: {path}')
        refs[role] = dict(path=str(path.relative_to(WORK)), sha256=digest)
    return refs


def run_one(mod, block, case, mask, series, catalog):
    key = f'{case}_{mask}' + ('' if series == 'principal' else '_'+series)
    run = WORK/'runs'/block/key
    run.mkdir(parents=True, exist_ok=False)
    engine_dir = run/'native'
    engine_dir.mkdir()
    manifest = WORK / catalog['cases'][case]['manifest']
    args = arguments(block,mask,series,manifest,engine_dir)
    record = dict(id=key, case=case, mode=mask, series=series, entrypoint='run_processing' if block=='A' else 'main',
                  argv=args, cwd='S5_STEREO_VALIDATION', utc=datetime.now(timezone.utc).isoformat(),
                  log=str((run/'console.log').relative_to(WORK)), status='FAILED', engine_exit=None)
    obs = Observer(mod, block, series != 'principal')
    oldargv = sys.argv
    with (run/'console.log').open('w') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            sys.argv = [str(ROOT/'sources'/ENGINES[block]), *args]
            parsed = mod.build_arg_parser().parse_args(args)
            record['parsed_options'] = vars(parsed).copy()
            record['inputs'] = check_inputs(manifest, catalog)
            if block in ('B','C') and (parsed.use_physical_residuals or parsed.correct_alignment or parsed.mask_mode!=mask):
                raise ValueError('No se cumplen las condiciones de la comparación')
            print('API:',record['entrypoint'],'; argv:',args,flush=True)
            sys.setprofile(obs)
            try:
                code = v3(mod,parsed,engine_dir,record) if block=='A' else mod.main(args)
            finally:
                sys.setprofile(None)
            record['engine_exit'] = code
            if code != 0:
                raise RuntimeError(f'El motor devolvió {code}; ver console.log (no se reintenta ni parchea).')
            outs = {}
            for role in ('SDV','SDI'):
                matches = list(engine_dir.rglob('*'+role+'*.wav'))
                if len(matches) != 1:
                    raise ValueError(f'Se esperaba un WAV de {role}, hay {len(matches)}')
                outs[role] = wav_stats(matches[0])
            record['outputs'] = outs
            if any(any(v['nonfinite']) for v in outs.values()):
                raise ValueError('Muestras de salida no finitas')
            x = read(WORK/record['inputs']['Mix']['path'])
            v, i = (read(WORK/outs[role]['path']) for role in ('SDV','SDI'))
            record['reconstruction'] = difference(v+i, x)
            if case == 'S3':
                record['gain_residual_rms_R_minus_quarter_L'] = {k:difference(y[:,1],y[:,0]/4)['rms'] for k,y in [('SDV',v),('SDI',i)]}
            if case == 'S4':
                record['event_windows'] = {}
                for label, lo, hi in [('V_L',SR//2,SR), ('I_R',2*SR,5*SR//2)]:
                    record['event_windows'][label] = {r:np.sqrt(np.mean(y[lo:hi]**2, axis=0)).tolist() for r,y in [('Mix',x),('SDV',v),('SDI',i)]}
            if case == 'S5':
                record['delay_residual_R_vs_L_delayed_2205'] = {r:difference(y[2205:,1],y[:-2205,0]) for r,y in [('Mix',x),('SDV',v),('SDI',i)]}
            record['status'] = 'OK'
        except Exception as exc:
            record['error'] = f'{type(exc).__name__}: {exc}'
            traceback.print_exc()
        finally:
            sys.argv = oldargv
            record['observation'] = obs.finish(run/'applied_mask.npy')
            if obs.masks:
                record['applied_mask'] = str((run/'applied_mask.npy').relative_to(WORK))
            if record['status']=='OK' and (obs.errors or not obs.masks or record['observation'].get('nonfinite')):
                record['status'] = 'OBSERVATION_INCOMPLETE'
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('block', choices=[*ENGINES,'all'])
    parser.add_argument('--solo-control-r', action='store_true', help='anexar el control unilateral a una matriz ya registrada')
    opt = parser.parse_args()
    selection = opt.block
    os.chdir(ROOT)
    catalog = load(ROOT/'signals/manifest.json')
    for block in ENGINES if selection=='all' else [selection]:
        verify()
        source = ROOT/'sources'/ENGINES[block]
        helptext = subprocess.check_output([sys.executable,'-B',str(source),'--help'], text=True)
        (ROOT/'logs'/('help_'+source.stem+'.txt')).write_text(helptext)
        mod = import_engine(block)
        entry = mod.run_processing if block=='A' else mod.main
        result = dict(block=block, source=source.name, sha256=sha(source.read_bytes()),
                      signature=str(inspect.signature(entry)), help='logs/help_'+source.stem+'.txt', runs=[])
        if opt.solo_control_r:
            result = load(ROOT/'results'/(RESULTS[block]+'.json'))
            if result['sha256'] != sha(source.read_bytes()) or any(r['series']=='unilateral' for r in result['runs']):
                raise ValueError('No se puede anexar este control')
        for case, mode, series in jobs(block):
            if opt.solo_control_r and series != 'unilateral':
                continue
            r = run_one(mod,block,case,mode,series,catalog)
            result['runs'].append(r)
            dump(ROOT/'results'/(RESULTS[block]+'.json'), result)
            print(block, r['id'],r['status'],r.get('error',''),flush=True)


if __name__ == '__main__':
    main()
