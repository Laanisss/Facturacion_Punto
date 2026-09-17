"""Administración local del servidor; nunca expone una ruta para crear administradores."""
import getpass
import re
import sqlite3
import sys
import uuid
from pathlib import Path
from server import connection, password_hash, DB_PATH

if len(sys.argv)<2:
    raise SystemExit('Uso: python manage.py create-admin | backup DESTINO.sqlite3')
if sys.argv[1]=='create-admin':
    username=input('Usuario administrador: ').strip().lower()
    if not re.fullmatch(r'[a-z0-9_.-]{3,40}',username):
        raise SystemExit('Usuario no válido.')
    password=getpass.getpass('Contraseña (mínimo 12 caracteres): ')
    if len(password)<12 or len(password)>128 or password!=getpass.getpass('Repite la contraseña: '):
        raise SystemExit('Contraseña demasiado corta o no coincide.')
    with connection() as c:
        if c.execute('SELECT 1 FROM users WHERE username=?',(username,)).fetchone():
            raise SystemExit('Ese usuario ya existe. No se modificó.')
        c.execute('INSERT INTO users VALUES(?,?,?,?,NULL)',(str(uuid.uuid4()),username,password_hash(password),'admin'))
    print('Administrador creado. Inicia sesión en Punto.')
elif sys.argv[1]=='backup' and len(sys.argv)==3:
    destination=Path(sys.argv[2])
    if destination.exists():
        raise SystemExit('El destino ya existe. Elige otro archivo.')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with sqlite3.connect(DB_PATH) as source,sqlite3.connect(destination) as target:
        source.backup(target)
    print('Copia completa creada. Contiene datos privados: protégela.')
else:
    raise SystemExit('Comando no reconocido.')
