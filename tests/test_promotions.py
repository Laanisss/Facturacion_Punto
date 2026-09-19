import uuid,json,sqlite3
from datetime import datetime,timedelta
import server
from test_server import client,stock,payload,isolated

def offer(c,**kwargs):
    pid=str(uuid.uuid4())
    data={'name':'Semana del café','kind':'percent','value':10,'starts':datetime.now(server.HN).date().isoformat(),**kwargs}
    r=c.put('/api/promotions/'+pid,json=data);assert r.status_code==200,r.text
    return r.json()

def use(s,p,**kw):
    return payload(s,promotion_id=p['id'],promotion_revision=p['revision'],**kw)

def test_percent_snapshot_replay_and_cash():
    c=client();s=stock(c);p=offer(c);request=use(s,p)
    sale=c.post('/api/sales',json=request).json()['sale']
    assert sale['discount']==550 and sale['total']==4950 and sale['promotion']['name']=='Semana del café'
    data={k:v for k,v in p.items() if k!='id'};data.update(name='Otra oferta',value=20,active=False)
    assert c.put('/api/promotions/'+p['id'],json=data).status_code==200
    repeat=c.post('/api/sales',json=request).json();assert repeat['sale']==sale
    assert repeat['state']['products'][0]['stock']==1
    assert c.get('/api/reports?start=2020-01-01&end=2099-12-31').json()['cash']==4950

def test_product_scope_and_fixed_discount_cap():
    c=client();s=stock(c);s.pop('sales');s['products'].append({'id':'two','name':'Pan','price':2000,'stock':2,'category':'Comida'})
    s=c.put('/api/state',json=s).json();p=offer(c,kind='fixed',value=10000,product_ids=['one'])
    r=c.post('/api/sales',json=use(s,p,lines=[{'id':'one','quantity':1},{'id':'two','quantity':1}],received=10000))
    assert r.status_code==200,r.text
    assert r.json()['sale']['discount']==5500 and r.json()['sale']['total']==2000

def test_minimum_schedule_paused_and_stale():
    c=client();s=stock(c);today=datetime.now(server.HN).date()
    p=offer(c,minimum=6000);assert c.post('/api/sales',json=use(s,p)).status_code==422
    p=offer(c,starts=(today+timedelta(days=1)).isoformat());assert c.post('/api/sales',json=use(s,p)).status_code==409
    p=offer(c,starts=(today-timedelta(days=2)).isoformat(),ends=(today-timedelta(days=1)).isoformat());assert c.post('/api/sales',json=use(s,p)).status_code==409
    p=offer(c,active=False);assert c.post('/api/sales',json=use(s,p)).status_code==409
    p=offer(c,ends=today.isoformat());changed={k:v for k,v in p.items() if k!='id'};changed['value']=20
    c.put('/api/promotions/'+p['id'],json=changed)
    assert c.post('/api/sales',json=use(s,p)).status_code==409
    assert c.get('/api/state').json()['sales']==[]

def test_tenant_and_manual_stacking():
    c=client();other=client('other');s=stock(c);os=stock(other);p=offer(c)
    assert other.get('/api/promotions').json()==[]
    assert other.post('/api/sales',json=use(os,p)).status_code==404
    data={k:v for k,v in p.items() if k!='id'}
    assert other.put('/api/promotions/'+p['id'],json=data).status_code==404
    assert c.post('/api/sales',json=use(s,p,discount=10,discount_reason='Extra descuento')).status_code==422
    assert c.put('/api/promotions/'+p['id'],json=data,headers={'X-CSRF-Token':'wrong'}).status_code==403

def test_validation_revision_and_product_eligibility():
    c=client();s=stock(c);p=offer(c);data={k:v for k,v in p.items() if k!='id'}
    assert c.put('/api/promotions/'+p['id'],json={**data,'value':101}).status_code==422
    assert c.put('/api/promotions/'+p['id'],json={**data,'ends':'2000-01-01'}).status_code==422
    assert c.put('/api/promotions/'+p['id'],json={**data,'product_ids':['other-tenant-product']}).status_code==422
    assert c.put('/api/promotions/'+p['id'],json={**data,'revision':0}).status_code==409
    s.pop('sales');s['settings']['currency']='$';assert c.put('/api/state',json=s).status_code==409
    assert c.get('/api/export').json()['promotions'][0]['id']==p['id']

def test_percent_rounding_and_dates_inclusive():
    c=client();s=stock(c);s.pop('sales');s['products'][0]['price']=101
    s=c.put('/api/state',json=s).json();p=offer(c,value=50,ends=datetime.now(server.HN).date().isoformat())
    sale=c.post('/api/sales',json=use(s,p)).json()['sale'];assert sale['discount']==51 and sale['total']==50

def test_v3_migration_preserves_sales():
    c=client();s=stock(c);c.post('/api/sales',json=payload(s))
    with server.connection() as db:
        old=db.execute('SELECT data FROM sales').fetchone()[0]
        db.executescript('DROP TABLE promotions; PRAGMA user_version=3;')
    server.init_db()
    with server.connection() as db:
        assert db.execute('SELECT data FROM sales').fetchone()[0]==old
        assert db.execute('PRAGMA user_version').fetchone()[0]==4
    path=list((server.DB_PATH.parent/'backups').glob('*.sqlite3'))[0]
    with sqlite3.connect(path) as db: assert db.execute('PRAGMA user_version').fetchone()[0]==3
    assert c.get('/api/promotions').json()==[]

def test_bundles_repeated_groups_and_remainders():
    for i,(buy,pay,quantity,free) in enumerate([(2,1,3,1),(3,2,7,2),(4,3,9,2),(5,2,12,6)]):
        c=client('bundle'+str(i));s=stock(c);s.pop('sales');s['products'][0]['stock']=20
        s=c.put('/api/state',json=s).json();p=offer(c,kind='bundle',buy_quantity=buy,pay_quantity=pay)
        request=use(s,p,lines=[{'id':'one','quantity':quantity}],received=200000)
        r=c.post('/api/sales',json=request);assert r.status_code==200,r.text
        sale=r.json()['sale'];assert sale['discount']==free*5500 and sale['total']==(quantity-free)*5500
        assert sale['promotion']['grouping']=='same_product'
        assert c.post('/api/sales',json=request).json()['sale']==sale

def test_bundle_does_not_mix_distinct_products():
    c=client();s=stock(c);s.pop('sales');s['products'].append({'id':'two','name':'Pan','price':2000,'stock':5,'category':'Comida'})
    s=c.put('/api/state',json=s).json();p=offer(c,kind='bundle',buy_quantity=2,pay_quantity=1)
    assert c.post('/api/sales',json=use(s,p,lines=[{'id':'one','quantity':1},{'id':'two','quantity':1}],received=20000)).status_code==422
    r=c.post('/api/sales',json=use(s,p,lines=[{'id':'one','quantity':2},{'id':'two','quantity':1}],received=20000))
    assert r.json()['sale']['total']==7500 and r.json()['sale']['discount']==5500

def test_bundle_invalid_quantities():
    c=client();p=offer(c,kind='bundle');data={k:v for k,v in p.items() if k!='id'}
    for buy,pay in [(2,2),(2,3),(1,1),(2,0)]:
        assert c.put('/api/promotions/'+p['id'],json={**data,'buy_quantity':buy,'pay_quantity':pay}).status_code==422
