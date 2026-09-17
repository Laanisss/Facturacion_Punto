import time,uuid
import pytest
from fastapi.testclient import TestClient
import server

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(server,'DB_PATH',tmp_path/'test.sqlite3');server.init_db()

def client(name='owner'):
    c=TestClient(server.app,base_url=server.ORIGIN,headers={'Origin':server.ORIGIN})
    r=c.post('/api/register',json={'username':name,'password':'test-pass-123456','business':'Negocio '+name})
    assert r.status_code==200,r.text
    c.headers['X-CSRF-Token']=r.json()['csrf'];return c

def stock(c):
    s=c.get('/api/state').json();s.pop('sales');s['products']=[{'id':'one','name':'Café','price':5500,'stock':2,'category':'Bebidas','icon':'☕'}]
    r=c.put('/api/state',json=s);assert r.status_code==200,r.text;return r.json()

def payload(s,**kw):
    return {'request_id':str(uuid.uuid4()),'revision':s['revision'],'lines':[{'id':'one','quantity':1}],'method':'cash','received':6000,**kw}

def admin_client():
    with server.connection() as db:db.execute('INSERT INTO users VALUES(?,?,?,?,NULL)',('admin-id','admin',server.password_hash('test-admin-12345'),'admin'))
    c=TestClient(server.app,base_url=server.ORIGIN,headers={'Origin':server.ORIGIN})
    r=c.post('/api/login',json={'username':'admin','password':'test-admin-12345'});assert r.status_code==200,r.text
    c.headers['X-CSRF-Token']=r.json()['csrf'];return c

def test_password_session_logout():
    c=client()
    with server.connection() as db:
        u=db.execute('SELECT * FROM users').fetchone();assert u['password_hash']!='test-pass-123456';assert server.verify('test-pass-123456',u['password_hash'])
        assert db.execute('SELECT * FROM sessions').fetchone()['token_hash']!=c.cookies.get('punto_session')
    assert c.get('/api/me').json()['role']=='owner';assert c.post('/api/logout',json={}).status_code==200
    assert c.get('/api/state').status_code==401
    assert c.post('/api/login',json={'username':'owner','password':'incorrect-pass'}).status_code==401

def test_tenant_isolation_and_roles():
    a,b=client('first'),client('second');stock(a)
    assert b.get('/api/state').json()['products']==[];assert b.get('/api/admin/businesses').status_code==403
    assert b.patch('/api/admin/businesses/x/subscription',json={'status':'active','plan':'pro','expires':2000000000,'reason':'hacked'}).status_code==403
    assert b.post('/api/register',json={'username':'third','password':'test-pass-123456','business':'x','role':'admin'}).status_code==422
    s=b.get('/api/state').json();s.pop('sales');s['business_id']=a.get('/api/me').json()['business']['id']
    assert b.put('/api/state',json=s).status_code==422

def test_csrf_origin():
    c=client();s=c.get('/api/state').json();s.pop('sales')
    assert c.put('/api/state',json=s,headers={'X-CSRF-Token':'wrong'}).status_code==403
    assert c.put('/api/state',json=s,headers={'Origin':'https://evil.example'}).status_code==403

def test_sale_idempotency_and_concurrency():
    c=client();s=stock(c);p=payload(s);r=c.post('/api/sales',json=p);assert r.status_code==200,r.text
    first=r.json();assert first['sale']['total']==5500;assert first['state']['products'][0]['stock']==1
    repeat=c.post('/api/sales',json=p).json();assert repeat['sale']['id']==first['sale']['id'];assert len(repeat['state']['sales'])==1
    assert c.post('/api/sales',json={**p,'received':7000}).status_code==409
    assert c.post('/api/sales',json=payload(s)).status_code==409
    s.pop('sales');assert c.put('/api/state',json=s).status_code==409

def test_simulated_failures_and_approval():
    c=client();s=stock(c)
    assert c.post('/api/sales',json=payload(s,method='card_simulated',scenario='declined')).status_code==402
    assert c.post('/api/sales',json=payload(s,method='card_simulated',scenario='error')).status_code==503
    state=c.get('/api/state').json();assert state['sales']==[] and state['products'][0]['stock']==2
    r=c.post('/api/sales',json=payload(s,method='card_simulated',received=0)).json();assert r['sale']['payment']['status']=='simulated_approved';assert r['sale']['received']==5500

def test_tampering_oversell():
    c=client();s=stock(c)
    assert c.post('/api/sales',json=payload(s,total=1)).status_code==422
    assert c.post('/api/sales',json=payload(s,received=1)).status_code==422
    assert c.post('/api/sales',json=payload(s,lines=[{'id':'one','quantity':3}])).status_code==409
    assert c.post('/api/sales',json=payload(s,method='bac_hit')).status_code==422
    assert c.get('/api/state').json()['products'][0]['stock']==2

def test_admin_suspend_export_reactivate_audit():
    c=client();s=stock(c);a=admin_client();bid=a.get('/api/admin/businesses').json()[0]['id']
    change={'status':'suspended','plan':'basic','expires':int(time.time())+86400,'reason':'Prueba de suspensión'}
    assert a.patch(f'/api/admin/businesses/{bid}/subscription',json=change).status_code==200
    assert c.post('/api/sales',json=payload(s)).status_code==403;assert c.get('/api/state').status_code==200
    change['status']='active';assert a.patch(f'/api/admin/businesses/{bid}/subscription',json=change).status_code==200
    assert c.post('/api/sales',json=payload(s)).status_code==200
    assert len(a.get('/api/admin/audit').json())==2;assert a.get('/api/state').status_code==403

def test_expired_trial_bac_block():
    c=client();s=stock(c)
    with server.connection() as db:db.execute('UPDATE businesses SET expires=0')
    assert c.post('/api/sales',json=payload(s)).status_code==403
    assert c.get('/api/payments/bac-hit/status').json()['connected'] is False
    assert c.post('/api/payments/bac-hit/charge',json={}).status_code==501

def test_currency_image_validation():
    c=client();s=stock(c);c.post('/api/sales',json=payload(s))
    s=c.get('/api/state').json();s.pop('sales');s['settings']['currency']='$';assert c.put('/api/state',json=s).status_code==409
    s['settings']['currency']='L';s['products'][0]['image']='javascript:alert(1)';assert c.put('/api/state',json=s).status_code==422

def test_session_expiry_rate_limit():
    c=client()
    with server.connection() as db:
        db.execute('UPDATE sessions SET expires=0');db.execute('INSERT INTO rate_limits VALUES(?,?,?)',('login:testclient',20,int(time.time())+900))
    assert c.get('/api/me').status_code==401
    assert c.post('/api/login',json={'username':'owner','password':'test-pass-123456'}).status_code==429

def test_health():
    c=TestClient(server.app)
    assert c.get('/health').json()=={'status':'ok'}
