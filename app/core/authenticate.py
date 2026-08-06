import logging
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from datetime import datetime, timedelta

from app.core.config import settings
from app.services.pydantic_schemas import User, UserInDB
from app.core.sql_connection import db_client  
from app.services import concept_queries as q

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# -----------------------------
# PASSWORD UTILITIES
# -----------------------------
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


# -----------------------------
# GET USER (SQL SERVER)
# -----------------------------
def get_user(username: str) -> UserInDB | None:
    with db_client() as conn:
        cursor = conn.cursor()

        query = f"""
            SELECT TOP 1
                u.id,
                u.username,
                a.role_id,
                u.hashed_password
            FROM {settings.USERS} u
            LEFT JOIN {settings.USER_ACCESS} a
                ON u.id = a.user_id
            WHERE u.username = ?
        """

        cursor.execute(query, (username,))
        row = cursor.fetchone()

        if row:
            return UserInDB(
                id=row[0],
                username=row[1],
                role_id=0,
                hashed_password=row[2]
            )

        return None


# -----------------------------
# AUTHENTICATE USER
# -----------------------------
def authenticate_user(username: str, password: str):
    user = get_user(username)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


# -----------------------------
# CREATE JWT TOKEN
# -----------------------------
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()

    expire = datetime.utcnow() + (
        expires_delta
        or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )


def create_jwt_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM
    )


# -----------------------------
# PENDING ROLE-SELECTION TOKEN
# -----------------------------
def create_pending_token(user_id: int, username: str) -> str:
    """
    Proves identity only, for the brief window between "password/SSO
    verified" and "role chosen" when a user has more than one role.
    Deliberately carries NO role_id and is short-lived (5 min), and
    get_current_user rejects it outright - it can only be used at
    /select-role, never as a real session token.
    """
    to_encode = {
        "sub": username,
        "user_id": user_id,
        "pending_role_selection": True,
        "exp": datetime.utcnow() + timedelta(minutes=5),
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_pending_token(token: str) -> dict:
    """Returns {user_id, username} from a pending token, or raises 401."""
    invalid = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired role-selection session. Please log in again.",
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise invalid

    if not payload.get("pending_role_selection"):
        raise invalid

    user_id = payload.get("user_id")
    username = payload.get("sub")
    if user_id is None or username is None:
        raise invalid

    return {"user_id": user_id, "username": username}


# -----------------------------
# GET CURRENT USER (JWT)
# -----------------------------
def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )

        username: str = payload.get("sub")
        user_id: int = payload.get("user_id")
        client_id: int = payload.get("client_id")
        role_id = payload.get("role_id")

        # A pending role-selection token has no role_id and must never be
        # accepted as a real session token - only /select-role may use it.
        if username is None or payload.get("pending_role_selection"):
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    return User(
        id=user_id,
        username=username,
        role_id=role_id if role_id is not None else 0,
        client_id=client_id
    )


def is_admin(role_id: int) -> bool:
    """
    True if role_id corresponds to the 'Admin' role. Deliberately checks
    against user_role (the same table/pattern as
    is_data_science_programmer_role in concept_queries.py) rather than a
    dedicated column on `users` - keeps one consistent authorization
    model instead of two. Requires an 'Admin' row to actually exist in
    user_role first (create it via POST /api/user-management/roles).
    """
    if role_id is None:
        return False

    with db_client() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT COUNT(*)
            FROM {settings.USER_ROLE}
            WHERE role_id = ? AND role_name = 'Admin'
        """, (role_id,))
        return cursor.fetchone()[0] > 0


def require_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    FastAPI dependency - drop in wherever an endpoint should be
    admin-only (e.g. the User Management module) in place of
    get_current_user. Checks current_user.role_id, which reflects
    whichever role is active for this session under the role-switcher.
    """
    if not is_admin(current_user.role_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )
    return current_user


def user_exists(username: str):
    """
    Validate if a user exists and is active, and return every role
    assigned to them. A user can have more than one role - callers
    (the Microsoft OAuth callback) must check len(roles):
        - 0 roles: no access, as before
        - 1 role: proceed to issue a full access token directly
        - 2+ roles: issue a pending token and require /select-role
    Returns:
        - {"id", "roles": [{"role_id","role_name"}, ...]} if user exists
        - None if not found / inactive
    """

    logger.info(f"[CHECK USER] username='{username}'")

    try:
        with db_client() as conn:
            cursor = conn.cursor()

            user_query = f"""
                SELECT TOP 1 u.id
                FROM {settings.USERS} u
                WHERE u.username = ? AND u.is_active = 1
            """

            cursor.execute(user_query, (username,))
            row = cursor.fetchone()

            if not row:
                logger.warning(f"USER NOT FOUND: {username}")
                return None

            user_id = row[0]
            roles = q.get_user_roles(cursor, user_id)

            logger.info(f"USER FOUND: {username} (id={user_id}) roles={roles}")

            return {
                "id": user_id,
                "roles": roles,
            }

    except Exception as e:
        logger.error(f"DB Error in user_exists: {e}", exc_info=True)
        raise