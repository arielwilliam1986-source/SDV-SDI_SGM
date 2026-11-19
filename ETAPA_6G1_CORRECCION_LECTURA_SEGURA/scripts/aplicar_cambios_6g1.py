"""Aplica la corrección 6G.1 a las copias: descriptor único y aborto seguro.

Sólo lectura, gestión de archivos, integridad y aborto. Ninguna función de DSP
cambia: no se toca el bucle de proceso, ni máscaras, ni STFT, ni ganancias.
"""
from pathlib import Path

MOT = Path(__file__).resolve().parent.parent / 'motores'
MOTORES = ('MOTOR_SEP_SDV-SDI_v3.1.1_Hardened_Final.py',
           'MOTOR_SEP_SDV-SDI_EVO.py',
           'sdv_sdi_mqr_engine.py')

IMPORT_ANCHOR = "                              verify_audio as _verify_audio_6g)\n"
IMPORT_NUEVO = ("from lectura_segura_6g1 import (MixCambiado as _MixCambiado_6g1,\n"
                "                                 abrir_mix as _abrir_mix_6g1,\n"
                "                                 abortar_6g1 as _abortar_6g1)\n")

VIEJO_APERTURA = 'hmix = sf.SoundFile(mix_info.path)'


def _ind(linea):
    return linea[:len(linea) - len(linea.lstrip(' '))]


def bloque_apertura(ind, mqr):
    cuerpo = (
        f"{ind}try:\n"
        f"{ind}    hmix = _abrir_mix_6g1(mix_info.path, mix_info.sha256)\n"
        f"{ind}except _MixCambiado_6g1 as _exc6g1:\n"
        f"{ind}    _abortar_6g1(run_dir, \"MIX_SUSTITUIDO_ANTES_DEL_DSP\", str(_exc6g1))\n"
        f"{ind}    log(\"[FATAL] Mix sustituido antes del DSP: %s\" % _exc6g1)\n"
        f"{ind}    close_tee()\n"
        f"{ind}    return EXIT_PROCESSING, None\n")
    if mqr:
        cuerpo += f'{ind}ctx["_mix_handle_6g1"] = hmix\n'
    return cuerpo


def parchear(nombre):
    mqr = (nombre == 'sdv_sdi_mqr_engine.py')
    p = MOT / nombre
    s = p.read_text(encoding='utf-8')
    if '_abrir_mix_6g1' in s:
        print('ya parcheado:', nombre)
        return

    assert s.count(IMPORT_ANCHOR) == 1, (nombre, 'import anchor')
    s = s.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + IMPORT_NUEVO)

    # 1. DSP: no reabrir por ruta (se conserva la indentación del sitio)
    lineas = s.splitlines(keepends=True)
    sitios = [i for i, l in enumerate(lineas) if l.strip() == VIEJO_APERTURA]
    assert len(sitios) == 1, (nombre, 'apertura', sitios)
    i = sitios[0]
    ind = _ind(lineas[i])
    lineas[i] = bloque_apertura(ind, mqr)
    s = ''.join(lineas)

    # 2. cierre temprano: se pospone a la verificación final
    assert s.count('        hmix.close()\n') == 1, (nombre, 'close temprano')
    s = s.replace('        hmix.close()\n',
                  '        # 6G.1: el descriptor sigue abierto durante todo el DSP\n')

    # 3. post_wav_identity: mismo inodo, no la ruta
    assert s.count('post_wav_identity(mix_info.path') == 1, (nombre, 'post_wav')
    s = s.replace('post_wav_identity(mix_info.path',
                  'post_wav_identity(hmix.ruta_lectura()')

    # 4. análisis de escala sobre el mismo descriptor
    if 'with sf.SoundFile(mix_info.path) as hm:' in s:
        s = s.replace('with sf.SoundFile(mix_info.path) as hm:',
                      'with _abrir_mix_6g1(mix_info.path, mix_info.sha256) as hm:')

    # 5. guarda final: contenido + identidad del descriptor vigilado
    if mqr:
        viejo = ('    ctx["container_6g"]["after"] = _check_unchanged_6g(\n'
                 '        mix_path, mix_info.sha256)\n')
        nuevo = ('    _h6g1 = ctx.get("_mix_handle_6g1")\n'
                 '    try:\n'
                 '        ctx["container_6g"]["after"] = _h6g1.verificar()\n'
                 '        ctx["container_6g"]["ruta_actual"] = _h6g1.ruta_apunta_al_mismo_objeto()\n'
                 '        _h6g1.close()\n'
                 '    except Exception as _exc6g1:\n'
                 '        ctx["container_6g"]["after"] = _check_unchanged_6g(\n'
                 '            mix_path, mix_info.sha256)\n'
                 '        ctx["container_6g"]["ruta_actual"] = dict(unchanged=True)\n'
                 '        log("[6G.1] descriptor no disponible: %s" % _exc6g1)\n')
        viejo_fin = ('    if not ctx["container_6g"]["after"].get("unchanged"):\n'
                     '        log("[FATAL] El Mix cambió durante el procesamiento: "\n'
                     '            + str(ctx["container_6g"]["after"]))\n'
                     '        return EXIT_PROCESSING, None\n')
        nuevo_fin = ('    if not (ctx["container_6g"]["after"].get("unchanged")\n'
                     '            and ctx["container_6g"].get("ruta_actual", {}).get("unchanged")):\n'
                     '        _info6g1 = _abortar_6g1(\n'
                     '            run_dir_final, "MIX_CAMBIADO_DURANTE_EL_PROCESAMIENTO",\n'
                     '            ctx["container_6g"])\n'
                     '        log("[FATAL] Mix cambiado: salidas de audio invalidadas: %s"\n'
                     '            % _info6g1["salidas_invalidadas"])\n'
                     '        return EXIT_PROCESSING, None\n')
    else:
        viejo = ('        ctx["container_6g"]["after"] = _check_unchanged_6g(\n'
                 '            mix_path, mix_info.sha256)\n')
        nuevo = ('        try:\n'
                 '            ctx["container_6g"]["after"] = hmix.verificar()\n'
                 '            ctx["container_6g"]["ruta_actual"] = hmix.ruta_apunta_al_mismo_objeto()\n'
                 '            hmix.close()\n'
                 '        except Exception as _exc6g1:\n'
                 '            ctx["container_6g"]["after"] = _check_unchanged_6g(\n'
                 '                mix_path, mix_info.sha256)\n'
                 '            ctx["container_6g"]["ruta_actual"] = dict(unchanged=True)\n'
                 '            log("[6G.1] descriptor no disponible: %s" % _exc6g1)\n')
        viejo_fin = ('        if not ctx["container_6g"]["after"].get("unchanged"):\n'
                     '            log("[FATAL] El Mix cambió durante el procesamiento: "\n'
                     '                + str(ctx["container_6g"]["after"]))\n'
                     '            return EXIT_PROCESSING, None\n')
        nuevo_fin = ('        if not (ctx["container_6g"]["after"].get("unchanged")\n'
                     '                and ctx["container_6g"].get("ruta_actual", {}).get("unchanged")):\n'
                     '            _info6g1 = _abortar_6g1(\n'
                     '                run_dir_final, "MIX_CAMBIADO_DURANTE_EL_PROCESAMIENTO",\n'
                     '                ctx["container_6g"])\n'
                     '            log("[FATAL] Mix cambiado: salidas de audio invalidadas: %s"\n'
                     '                % _info6g1["salidas_invalidadas"])\n'
                     '            return EXIT_PROCESSING, None\n')

    assert s.count(viejo) == 1, (nombre, 'guarda 6G')
    s = s.replace(viejo, nuevo)
    assert s.count(viejo_fin) == 1, (nombre, 'fin 6G')
    s = s.replace(viejo_fin, nuevo_fin)

    p.write_text(s, encoding='utf-8')
    print('parcheado:', nombre)


def parchear_mqr_escala():
    """MQR lee el Mix por ruta en guide_scale_analysis: usar el mismo inodo."""
    p = MOT / 'sdv_sdi_mqr_engine.py'
    s = p.read_text(encoding='utf-8')
    viejo = ('    mix_common = stream_level_stats(mix_info.path,\n'
             '                                    limit_frames=mix_info.frames)\n')
    if viejo not in s:
        print('MQR escala: patrón ausente')
        return
    nuevo = ('    with _abrir_mix_6g1(mix_info.path, mix_info.sha256) as _hm6g1:\n'
             '        mix_common = stream_level_stats(_hm6g1.ruta_lectura(),\n'
             '                                        limit_frames=mix_info.frames)\n')
    s = s.replace(viejo, nuevo)
    p.write_text(s, encoding='utf-8')
    print('parcheado: MQR guide_scale usa el descriptor')


def main():
    for nombre in MOTORES:
        parchear(nombre)
    parchear_mqr_escala()


if __name__ == '__main__':
    main()
