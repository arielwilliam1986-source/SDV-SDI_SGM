# Etapa 6G.1 — Auditoría del runner, propuesta de aislamiento y detector F

Repositorio de **solo materiales de revisión**. No contiene código ejecutable
del proyecto original, no se conecta a nada y no ejecuta ningún motor.

**Estado de la propuesta: `PENDIENTE_REVISION_CRIS`**
No está aprobada. No está autorizada su ejecución. Un resultado estático
positivo **no** es validación dinámica.

---

## Qué hay aquí

| Carpeta | Contenido |
|---|---|
| `01_propuesta/` | La propuesta completa del runner y el parche unificado |
| `02_original/` | El runner original del commit, **sin modificar** (referencia) |
| `03_pruebas/` | Los dos bancos de pruebas sintéticas y sus salidas reales |
| `04_informes/` | Los paquetes de entrega en texto plano |

---

## Identidades (SHA-256)

Verificables con `sha256sum`. Son la referencia de integridad.

```
7b1165e834bea12ed58f077cb3bf6f9e494c41d1105494c8c82f581663dcb4c5  01_propuesta/pruebas_auditoria_cierre_6g1.PROPUESTA.py
79d5501ef1fa2b512f29c37919cc33613094094dc366b2cb077a68d812a92fdb  01_propuesta/propuesta_6g1.patch
31f724b3d19b89ea9210cdd02e1d5a94bc5fd5bdfdc86e7c651c9d0acdc54852  02_original/pruebas_auditoria_cierre_6g1.ORIGINAL.py
```

El fichero `SHA256SUMS.txt` contiene la lista completa.

---

## De dónde sale la propuesta

Del **runner original del commit**, con este hash:

```
31f724b3d19b89ea9210cdd02e1d5a94bc5fd5bdfdc86e7c651c9d0acdc54852
```

Ese original es el de:

```
ETAPA_6G1_CORRECCION_LECTURA_SEGURA/scripts/pruebas_auditoria_cierre_6g1.py
```

en el repositorio `arielwilliam1986-source/SDV-SDI_SGM`, commit
`c80f7f11651e08267a4929527b3035ae40c39e13`.

**No** se ha usado como fuente ningún runner reconstruido anterior. Esa
reconstrucción dio un hash distinto del aprobado y quedó descartada.

---

## Cómo reconstruir y verificar

```bash
cp 02_original/pruebas_auditoria_cierre_6g1.ORIGINAL.py pruebas_auditoria_cierre_6g1.py
patch -p1 < 01_propuesta/propuesta_6g1.patch
sha256sum pruebas_auditoria_cierre_6g1.py
# debe dar 7b1165e8...cdb4c5
```

Comprobado: el parche aplica limpiamente sobre el original y reproduce la
propuesta byte a byte.

---

## Pruebas

```bash
cd 03_pruebas
python3 -B test_rutas_sinteticas.py        # 23/23
python3 -B test_detector_f_sintetico.py    # 26/26
```

Ambos bancos son autocontenidos: crean sus propios árboles temporales y los
borran. No tocan el repositorio oficial salvo para leer.

Las salidas están guardadas en `SALIDA_*.txt`, tal como se obtuvieron.

### Control sobre los motores reales

`03_pruebas/SALIDA_motores_reales.txt` recoge el análisis estático de los tres
motores (Hardened, EVO, MQR). **Se leyeron y parsearon, nunca se ejecutaron.**

Resultado: los tres dan `CONCLUYENTE_TRUE` en su función de liberación.
`validacion_dinamica` sigue `PENDIENTE`.

---

## Lo que este repositorio NO afirma

- No afirma que el runner esté aprobado.
- No afirma que el aislamiento sea completo. Quedan ventanas TOCTOU
  documentadas que solo se cerrarían anclando las operaciones a descriptores
  (trabajo futuro, PDA-1).
- No afirma que la validación dinámica esté hecha.
- No convierte ningún `UNKNOWN` histórico en `PASS`.
- No modifica ni reinterpreta los veredictos de las etapas anteriores.

---

## Qué se ejecutó y qué no

**No se ejecutó:** `main()`, `bateria()`, `ejecutar()`, el inyector, ninguno de
los tres motores, ningún procesamiento de audio, la batería de 27 escenarios,
ni el C5 histórico D18-R1.

**No se instaló** ninguna dependencia.

**No se modificó** ningún archivo del repositorio oficial del proyecto.

Solo se ejecutaron los dos bancos sintéticos de `03_pruebas/`.
