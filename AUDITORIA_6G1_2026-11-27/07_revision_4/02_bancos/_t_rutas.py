"""Pruebas sinteticas de validar_rutas(). No llama a main(), ejecutar() ni bateria().
No ejecuta motores ni toca el repositorio oficial: solo lee de el para verificar."""
import importlib.util, os, sys, shutil, tempfile
from pathlib import Path

sys.dont_write_bytecode = True
ESP = '/home/user/SDV-SDI_SGM/ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts'
sys.path.insert(0, ESP)
spec = importlib.util.spec_from_file_location('prop', '/tmp/prop6g1/pruebas_auditoria_cierre_6g1.PROPUESTA.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

OFICIAL = '/home/user/SDV-SDI_SGM'
BASE = Path(tempfile.mkdtemp(prefix='t6g1_', dir='/tmp'))
copia = BASE / 'copia'
(copia / 'scripts').mkdir(parents=True)
(copia / '.git').mkdir()
res = []

def caso(n, desc, esperado, fn):
    try:
        r = fn()
        ok = r.get('ok', False)
        motivo = r.get('motivo') or ''
    except m.RechazoRutas as exc:
        ok, motivo = False, str(exc)
    except Exception as exc:
        ok, motivo = False, 'EXCEPCION %r' % exc
    acierto = (ok == esperado)
    res.append((n, desc, esperado, ok, acierto, motivo))
    print('  %2d %-46s esperado=%-5s obtenido=%-5s %s  %s' % (
        n, desc, esperado, ok, 'OK ' if acierto else '***', motivo[:78]))

def v(work=None, ev=None, base=None, oficial=OFICIAL):
    return m.validar_rutas(oficial, copia, work or str(BASE/'w'), ev or str(BASE/'e'), base)

# 1 valida fuera de ambos
caso(1, 'ruta valida fuera de ambos repos', True, lambda: v())
# 2 dentro del oficial
caso(2, 'destino dentro del repositorio oficial', False,
     lambda: v(work=OFICIAL + '/tmp_ai'))
# 3 igual al oficial
caso(3, 'destino IGUAL a la raiz oficial', False, lambda: v(work=OFICIAL))
# 4 dentro de la copia
caso(4, 'destino dentro de la copia desechable', False,
     lambda: v(work=str(copia / 'work')))
# 5 preexistente
(BASE/'ya').mkdir()
caso(5, 'directorio preexistente', False, lambda: v(work=str(BASE/'ya')))
# 6 enlace simbolico a zona protegida
os.symlink(OFICIAL, str(BASE/'lnk_of'))
caso(6, 'symlink que apunta al oficial', False, lambda: v(work=str(BASE/'lnk_of/work2')))
# 7 enlace roto
os.symlink(str(BASE/'no_existe'), str(BASE/'lnk_roto'))
caso(7, 'enlace simbolico roto', False, lambda: v(work=str(BASE/'lnk_roto')))
# 8 historico
caso(8, 'ruta historica /tmp/f6g1ai', False, lambda: v(work='/tmp/f6g1ai'))
# 9 work == ev
caso(9, 'work-root igual a evidence-dir', False,
     lambda: v(work=str(BASE), ev=str(BASE)))
# 10 anidados
caso(10, 'work-root dentro de evidence-dir', False,
     lambda: v(work=str(BASE/'e'/'w'), ev=str(BASE/'e')))
# 11 prefijo textual, no componente
caso(11, '/tmp/ab y /tmp/abc: no es anidamiento', True,
     lambda: v(work='/tmp/ab_t6g1', ev='/tmp/abc_t6g1'))
# 12 raiz oficial falsa (sin .git)
(BASE/'falso').mkdir()
caso(12, 'raiz-oficial sin .git: se rechaza', False, lambda: v(oficial=str(BASE/'falso')))
# 13 raiz oficial inexistente
caso(13, 'raiz-oficial inexistente', False, lambda: v(oficial=str(BASE/'nada')))
# 14 relativa
caso(14, 'ruta relativa', False, lambda: v(work='relativa/x'))
# 15 con ..
caso(15, 'ruta con ".."', False, lambda: v(work=str(BASE/'w') + '/../w2'))
# 16 --base dentro del oficial
caso(16, '--base dentro del repositorio oficial', False,
     lambda: v(base=OFICIAL + '/ETAPA_6G1_CORRECCION_LECTURA_SEGURA'))
# 17 --base fuera
caso(17, '--base fuera (copia desechable)', False, lambda: v(base=str(copia)))
# 18 --base legitima
(BASE/'baseok').mkdir()
caso(18, '--base valida fuera de ambos', True, lambda: v(base=str(BASE/'baseok')))
# 19/20 work y ev dentro del oficial por separado
caso(19, 'evidence-dir dentro del oficial', False, lambda: v(ev=OFICIAL + '/ev'))
caso(20, 'work y ev iguales dentro de /tmp protegido', False,
     lambda: v(work='/tmp/f6g1ai/x', ev='/tmp/e9'))
# 21 ancestro que es enlace al oficial (work bajo el enlace)
caso(21, 'ancestro enlazado al oficial', False,
     lambda: v(work=str(BASE/'lnk_of')))
# 22 nombre con prefijo del oficial pero distinto
caso(22, 'nombre que empieza como el oficial', True,
     lambda: v(work='/tmp/SDV-SDI_SGM_falso_t6g1'))
# 23 copia == oficial
caso(23, 'copia igual a la raiz oficial', False,
     lambda: m.validar_rutas(OFICIAL, OFICIAL, str(BASE/'w'), str(BASE/'e')))

malos = [r for r in res if not r[4]]
print()
print('RESULTADO: %d/%d correctos' % (len(res) - len(malos), len(res)))
for r in malos:
    print('  FALLO caso %d: %s -> %s' % (r[0], r[1], r[5]))
shutil.rmtree(BASE)
print('arbol temporal eliminado:', not BASE.exists())
