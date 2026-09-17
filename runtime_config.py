"""Validación de persistencia y origen antes de abrir la base en Railway."""
import os
from pathlib import Path
from urllib.parse import urlsplit

def configure(environ=None):
    env = os.environ if environ is None else environ
    if not (env.get('RAILWAY_ENVIRONMENT_ID') or env.get('RAILWAY_SERVICE_ID')):
        return
    origin = env.get('PUNTO_ORIGIN','').rstrip('/')
    url = urlsplit(origin)
    if url.scheme!='https' or not url.hostname or url.path or url.query or url.fragment or url.username or url.password:
        raise RuntimeError('En Railway configura PUNTO_ORIGIN con el dominio HTTPS exacto, sin rutas.')
    mount = env.get('RAILWAY_VOLUME_MOUNT_PATH')
    database = env.get('PUNTO_DB')
    if not mount or not database:
        raise RuntimeError('Conecta un volumen persistente y configura PUNTO_DB dentro de él.')
    volume = Path(mount).resolve()
    path = Path(database)
    if not path.is_absolute() or not path.resolve().is_relative_to(volume) or path.resolve()==volume:
        raise RuntimeError('PUNTO_DB debe ser un archivo dentro del volumen persistente.')
    if not volume.is_dir():
        raise RuntimeError('El volumen persistente no está montado.')
