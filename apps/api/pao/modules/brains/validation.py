"""Brain validation errors never echo raw notes, secrets or malformed Unicode."""
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.responses import JSONResponse
from fastapi import HTTPException

class BrainBodyLimit:
    """Bound JSON before Pydantic/JSON parsing; raw file/ZIP routes bound streams."""
    def __init__(self,app):self.app=app
    async def __call__(self,scope,receive,send):
        path=scope.get('path','')
        lifecycle_path = '/lifecycle' in path or path.startswith('/v1/auth/')
        planning_path=path.startswith('/v1/workspaces/') and '/business-planning/' in path
        inventory_path=path.startswith('/v1/workspaces/') and ('/connection-inventory' in path or '/cli-connections' in path or path.endswith('/model-grants'))
        resource_path=path.startswith('/v1/workspaces/') and ('/resources/' in path or '/enterprise-ai' in path or '/personal-cli' in path)
        model_path=path.startswith('/v1/model-providers')
        telegram_mapping_path=path.startswith('/v1/telegram/legacy/')
        telegram_setup_path=path.startswith('/v1/telegram/scoped')
        ads_oauth_path=path.startswith(('/v1/integrations/meta/','/v1/integrations/google-ads/'))
        engine_path=path=='/v1/engines' or (path.startswith(('/v1/sessions/','/v1/runs/')) and path.endswith('/engine'))
        if lifecycle_path or planning_path or ads_oauth_path or model_path or resource_path or engine_path or telegram_mapping_path or telegram_setup_path or path.startswith('/v1/connectors'):
            original_send=send
            async def no_store_send(message):
                if message['type']=='http.response.start':
                    message={**message,'headers':[(key,value) for key,value in message.get('headers',[])
                        if key.lower()!=b'cache-control']+[(b'cache-control',b'no-store')]}
                await original_send(message)
            send=no_store_send
        knowledge_path=lifecycle_path or planning_path or ads_oauth_path or telegram_setup_path or telegram_mapping_path or model_path or resource_path or inventory_path or path == '/v1/integrations/meta/app-config' or path.startswith(('/v1/engines','/v1/studio','/v1/connectors')) or (path.startswith('/v1/sessions/') and (path.endswith('/knowledge') or path.endswith('/attachments') or path.endswith('/engine')))
        if scope['type']!='http' or not (path.startswith('/v1/brains') or path.endswith('/brain') or knowledge_path):
            return await self.app(scope,receive,send)
        headers=dict(scope.get('headers',[]))
        # Typed JSON endpoints must be bounded even for +json or a wrong MIME.
        # The two raw streaming endpoints have their own strict size/MIME guards.
        if scope.get('method')=='POST' and (path.endswith('/files') or path.endswith('/imports/preview')):
            return await self.app(scope,receive,send)
        limit=65536 if planning_path else 2097152 if telegram_setup_path and path.endswith('/webhook') else 8192 if ads_oauth_path or telegram_setup_path or telegram_mapping_path or model_path or resource_path or engine_path or inventory_path or path == '/v1/integrations/meta/app-config' else 65536 if path.startswith(('/v1/studio','/v1/connectors')) else 524288
        if lifecycle_path:limit=8192
        try:declared=int(headers.get(b'content-length',b'0'))
        except ValueError:declared=0
        if declared>limit:
            return await JSONResponse(status_code=413,content={'detail':'Brain JSON vượt giới hạn'})(scope,receive,send)
        total=0
        async def bounded_receive():
            nonlocal total
            item=await receive()
            total+=len(item.get('body',b''))
            if total>limit:raise HTTPException(413,'Brain JSON vượt giới hạn')
            return item
        return await self.app(scope,bounded_receive,send)

async def safe_validation(request,exc):
    path=request.scope.get('path','')
    if path.startswith('/v1/workspaces/') and '/personal-cli' in path:
        return JSONResponse(status_code=422,content={'detail':'personal_cli_invalid_input'},headers={'Cache-Control':'no-store'})
    if path.startswith('/v1/workspaces/') and '/enterprise-ai' in path:
        return JSONResponse(status_code=422,content={'detail':'enterprise_ai_invalid_input'},headers={'Cache-Control':'no-store'})
    if '/lifecycle' in path or path.startswith('/v1/auth/'):
        return JSONResponse(status_code=422, content={'detail':'Dữ liệu tài khoản hoặc phạm vi yêu cầu không hợp lệ'}, headers={'Cache-Control':'no-store'})
    if path.startswith('/v1/workspaces/') and '/business-planning/' in path:
        return JSONResponse(status_code=422,content={'detail':'business_planning_invalid_input'},headers={'Cache-Control':'no-store'})
    if path.startswith(('/v1/integrations/meta/','/v1/integrations/google-ads/')) and path!='/v1/integrations/meta/app-config':
        return JSONResponse(status_code=422,content={'detail':'ads_app_invalid_input'},headers={'Cache-Control':'no-store'})
    if path.startswith('/v1/telegram/scoped'):
        return JSONResponse(status_code=422,content={'detail':'telegram_setup_invalid_input'},headers={'Cache-Control':'no-store'})
    if path.startswith('/v1/telegram/legacy/'):
        return JSONResponse(status_code=422,content={'detail':'telegram_mapping_invalid_input'},headers={'Cache-Control':'no-store'})
    if path.startswith('/v1/model-providers'):
        return JSONResponse(status_code=422,content={'detail':'model_provider_invalid_input'},headers={'Cache-Control':'no-store'})
    if path.startswith('/v1/workspaces/') and '/resources/' in path:
        return JSONResponse(status_code=422,content={'detail':'tenant_resource_invalid_input'},headers={'Cache-Control':'no-store'})
    if path.startswith('/v1/workspaces/') and '/cli-connections' in path:
        return JSONResponse(status_code=422, content={'detail':'cli_connection_invalid_input'}, headers={'Cache-Control':'no-store'})
    if path.startswith('/v1/workspaces/') and ('/connection-inventory' in path or path.endswith('/model-grants')):
        return JSONResponse(status_code=422, content={'detail':'connection_inventory_invalid_input'})
    if path == '/v1/integrations/meta/app-config':
        return JSONResponse(status_code=422, content={'detail':'meta_app_config_invalid_input'})
    if path.startswith(('/v1/engines','/v1/studio','/v1/connectors')) or path.startswith('/v1/brains') or path.endswith('/brain') or (path.startswith('/v1/sessions/') and ('/attachments' in path or path.endswith('/knowledge') or path.endswith('/engine'))):
        return JSONResponse(status_code=422,content={'detail':[{
            'loc':['request'],'msg':'Dữ liệu Brain không hợp lệ','type':'request_validation'}]})
    return await request_validation_exception_handler(request,exc)
