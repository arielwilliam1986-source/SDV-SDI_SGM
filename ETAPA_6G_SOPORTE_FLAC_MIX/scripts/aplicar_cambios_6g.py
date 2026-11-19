"""Aplica los cambios 6G a las copias: validación de contenedor y trazabilidad.

Sólo lectura, validación y traza: no toca ninguna función DSP.
Idempotente: si el archivo ya contiene la marca `container_6g`, lo omite.
"""
import re
from pathlib import Path

MOT = Path(__file__).resolve().parent.parent / 'motores'
MOTORES = ('MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py',
           'MOTOR_SEP_SDV-SDI_EVO.py',
           'sdv_sdi_mqr_engine.py')

IMPORT_ANCHOR = "from atribucion_6f import (measure, verify_wave, alignment_gate,"
IMPORT_NEW = ("from audio_integridad_6g import (check_file_unchanged as _check_unchanged_6g,\n"
              "                              container_of as _container_6g,\n"
              "                              verify_audio as _verify_audio_6g)\n\n")

INIT_6G = '''    # 6G: trazabilidad del contenedor de entrada (no toca el DSP)
    ctx["container_6g"] = {
        "mix_path": os.path.abspath(mix_path),
        "container": _container_6g(mix_path),
        "format": mix_info.format, "subtype": mix_info.subtype,
        "probe_sha256": mix_info.sha256, "after": None,
        "policy": "detect_only_no_conversion"}

'''


def fin_6g(ind: str) -> str:
    return (
        f'{ind}ctx["container_6g"]["after"] = _check_unchanged_6g(\n'
        f'{ind}    mix_path, mix_info.sha256)\n'
        f'{ind}try:\n'
        f'{ind}    with open(os.path.join(run_dir_final, "input_integrity_6g.json"),\n'
        f'{ind}              "w", encoding="utf-8") as _f6g:\n'
        f'{ind}        json.dump(json_safe(ctx["container_6g"]), _f6g, indent=2,\n'
        f'{ind}                  ensure_ascii=False)\n'
        f'{ind}except Exception as _exc6g:\n'
        f'{ind}    log("[6G] no se pudo escribir input_integrity_6g.json: %s" % _exc6g)\n'
        f'{ind}if not ctx["container_6g"]["after"].get("unchanged"):\n'
        f'{ind}    log("[FATAL] El Mix cambió durante el procesamiento: "\n'
        f'{ind}        + str(ctx["container_6g"]["after"]))\n'
        f'{ind}    return EXIT_PROCESSING, None\n')


def main():
    for nombre in MOTORES:
        p = MOT / nombre
        s = p.read_text(encoding='utf-8')
        if 'container_6g' in s:
            print('ya parcheado:', nombre)
            continue

        assert s.count('        verify_wave(path, sfi)') == 1, nombre
        s = s.replace('        verify_wave(path, sfi)', '        _verify_audio_6g(path, sfi)')

        assert s.count(IMPORT_ANCHOR) == 1, nombre
        s = s.replace(IMPORT_ANCHOR, IMPORT_NEW + IMPORT_ANCHOR)

        assert s.count('    ctx["mix_info"] = mix_info') == 1, nombre
        s = s.replace('    ctx["mix_info"] = mix_info\n',
                      '    ctx["mix_info"] = mix_info\n' + INIT_6G, 1)

        patron = re.compile(r'^(\s*)return EXIT_OK, run_dir_final$', re.M)
        hallados = patron.findall(s)
        assert len(hallados) == 1, (nombre, len(hallados))
        ind = hallados[0]
        s = patron.sub(lambda m: fin_6g(ind) + m.group(0), s, count=1)

        p.write_text(s, encoding='utf-8')
        print('motor parcheado:', nombre)

    p = MOT / 'sdv_sdi_mqr_engine.py'
    s = p.read_text(encoding='utf-8')
    if 'MIX_ALLOWED_EXTENSIONS = (".wav", ".flac")' not in s:
        assert s.count('MIX_ALLOWED_EXTENSIONS = (".wav",)') == 1
        s = s.replace('MIX_ALLOWED_EXTENSIONS = (".wav",)',
                      'MIX_ALLOWED_EXTENSIONS = (".wav", ".flac")  # 6G: contenedor verificado')
        p.write_text(s, encoding='utf-8')
        print('MQR: MIX_ALLOWED_EXTENSIONS actualizado')
    else:
        print('MQR: extensiones ya actualizadas')

    p = MOT / 'atribucion_6f.py'
    s = p.read_text(encoding='utf-8')
    if 'open_audio as open_validated' in s:
        print('atribucion: ya despachada por contenedor')
        return
    viejo = ("from wav_integridad_6f import (WaveError, check_unchanged, open_validated,\n"
             "                               verify_wave)")
    assert s.count(viejo) == 1
    s = s.replace(viejo,
                  "from wav_integridad_6f import WaveError, check_unchanged\n"
                  "from audio_integridad_6g import open_audio as open_validated")
    p.write_text(s, encoding='utf-8')
    print('atribucion: lectura despachada por contenedor')


if __name__ == '__main__':
    main()
