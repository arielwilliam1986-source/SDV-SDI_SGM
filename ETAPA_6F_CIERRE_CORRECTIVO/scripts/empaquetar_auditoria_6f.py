"""Empaqueta el expediente 6F en dos tomos de texto autocontenidos.

Uso: python -B scripts/empaquetar_auditoria_6f.py

Tomo 1: índice + los nueve informes.
Tomo 2: manifiesto resumido, hashes y las tres matrices completas.
El paquete se regenera de las fuentes; no contiene datos propios.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent

INFORMES = [
    ('INFORME_IMPLEMENTACION_6F.md', 'Informe de implementación'),
    ('INFORME_VALIDACION_INDEPENDIENTE_6F.md', 'Informe de validación con reserva independiente'),
    ('AUDITORIA_CLI_6F.md', 'Auditoría de CLI y bloqueos'),
    ('AUDITORIA_WAV_6F.md', 'Auditoría de integridad WAV'),
    ('DIAGNOSTICO_MQR_S7_6F.md', 'Diagnóstico MQR S7'),
    ('ANALISIS_ESTEREO_LR_6F.md', 'Análisis estéreo L/R'),
    ('NO_REGRESION_DSP_6F.md', 'No regresión DSP'),
    ('RECURSOS_Y_DURACIONES_6F.md', 'Recursos y duraciones'),
    ('LIMITACIONES_Y_CASOS_UNKNOWN_6F.md', 'Limitaciones y casos fuera de capacidad'),
]

CABECERA = """# Etapa 6F · {titulo}

Documento autogenerado por `scripts/empaquetar_auditoria_6f.py`.
Fuente: `arielwilliam1986-source/SDV-SDI_SGM`, rama
`arena/89d5c189-sdv-sdi-sgm`, base `b72ce49ae787c72a1148bbec95db35dba460d279`,
congelamiento `5d344e1`. Cualquier cifra de este tomo proviene de los informes y
la evidencia versionada; el tomo no añade afirmaciones nuevas.

Dictamen de la etapa: **APROBADO CON LIMITACIONES** (ver §Limitaciones).

---
"""


def seccion(titulo, texto, nivel='##'):
    return f'\n{nivel} {titulo}\n\n{texto.strip()}\n'


def main():
    partes = [CABECERA.format(titulo='Tomo 1 · Informes')]
    partes.append(seccion('Índice', (HERE / 'INDICE_PARA_AUDITORIA.md').read_text(encoding='utf-8')))
    for archivo, titulo in INFORMES:
        partes.append('\n---\n')
        partes.append(seccion(titulo, (HERE / archivo).read_text(encoding='utf-8')))
    t1 = ''.join(partes)
    (HERE / 'AUDITORIA_6F_TOMO_1_INFORMES.md').write_text(t1, encoding='utf-8')

    partes = [CABECERA.format(titulo='Tomo 2 · Evidencia, hashes y matrices')]
    partes.append(seccion('Hashes del expediente',
                          (HERE / 'SHA256SUMS.txt').read_text(encoding='utf-8'), nivel='##'))
    for archivo, titulo in (('MATRIZ_RESULTADOS_6F.csv', 'Matriz de atribución (desarrollo + reserva)'),
                            ('MATRIZ_CLI_6F.csv', 'Matriz de CLI'),
                            ('MATRIZ_WAV_6F.csv', 'Matriz de WAV')):
        partes.append('\n---\n')
        partes.append(seccion(f'{titulo} — `{archivo}`',
                              '```csv\n' + (HERE / archivo).read_text(encoding='utf-8').strip() + '\n```'))
    partes.append(seccion('Cómo verificar',
                          '```sh\ncd ETAPA_6F_CIERRE_CORRECTIVO && sha256sum -c SHA256SUMS.txt\n```\n'
                          'Cada JSON de `evidence/` se regenera con los scripts listados en `README.md`. '
                          'El código completo de los tres motores y de los dos módulos nuevos está en '
                          '`motores/`; los scripts de prueba en `scripts/`.'))
    t2 = ''.join(partes)
    (HERE / 'AUDITORIA_6F_TOMO_2_EVIDENCIA.md').write_text(t2, encoding='utf-8')

    for nombre in ('AUDITORIA_6F_TOMO_1_INFORMES.md', 'AUDITORIA_6F_TOMO_2_EVIDENCIA.md'):
        p = HERE / nombre
        print(f'{nombre}: {p.stat().st_size} bytes, '
              f'{sum(1 for _ in p.open(encoding="utf-8"))} líneas')


if __name__ == '__main__':
    main()
