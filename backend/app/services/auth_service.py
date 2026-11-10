"""PBKDF2 passwords, random opaque bearer tokens, server-side revocation and audit.
Sessions live in PostgreSQL, never in localStorage. No self-service registration.
"""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
def get_connection():
    from app.services.database import get_connection as real
    return real()

ROLES = frozenset({'admin','product_owner','engineer','viewer'})

def password_hash(password: str, *, salt: bytes | None = None) -> str:
    if len(password) < 12:
        raise ValueError('Password must contain at least 12 characters')
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 600000)
    return f'pbkdf2_sha256$600000${salt.hex()}${digest.hex()}'

def password_matches(password: str, stored: str) -> bool:
    try:
        algorithm, count, salt, expected = stored.split('$')
        if algorithm != 'pbkdf2_sha256' or int(count) < 600000:
            return False
        digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(count))
        return hmac.compare_digest(digest, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False

def record_audit(actor_id, event: str, object_type=None, object_id=None, detail=None):
    from psycopg.types.json import Jsonb
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute('INSERT INTO security_audit(actor_id,event,object_type,object_id,detail) VALUES (%s,%s,%s,%s,%s)',
                    (actor_id, event, object_type, str(object_id) if object_id else None, Jsonb(detail or {})))

def create_user(username: str, password: str, role: str):
    if role not in ROLES or not username or len(username) > 100:
        raise ValueError('Invalid username or role')
    digest = password_hash(password)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute('INSERT INTO app_users(username,password_hash,role) VALUES (%s,%s,%s) RETURNING id',
                    (username, digest, role))
        return str(cur.fetchone()[0])

def authenticate(username: str, password: str):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute('SELECT id,username,password_hash,role FROM app_users WHERE username=%s AND active', (username,))
        row = cur.fetchone()
    # Constant-cost computation even if username is absent; do not disclose which field failed.
    if not row:
        password_matches(password, password_hash('placeholder-password-for-check'))
        return None
    if not password_matches(password, row[2]):
        return None
    return {'id':str(row[0]), 'username':row[1], 'role':row[3]}

def start_session(user):
    token = secrets.token_urlsafe(40)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(hours=8)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute('INSERT INTO auth_sessions(user_id,token_hash,expires_at) VALUES (%s,%s,%s)',
                    (user['id'], token_hash, expires))
    return token, expires.isoformat()

def resolve_bearer(authorization: str | None):
    if not authorization or not authorization.startswith('Bearer '):
        return None
    token = authorization[7:]
    if len(token) > 256 or len(token) < 30:
        return None
    digest = hashlib.sha256(token.encode()).hexdigest()
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""SELECT u.id,u.username,u.role,s.id FROM auth_sessions s
                       JOIN app_users u ON u.id=s.user_id
                       WHERE s.token_hash=%s AND s.expires_at>NOW() AND s.revoked_at IS NULL AND u.active""", (digest,))
        row = cur.fetchone()
    return {'id':str(row[0]), 'username':row[1], 'role':row[2], 'session_id':str(row[3])} if row else None

def revoke_session(session_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute('UPDATE auth_sessions SET revoked_at=NOW() WHERE id=%s', (session_id,))

def require_roles(*roles):
    """Dependency used for write endpoints in addition to global bearer enforcement."""
    from fastapi import Request
    def dependency(request: Request):
        user = getattr(request.state, 'user', None)
        if not user:
            raise HTTPException(401, 'Authentication required')
        if user['role'] not in roles and user['role'] != 'admin':
            raise HTTPException(403, 'Insufficient role')
        return user
    return dependency
