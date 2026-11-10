from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field
from app.services.auth_service import authenticate, start_session, revoke_session, record_audit, require_roles
from app.services.database import get_connection
from app.core.config import settings
import hashlib
import redis

router = APIRouter(prefix='/auth', tags=['Phase 6 Authentication'])
class LoginRequest(BaseModel):
    username: str = Field(min_length=1,max_length=100)
    password: str = Field(min_length=1,max_length=256)

@router.post('/login')
def login(payload: LoginRequest, request: Request):
    # Use same error for unknown user and wrong password; do not record secrets.
    # Rate-limit by username + client address without storing the username in Redis.
    remote=request.client.host if request.client else 'unknown'
    identifier=hashlib.sha256((remote+'|'+payload.username.lower()).encode()).hexdigest()
    try:
        cache=redis.Redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
        attempts=cache.incr('reqflow:login:'+identifier)
        if attempts==1: cache.expire('reqflow:login:'+identifier,300)
    except redis.RedisError as exc:
        raise HTTPException(503,'Authentication temporarily unavailable') from exc
    if attempts>8:
        raise HTTPException(429,'Too many login attempts; try later')
    user = authenticate(payload.username, payload.password)
    if not user:
        raise HTTPException(401, 'Invalid username or password')
    cache.delete('reqflow:login:'+identifier)
    token, expires = start_session(user)
    record_audit(user['id'], 'auth.login')
    return {'access_token':token, 'token_type':'bearer', 'expires_at':expires, 'user':user}

@router.get('/me')
def me(user=Depends(require_roles('admin','product_owner','engineer','viewer'))):
    return {k:user[k] for k in ('id','username','role')}

@router.post('/logout')
def logout(user=Depends(require_roles('admin','product_owner','engineer','viewer'))):
    revoke_session(user['session_id'])
    record_audit(user['id'], 'auth.logout')
    return {'revoked':True}

@router.get('/audit')
def audit(user=Depends(require_roles('admin'))):
    with get_connection() as conn,conn.cursor() as cur:
        cur.execute('SELECT event,object_type,object_id,created_at FROM security_audit ORDER BY created_at DESC LIMIT 100')
        rows=cur.fetchall()
    return [{'event':r[0],'object_type':r[1],'object_id':r[2],'created_at':r[3].isoformat()} for r in rows]
