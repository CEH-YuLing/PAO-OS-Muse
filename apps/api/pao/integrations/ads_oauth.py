"""OAuth orchestration shared by provider routes, never shared user tokens."""
import hashlib
import secrets
from datetime import timedelta
from html import escape
from urllib.parse import urlencode,urlsplit

from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select,update

from ..auth import rate_limit
from ..models import MetaConnection,GoogleAdsConnection,MetaOAuthState,GoogleAdsOAuthState,Member,User,now
from ..modules.connections.read_authority import lock_scope
from . import ads_apps


def digest(value):return hashlib.sha256(value.encode()).hexdigest()


async def start(db,who,wid,request,response,provider,connection,cookie,callback):
    row=await connection(db,who,wid,True,True)
    member=await db.get(Member,(row.workspace_id,who.id),with_for_update={'read':True},populate_existing=True)
    user=await db.get(User,who.id,with_for_update={'read':True},populate_existing=True)
    if not member or member.role not in ('owner','admin') or not user or not user.active:raise HTTPException(403,'ads_app_manager_required')
    context=await ads_apps.resolve(db,row.workspace_id,provider)
    try:ads_apps.validate(context,provider)
    except Exception as exc:raise HTTPException(409 if str(exc)=='meta_app_restart_required' else 503,str(exc)) from None
    c=context.config;redirect=c.meta_redirect_uri if provider=='meta' else c.google_ads_redirect_uri
    target=urlsplit(redirect);origin=request.headers.get('origin')
    if origin and origin.rstrip('/')!=f'{target.scheme}://{target.netloc}':raise HTTPException(400,'ads_oauth_origin_mismatch')
    await rate_limit(request.app.state.redis,provider+'-connect',who.id,5,60)
    model=MetaOAuthState if provider=='meta' else GoogleAdsOAuthState
    state=secrets.token_urlsafe(32);browser=secrets.token_urlsafe(32)
    await db.execute(update(model).where(model.connection_id==row.id).values(used=True))
    db.add(model(digest=digest(state),browser_digest=digest(browser),connection_id=row.id,
        connection_version=row.version,app_binding=context.binding,expires_at=now()+timedelta(minutes=10)))
    await db.commit()
    response.set_cookie(cookie,browser,max_age=600,httponly=True,secure=redirect.startswith('https:'),samesite='lax',path=callback)
    response.headers['Cache-Control']='no-store'
    if provider=='meta':
        endpoint=f'https://www.facebook.com/{c.meta_graph_api_version}/dialog/oauth'
        params={'client_id':c.meta_app_id,'redirect_uri':redirect,'state':state,'scope':'ads_read,ads_management' if c.meta_write_enabled else 'ads_read','response_type':'code'}
    else:
        endpoint='https://accounts.google.com/o/oauth2/v2/auth'
        params={'client_id':c.google_ads_client_id,'redirect_uri':redirect,'response_type':'code','scope':'https://www.googleapis.com/auth/adwords',
            'access_type':'offline','prompt':'consent','include_granted_scopes':'true','state':state}
    return {'authorization_url':endpoint+'?'+urlencode(params)}


async def callback(db,request,state,code,provider,cookie,path):
    from .meta.client import MetaClient,encrypt,MetaError
    from .google_ads.client import GoogleAdsClient,GoogleAdsError
    state_model=MetaOAuthState if provider=='meta' else GoogleAdsOAuthState
    model=MetaConnection if provider=='meta' else GoogleAdsConnection
    if any(len(request.query_params.getlist(key))>1 for key in ('state','code','error')):
        raise HTTPException(400,'ads_oauth_invalid_state')
    record=await db.get(state_model,digest(state),with_for_update=True)
    browser=request.cookies.get(cookie,'')
    if not record or record.used or record.expires_at<=now() or not browser or not secrets.compare_digest(record.browser_digest,digest(browser)):
        raise HTTPException(400,'ads_oauth_invalid_state')
    cid,version,pin=record.connection_id,record.connection_version,record.app_binding
    record.used=True;await db.commit()  # Consume before exchange; never retry a code after uncertain ACK.
    try:
        row=await db.get(model,cid)
        if not row:raise ads_apps.error(provider,'ads_oauth_connection_changed')
        await lock_scope(db,row.workspace_id)
        await db.refresh(row,with_for_update={'read':False})
        context=await ads_apps.resolve(db,row.workspace_id,provider)
        ads_apps.validate(context,provider)
        member=await db.get(Member,(row.workspace_id,row.user_id),with_for_update={'read':True})
        user=await db.get(User,row.user_id,with_for_update={'read':True})
        if not pin or pin!=context.binding or row.version!=version or not member or member.role not in ('owner','admin') or not user or not user.active:
            raise ads_apps.error(provider,'ads_oauth_connection_changed')
        if not code or request.query_params.get('error'):raise ads_apps.error(provider,'ads_oauth_cancelled')
        if provider=='meta':
            token,seconds=await MetaClient(config=context.config).exchange(code)
            remote,scopes=await MetaClient(token,config=context.config).identity()
            if isinstance(seconds,bool) or not isinstance(seconds,(int,float)) or not 0<seconds<=366*86400:raise MetaError('meta_invalid_token_expiry')
            row.token_ciphertext=encrypt(token);row.remote_user_id=remote;row.expires_at=now()+timedelta(seconds=seconds)
        else:
            client=GoogleAdsClient(config=context.config)
            refresh,scopes=await client.exchange(code);await client.accessible(refresh)
            row.refresh_token_ciphertext=encrypt(refresh)
        if (await ads_apps.resolve(db,row.workspace_id,provider)).binding!=pin:raise ads_apps.error(provider,'ads_oauth_connection_changed')
        row.scopes=scopes;row.connected_at=now();row.status='connected';row.version+=1;row.app_binding=context.binding
        await db.commit()
        message='Kết nối thành công trong doanh nghiệp đã chọn. Đóng cửa sổ này và đọc lại trạng thái PAO.'
    except (MetaError,GoogleAdsError):
        await db.rollback();message='Kết nối chưa hoàn tất. Đọc lại trạng thái trong PAO; kiểm tra quyền, cấu hình ứng dụng và bắt đầu phiên kết nối mới khi cần. Không gửi lại mã cũ.'
    response=HTMLResponse('<!doctype html><meta charset="utf-8"><title>PAO OAuth</title><p>'+escape(message)+'</p>',headers={
        'Cache-Control':'no-store','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'"})
    response.delete_cookie(cookie,path=path)
    return response
