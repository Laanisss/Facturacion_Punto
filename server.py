"""Punto 0.5.1-beta: base de servidor para desarrollo/piloto; no procesa pagos BAC."""
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
app = FastAPI(title='Punto', version='0.5.1-beta', docs_url=None, redoc_url=None, openapi_url=None)

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
        version=c.execute('PRAGMA user_version').fetchone()[0]
        if version>4:
            raise RuntimeError('Base de datos más nueva que este servidor.')
        if version in (1,2,3):
            backup=DB_PATH.parent/'backups'/('antes-0.5.1-'+str(time.time_ns())+'.sqlite3')
            backup.parent.mkdir(parents=True,exist_ok=True)
            with sqlite3.connect(backup) as target:
                c.backup(target)
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript('''
        BEGIN IMMEDIATE;
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
        CREATE TABLE IF NOT EXISTS plan_prices(plan TEXT PRIMARY KEY,amount INTEGER);
        INSERT OR IGNORE INTO plan_prices VALUES('basic',NULL),('pro',NULL);
        CREATE TABLE IF NOT EXISTS subscription_requests(
          id TEXT PRIMARY KEY,business_id TEXT NOT NULL REFERENCES businesses(id),
          plan TEXT NOT NULL,amount INTEGER NOT NULL,status TEXT NOT NULL DEFAULT 'pending',
          created INTEGER NOT NULL,processed INTEGER,reference TEXT NOT NULL DEFAULT '',
          note TEXT NOT NULL DEFAULT '');
        CREATE UNIQUE INDEX IF NOT EXISTS one_pending_request
          ON subscription_requests(business_id) WHERE status='pending';
        CREATE TABLE IF NOT EXISTS customers(id TEXT PRIMARY KEY,business_id TEXT NOT NULL REFERENCES businesses(id),
          name TEXT NOT NULL,phone TEXT NOT NULL,note TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS shifts(id TEXT PRIMARY KEY,business_id TEXT NOT NULL REFERENCES businesses(id),
          opened INTEGER NOT NULL,closed INTEGER,opening INTEGER NOT NULL,counted INTEGER,expected INTEGER,note TEXT NOT NULL DEFAULT '');
        CREATE UNIQUE INDEX IF NOT EXISTS one_open_shift ON shifts(business_id) WHERE closed IS NULL;
        CREATE TABLE IF NOT EXISTS cash_movements(id TEXT PRIMARY KEY,business_id TEXT NOT NULL REFERENCES businesses(id),
          shift_id TEXT NOT NULL REFERENCES shifts(id),amount INTEGER NOT NULL,reason TEXT NOT NULL,created INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS stock_movements(id INTEGER PRIMARY KEY,business_id TEXT NOT NULL REFERENCES businesses(id),
          product_id TEXT NOT NULL,name TEXT NOT NULL,delta INTEGER NOT NULL,reason TEXT NOT NULL,created INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS promotions(id TEXT PRIMARY KEY,business_id TEXT NOT NULL REFERENCES businesses(id),
          data TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 1);
        PRAGMA user_version=4;
        COMMIT;
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
    require_shift: bool = False
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
    discount: int = Field(default=0,ge=0,le=1_000_000_000_000,strict=True)
    discount_reason: str = Field(default='',max_length=120)
    customer_id: str | None = Field(default=None,max_length=50)
    promotion_id: str | None = Field(default=None,max_length=64)
    promotion_revision: int | None = Field(default=None,ge=1,strict=True)

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
        limit=100 if b['plan']=='basic' else 1000
        old_ids={p['id'] for p in old['products']}
        if len(ids)>limit and set(ids)-old_ids:
            raise HTTPException(403,f'Tu plan permite hasta {limit} productos. Cambia de plan o reduce el catálogo.')
        has_sales=c.execute('SELECT 1 FROM sales WHERE business_id=?',(b['id'],)).fetchone()
        if has_sales and data.settings.currency!=old['settings']['currency']:
            raise HTTPException(409,'No puedes cambiar la moneda después de registrar ventas.')
        if data.settings.currency!=old['settings']['currency'] and (c.execute('SELECT 1 FROM shifts WHERE business_id=?',(b['id'],)).fetchone() or c.execute('SELECT 1 FROM promotions WHERE business_id=?',(b['id'],)).fetchone()):
            raise HTTPException(409,'No puedes cambiar la moneda después de abrir una caja o crear promociones.')
        old_products={p['id']:p for p in old['products']}
        for product in data.products:
            delta=product.stock-old_products.get(product.id,{}).get('stock',0)
            if delta: stock_log(c,b['id'],product.id,product.name,delta,'Edición del catálogo')
        for pid,p in old_products.items():
            if pid not in ids and p['stock']: stock_log(c,b['id'],pid,p['name'],-p['stock'],'Producto eliminado del catálogo')
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
        shift=c.execute('SELECT id FROM shifts WHERE business_id=? AND closed IS NULL',(b['id'],)).fetchone()
        if state['settings'].get('require_shift') and not shift:
            raise HTTPException(409,'Abre una caja antes de registrar ventas.')
        customer=None
        if data.customer_id:
            customer=c.execute('SELECT id,name,phone FROM customers WHERE id=? AND business_id=?',(data.customer_id,b['id'])).fetchone()
            if not customer: raise HTTPException(404,'Cliente no encontrado en este negocio.')
            customer=dict(customer)
        if total>1_000_000_000_000: raise HTTPException(422,'El importe supera el límite por venta del piloto.')
        subtotal=total
        if data.discount>subtotal or (data.discount and len(data.discount_reason.strip())<3):
            raise HTTPException(422,'Revisa el descuento y escribe su motivo (mínimo 3 caracteres).')
        discount=data.discount;discount_reason=data.discount_reason;promotion=None
        if data.promotion_id:
            if data.discount: raise HTTPException(422,'No puedes combinar una promoción con un descuento manual.')
            promotion=calculate_promotion(c,b['id'],data.promotion_id,data.promotion_revision,lines,subtotal)
            discount=promotion['discount'];discount_reason='Promoción: '+promotion['name']
        elif data.promotion_revision is not None:
            raise HTTPException(422,'Selecciona la promoción correspondiente.')
        total-=discount
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
              'subtotal':subtotal,'discount':discount,'discount_reason':discount_reason,'promotion':promotion,'customer':customer,'shift_id':shift['id'] if shift else None,'status':'completed',
              'received':total if card else data.received,'payment':payment,'settings':state['settings'],'lines':lines}
        for line in lines:
            products[line['id']]['stock']-=line['quantity']
            stock_log(c,b['id'],line['id'],line['name'],-line['quantity'],'Venta '+sale['id'])
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

# Subscription collections are confirmed manually; this module never charges a card.
from datetime import datetime, timedelta, timezone, date
import csv
import io

PLANS={
 'basic':{'name':'Básico','products':100,'benefits':['Hasta 100 productos','Fotos y logo del negocio','Caja, cierres y movimientos de efectivo','Clientes, descuentos y anulaciones','Inventario con historial de ajustes','Recibos centrados y 3 plantillas','Historial de ventas y copia JSON','1 cuenta de propietario']},
 'pro':{'name':'Pro','products':1000,'benefits':['Todo lo de Básico','Hasta 1.000 productos','Reportes por fechas','Productos más vendidos en efectivo','Panel de inventario bajo en reportes','Exportación de ventas en CSV']}}
HN=timezone(timedelta(hours=-6))

class PriceUpdate(Model):
    amount: int | None = Field(default=None,ge=0,le=100000000,strict=True)

class PlanRequest(Model):
    plan: Literal['basic','pro']
    quoted_amount: int = Field(ge=0,le=100000000,strict=True)

class Decision(Model):
    action: Literal['approve','reject']
    reference: str = Field(default='',max_length=120)
    note: str = Field(min_length=3,max_length=200)
    payment_confirmed: bool = False

def plans_result(c):
    prices={r['plan']:r['amount'] for r in c.execute('SELECT * FROM plan_prices')}
    return [{'id':key,**value,'amount':prices[key],'currency':'HNL','days':30} for key,value in PLANS.items()]

def billing_audit(c,u,action,target,detail):
    c.execute('INSERT INTO audit(actor,action,target,detail,created) VALUES(?,?,?,?,?)',
              (u['id'],action,target,json.dumps(detail),int(time.time())))

@app.get('/api/plans')
def get_plans(request:Request):
    identity(request)
    with connection() as c:
        return plans_result(c)

@app.put('/api/admin/plans/{plan}')
def set_price(plan:str,data:PriceUpdate,request:Request):
    u=admin(request)
    if plan not in PLANS: raise HTTPException(404,'Plan no encontrado.')
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        old=c.execute('SELECT amount FROM plan_prices WHERE plan=?',(plan,)).fetchone()['amount']
        c.execute('UPDATE plan_prices SET amount=? WHERE plan=?',(data.amount,plan))
        billing_audit(c,u,'plan.price',plan,{'before':old,'amount':data.amount,'currency':'HNL'})
    return {'ok':True}

@app.get('/api/subscription')
def my_subscription(request:Request):
    u=owner(request)
    with connection() as c:
        b=c.execute('SELECT * FROM businesses WHERE id=?',(u['business_id'],)).fetchone()
        return {'plan':b['plan'],'status':b['status'],'expires':b['expires'],
                'used':len(json.loads(b['state'])['products']),
                'limit':100 if b['plan']=='basic' else 1000,
                'plans':plans_result(c),
                'requests':[dict(r) for r in c.execute('SELECT * FROM subscription_requests WHERE business_id=? ORDER BY created DESC,rowid DESC LIMIT 100',(b['id'],))]}

@app.post('/api/subscription/requests')
def request_plan(data:PlanRequest,request:Request):
    u=owner(request)
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        pending=c.execute("SELECT * FROM subscription_requests WHERE business_id=? AND status='pending'",(u['business_id'],)).fetchone()
        if pending:
            if pending['plan']==data.plan and pending['amount']==data.quoted_amount: return dict(pending)
            raise HTTPException(409,'Ya tienes una solicitud pendiente. Cancélala antes de elegir otro plan.')
        amount=c.execute('SELECT amount FROM plan_prices WHERE plan=?',(data.plan,)).fetchone()['amount']
        if amount is None: raise HTTPException(409,'El administrador aún no ha definido el precio.')
        if amount!=data.quoted_amount: raise HTTPException(409,'El precio cambió. Recarga y revisa el nuevo precio.')
        rid=str(uuid.uuid4())
        c.execute('INSERT INTO subscription_requests(id,business_id,plan,amount,created) VALUES(?,?,?,?,?)',
                  (rid,u['business_id'],data.plan,amount,int(time.time())))
        billing_audit(c,u,'subscription.requested',u['business_id'],{'request':rid,'plan':data.plan,'amount':amount})
        return dict(c.execute('SELECT * FROM subscription_requests WHERE id=?',(rid,)).fetchone())

@app.post('/api/subscription/requests/{rid}/cancel')
def cancel_request(rid:str,request:Request):
    u=owner(request)
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        r=c.execute('SELECT * FROM subscription_requests WHERE id=? AND business_id=?',(rid,u['business_id'])).fetchone()
        if not r: raise HTTPException(404,'Solicitud no encontrada.')
        if r['status']!='pending': raise HTTPException(409,'La solicitud ya fue procesada.')
        c.execute("UPDATE subscription_requests SET status='cancelled',processed=? WHERE id=?",(int(time.time()),rid))
        billing_audit(c,u,'subscription.cancelled',u['business_id'],{'request':rid})
    return {'ok':True}

@app.get('/api/admin/subscription-requests')
def all_requests(request:Request):
    admin(request)
    with connection() as c:
        return [dict(r) for r in c.execute('''SELECT r.*,b.name FROM subscription_requests r
          JOIN businesses b ON b.id=r.business_id ORDER BY (r.status='pending') DESC,r.created DESC,r.rowid DESC LIMIT 500''')]

@app.post('/api/admin/subscription-requests/{rid}/decision')
def decide_request(rid:str,data:Decision,request:Request):
    u=admin(request)
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        r=c.execute('SELECT * FROM subscription_requests WHERE id=?',(rid,)).fetchone()
        if not r: raise HTTPException(404,'Solicitud no encontrada.')
        if r['status']!='pending': raise HTTPException(409,'Ya se procesó esta solicitud; no se duplicó la renovación.')
        now=int(time.time());detail={'request':rid,**data.model_dump(),'amount':r['amount'],'plan':r['plan']}
        if data.action=='approve':
            if not data.payment_confirmed or len(data.reference.strip())<3:
                raise HTTPException(422,'Confirma el pago recibido y escribe su referencia (o la autorización de cortesía).')
            b=c.execute('SELECT * FROM businesses WHERE id=?',(r['business_id'],)).fetchone()
            # Renew same paid plan from its end. Plan changes start a new 30-day cycle now.
            start=max(now,b['expires']) if b['status']=='active' and b['plan']==r['plan'] else now
            expires=start+30*86400
            c.execute("UPDATE businesses SET plan=?,status='active',expires=? WHERE id=?",(r['plan'],expires,b['id']))
            detail.update(previous={'plan':b['plan'],'status':b['status'],'expires':b['expires']},expires=expires)
        c.execute('UPDATE subscription_requests SET status=?,processed=?,reference=?,note=? WHERE id=?',
                  ('approved' if data.action=='approve' else 'rejected',now,data.reference,data.note,rid))
        billing_audit(c,u,'subscription.'+data.action,r['business_id'],detail)
    return {'ok':True}

def report_data(c,b,start,end):
    if b['plan'] not in ('trial','pro'):
        raise HTTPException(403,'Los reportes avanzados están incluidos en Pro. Tu historial y copia JSON siguen disponibles.')
    # Read-only reporting remains accessible for expired Pro accounts.
    if start>end: raise HTTPException(422,'La fecha inicial debe ser anterior o igual a la final.')
    rows=[];top={};cash=simulated=0;cash_count=0
    for r in c.execute('SELECT data FROM sales WHERE business_id=? ORDER BY rowid',(b['id'],)):
        s=json.loads(r['data']);day=datetime.fromisoformat(s['date'].replace('Z','+00:00')).astimezone(HN).date()
        if not start<=day<=end: continue
        rows.append(s)
        if s.get('status')=='voided': continue
        if s.get('payment',{}).get('method')=='card_simulated': simulated+=s['total'];continue
        cash+=s['total'];cash_count+=1
        for item in s['lines']:
            entry=top.setdefault(item['id'],{'name':item['name'],'quantity':0,'total':0})
            entry['quantity']+=item['quantity'];entry['total']+=item['quantity']*item['price']
    return {'cash':cash,'cash_count':cash_count,'simulated':simulated,'operations':len(rows),
            'average':round(cash/cash_count) if cash_count else 0,
            'top':sorted(top.values(),key=lambda x:x['total'],reverse=True)[:10],
            'low_stock':[p for p in json.loads(b['state'])['products'] if p['stock']<=5], 'sales':rows}

@app.get('/api/reports')
def reports(request:Request,start:date,end:date):
    u=owner(request)
    with connection() as c:
        b=c.execute('SELECT * FROM businesses WHERE id=?',(u['business_id'],)).fetchone()
        return report_data(c,b,start,end)

@app.get('/api/reports.csv')
def reports_csv(request:Request,start:date,end:date):
    u=owner(request)
    with connection() as c:
        b=c.execute('SELECT * FROM businesses WHERE id=?',(u['business_id'],)).fetchone()
        report=report_data(c,b,start,end)
    output=io.StringIO();writer=csv.writer(output)
    writer.writerow(['Referencia','Fecha Honduras','Método','Moneda','Total','Unidades','Estado','Descuento'])
    for s in report['sales']:
        writer.writerow([s['id'],datetime.fromisoformat(s['date'].replace('Z','+00:00')).astimezone(HN).isoformat(),
                         'SIMULACIÓN' if s.get('payment',{}).get('method')=='card_simulated' else 'Efectivo',
                         s['settings']['currency'],f"{s['total']/100:.2f}",sum(i['quantity'] for i in s['lines']),s.get('status','completed'),f"{s.get('discount',0)/100:.2f}"])
    return Response('\ufeff'+output.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="punto-ventas.csv"'})

# Daily business operations. All money values are integer minor units.
class CustomerInput(Model):
    name: str = Field(min_length=1,max_length=80)
    phone: str = Field(default='',max_length=35)
    note: str = Field(default='',max_length=250)
    revision: int = Field(default=0,ge=0,strict=True)

class OpenShift(Model):
    request_id: str = Field(min_length=16,max_length=64,pattern=r'^[a-zA-Z0-9_-]+$')
    opening: int = Field(ge=0,le=1_000_000_000_000,strict=True)

class CashInput(Model):
    request_id: str = Field(min_length=16,max_length=64,pattern=r'^[a-zA-Z0-9_-]+$')
    amount: int = Field(gt=0,le=1_000_000_000_000,strict=True)
    kind: Literal['in','out']
    reason: str = Field(min_length=3,max_length=200)

class CloseShift(Model):
    counted: int = Field(ge=0,le=1_000_000_000_000,strict=True)
    note: str = Field(min_length=3,max_length=200)

class VoidInput(Model):
    reason: str = Field(min_length=3,max_length=200)
    refund_confirmed: bool = False

class StockInput(Model):
    revision: int = Field(ge=0,strict=True)
    quantity: int = Field(ge=0,le=1000000,strict=True)
    reason: str = Field(min_length=3,max_length=200)

def current_business(c,u):
    return c.execute('SELECT * FROM businesses WHERE id=?',(u['business_id'],)).fetchone()

def stock_log(c,bid,pid,name,delta,reason):
    c.execute('INSERT INTO stock_movements(business_id,product_id,name,delta,reason,created) VALUES(?,?,?,?,?,?)',
              (bid,pid,name,delta,reason,int(time.time())))

@app.get('/api/customers')
def customers(request:Request):
    u=owner(request)
    with connection() as c:
        return [dict(r) for r in c.execute('SELECT * FROM customers WHERE business_id=? ORDER BY name',(u['business_id'],))]

@app.put('/api/customers/{cid}')
def save_customer(cid:str,data:CustomerInput,request:Request):
    u=owner(request)
    if not re.fullmatch(r'[a-zA-Z0-9_-]{16,64}',cid): raise HTTPException(422,'Identificador no válido.')
    with connection() as c:
        c.execute('BEGIN IMMEDIATE');check_writes(current_business(c,u))
        previous=c.execute('SELECT * FROM customers WHERE id=?',(cid,)).fetchone()
        if previous and previous['business_id']!=u['business_id']: raise HTTPException(404,'Cliente no encontrado.')
        if previous and previous['revision']!=data.revision: raise HTTPException(409,'Otro equipo cambió el cliente. Recarga.')
        if not previous and c.execute('SELECT COUNT(*) FROM customers WHERE business_id=?',(u['business_id'],)).fetchone()[0]>=5000:
            raise HTTPException(409,'Límite del piloto: 5.000 clientes por negocio.')
        c.execute('''INSERT INTO customers VALUES(?,?,?,?,?,1) ON CONFLICT(id) DO UPDATE SET
          name=excluded.name,phone=excluded.phone,note=excluded.note,revision=customers.revision+1''',
          (cid,u['business_id'],data.name,data.phone,data.note))
        billing_audit(c,u,'customer.saved',cid,{'name':data.name})
    return {'ok':True}

@app.get('/api/stock-movements')
def stock_movements(request:Request):
    u=owner(request)
    with connection() as c:
        return [dict(r) for r in c.execute('SELECT * FROM stock_movements WHERE business_id=? ORDER BY id DESC LIMIT 300',(u['business_id'],))]

@app.post('/api/products/{pid}/stock')
def adjust_stock(pid:str,data:StockInput,request:Request):
    u=owner(request)
    with connection() as c:
        c.execute('BEGIN IMMEDIATE');b=current_business(c,u);check_writes(b)
        if data.revision!=b['revision']: raise HTTPException(409,'El inventario cambió. Recarga antes de ajustar.')
        state=json.loads(b['state']);product=next((p for p in state['products'] if p['id']==pid),None)
        if not product: raise HTTPException(404,'Producto no encontrado.')
        delta=data.quantity-product['stock'];product['stock']=data.quantity
        stock_log(c,b['id'],pid,product['name'],delta,data.reason)
        c.execute('UPDATE businesses SET state=?,revision=revision+1 WHERE id=?',(json.dumps(state),b['id']))
        return state_result(c,b['id'])

def shift_summary(c,s):
    result=dict(s);income=refunds=0;count=0
    for r in c.execute('SELECT data FROM sales WHERE business_id=?',(s['business_id'],)):
        sale=json.loads(r['data'])
        if sale.get('payment',{}).get('method')=='card_simulated': continue
        if sale.get('shift_id')==s['id']: income+=sale['total'];count+=1
        if sale.get('void',{}).get('refund_shift_id')==s['id']: refunds+=sale['total']
    movements=[dict(r) for r in c.execute('SELECT * FROM cash_movements WHERE shift_id=? ORDER BY created,rowid',(s['id'],))]
    result.update(income=income,refunds=refunds,sales_count=count,movements=movements)
    result['balance']=s['opening']+income-refunds+sum(r['amount'] for r in movements)
    result['difference']=s['counted']-s['expected'] if s['closed'] else None
    return result

@app.get('/api/cash')
def cash_register(request:Request):
    u=owner(request)
    with connection() as c:
        opened=c.execute('SELECT * FROM shifts WHERE business_id=? AND closed IS NULL',(u['business_id'],)).fetchone()
        closed=[dict(r) for r in c.execute('SELECT * FROM shifts WHERE business_id=? AND closed IS NOT NULL ORDER BY closed DESC LIMIT 100',(u['business_id'],))]
        return {'open':shift_summary(c,opened) if opened else None,'closed':closed}

@app.post('/api/cash/open')
def open_shift(data:OpenShift,request:Request):
    u=owner(request)
    with connection() as c:
        c.execute('BEGIN IMMEDIATE');check_writes(current_business(c,u))
        existing=c.execute('SELECT * FROM shifts WHERE id=?',(data.request_id,)).fetchone()
        if existing:
            if existing['business_id']!=u['business_id'] or existing['opening']!=data.opening: raise HTTPException(409,'Referencia ya usada.')
            return shift_summary(c,existing)
        if c.execute('SELECT 1 FROM shifts WHERE business_id=? AND closed IS NULL',(u['business_id'],)).fetchone(): raise HTTPException(409,'Ya existe una caja abierta. Recarga.')
        c.execute('INSERT INTO shifts(id,business_id,opened,opening) VALUES(?,?,?,?)',(data.request_id,u['business_id'],int(time.time()),data.opening))
        billing_audit(c,u,'cash.opened',data.request_id,{'opening':data.opening})
        return shift_summary(c,c.execute('SELECT * FROM shifts WHERE id=?',(data.request_id,)).fetchone())

@app.post('/api/cash/{sid}/movement')
def cash_movement(sid:str,data:CashInput,request:Request):
    u=owner(request);amount=data.amount*(1 if data.kind=='in' else -1)
    if amount==0: raise HTTPException(422,'El importe debe ser mayor que cero.')
    with connection() as c:
        c.execute('BEGIN IMMEDIATE');check_writes(current_business(c,u))
        existing=c.execute('SELECT * FROM cash_movements WHERE id=?',(data.request_id,)).fetchone()
        if existing:
            if existing['business_id']==u['business_id'] and existing['shift_id']==sid and existing['amount']==amount and existing['reason']==data.reason: return {'ok':True}
            raise HTTPException(409,'Referencia ya usada con otros datos.')
        shift=c.execute('SELECT * FROM shifts WHERE id=? AND business_id=?',(sid,u['business_id'])).fetchone()
        if not shift or shift['closed']: raise HTTPException(409,'Esta caja no está abierta.')
        if shift_summary(c,shift)['balance']+amount<0: raise HTTPException(409,'La salida supera el efectivo esperado en caja.')
        c.execute('INSERT INTO cash_movements VALUES(?,?,?,?,?,?)',(data.request_id,u['business_id'],sid,amount,data.reason,int(time.time())))
        billing_audit(c,u,'cash.movement',sid,{'amount':amount,'reason':data.reason})
    return {'ok':True}

@app.post('/api/cash/{sid}/close')
def close_shift(sid:str,data:CloseShift,request:Request):
    u=owner(request)
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        shift=c.execute('SELECT * FROM shifts WHERE id=? AND business_id=?',(sid,u['business_id'])).fetchone()
        if not shift: raise HTTPException(404,'Caja no encontrada.')
        if shift['closed']:
            if shift['counted']==data.counted and shift['note']==data.note: return dict(shift)
            raise HTTPException(409,'La caja ya está cerrada; el cierre no puede modificarse.')
        summary=shift_summary(c,shift)
        c.execute('UPDATE shifts SET closed=?,counted=?,expected=?,note=? WHERE id=?',(int(time.time()),data.counted,summary['balance'],data.note,sid))
        billing_audit(c,u,'cash.closed',sid,{'counted':data.counted,'expected':summary['balance'],'note':data.note})
        return dict(c.execute('SELECT * FROM shifts WHERE id=?',(sid,)).fetchone())

@app.post('/api/sales/{sale_id}/void')
def void_sale(sale_id:str,data:VoidInput,request:Request):
    u=owner(request)
    with connection() as c:
        c.execute('BEGIN IMMEDIATE');b=current_business(c,u);check_writes(b)
        row=c.execute('SELECT * FROM sales WHERE id=? AND business_id=?',(sale_id,b['id'])).fetchone()
        if not row: raise HTTPException(404,'Venta no encontrada.')
        sale=json.loads(row['data'])
        if sale.get('status')=='voided': return {'sale':sale,'state':state_result(c,b['id'])}
        cash=sale.get('payment',{}).get('method')!='card_simulated'
        shift=c.execute('SELECT * FROM shifts WHERE business_id=? AND closed IS NULL',(b['id'],)).fetchone()
        if cash and (not data.refund_confirmed or not shift): raise HTTPException(409,'Abre una caja y confirma la devolución manual del efectivo.')
        if cash and shift_summary(c,shift)['balance']<sale['total']: raise HTTPException(409,'La caja no tiene suficiente efectivo esperado para esta devolución.')
        state=json.loads(b['state']);products={p['id']:p for p in state['products']}
        for line in sale['lines']:
            product=products.get(line['id'])
            if not product or product['stock']+line['quantity']>1000000: raise HTTPException(409,'No se puede reponer un producto eliminado o con stock fuera del límite.')
            product['stock']+=line['quantity'];stock_log(c,b['id'],line['id'],line['name'],line['quantity'],'Anulación '+sale_id+': '+data.reason)
        sale['status']='voided';sale['void']={'reason':data.reason,'date':int(time.time()),'actor':u['username'],'refund_shift_id':shift['id'] if cash else None}
        c.execute('UPDATE sales SET data=? WHERE id=?',(json.dumps(sale),sale_id))
        c.execute('UPDATE businesses SET state=?,revision=revision+1 WHERE id=?',(json.dumps(state),b['id']))
        billing_audit(c,u,'sale.voided',sale_id,sale['void'])
        return {'sale':sale,'state':state_result(c,b['id'])}

@app.get('/api/export')
def export_business(request:Request):
    u=owner(request)
    with connection() as c:
        result=state_result(c,u['business_id'])
        for table in ('customers','shifts','cash_movements','stock_movements','promotions'):
            result[table]=[dict(r) for r in c.execute('SELECT * FROM '+table+' WHERE business_id=?',(u['business_id'],))]
        result['export_version']=4
        return result

class PromotionInput(Model):
    name: str = Field(min_length=1,max_length=70)
    kind: Literal['percent','fixed','bundle']
    value: int = Field(default=1,gt=0,le=1000000000,strict=True)
    buy_quantity: int = Field(default=2,ge=2,le=100,strict=True)
    pay_quantity: int = Field(default=1,ge=1,le=99,strict=True)
    product_ids: list[str] = Field(default_factory=list,max_length=1000)
    minimum: int = Field(default=0,ge=0,le=1000000000000,strict=True)
    starts: date
    ends: date | None = None
    active: bool = True
    revision: int = Field(default=0,ge=0,strict=True)

    @field_validator('product_ids')
    @classmethod
    def unique_products(cls,value):
        if len(value)!=len(set(value)) or any(not re.fullmatch(r'[a-zA-Z0-9_-]{1,50}',pid) for pid in value):
            raise ValueError('Productos duplicados o no válidos.')
        return value

def promotion_result(r):
    return {'id':r['id'],**json.loads(r['data']),'revision':r['revision']}

@app.get('/api/promotions')
def get_promotions(request:Request):
    u=owner(request)
    with connection() as c:
        return [promotion_result(r) for r in c.execute('SELECT * FROM promotions WHERE business_id=? ORDER BY rowid DESC',(u['business_id'],))]

@app.put('/api/promotions/{pid}')
def save_promotion(pid:str,data:PromotionInput,request:Request):
    u=owner(request)
    if not re.fullmatch(r'[a-zA-Z0-9_-]{16,64}',pid): raise HTTPException(422,'Identificador no válido.')
    if data.kind=='percent' and data.value>100: raise HTTPException(422,'El porcentaje debe estar entre 1 y 100.')
    if data.kind=='bundle' and data.pay_quantity>=data.buy_quantity: raise HTTPException(422,'Las unidades que se pagan deben ser menores que las que se llevan.')
    if data.ends and data.ends<data.starts: raise HTTPException(422,'La fecha final no puede ser anterior a la inicial.')
    with connection() as c:
        c.execute('BEGIN IMMEDIATE');b=current_business(c,u);check_writes(b)
        old=c.execute('SELECT * FROM promotions WHERE id=?',(pid,)).fetchone()
        if old and old['business_id']!=b['id']: raise HTTPException(404,'Promoción no encontrada.')
        if old and old['revision']!=data.revision: raise HTTPException(409,'La promoción cambió en otro equipo. Recarga.')
        if not old and data.revision: raise HTTPException(409,'La promoción no existe. Recarga.')
        if not old and c.execute('SELECT COUNT(*) FROM promotions WHERE business_id=?',(b['id'],)).fetchone()[0]>=500:
            raise HTTPException(409,'Límite del piloto: 500 promociones por negocio. Edita una existente.')
        ids={p['id'] for p in json.loads(b['state'])['products']}
        # Allow existing deleted product references when pausing an older promotion.
        previous_ids=set(json.loads(old['data'])['product_ids']) if old else set()
        if set(data.product_ids)-ids-previous_ids: raise HTTPException(422,'Uno de los productos no pertenece a este catálogo.')
        encoded=data.model_dump_json(exclude={'revision'})
        c.execute('''INSERT INTO promotions VALUES(?,?,?,1) ON CONFLICT(id) DO UPDATE SET
          data=excluded.data,revision=promotions.revision+1''',(pid,b['id'],encoded))
        billing_audit(c,u,'promotion.saved',pid,{'before':promotion_result(old) if old else None,'after':data.model_dump(mode='json')})
        return promotion_result(c.execute('SELECT * FROM promotions WHERE id=?',(pid,)).fetchone())

def calculate_promotion(c,bid,pid,revision,lines,subtotal):
    row=c.execute('SELECT * FROM promotions WHERE id=? AND business_id=?',(pid,bid)).fetchone()
    if not row: raise HTTPException(404,'Promoción no encontrada en este negocio.')
    if row['revision']!=revision: raise HTTPException(409,'La promoción cambió. Actualiza los datos y revisa el descuento antes de cobrar.')
    p=json.loads(row['data']);today=datetime.now(HN).date().isoformat()
    if not p['active'] or today<p['starts'] or p['ends'] and today>p['ends']:
        raise HTTPException(409,'La promoción está pausada o fuera de su período de vigencia.')
    if subtotal<p['minimum']: raise HTTPException(422,'La venta no alcanza la compra mínima de esta promoción.')
    eligible=sum(l['price']*l['quantity'] for l in lines if not p['product_ids'] or l['id'] in p['product_ids'])
    if eligible==0: raise HTTPException(422,'No hay productos elegibles para esta promoción.')
    if p['kind']=='bundle':
        discount=sum((l['quantity']//p['buy_quantity'])*(p['buy_quantity']-p['pay_quantity'])*l['price']
                     for l in lines if not p['product_ids'] or l['id'] in p['product_ids'])
    else:
        discount=(eligible*p['value']+50)//100 if p['kind']=='percent' else min(eligible,p['value'])
    if discount==0: raise HTTPException(422,'La promoción no genera descuento para este importe.')
    return {'id':pid,'name':p['name'],'kind':p['kind'],'value':p['value'],'revision':revision,'eligible':eligible,'discount':discount,
            **({'buy_quantity':p['buy_quantity'],'pay_quantity':p['pay_quantity'],'grouping':'same_product'} if p['kind']=='bundle' else {})}

init_db()
