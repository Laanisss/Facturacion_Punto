import pytest
from runtime_config import configure

def environment(tmp_path):
    return {'RAILWAY_SERVICE_ID':'test','PUNTO_ORIGIN':'https://punto.example',
            'RAILWAY_VOLUME_MOUNT_PATH':str(tmp_path),'PUNTO_DB':str(tmp_path/'punto.sqlite3')}

def test_railway_requires_volume(tmp_path):
    env=environment(tmp_path);del env['RAILWAY_VOLUME_MOUNT_PATH']
    with pytest.raises(RuntimeError,match='volumen'):configure(env)

def test_railway_rejects_ephemeral_database(tmp_path):
    env=environment(tmp_path);env['PUNTO_DB']='/app/data/db.sqlite3'
    with pytest.raises(RuntimeError,match='volumen'):configure(env)

def test_railway_rejects_http_origin(tmp_path):
    env=environment(tmp_path);env['PUNTO_ORIGIN']='http://localhost:8000'
    with pytest.raises(RuntimeError,match='HTTPS'):configure(env)

def test_railway_valid_config_and_local_defaults(tmp_path):
    configure(environment(tmp_path));configure({})
