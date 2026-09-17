import os
from runtime_config import configure

if __name__ == '__main__':
    configure()
    port=int(os.environ.get('PORT','8000'))
    if not 1<=port<=65535:
        raise RuntimeError('PORT debe estar entre 1 y 65535.')
    import uvicorn
    uvicorn.run('server:app',host='0.0.0.0',port=port,workers=1,proxy_headers=False)
