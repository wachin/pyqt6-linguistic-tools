# PyQt6 Linguistic Tools

Infraestructura lingüística reutilizable para aplicaciones Python y PyQt6.
El proyecto tendrá una sola API multiplataforma para corrección ortográfica,
sugerencias y sinónimos.

El desarrollo se encuentra en la etapa de estabilización de sus motores
portables:

- [Spylls](https://github.com/zverok/spylls), para diccionarios Hunspell.
- [PyThes](https://github.com/corerd/pythes), para tesauros MyThes.

Hunspell y MyThes nativos quedan fuera de esta primera etapa. En el futuro
podrán existir como backends opcionales sin cambiar la API pública.

## Preparar el repositorio

```bash
git submodule update --init --recursive
python -m pip install -e '.[test]'
python -m pytest
```

Las pruebas rápidas no necesitan descargar diccionarios externos. La suite de
compatibilidad usa una colección de LibreOffice indicada explícitamente:

```bash
LIBREOFFICE_DICTIONARIES_PATH=/ruta/a/dicts \
  python -m pytest -m 'corpus and not full_corpus'
```

También se puede utilizar:

```bash
python -m pytest -m 'corpus and not full_corpus' \
  --dictionary-corpus=/ruta/a/dicts
```

La pasada completa de tesauros se reserva para ejecución manual o programada:

```bash
python -m pytest -m full_corpus --dictionary-corpus=/ruta/a/dicts
```

La ruta nunca queda incorporada al paquete. Consulta
[`docs/engine-baseline.md`](docs/engine-baseline.md) para conocer el estado
inicial comprobado de los motores.
