"""Punto 0.3.1: base de servidor para desarrollo/piloto; no procesa pagos BAC."""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from runtime_config import configure

configure()
ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('PUNTO_DB', str(ROOT / 'data' / 'punto.sqlite3')))
ORIGIN = os.environ.get('PUNTO_ORIGIN', 'http://127.0.0.1:8000').rstrip('/')
SECURE = ORIGIN.startswith('https://')
app = FastAPI(title='Punto', version='0.3.1', docs_url=None, redoc_url=None, openapi_url=None)

@contextmanager
def connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

def init_db():
    with connection() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript('''
        CREATE TABLE IF NOT EXISTS businesses(id TEXT PRIMARY KEY, name TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'trial', plan TEXT NOT NULL DEFAULT 'trial',
          expires INTEGER NOT NULL, state TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE,
          password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('owner','admin')),
          business_id TEXT REFERENCES businesses(id));
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),
          csrf TEXT NOT NULL, expires INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS sales(id TEXT PRIMARY KEY,business_id TEXT NOT NULL REFERENCES businesses(id),
          request_id TEXT NOT NULL,request_hash TEXT NOT NULL,data TEXT NOT NULL,
          UNIQUE(business_id,request_id));
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,actor TEXT NOT NULL,action TEXT NOT NULL,
          target TEXT NOT NULL,detail TEXT NOT NULL,created INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS rate_limits(bucket TEXT PRIMARY KEY,count INTEGER NOT NULL,expires INTEGER NOT NULL);
        PRAGMA user_version=1;
        ''')

class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class Credentials(Model):
    username: str = Field(min_length=3, max_length=40, pattern=r'^[a-zA-Z0-9_.-]+$')
    password: str = Field(min_length=10, max_length=128)
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)

class Registration(Credentials):
    business: str = Field(min_length=1, max_length=70)

    @field_validator('business')
    @classmethod
    def clean_business(cls, value):
        value=value.strip()
        if not value:
            raise ValueError('Escribe el nombre del negocio')
        return value

class Settings(Model):
    name: str = Field(min_length=1, max_length=70)
    currency: Literal['L','$','€'] = 'L'
    color: str = Field(default='#17684b', pattern=r'^#[0-9a-fA-F]{6}$')
    type: Literal['Comida','Tienda','Negocio general'] = 'Comida'
    message: str = Field(default='¡Gracias por tu compra!', max_length=120)
    template: Literal['natural','boutique','studio'] = 'natural'
    logo: str = Field(default='', max_length=450000)

    @field_validator('logo')
    @classmethod
    def valid_image(cls, value):
        if value and not re.fullmatch(r'data:image/(?:png|jpeg|webp);base64,[A-Za-z0-9+/=]+', value):
            raise ValueError('Imagen no válida')
        return value

class Product(Model):
    id: str = Field(min_length=1,max_length=50,pattern=r'^[a-zA-Z0-9_-]+$')
    name: str = Field(min_length=1,max_length=80)
    price: int = Field(gt=0,le=1_000_000_000,strict=True)
    category: str = Field(min_length=1,max_length=35)
    stock: int = Field(ge=0,le=1_000_000,strict=True)
    icon: str = Field(default='📦',max_length=24)
    image: str = Field(default='',max_length=450000)
    _image = field_validator('image')(Settings.valid_image.__func__)

class StateUpdate(Model):
    settings: Settings
    products: list[Product] = Field(max_length=1000)
    revision: int = Field(ge=0,strict=True)

class Line(Model):
    id: str = Field(min_length=1,max_length=50)
    quantity: int = Field(ge=1,le=1000000,strict=True)

class SaleInput(Model):
    request_id: str = Field(min_length=16,max_length=64,pattern=r'^[a-zA-Z0-9_-]+$')
    revision: int = Field(ge=0,strict=True)
    lines: list[Line] = Field(min_length=1,max_length=1000)
    method: Literal['cash','card_simulated']
    received: int = Field(ge=0,le=1_000_000_000_000,strict=True)
    scenario: Literal['approved','declined','error'] = 'approved'

class Subscription(Model):
    status: Literal['trial','active','suspended']
    plan: Literal['trial','basic','pro']
    expires: int = Field(ge=0,le=4102444800,strict=True)
    reason: str = Field(min_length=3,max_length=200)


def password_hash(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    result = hashlib.scrypt(password.encode(),salt=salt,n=32768,r=8,p=1,dklen=32,maxmem=64*1024*1024)
    return salt.hex()+':'+result.hex()

def verify(password, stored):
    salt = bytes.fromhex(stored.split(':')[0])
    return hmac.compare_digest(password_hash(password,salt),stored)

def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()

def throttle(request, action):
    bucket = action+':'+(request.client.host if request.client else 'unknown')
    now = int(time.time())
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('DELETE FROM rate_limits WHERE expires < ?', (now,))
        row = c.execute('SELECT * FROM rate_limits WHERE bucket=?',(bucket,)).fetchone()
        if row and row['count']>=20:
            raise HTTPException(429,'Demasiados intentos. Intenta de nuevo en 15 minutos.')
        c.execute('INSERT INTO rate_limits VALUES(?,?,?) ON CONFLICT(bucket) DO UPDATE SET count=count+1',
                  (bucket,1,now+900))

def identity(request):
    raw = request.cookies.get('punto_session','')
    with connection() as c:
        row = c.execute('''SELECT u.*,s.csrf,s.expires FROM sessions s JOIN users u ON u.id=s.user_id
          WHERE s.token_hash=? AND s.expires>?''',(token_hash(raw),int(time.time()))).fetchone()
    if not row:
        raise HTTPException(401,'Inicia sesión para continuar.')
    if request.method not in ('GET','HEAD') and not hmac.compare_digest(request.headers.get('x-csrf-token',''),row['csrf']):
        raise HTTPException(403,'Sesión de seguridad no válida. Vuelve a iniciar sesión.')
    return dict(row)

def owner(request):
    u = identity(request)
    if not u['business_id']:
        raise HTTPException(403,'Esta cuenta administra la plataforma; no tiene una caja.')
    return u

def admin(request):
    u = identity(request)
    if u['role']!='admin':
        raise HTTPException(403,'Solo el administrador de la plataforma tiene acceso.')
    return u

def check_writes(b):
    if b['status']=='suspended' or b['expires']<=int(time.time()):
        raise HTTPException(403,'La suscripción está suspendida o vencida. Puedes consultar y exportar tus datos.')

def state_result(c,bid):
    b = c.execute('SELECT * FROM businesses WHERE id=?',(bid,)).fetchone()
    data = json.loads(b['state'])
    data['sales']=[json.loads(r['data']) for r in c.execute('SELECT data FROM sales WHERE business_id=? ORDER BY rowid',(bid,))]
    data['revision']=b['revision']
    return data

def user_result(u):
    result={'username':u['username'],'role':u['role'],'csrf':u['csrf'],'business':None}
    if u['business_id']:
        with connection() as c:
            b=c.execute('SELECT id,name,status,plan,expires FROM businesses WHERE id=?',(u['business_id'],)).fetchone()
            result['business']=dict(b)
    return result

def new_session(c,uid,response):
    raw,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
    c.execute('DELETE FROM sessions WHERE expires<?',(int(time.time()),))
    c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(token_hash(raw),uid,csrf,int(time.time())+28800))
    response.set_cookie('punto_session',raw,max_age=28800,httponly=True,secure=SECURE,samesite='strict',path='/')
    return csrf

@app.middleware('http')
async def perimeter(request,call_next):
    if request.method in ('POST','PUT','PATCH','DELETE'):
        if request.headers.get('origin')!=ORIGIN:
            return JSONResponse({'detail':'Origen no autorizado.'},403)
        # No browser forms or cross-origin scripts can submit changes.
        if request.headers.get('content-type','').split(';')[0]!='application/json':
            return JSONResponse({'detail':'Se requiere JSON.'},415)
        length=0;parts=[]
        async for chunk in request.stream():
            length+=len(chunk)
            if length>8*1024*1024:
                return JSONResponse({'detail':'Solicitud demasiado grande (máximo 8 MB).'},413)
            parts.append(chunk)
        request._body=b''.join(parts)
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['X-Frame-Options']='DENY'
    return response

@app.get('/health')
def health():
    try:
        with connection() as c:
            c.execute('SELECT id FROM businesses LIMIT 1').fetchone()
        return {'status':'ok'}
    except sqlite3.Error:
        return JSONResponse({'status':'unavailable'},503)

@app.get('/')
def index():
    text=(ROOT/'static'/'index.html').read_text()
    script=text.split('<script>')[1].split('</script>')[0]
    digest=base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    return HTMLResponse(text,headers={'Content-Security-Policy':f"default-src 'self'; script-src 'self' 'sha256-{digest}'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"})

@app.post('/api/register')
def register(data:Registration,request:Request,response:Response):
    throttle(request,'register')
    username=data.username.lower();bid,uid=str(uuid.uuid4()),str(uuid.uuid4())
    hashed=password_hash(data.password)
    with connection() as c:
        if c.execute('SELECT 1 FROM users WHERE username=?',(username,)).fetchone():
            raise HTTPException(409,'Usuario no disponible.')
        state={'settings':Settings(name=data.business).model_dump(),'products':[]}
        c.execute('INSERT INTO businesses(id,name,expires,state) VALUES(?,?,?,?)',
                  (bid,data.business,int(time.time())+14*86400,json.dumps(state)))
        c.execute('INSERT INTO users VALUES(?,?,?,?,?)',(uid,username,hashed,'owner',bid))
        csrf=new_session(c,uid,response)
    return {'username':username,'role':'owner','csrf':csrf}

@app.post('/api/login')
def login(data:Credentials,request:Request,response:Response):
    throttle(request,'login')
    with connection() as c:
        u=c.execute('SELECT * FROM users WHERE username=?',(data.username.lower(),)).fetchone()
        if not u:
            password_hash(data.password) # Comparable work for unknown usernames.
            raise HTTPException(401,'Usuario o contraseña incorrectos.')
        if not verify(data.password,u['password_hash']):
            raise HTTPException(401,'Usuario o contraseña incorrectos.')
        c.execute('DELETE FROM sessions WHERE token_hash=?',(token_hash(request.cookies.get('punto_session','')),))
        csrf=new_session(c,u['id'],response)
    return {'username':u['username'],'role':u['role'],'csrf':csrf}

@app.get('/api/me')
def me(request:Request):
    return user_result(identity(request))

@app.post('/api/logout')
def logout(request:Request,response:Response):
    identity(request)
    with connection() as c:
        c.execute('DELETE FROM sessions WHERE token_hash=?',(token_hash(request.cookies.get('punto_session','')),))
    response.delete_cookie('punto_session',path='/')
    return {'ok':True}

@app.get('/api/state')
def state(request:Request):
    u=owner(request)
    with connection() as c:
        return state_result(c,u['business_id'])

@app.put('/api/state')
def update_state(data:StateUpdate,request:Request):
    u=owner(request)
    ids=[p.id for p in data.products]
    if len(ids)!=len(set(ids)):
        raise HTTPException(422,'Los productos deben tener identificadores únicos.')
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        b=c.execute('SELECT * FROM businesses WHERE id=?',(u['business_id'],)).fetchone()
        check_writes(b)
        if b['revision']!=data.revision:
            raise HTTPException(409,'Otro equipo cambió estos datos. Recarga antes de guardar.')
        old=json.loads(b['state'])
        has_sales=c.execute('SELECT 1 FROM sales WHERE business_id=?',(b['id'],)).fetchone()
        if has_sales and data.settings.currency!=old['settings']['currency']:
            raise HTTPException(409,'No puedes cambiar la moneda después de registrar ventas.')
        payload=data.model_dump(exclude={'revision'})
        c.execute('UPDATE businesses SET state=?,name=?,revision=revision+1 WHERE id=?',
                  (json.dumps(payload),data.settings.name,b['id']))
        return state_result(c,b['id'])

@app.post('/api/sales')
def create_sale(data:SaleInput,request:Request):
    u=owner(request)
    fingerprint=hashlib.sha256(data.model_dump_json().encode()).hexdigest()
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        previous=c.execute('SELECT * FROM sales WHERE business_id=? AND request_id=?',(u['business_id'],data.request_id)).fetchone()
        if previous:
            if previous['request_hash']!=fingerprint:
                raise HTTPException(409,'La referencia ya fue utilizada para otro pedido.')
            return {'sale':json.loads(previous['data']),'state':state_result(c,u['business_id'])}
        b=c.execute('SELECT * FROM businesses WHERE id=?',(u['business_id'],)).fetchone();check_writes(b)
        if b['revision']!=data.revision:
            raise HTTPException(409,'Cambió el catálogo. Recarga y revisa el pedido.')
        state=json.loads(b['state']);products={p['id']:p for p in state['products']};lines=[];seen=set();total=0
        for item in data.lines:
            if item.id in seen:
                raise HTTPException(422,'Producto repetido.')
            seen.add(item.id);p=products.get(item.id)
            if not p or p['stock']<item.quantity:
                raise HTTPException(409,'Producto no disponible o existencias insuficientes.')
            total+=p['price']*item.quantity
            lines.append({**{k:v for k,v in p.items() if k!='image'},'quantity':item.quantity})
        card=data.method=='card_simulated'
        if card and data.scenario!='approved':
            raise HTTPException(402 if data.scenario=='declined' else 503,
                                'Tarjeta de prueba rechazada.' if data.scenario=='declined' else 'Terminal simulado sin conexión.')
        if not card and data.received<total:
            raise HTTPException(422,'El efectivo no cubre el total.')
        payment={'method':data.method,'status':'simulated_approved' if card else 'recorded'}
        if card:
            payment.update(reference='SIM-'+uuid.uuid4().hex[:8].upper(),last4='0000')
        sale={'id':str(uuid.uuid4()),'date':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'total':total,
              'received':total if card else data.received,'payment':payment,'settings':state['settings'],'lines':lines}
        for line in lines:
            products[line['id']]['stock']-=line['quantity']
        c.execute('UPDATE businesses SET state=?,revision=revision+1 WHERE id=?',(json.dumps(state),b['id']))
        c.execute('INSERT INTO sales VALUES(?,?,?,?,?)',(sale['id'],b['id'],data.request_id,fingerprint,json.dumps(sale)))
        return {'sale':sale,'state':state_result(c,b['id'])}

@app.get('/api/admin/businesses')
def businesses(request:Request):
    admin(request)
    with connection() as c:
        return [dict(r) for r in c.execute('''SELECT b.id,b.name,b.status,b.plan,b.expires,u.username,
            (SELECT COUNT(*) FROM sales s WHERE s.business_id=b.id) AS sales_count
            FROM businesses b JOIN users u ON u.business_id=b.id ORDER BY b.rowid DESC''')]

@app.patch('/api/admin/businesses/{bid}/subscription')
def subscription(bid:str,data:Subscription,request:Request):
    u=admin(request)
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        old=c.execute('SELECT status,plan,expires FROM businesses WHERE id=?',(bid,)).fetchone()
        if not old:
            raise HTTPException(404,'Negocio no encontrado.')
        c.execute('UPDATE businesses SET status=?,plan=?,expires=? WHERE id=?',(data.status,data.plan,data.expires,bid))
        c.execute('INSERT INTO audit(actor,action,target,detail,created) VALUES(?,?,?,?,?)',
                  (u['id'],'subscription.changed',bid,json.dumps({'before':dict(old),'after':data.model_dump()}),int(time.time())))
    return {'ok':True}

@app.get('/api/admin/audit')
def audit(request:Request):
    admin(request)
    with connection() as c:
        return [dict(r) for r in c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 100')]

@app.get('/api/payments/bac-hit/status')
def bac_status(request:Request):
    identity(request)
    return {'provider':'BAC HIT','connected':False,'mode':'blocked',
            'reason':'Pendiente de documentación oficial y acceso de BAC. No hay conexión automática a HIT.',
            'official_url':'https://www.baccredomatic.com/es-hn/pymes/puntos-de-venta'}

@app.post('/api/payments/bac-hit/charge')
def bac_charge(request:Request):
    owner(request)
    raise HTTPException(501,'BAC HIT no está integrado. No se ha enviado ningún cobro.')

init_db()
