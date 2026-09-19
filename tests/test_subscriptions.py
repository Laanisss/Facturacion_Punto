import json,time,sqlite3
from datetime import date
import pytest
import server
from test_server import client,stock,payload,admin_client,isolated

def setup_request(c,a,plan='pro',amount=29900):
    assert a.put('/api/admin/plans/'+plan,json={'amount':amount}).status_code==200
    r=c.post('/api/subscription/requests',json={'plan':plan,'quoted_amount':amount})
    assert r.status_code==200,r.text
    return r.json()

def decision(a,r,**kw):
    return a.post('/api/admin/subscription-requests/'+r['id']+'/decision',json={
        'action':'approve','reference':'transferencia-123','note':'Pago verificado','payment_confirmed':True,**kw})

def test_quote_approval_and_double_renewal():
    c=client();a=admin_client();r=setup_request(c,a)
    assert c.post('/api/subscription/requests',json={'plan':'pro','quoted_amount':29900}).json()['id']==r['id']
    a.put('/api/admin/plans/pro',json={'amount':39900})
    assert decision(a,r,payment_confirmed=False).status_code==422
    before=int(time.time());assert decision(a,r).status_code==200
    b=c.get('/api/me').json()['business'];assert b['plan']=='pro' and b['status']=='active'
    assert before+30*86400<=b['expires']<=int(time.time())+30*86400
    assert decision(a,r).status_code==409
    assert c.get('/api/subscription').json()['requests'][0]['amount']==29900
    r2=setup_request(c,a,amount=39900);assert decision(a,r2).status_code==200
    assert c.get('/api/me').json()['business']['expires']==b['expires']+30*86400

def test_request_tenant_csrf_price_and_cancel():
    c=client();b=client('other');a=admin_client()
    assert c.post('/api/subscription/requests',json={'plan':'basic','quoted_amount':0}).status_code==409
    r=setup_request(c,a,'basic')
    assert b.post('/api/subscription/requests/'+r['id']+'/cancel',json={}).status_code==404
    assert decision(c,r).status_code==403
    assert c.get('/api/admin/subscription-requests').status_code==403
    assert c.put('/api/admin/plans/pro',json={'amount':0}).status_code==403
    assert c.post('/api/subscription/requests/'+r['id']+'/cancel',json={},headers={'X-CSRF-Token':'wrong'}).status_code==403
    assert c.post('/api/subscription/requests/'+r['id']+'/cancel',json={}).status_code==200
    assert decision(a,r).status_code==409
    assert c.post('/api/subscription/requests',json={'plan':'basic','quoted_amount':1}).status_code==409

def test_plan_caps_and_downgrade_preserves_catalog():
    c=client();s=stock(c);s.pop('sales');s['products']=[{**s['products'][0],'id':str(i)} for i in range(101)]
    assert c.put('/api/state',json=s).status_code==200
    with server.connection() as db: db.execute("UPDATE businesses SET plan='basic'")
    s=c.get('/api/state').json();s.pop('sales');s['products'][0]['stock']=25
    assert c.put('/api/state',json=s).status_code==200
    s=c.get('/api/state').json();s.pop('sales');s['products'].append({**s['products'][0],'id':'new'})
    assert c.put('/api/state',json=s).status_code==403
    assert len(c.get('/api/state').json()['products'])==101
    s['products']=s['products'][:99]+[s['products'][-1]]
    assert c.put('/api/state',json=s).status_code==200

def test_reports_cash_simulation_dates_and_gating():
    c=client();s=stock(c);r=c.post('/api/sales',json=payload(s)).json()
    assert c.post('/api/sales',json=payload(r['state'],method='card_simulated',received=0)).status_code==200
    url='/api/reports?start=2020-01-01&end=2099-12-31'
    data=c.get(url).json();assert data['cash']==5500 and data['simulated']==5500
    assert data['top'][0]['quantity']==1 and data['low_stock'][0]['stock']==0
    assert c.get('/api/reports.csv?start=2020-01-01&end=2099-12-31').text.count('SIMULACIÓN')==1
    assert c.get('/api/reports?start=2099-01-01&end=2020-01-01').status_code==422
    with server.connection() as db: db.execute("UPDATE businesses SET plan='basic'")
    assert c.get(url).status_code==403
    assert c.get('/api/reports.csv?start=2020-01-01&end=2099-12-31').status_code==403
    assert c.get('/api/state').status_code==200

def test_migration_preserves_data_and_backs_up():
    c=client();stock(c)
    with server.connection() as db:
        db.executescript('DROP TABLE subscription_requests; DROP TABLE plan_prices; PRAGMA user_version=1;')
        original=dict(db.execute('SELECT * FROM users').fetchone())
    server.init_db()
    with server.connection() as db:
        assert dict(db.execute('SELECT * FROM users').fetchone())==original
        assert db.execute('PRAGMA user_version').fetchone()[0]==4
    backups=list((server.DB_PATH.parent/'backups').glob('*.sqlite3'));assert len(backups)==1
    with sqlite3.connect(backups[0]) as db: assert db.execute('PRAGMA user_version').fetchone()[0]==1
    server.init_db();assert len(list((server.DB_PATH.parent/'backups').glob('*.sqlite3')))==1
    assert len(c.get('/api/state').json()['products'])==1

def test_expired_owner_can_renew_rejection_does_not_activate():
    c=client();a=admin_client()
    with server.connection() as db: db.execute('UPDATE businesses SET expires=0')
    r=setup_request(c,a,'basic',0)
    assert decision(a,r,action='reject',payment_confirmed=False,reference='').status_code==200
    assert c.get('/api/me').json()['business']['expires']==0
    r=setup_request(c,a,'basic',0);assert decision(a,r).status_code==200
    assert c.get('/api/me').json()['business']['plan']=='basic'
