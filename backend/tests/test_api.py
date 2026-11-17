import hashlib
import hmac
import importlib
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("COURTMATE_DB", str(tmp_path / "court.db"))
    monkeypatch.setenv("COURTMATE_ADMIN_TOKEN", "test-admin-token-longer-than-thirty-two-characters")
    monkeypatch.setenv("COURTMATE_GATEWAY_WEBHOOK_SECRET", "test-gateway-secret-longer-than-thirty-two-characters")
    monkeypatch.setenv("COURTMATE_PAYMENT_URL_TEMPLATE", "https://payments.example.invalid/pay?r={reference}&v={amount}")
    monkeypatch.setenv("COURTMATE_PUBLIC_BOOKING", "true")
    import app
    app.init_db()
    app._public_attempts.clear()
    app._login_attempts.clear()
    with TestClient(app.app) as c:
        yield c, app


def admin():
    return {"Authorization":"Bearer test-admin-token-longer-than-thirty-two-characters"}


def book(date, start="18:00", end="19:00"):
    return {"court_id":1,"date":date,"start":start,"end":end,
            "customer_name":"Nguyen Van A","customer_phone":"0987654321"}


def today():
    # Book tomorrow so tests do not fail after 18:00 local time.
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    return (datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date() + timedelta(days=1)).isoformat()


def test_rbac_and_booking_conflict(api):
    c, _ = api
    assert c.get('/v1/admin/bookings').status_code == 401
    r = c.post('/v1/admin/courts', headers=admin(),json={"name":"San 1","price_hour":120000})
    assert r.status_code == 201
    b = c.post('/v1/public/bookings',json=book(today()))
    assert b.status_code == 201
    assert b.json()['amount'] == 120000
    assert b.json()['status'] == 'PENDING'
    assert 'customer_phone' not in b.json()
    assert c.post('/v1/public/bookings',json=book(today(),"18:30","19:30")).status_code == 409
    assert c.post('/v1/public/bookings',json=book(today(),"19:00","20:00")).status_code == 201
    listing = c.get('/v1/admin/bookings', headers=admin()).json()
    assert len(listing) == 2
    assert c.patch(f"/v1/admin/bookings/{b.json()['id']}",headers=admin(),json={"status":"CONFIRMED"}).status_code == 200


def test_concurrent_reservation_one_winner(api):
    c, application = api
    c.post('/v1/admin/courts',headers=admin(),json={"name":"San A","price_hour":100000})
    barrier = threading.Barrier(6)
    def reserve(_):
        barrier.wait()
        return c.post('/v1/public/bookings',json=book(today())).status_code
    with ThreadPoolExecutor(max_workers=6) as pool:
        statuses = list(pool.map(reserve, range(6)))
    assert statuses.count(201)==1, statuses
    assert statuses.count(409)==5, statuses


def test_payment_rejects_unverified_and_duplicate(api):
    c, application = api
    c.post('/v1/admin/courts', headers=admin(),json={"name":"San A","price_hour":100000})
    booking = c.post('/v1/admin/bookings',headers=admin(),json=book(today())).json()
    booking_id = booking['id']
    intent = c.post(f'/v1/admin/bookings/{booking_id}/bank-intent',headers=admin())
    assert intent.status_code == 200
    data = intent.json()
    event = {"event_id":"evt-0000001","reference":data['reference'],"amount":100000,
             "currency":"VND","status":"SUCCESS"}
    body = json.dumps(event,separators=(',',':')).encode()
    timestamp = str(int(time.time()))
    sig = hmac.new(os.getenv("COURTMATE_GATEWAY_WEBHOOK_SECRET").encode(),
                   timestamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
    headers={'X-Courtmate-Timestamp':timestamp,'X-Courtmate-Signature':sig,'Content-Type':'application/json'}
    assert c.post('/v1/provider/webhooks/payment',content=body,headers={**headers,'X-Courtmate-Signature':'wrong'}).status_code==401
    wrong = dict(event, event_id='evt-0000002', amount=99999)
    wrong_body = json.dumps(wrong,separators=(',',':')).encode()
    wrong_sig = hmac.new(os.getenv('COURTMATE_GATEWAY_WEBHOOK_SECRET').encode(),
                         timestamp.encode()+b'.'+wrong_body,hashlib.sha256).hexdigest()
    assert c.post('/v1/provider/webhooks/payment',content=wrong_body,
                  headers={**headers,'X-Courtmate-Signature':wrong_sig}).status_code==409
    assert c.post('/v1/provider/webhooks/payment',content=body,headers=headers).json()['accepted'] is True
    assert c.post('/v1/provider/webhooks/payment',content=body,headers=headers).json()['duplicate'] is True
    assert c.get('/v1/admin/bookings',headers=admin()).json()[0]['payment_status'] == 'PAID'
    assert c.patch(f'/v1/admin/bookings/{booking_id}',headers=admin(),json={"status":"CANCELLED"}).status_code==409
    assert c.post(f'/v1/admin/bookings/{booking_id}/bank-intent',headers=admin()).status_code==409


def test_public_portal_off_and_invalid_duration(api, monkeypatch):
    c,_ = api
    c.post('/v1/admin/courts', headers=admin(),json={"name":"San 1","price_hour":60000})
    assert c.post('/v1/public/bookings',json=book(today(),"18:00","18:10")).status_code==422
    monkeypatch.setenv('COURTMATE_PUBLIC_BOOKING','false')
    assert c.post('/v1/public/bookings',json=book(today())).status_code==503
    assert c.get('/v1/public/courts').status_code==503


def test_customer_private_status_and_payment_url(api):
    c, _ = api
    c.post('/v1/admin/courts',headers=admin(),json={"name":"San 1","price_hour":100000})
    created = c.post('/v1/public/bookings',json=book(today())).json()
    assert created['access_token']
    payload = {'id':created['id'], 'access_token':'bad_bad_bad_bad_bad_bad_bad_bad_bad_bad_bad'}
    assert c.post('/v1/public/booking-status',json=payload).status_code == 404
    payload['access_token'] = created['access_token']
    status = c.post('/v1/public/booking-status',json=payload).json()
    assert status['status'] == 'PENDING'
    assert 'customer_name' not in status and 'customer_phone' not in status
    c.post(f"/v1/admin/bookings/{created['id']}/status",headers=admin(),json={'status':'CONFIRMED'})
    c.post(f"/v1/admin/bookings/{created['id']}/bank-intent",headers=admin())
    status = c.post('/v1/public/booking-status',json=payload).json()
    assert status['payment_status'] == 'BANK_PENDING'
    assert status['payment_url'].startswith('https://')
    assert c.post(f"/v1/admin/bookings/{created['id']}/status",headers=admin(),
                  json={'status':'CANCELLED'}).status_code == 409


def test_expired_hold_is_released(api):
    c, application = api
    c.post('/v1/admin/courts',headers=admin(),json={"name":"San 1","price_hour":100000})
    created = c.post('/v1/public/bookings',json=book(today())).json()
    with application.connection() as db:
        db.execute("UPDATE bookings SET hold_until='2000-01-01T00:00:00+00:00' WHERE id=?", (created['id'],))
    new = c.post('/v1/public/bookings',json=book(today()))
    assert new.status_code == 201
    with application.connection() as db:
        row = db.execute('SELECT status FROM bookings WHERE id=?',(created['id'],)).fetchone()
        assert row['status'] == 'CANCELLED'


def test_replay_timestamp_rejected(api):
    c, application = api
    body = b'{"event_id":"deadbeef","reference":"CM123","amount":1000,"currency":"VND","status":"SUCCESS"}'
    time_sent = str(int(time.time()) - 1000)
    sig = hmac.new(os.environ['COURTMATE_GATEWAY_WEBHOOK_SECRET'].encode(),time_sent.encode()+b'.'+body,hashlib.sha256).hexdigest()
    response = c.post('/v1/provider/webhooks/payment',content=body, headers={
        'X-Courtmate-Timestamp':time_sent,'X-Courtmate-Signature':sig})
    assert response.status_code == 401


def test_payment_disabled_without_partner_env(api,monkeypatch):
    c, application = api
    c.post('/v1/admin/courts',headers=admin(),json={'name':'San 1','price_hour':120000})
    record = c.post('/v1/admin/bookings',headers=admin(),json=book(today())).json()
    monkeypatch.delenv('COURTMATE_PAYMENT_URL_TEMPLATE',raising=False)
    r=c.post(f"/v1/admin/bookings/{record['id']}/bank-intent",headers=admin())
    assert r.status_code==503
    assert c.get('/v1/admin/bookings',headers=admin()).json()[0]['payment_status']=='UNPAID'


def test_public_cancel_requires_secret_and_releases_slot(api):
    c, _ = api
    c.post('/v1/admin/courts', headers=admin(), json={"name":"San A", "price_hour":120000})
    created = c.post('/v1/public/bookings', json=book(today())).json()
    data = {"id": created['id'], "access_token": created['access_token']}
    assert c.post('/v1/public/bookings/cancel', json={**data, 'access_token':'wrong-secret-' * 3}).status_code == 404
    cancelled = c.post('/v1/public/bookings/cancel', json=data)
    assert cancelled.status_code == 200
    assert cancelled.json()['status'] == 'CANCELLED'
    assert c.post('/v1/public/bookings/cancel', json=data).status_code == 200  # idempotent
    assert c.post('/v1/public/bookings', json=book(today())).status_code == 201


def test_confirmed_booking_cannot_be_cancelled_by_customer(api):
    c, _ = api
    c.post('/v1/admin/courts', headers=admin(), json={"name":"San A", "price_hour":120000})
    created = c.post('/v1/public/bookings', json=book(today())).json()
    c.patch(f"/v1/admin/bookings/{created['id']}", headers=admin(), json={'status':'CONFIRMED'})
    assert c.post('/v1/public/bookings/cancel', json={
        'id':created['id'], 'access_token':created['access_token']}).status_code == 409


def test_court_maintenance_via_admin_and_android_alias(api):
    c, _ = api
    assert c.patch('/v1/admin/courts/1', json={'active':False}).status_code == 401
    created = c.post('/v1/admin/courts', headers=admin(), json={
        'name':'San A', 'price_hour':100000}).json()
    court_id = created['id']
    assert c.patch(f'/v1/admin/courts/{court_id}', headers=admin(), json={}).status_code == 422
    assert c.patch(f'/v1/admin/courts/{court_id}', headers=admin(), json={'name':'   '}).status_code == 422
    disabled = c.post(f'/v1/admin/courts/{court_id}/update', headers=admin(), json={
        'active':False, 'price_hour':140000})
    assert disabled.status_code == 200
    assert disabled.json()['active'] == 0
    assert disabled.json()['price_hour'] == 140000
    assert c.post('/v1/public/bookings', json=book(today())).status_code == 404
    assert c.get('/v1/public/availability', params={'court_id':court_id,'date':today()}).status_code == 404
    assert c.patch(f'/v1/admin/courts/{court_id}', headers=admin(), json={'active':True}).status_code == 200
    assert c.post('/v1/public/bookings', json=book(today())).status_code == 201


def test_summary_daily_counts_and_actual_paid_amount(api):
    c, application = api
    assert c.get('/v1/admin/summary').status_code == 401
    c.post('/v1/admin/courts', headers=admin(), json={"name":"San A", "price_hour":100000})
    pending = c.post('/v1/public/bookings', json=book(today())).json()
    assert c.patch(f"/v1/admin/bookings/{pending['id']}",headers=admin(),json={'status':'CONFIRMED'}).status_code==200
    c.post('/v1/admin/bookings',headers=admin(),json=book(today(),'19:00','20:00'))
    c.post('/v1/public/bookings',json=book(today(),'20:00','21:00'))
    cancelled = c.post('/v1/public/bookings',json=book(today(),'21:00','22:00')).json()
    c.post('/v1/public/bookings/cancel',json={'id':cancelled['id'],'access_token':cancelled['access_token']})
    with application.connection() as db:
        db.execute("UPDATE bookings SET payment_status='PAID' WHERE id=?", (pending['id'],))
    data = c.get('/v1/admin/summary',headers=admin(),params={'date':today()}).json()
    assert data['active_courts'] == 1
    assert data['total_bookings'] == 4
    assert data['confirmed'] == 2 and data['pending'] == 1 and data['cancelled'] == 1
    assert data['paid_amount'] == 100000 and data['amount_to_collect'] == 100000
    assert c.get('/v1/admin/summary',headers=admin(),params={'date':'bad'}).status_code == 422


def test_staff_api_does_not_expose_customer_secret(api):
    c, _ = api
    c.post('/v1/admin/courts',headers=admin(),json={'name':'San A','price_hour':100000})
    created = c.post('/v1/public/bookings',json=book(today())).json()
    assert len(created['access_token']) >= 30
    listing = c.get('/v1/admin/bookings',headers=admin()).json()
    assert 'public_token' not in listing[0]
    internal = c.post('/v1/admin/bookings',headers=admin(),json=book(today(),'19:00','20:00')).json()
    assert 'public_token' not in internal
    assert c.get('/v1/admin/bookings',headers=admin(),params={'date':'broken-date'}).status_code == 422


def test_today_past_times_are_blocked(api):
    c, _ = api
    from datetime import datetime
    from zoneinfo import ZoneInfo
    c.post('/v1/admin/courts',headers=admin(),json={'name':'San A','price_hour':100000})
    date = datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date().isoformat()
    past = c.post('/v1/public/bookings',json=book(date,'00:00','01:00'))
    assert past.status_code == 422


def test_public_status_is_rate_limited(api):
    c, _ = api
    payload = {'id':1, 'access_token':'a' * 32}
    statuses = [c.post('/v1/public/booking-status',json=payload).status_code for _ in range(31)]
    assert statuses[:30] == [404]*30
    assert statuses[-1] == 429


def test_court_name_is_normalized(api):
    c, _ = api
    assert c.post('/v1/admin/courts',headers=admin(),json={'name':'  ', 'price_hour':100}).status_code == 422
    record = c.post('/v1/admin/courts',headers=admin(),json={'name':'  San A  ','price_hour':100}).json()
    assert record['name'] == 'San A'
    assert c.post('/v1/admin/courts',headers=admin(),json={'name':'San A','price_hour':100}).status_code == 409


def test_expired_pending_hold_cannot_be_resurrected_by_admin(api):
    """A new customer must not lose a slot to an expired old hold."""
    c, application = api
    c.post('/v1/admin/courts', headers=admin(), json={'name': 'San B', 'price_hour': 90000})
    first = c.post('/v1/public/bookings', json=book(today())).json()
    with application.connection() as db:
        db.execute("UPDATE bookings SET hold_until='2000-01-01T00:00:00+00:00' WHERE id=?", (first['id'],))
    late_confirmation = c.post(f"/v1/admin/bookings/{first['id']}/status",
                               headers=admin(), json={'status': 'CONFIRMED'})
    assert late_confirmation.status_code == 409
    second = c.post('/v1/public/bookings', json=book(today()))
    assert second.status_code == 201
    with application.connection() as db:
        old = db.execute('SELECT status FROM bookings WHERE id=?', (first['id'],)).fetchone()
        new = db.execute('SELECT status FROM bookings WHERE id=?', (second.json()['id'],)).fetchone()
    assert old['status'] == 'CANCELLED' and new['status'] == 'PENDING'


def test_availability_uses_booking_date_window(api):
    c, _ = api
    c.post('/v1/admin/courts', headers=admin(), json={'name': 'San B', 'price_hour': 90000})
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    current_day = datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date()
    for invalid_day in (current_day - timedelta(days=1), current_day + timedelta(days=366)):
        r = c.get('/v1/public/availability', params={'court_id': 1, 'date': invalid_day.isoformat()})
        assert r.status_code == 422, (invalid_day, r.status_code)
    good = c.get('/v1/public/availability', params={'court_id': 1, 'date': today()})
    assert good.status_code == 200


def test_public_rate_limiter_bounded_memory_and_retry_after(api):
    from types import SimpleNamespace
    c, application = api
    for ip_num in range(4300):
        application.limit_public_bookings(SimpleNamespace(client=SimpleNamespace(host=f'demo-{ip_num}')))
    assert len(application._public_attempts) <= 4096
    # Existing clients still see an actionable response when they exceed their quota.
    for _ in range(30):
        application.limit_public_bookings(SimpleNamespace(client=SimpleNamespace(host='repeat-client')))
    with pytest.raises(application.HTTPException) as exc:
        application.limit_public_bookings(SimpleNamespace(client=SimpleNamespace(host='repeat-client')))
    assert exc.value.status_code == 429
    assert exc.value.headers['Retry-After'] == '60'


def test_daily_and_expiring_indexes_exist(api):
    c, application = api
    with application.connection() as db:
        indexes = {r['name'] for r in db.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert 'idx_bookings_day' in indexes
    assert 'idx_bookings_expirable' in indexes


def test_admin_booking_pagination_preserves_default_contract(api):
    c, _ = api
    c.post('/v1/admin/courts', headers=admin(), json={'name': 'San C', 'price_hour': 100000})
    first = c.post('/v1/admin/bookings', headers=admin(), json=book(today(),'18:00','19:00')).json()
    second = c.post('/v1/admin/bookings', headers=admin(), json=book(today(),'19:00','20:00')).json()
    full = c.get('/v1/admin/bookings', headers=admin())
    assert full.status_code == 200
    assert [row['id'] for row in full.json()] == [first['id'], second['id']]
    page1 = c.get('/v1/admin/bookings', headers=admin(), params={'limit':1,'offset':0})
    page2 = c.get('/v1/admin/bookings', headers=admin(), params={'limit':1,'offset':1})
    assert [row['id'] for row in page1.json()] == [first['id']]
    assert [row['id'] for row in page2.json()] == [second['id']]
    assert not any('public_token' in row for row in page1.json() + page2.json())
    assert c.get('/v1/admin/bookings', headers=admin(), params={'limit':201}).status_code == 422
    assert c.get('/v1/admin/bookings', headers=admin(), params={'offset':-1}).status_code == 422


def _staff_bootstrap(client):
    return client.post('/v1/auth/bootstrap', headers=admin(), json={
        'username':'Owner01','password':'OwnerPassword!2026'})


def _staff_login(client, username='owner01', password='OwnerPassword!2026'):
    return client.post('/v1/auth/login', json={'username':username,'password':password})


def _bearer(session):
    return {'Authorization':'Bearer '+session['access_token']}


def test_cloud_staff_bootstrap_is_one_time_and_requires_admin_token(api):
    c, application = api
    credentials={'username':'Owner01','password':'OwnerPassword!2026'}
    assert c.post('/v1/auth/bootstrap', json=credentials).status_code == 401
    assert c.post('/v1/auth/bootstrap',headers={'Authorization':'Bearer '+('bad'*12)},json=credentials).status_code == 401
    created = _staff_bootstrap(c)
    assert created.status_code==201 and created.json()['username']=='owner01'
    assert created.json()['role']=='ADMIN' and 'password' not in created.json()
    assert _staff_bootstrap(c).status_code == 409
    with application.connection() as db:
        row=db.execute('SELECT * FROM staff_users WHERE username=?',('owner01',)).fetchone()
    assert row['password_hash'] != 'OwnerPassword!2026'
    assert len(row['password_salt']) == 32


def test_staff_role_permissions_and_admin_management(api):
    c, _ = api
    _staff_bootstrap(c)
    administrator = _staff_login(c).json()
    admin_session=_bearer(administrator)
    assert c.get('/v1/auth/me',headers=admin_session).json()['role']=='ADMIN'
    staff = c.post('/v1/admin/staff',headers=admin_session,json={
        'username':'Staff01','password':'StaffPassword!2026','role':'STAFF'})
    assert staff.status_code == 201
    assert staff.json()['role'] == 'STAFF'
    clerk = _staff_login(c,'staff01','StaffPassword!2026').json()
    session = _bearer(clerk)
    assert c.get('/v1/auth/me',headers=session).json() == {
        'username':'staff01','role':'STAFF','legacy':False}
    assert c.get('/v1/admin/courts',headers=session).status_code == 200
    assert c.get('/v1/admin/summary',headers=session).status_code == 200
    assert c.get('/v1/admin/bookings',headers=session).status_code == 200
    assert c.post('/v1/admin/courts',headers=session,json={'name':'Sân mới','price_hour':100000}).status_code == 403
    assert c.get('/v1/admin/staff',headers=session).status_code == 403
    assert c.post('/v1/admin/staff',headers=session,json={
        'username':'Staff02','password':'StaffPassword!2026'}).status_code == 403
    assert c.post('/v1/admin/courts',headers=admin_session,json={
        'name':'Sân A','price_hour':100000}).status_code == 201
    booking=c.post('/v1/admin/bookings',headers=session,json=book(today()))
    assert booking.status_code == 201
    assert c.post(f"/v1/admin/bookings/{booking.json()['id']}/bank-intent",headers=session).status_code == 403
    assert c.post(f"/v1/admin/bookings/{booking.json()['id']}/status",headers=session,json={
        'status':'CANCELLED'}).status_code == 200
    listing=c.get('/v1/admin/staff',headers=admin_session).json()
    assert len(listing) == 2
    assert all('password_hash' not in row and 'password_salt' not in row for row in listing)


def test_staff_disable_revokes_active_sessions_and_blocks_new_login(api):
    c, _ = api
    _staff_bootstrap(c)
    superuser = _bearer(_staff_login(c).json())
    new=c.post('/v1/admin/staff',headers=superuser,json={
        'username':'Clerk01','password':'ClerkPassword!2026','role':'STAFF'}).json()
    clerk=_bearer(_staff_login(c,'clerk01','ClerkPassword!2026').json())
    assert c.get('/v1/admin/bookings',headers=clerk).status_code==200
    stopped=c.patch(f"/v1/admin/staff/{new['id']}",headers=superuser,json={'active':False})
    assert stopped.status_code==200
    assert c.get('/v1/admin/bookings',headers=clerk).status_code==401
    assert _staff_login(c,'clerk01','ClerkPassword!2026').status_code==401
    assert c.patch(f"/v1/admin/staff/{new['id']}",headers=superuser,json={'active':True}).status_code==200
    assert _staff_login(c,'clerk01','ClerkPassword!2026').status_code==200


def test_logout_revokes_only_the_current_session(api):
    c, _ = api
    _staff_bootstrap(c)
    token1=_bearer(_staff_login(c).json())
    token2=_bearer(_staff_login(c).json())
    assert c.post('/v1/auth/logout',headers=token1).json() == {'revoked':True}
    assert c.get('/v1/auth/me',headers=token1).status_code == 401
    assert c.get('/v1/auth/me',headers=token2).status_code == 200
    assert c.post('/v1/auth/logout',headers=admin()).status_code==409


def test_session_expiry_and_legacy_key_transition(api, monkeypatch):
    c, application = api
    _staff_bootstrap(c)
    valid=_bearer(_staff_login(c).json())
    with application.connection() as db:
        db.execute("UPDATE staff_sessions SET expires_at='2000-01-01T00:00:00+00:00'")
    assert c.get('/v1/auth/me',headers=valid).status_code==401
    valid=_bearer(_staff_login(c).json())
    monkeypatch.setenv('COURTMATE_ALLOW_LEGACY_ADMIN','false')
    assert c.get('/v1/admin/summary',headers=admin()).status_code==401
    assert c.get('/v1/admin/summary',headers=valid).status_code==200
    assert c.post('/v1/auth/bootstrap',headers=admin(),json={
        'username':'Another','password':'AnotherPassword!2026'}).status_code==401


def test_last_active_admin_cannot_be_disabled(api):
    c, _ = api
    admin_user=_staff_bootstrap(c).json()
    key=_bearer(_staff_login(c).json())
    assert c.patch(f"/v1/admin/staff/{admin_user['id']}",headers=key,json={'active':False}).status_code==409
    assert c.get('/v1/auth/me',headers=key).status_code==200


def test_login_has_bounded_rate_limit(api):
    c, application = api
    _staff_bootstrap(c)
    application._login_attempts.clear()
    for _ in range(10):
        assert _staff_login(c,'owner01','badPassword!123').status_code==401
    exhausted=_staff_login(c)
    assert exhausted.status_code==429 and exhausted.headers['Retry-After']=='300'
    application._login_attempts.clear()
    assert _staff_login(c).status_code==200


def test_staff_conflict_and_validation(api):
    c, _ = api
    _staff_bootstrap(c)
    session=_bearer(_staff_login(c).json())
    duplicate=c.post('/v1/admin/staff',headers=session,json={
        'username':'OWNER01','password':'AnotherPassword!2026','role':'STAFF'})
    assert duplicate.status_code==409
    assert c.post('/v1/admin/staff',headers=session,json={
        'username':'xy','password':'short','role':'ADMIN'}).status_code==422
    assert c.patch('/v1/admin/staff/999',headers=session,json={'active':False}).status_code==404


def test_auth_schema_migrates_existing_cloud_data(api):
    c, application = api
    court = c.post('/v1/admin/courts',headers=admin(),json={'name':'Sân cũ','price_hour':100000}).json()
    booking = c.post('/v1/admin/bookings',headers=admin(),json=book(today())).json()
    application.init_db()  # rerun migration with existing cloud rows
    assert c.get('/v1/admin/courts',headers=admin()).json()[0]['id'] == court['id']
    assert c.get('/v1/admin/bookings',headers=admin()).json()[0]['id'] == booking['id']
    assert _staff_bootstrap(c).status_code == 201
    assert _staff_login(c).status_code == 200


def test_change_feed_requires_staff_and_never_leaks_private_token(api):
    c, application = api
    assert c.get('/v1/admin/changes').status_code == 401
    assert c.get('/v1/admin/changes', headers=admin(), params={'after': -1}).status_code == 422
    assert c.get('/v1/admin/changes', headers=admin(), params={'limit': 201}).status_code == 422
    court = c.post('/v1/admin/courts', headers=admin(), json={
        'name': 'Sân tập', 'price_hour': 100000}).json()
    created = c.post('/v1/public/bookings', json=book(today())).json()
    result = c.get('/v1/admin/changes', headers=admin()).json()
    assert len(result['events']) == 2
    assert result['events'][0]['resource'] == 'court'
    assert result['events'][0]['record']['id'] == court['id']
    assert result['events'][1]['resource'] == 'booking'
    assert result['events'][1]['record']['id'] == created['id']
    assert result['events'][1]['record']['status'] == 'PENDING'
    assert 'public_token' not in str(result)
    assert 'access_token' not in str(result)
    assert result['events'][0]['seq'] < result['events'][1]['seq']
    assert not result['has_more']
    after = result['next_cursor']
    assert c.get('/v1/admin/changes', headers=admin(), params={'after': after}).json()['events'] == []


def test_change_feed_cursor_pages_and_staff_permissions(api):
    c, application = api
    assert _staff_bootstrap(c).status_code == 201
    supervisor = _bearer(_staff_login(c).json())
    c.post('/v1/admin/staff',headers=supervisor,json={
        'username':'Operator01', 'password':'OperatorPass!2026', 'role':'STAFF'})
    operator = _bearer(_staff_login(c,'operator01','OperatorPass!2026').json())
    record = c.post('/v1/admin/courts', headers=supervisor, json={
        'name':'Sân dành cho test','price_hour':100000}).json()
    c.post('/v1/admin/bookings', headers=operator, json=book(today()))
    c.patch(f"/v1/admin/courts/{record['id']}", headers=supervisor, json={'active':False})
    collected=[]
    cursor=0
    while True:
        page=c.get('/v1/admin/changes',headers=operator,
                   params={'after':cursor, 'limit':1})
        assert page.status_code == 200
        data=page.json()
        collected.extend(data['events'])
        if not data['has_more']:
            cursor=data['next_cursor']
            break
        assert data['next_cursor'] > cursor
        cursor = data['next_cursor']
    assert len(collected) == 3
    assert [x['seq'] for x in collected] == sorted(x['seq'] for x in collected)
    assert collected[-1]['resource'] == 'court'
    assert collected[-1]['record']['active'] == 0
    assert c.get('/v1/admin/changes',headers=operator,params={'after':cursor}).json()['events'] == []
    # Revoked employees cannot use feed access to see personal customer data.
    staff_id = c.get('/v1/admin/staff',headers=supervisor).json()[1]['id']
    assert c.patch(f'/v1/admin/staff/{staff_id}',headers=supervisor,json={'active':False}).status_code==200
    assert c.get('/v1/admin/changes',headers=operator).status_code == 401


def test_change_feed_expired_hold_payment_and_cancel(api):
    c, application=api
    c.post('/v1/admin/courts',headers=admin(),json={'name':'Sân A','price_hour':100000})
    booking=c.post('/v1/public/bookings',json=book(today())).json()
    before=c.get('/v1/admin/changes',headers=admin()).json()['next_cursor']
    with application.connection() as db:
        db.execute("UPDATE bookings SET hold_until='2000-01-01T00:00:00+00:00' WHERE id=?",(booking['id'],))
    after=c.get('/v1/admin/changes',headers=admin(),params={'after':before}).json()
    assert len(after['events']) == 2  # hold field and expiration status changes
    assert after['events'][-1]['record']['status'] == 'CANCELLED'
    assert all(event['resource'] == 'booking' for event in after['events'])
    assert c.get('/v1/admin/changes',headers=admin(),params={'after':after['next_cursor']}).json()['events'] == []


def test_change_feed_backfill_existing_records_is_idempotent(api):
    c, application=api
    c.post('/v1/admin/courts', headers=admin(), json={'name':'Sân cũ','price_hour':100000})
    c.post('/v1/admin/bookings',headers=admin(),json=book(today()))
    # Simulate an upgraded database that previously had no change journal.
    with application.connection() as db:
        db.execute('DELETE FROM cloud_changes')
    application.init_db()
    first=c.get('/v1/admin/changes',headers=admin()).json()['events']
    assert [event['resource'] for event in first] == ['court','booking']
    application.init_db()
    assert c.get('/v1/admin/changes',headers=admin()).json()['events'] == first


def test_retry_key_is_idempotent_and_checks_payload(api):
    c, application=api
    c.post('/v1/admin/courts',headers=admin(),json={'name':'Sân A','price_hour':100000})
    payload={**book(today()),'client_request_id':'stable-booking-request-0001'}
    first=c.post('/v1/admin/bookings',headers=admin(),json=payload)
    second=c.post('/v1/admin/bookings',headers=admin(),json=payload)
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()['id'] == second.json()['id']
    assert len(c.get('/v1/admin/bookings',headers=admin()).json()) == 1
    with application.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM cloud_changes WHERE resource='booking'").fetchone()[0] == 1
    mismatch=c.post('/v1/admin/bookings',headers=admin(),json={**payload,'customer_name':'Other Name'})
    assert mismatch.status_code == 409
    assert c.post('/v1/admin/bookings',headers=admin(),json={
        **book(today(),'19:00','20:00'),'client_request_id':'invalid key spaces'}).status_code == 422
    assert c.post('/v1/public/bookings',json=payload).status_code == 422


def test_retry_key_concurrent_requests_produce_single_booking(api):
    c, application=api
    c.post('/v1/admin/courts',headers=admin(),json={'name':'Sân A','price_hour':100000})
    payload={**book(today()),'client_request_id':'one-request-across-devices-123'}
    barrier=threading.Barrier(4)
    def retry(_):
        barrier.wait()
        result=c.post('/v1/admin/bookings',headers=admin(),json=payload)
        return result.status_code, result.json().get('id')
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses=list(pool.map(retry,range(4)))
    assert all(status==201 for status,_ in responses), responses
    assert len({id for _,id in responses}) == 1
    with application.connection() as db:
        assert db.execute('SELECT count(*) FROM bookings').fetchone()[0] == 1


def test_change_feed_delete_tombstones(api):
    c, application=api
    court=c.post('/v1/admin/courts',headers=admin(),json={'name':'Sân A','price_hour':100000}).json()
    booking=c.post('/v1/admin/bookings',headers=admin(),json=book(today())).json()
    checkpoint=c.get('/v1/admin/changes',headers=admin()).json()['next_cursor']
    with application.connection() as db:
        db.execute('DELETE FROM bookings WHERE id=?',(booking['id'],))
        db.execute('DELETE FROM courts WHERE id=?',(court['id'],))
    feed=c.get('/v1/admin/changes',headers=admin(),params={'after':checkpoint}).json()
    assert [e['action'] for e in feed['events']]==['DELETE','DELETE']
    assert all(e['record'] is None for e in feed['events'])
