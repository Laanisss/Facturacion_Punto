"""Runs UI checks only against an isolated disposable local server."""
import os,socket,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix='punto-ui-') as folder:
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    origin=f'http://127.0.0.1:{port}'
    env={k:v for k,v in os.environ.items() if not k.startswith('RAILWAY_')}
    env.update(PUNTO_DB=str(Path(folder)/'test.sqlite3'),PUNTO_ORIGIN=origin,PUNTO_TEST_ORIGIN=origin)
    subprocess.run([sys.executable,'-c',"import server\nwith server.connection() as c: c.execute('INSERT INTO users VALUES(?,?,?,?,NULL)',('qa-admin','qa-admin',server.password_hash('qa-admin-password-123'),'admin'))"],cwd=root,env=env,check=True)
    with open(Path(folder)/'server.log','w+') as log:
        process=subprocess.Popen([sys.executable,'-m','uvicorn','server:app','--host','127.0.0.1','--port',str(port)],cwd=root,env=env,stdout=log,stderr=log)
        try:
            for _ in range(100):
                try:
                    with urllib.request.urlopen(origin+'/health',timeout=1): break
                except Exception: time.sleep(.1)
            else: raise RuntimeError('Servidor de prueba no disponible')
            for script in ('ui.mjs','ui-billing.mjs','ui-operations.mjs','ui-promotions.mjs'):
                subprocess.run(['node','tests/'+script],cwd=root,env=env,check=True,timeout=60)
        except Exception:
            log.seek(0);print(log.read());raise
        finally:
            process.terminate();process.wait(timeout=10)
