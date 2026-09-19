import uuid,json,sqlite3
import server
from test_server import client,stock,payload,isolated

def open_cash(c,amount=10000):
    data={'request_id':str(uuid.uuid4()),'opening':amount}
    r=c.post('/api/cash/open',json=data);assert r.status_code==200,r.text
    assert c.post('/api/cash/open',json=data).json()['id']==r.json()['id']
    return r.json()['id']

def test_cash_discount_void_and_close():
    c=client();s=stock(c);sid=open_cash(c)
    p=payload(s,discount=500,discount_reason='Promoción')
    r=c.post('/api/sales',json=p);assert r.status_code==200,r.text
    sale=r.json()['sale'];assert sale['subtotal']==5500 and sale['total']==5000 and sale['shift_id']==sid
    assert c.get('/api/cash').json()['open']['balance']==15000
    move={'request_id':str(uuid.uuid4()),'amount':1200,'kind':'out','reason':'Compra de bolsas'}
    assert c.post('/api/cash/'+sid+'/movement',json=move).status_code==200
    assert c.post('/api/cash/'+sid+'/movement',json=move).status_code==200
    assert c.get('/api/cash').json()['open']['balance']==13800
    v={'reason':'Cliente devolvió el producto','refund_confirmed':True}
    assert c.post('/api/sales/'+sale['id']+'/void',json=v).status_code==200
    assert c.post('/api/sales/'+sale['id']+'/void',json=v).status_code==200
    assert c.get('/api/state').json()['products'][0]['stock']==2
    cash=c.get('/api/cash').json()['open'];assert cash['balance']==8800 and cash['refunds']==5000
    close={'counted':8700,'note':'Faltante de cien'}
    assert c.post('/api/cash/'+sid+'/close',json=close).json()['expected']==8800
    assert c.post('/api/cash/'+sid+'/close',json=close).status_code==200
    assert c.post('/api/cash/'+sid+'/close',json={**close,'counted':8800}).status_code==409
    assert c.post('/api/sales',json=p).json()['sale']['status']=='voided'
    assert len(c.get('/api/state').json()['sales'])==1
    assert c.get('/api/reports?start=2020-01-01&end=2099-12-31').json()['cash']==0

def test_refund_in_new_shift_preserves_previous_close():
    c=client();s=stock(c);sid=open_cash(c,0)
    sale=c.post('/api/sales',json=payload(s)).json()['sale']
    c.post('/api/cash/'+sid+'/close',json={'counted':5500,'note':'Todo correcto'})
    v={'reason':'Devolución completa','refund_confirmed':True}
    assert c.post('/api/sales/'+sale['id']+'/void',json=v).status_code==409
    new=open_cash(c,6000)
    assert c.post('/api/sales/'+sale['id']+'/void',json=v).status_code==200
    cash=c.get('/api/cash').json();assert cash['open']['balance']==500
    assert cash['closed'][0]['expected']==5500

def test_require_shift_and_simulation_no_cash():
    c=client();s=stock(c);s.pop('sales');s['settings']['require_shift']=True
    s=c.put('/api/state',json=s).json()
    assert c.post('/api/sales',json=payload(s)).status_code==409
    sid=open_cash(c,5000)
    sale=c.post('/api/sales',json=payload(s,method='card_simulated')).json()['sale']
    assert c.get('/api/cash').json()['open']['balance']==5000
    assert c.post('/api/sales/'+sale['id']+'/void',json={'reason':'Anular simulación'}).status_code==200
    assert c.get('/api/cash').json()['open']['balance']==5000

def test_customers_tenant_revision_and_snapshot():
    c=client();other=client('other');cid=str(uuid.uuid4());customer={'name':'Ana','phone':'9999-1234','note':'Cliente habitual','revision':0}
    assert c.put('/api/customers/'+cid,json=customer).status_code==200
    assert other.get('/api/customers').json()==[]
    assert other.put('/api/customers/'+cid,json=customer).status_code==404
    s=stock(other)
    assert other.post('/api/sales',json=payload(s,customer_id=cid)).status_code==404
    s=stock(c);sale=c.post('/api/sales',json=payload(s,customer_id=cid)).json()['sale'];assert sale['customer']['name']=='Ana'
    assert c.put('/api/customers/'+cid,json={**customer,'name':'Ana nueva','revision':0}).status_code==409
    assert c.put('/api/customers/'+cid,json={**customer,'name':'Ana nueva','revision':1}).status_code==200
    assert c.get('/api/state').json()['sales'][0]['customer']['name']=='Ana'
    exported=c.get('/api/export').json();assert exported['customers'][0]['name']=='Ana nueva' and exported['export_version']==4

def test_stock_adjustment_audit_and_stale_write():
    c=client();other=client('other');s=stock(c)
    p={'quantity':20,'reason':'Compra recibida','revision':s['revision']}
    assert c.post('/api/products/one/stock',json=p).status_code==200
    assert c.post('/api/products/one/stock',json=p).status_code==409
    assert other.get('/api/stock-movements').json()==[]
    move=c.get('/api/stock-movements').json()[0];assert move['delta']==18 and move['reason']=='Compra recibida'

def test_invalid_discount_and_refund_atomicity():
    c=client();s=stock(c)
    assert c.post('/api/sales',json=payload(s,discount=5501,discount_reason='Promoción')).status_code==422
    assert c.post('/api/sales',json=payload(s,discount=500)).status_code==422
    sale=c.post('/api/sales',json=payload(s)).json()['sale'];open_cash(c,0)
    assert c.post('/api/sales/'+sale['id']+'/void',json={'reason':'Devolver','refund_confirmed':True}).status_code==409
    assert c.get('/api/state').json()['products'][0]['stock']==1
    sid=c.get('/api/cash').json()['open']['id']
    assert c.post('/api/cash/'+sid+'/movement',json={'request_id':str(uuid.uuid4()),'amount':10,'kind':'out','reason':'Retiro'}).status_code==409

def test_migration_v2_keeps_business_and_subscription():
    c=client();stock(c)
    with server.connection() as db:
        db.executescript('DROP TABLE cash_movements; DROP TABLE shifts; DROP TABLE customers; DROP TABLE stock_movements; PRAGMA user_version=2;')
        old=dict(db.execute('SELECT * FROM businesses').fetchone())
    server.init_db()
    with server.connection() as db:
        assert dict(db.execute('SELECT * FROM businesses').fetchone())==old
        assert db.execute('PRAGMA user_version').fetchone()[0]==4
    backup=list((server.DB_PATH.parent/'backups').glob('*.sqlite3'))[0]
    with sqlite3.connect(backup) as db: assert db.execute('PRAGMA user_version').fetchone()[0]==2
    assert c.get('/api/cash').json()['open'] is None

def test_tenant_and_csrf_operations():
    c=client();other=client('other');sid=open_cash(c)
    assert other.post('/api/cash/'+sid+'/close',json={'counted':10000,'note':'Cerrar caja'}).status_code==404
    assert c.post('/api/cash/'+sid+'/close',json={'counted':10000,'note':'Cerrar caja'},headers={'X-CSRF-Token':'wrong'}).status_code==403
    assert other.get('/api/cash').json()=={'open':None,'closed':[]}

def test_total_limit_avoids_unsafe_large_money_values():
    c=client();s=stock(c);s.pop('sales');s['products'][0].update(price=1000000000,stock=1000000)
    s=c.put('/api/state',json=s).json()
    assert c.post('/api/sales',json=payload(s,method='card_simulated',lines=[{'id':'one','quantity':1000000}])).status_code==422
    assert c.get('/api/state').json()['products'][0]['stock']==1000000

def test_expired_can_close_and_export_but_not_change_operations():
    c=client();sid=open_cash(c)
    with server.connection() as db:db.execute('UPDATE businesses SET expires=0')
    assert c.post('/api/cash/'+sid+'/close',json={'counted':10000,'note':'Conciliar al vencer'}).status_code==200
    assert c.get('/api/export').json()['shifts'][0]['counted']==10000
    assert c.post('/api/cash/open',json={'request_id':str(uuid.uuid4()),'opening':0}).status_code==403
    assert c.put('/api/customers/'+str(uuid.uuid4()),json={'name':'Ana'}).status_code==403
