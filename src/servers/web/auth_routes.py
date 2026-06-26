#!/usr/bin/env python3
"""APIRouter routes extracted from web_server.py: authentication and identity routes."""

from fastapi import APIRouter
from . import web_server as _web

globals().update({name: value for name, value in vars(_web).items() if not name.startswith("__")})
router = APIRouter()

async def login_page(request: Request, message: str = None):
    """Serve the SPA login shell for active GET /login traffic."""
    return _ui_index_response()


# Login handler

@router.post("/login")
async def login(username: str = Form(...), password: str = Form(...), request: Request = None):
    """Handle login"""
    # Get configured credentials
    expected_username = _require_config(config.get("web_server.username"), "web_server.username")
    expected_password = _require_config(
        _resolved_runtime_secret(config.get("web_server.password")),
        "web_server.password",
    )

    if username == expected_username and password == expected_password:
        # Set session
        request.session["user"] = username
        request.session["user_id"] = 1
        request.session["role"] = "admin"
        _emit_login_audit(request, username, outcome="success", auth_method="password_form")
        return RedirectResponse(url="/dashboard", status_code=302)
    else:
        _emit_login_audit(
            request,
            username,
            outcome="failure",
            auth_method="password_form",
            reason="invalid_credentials",
        )
        return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
    <title>Login Failed</title>
    <meta http-equiv="refresh" content="2;url=/login">
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            padding: 50px;
            background: #f5f5f5;
        }
        .error {
            background: #fee;
            border: 1px solid #fcc;
            padding: 20px;
            border-radius: 5px;
            display: inline-block;
        }
    </style>
</head>
<body>
    <div class="error">
        <h2>❌ Login Failed</h2>
        <p>Invalid username or password</p>
        <p>Redirecting back to login...</p>
    </div>
</body>
</html>
""")


# Logout

@router.get("/logout")
async def logout(request: Request):
    """Handle logout"""
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)

@router.post("/auth/login")
async def auth_login(request: Request):
    """JSON cookie login for the monorepo notification UI."""
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid login payload: {exc}")

    # Resolve config resiliently: this route is registered directly on the
    # APIRouter, so it must not rely on the web_server wrapper having synced the
    # global `config` first. `_temp_config` is always available from import.
    cfg = config or _temp_config

    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "").strip()

    # Thread-a (PROGRAM-IDAM-RECOVERY-2) flat-role login: authenticate the three
    # flat accounts (admin / read-write / read-only) via a constant-time compare
    # (no username enumeration). The matched account decides the flat role; the
    # session permissions are derived from the ONE shared idam guard. The admin
    # account reuses the historical web_server.username/password credentials.
    flat_role = _match_flat_account(username, password)
    if flat_role is not None:
        request.session["user"] = username
        request.session["user_id"] = {
            ADMIN_ROLE: 1, READ_WRITE_ROLE: 2, READ_ONLY_ROLE: 3
        }[flat_role]
        request.session["role"] = flat_role
        request.session["user_email"] = f"{username}@cloud-dog.local"
        # Best-effort last_login bookkeeping for a matching DB user (no-op if absent).
        try:
            db_uri = cfg.get("db.uri")
            if db_uri:
                db = get_db_manager(str(db_uri))
                db.connect()
                try:
                    matched = UserRepository(db).get_by_username(username)
                    if matched:
                        UserRepository(db).update_last_login(matched["id"])
                finally:
                    db.close()
        except Exception:
            pass
        _emit_login_audit(request, username, outcome="success", auth_method="password_json")
        response = JSONResponse({"user": _session_user_payload(request)})
        api_key_for_browser = _resolved_runtime_secret(cfg.get("api_server.api_key"))
        if api_key_for_browser:
            response.set_cookie(
                "notification_api_key",
                api_key_for_browser,
                max_age=_session_max_age,
                path="/",
                secure=False,
                samesite="lax",
                httponly=False,
            )
        # Thread-a flat-role marker for the unified read-only write-gate (covers
        # /api + /mcp + /a2a, which bypass the web-app gate). Server-read only.
        response.set_cookie(
            "notification_role",
            flat_role,
            max_age=_session_max_age,
            path="/",
            secure=False,
            samesite="lax",
            httponly=True,
        )
        return response

    expected_username = cfg.get("web_server.username", "admin")
    expected_password = _require_config(cfg.get("web_server.password"), "web_server.password")

    db_user = None
    if username != expected_username or password != expected_password:
        try:
            db_uri = _require_config(cfg.get("db.uri"), "db.uri")
            db = get_db_manager(str(db_uri))
            db.connect()
            try:
                user_repo = UserRepository(db)
                candidate = user_repo.get_by_username(username)
                password_hash = str((candidate or {}).get("password_hash") or "")
                if candidate and password_hash and idam_runtime.verify_password(password, password_hash):
                    db_user = candidate
                    user_repo.update_last_login(candidate["id"])
            finally:
                db.close()
        except Exception as exc:
            if logger:
                logger.debug(f"Database JSON auth failed for '{username}': {exc}")

        if not db_user:
            _emit_login_audit(
                request,
                username,
                outcome="failure",
                auth_method="password_json",
                reason="invalid_credentials",
            )
            raise HTTPException(status_code=401, detail="Invalid credentials")

    if db_user:
        request.session["user"] = db_user["username"]
        request.session["user_id"] = db_user["id"]
        request.session["role"] = db_user.get("role", "viewer")
        request.session["user_email"] = db_user.get("email")
    else:
        request.session["user"] = username
        request.session["user_id"] = 1
        request.session["role"] = "admin"
        request.session["user_email"] = f"{username}@cloud-dog.local"
        # NOTIFWEB-096: update last_login_at on cookie login
        try:
            db_uri = cfg.get("db.uri")
            if db_uri:
                db = get_db_manager(str(db_uri))
                db.connect()
                try:
                    user_repo = UserRepository(db)
                    matched = user_repo.get_by_username(username)
                    if matched:
                        user_repo.update_last_login(matched["id"])
                finally:
                    db.close()
        except Exception:
            pass

    _emit_login_audit(request, request.session["user"], outcome="success", auth_method="password_json")
    response = JSONResponse({"user": _session_user_payload(request)})
    api_key_for_browser = _resolved_runtime_secret(cfg.get("api_server.api_key"))
    if api_key_for_browser:
        response.set_cookie(
            "notification_api_key",
            api_key_for_browser,
            max_age=_session_max_age,
            path="/",
            secure=False,
            samesite="lax",
            httponly=False,
        )
    response.set_cookie(
        "notification_role",
        normalise_flat_role(request.session.get("role")),
        max_age=_session_max_age,
        path="/",
        secure=False,
        samesite="lax",
        httponly=True,
    )
    return response

@router.get("/auth/me")
async def auth_me(request: Request):
    """Return current cookie-backed UI user."""
    return {"user": _session_user_payload(request)}

@router.post("/auth/logout")
async def auth_logout(request: Request):
    """JSON logout contract for the monorepo notification UI."""
    request.session.clear()
    response = JSONResponse({"ok": True})
    # W28A-#A89: Clear the api-key bridge cookie alongside the session.
    response.delete_cookie("notification_api_key", path="/")
    response.delete_cookie("notification_role", path="/")
    return response

@router.post("/auth/refresh")
async def auth_refresh(request: Request):
    """Cookie-backed refresh mirrors session inspection for the monorepo UI."""
    return {"user": _session_user_payload(request)}


# ============================================================================
# Keycloak OAuth2 Authentication
# ============================================================================

def is_keycloak_enabled():
    """Check if Keycloak OAuth2 is enabled"""
    return config.get("idp.enabled", False) and config.get("idp.keycloak.enabled", False)

def get_keycloak_config():
    """Get Keycloak configuration"""
    if not is_keycloak_enabled():
        return None

    base_url = config.get("idp.keycloak.base_url", "")
    realm = config.get("idp.keycloak.realm", "")
    client_id = config.get("idp.keycloak.client_id", "")
    client_secret = config.get("idp.keycloak.client_secret", "")
    redirect_uri = config.get("idp.keycloak.redirect_uri", "")
    scopes = config.get("idp.keycloak.scopes", "openid email profile")

    if not all([base_url, realm, client_id, client_secret, redirect_uri]):
        return None

    return {
        "base_url": base_url.rstrip("/"),
        "realm": realm,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "scopes": scopes,
        "authorization_endpoint": f"{base_url.rstrip('/')}/realms/{realm}/protocol/openid-connect/auth",
        "token_endpoint": f"{base_url.rstrip('/')}/realms/{realm}/protocol/openid-connect/token",
        "userinfo_endpoint": f"{base_url.rstrip('/')}/realms/{realm}/protocol/openid-connect/userinfo",
    }

@router.get("/auth/keycloak/login")
async def keycloak_login(request: Request):
    """Initiate Keycloak OAuth2 login flow"""
    kc_config = get_keycloak_config()
    if not kc_config:
        raise HTTPException(status_code=500, detail="Keycloak not configured")

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state

    # Build authorization URL
    params = {
        "client_id": kc_config["client_id"],
        "redirect_uri": kc_config["redirect_uri"],
        "response_type": "code",
        "scope": kc_config["scopes"],
        "state": state,
    }

    auth_url = f"{kc_config['authorization_endpoint']}?{urlencode(params)}"
    _emit_oauth_audit(
        request,
        action="oauth_redirect",
        outcome="success",
        reason="redirect_initiated",
        provider="keycloak",
        flow_target=urlparse(kc_config["authorization_endpoint"]).path or "authorization_endpoint",
        authorization_endpoint=urlparse(kc_config["authorization_endpoint"]).path or "",
    )
    return RedirectResponse(url=auth_url, status_code=302)

@router.get("/auth/keycloak/callback")
async def keycloak_callback(request: Request, code: str = Query(None), state: str = Query(None), error: str = Query(None)):
    """Handle Keycloak OAuth2 callback"""
    kc_config = get_keycloak_config()
    if not kc_config:
        raise HTTPException(status_code=500, detail="Keycloak not configured")

    # Check for errors
    if error:
        _emit_oauth_audit(
            request,
            action="oauth_callback",
            outcome="error",
            reason="provider_error",
            provider="keycloak",
            flow_target="callback",
            provider_error=str(error),
        )
        return RedirectResponse(url="/login?message=oauth_error", status_code=302)

    # Verify state
    stored_state = request.session.get("oauth_state")
    if not stored_state or stored_state != state:
        _emit_oauth_audit(
            request,
            action="oauth_callback",
            outcome="denied",
            reason="state_mismatch",
            provider="keycloak",
            flow_target="callback",
        )
        return RedirectResponse(url="/login?message=oauth_error", status_code=302)

    # Remove state from session
    request.session.pop("oauth_state", None)

    if not code:
        _emit_oauth_audit(
            request,
            action="oauth_callback",
            outcome="error",
            reason="missing_authorization_code",
            provider="keycloak",
            flow_target="callback",
        )
        return RedirectResponse(url="/login?message=oauth_error", status_code=302)

    try:
        # Exchange code for tokens
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": kc_config["redirect_uri"],
            "client_id": kc_config["client_id"],
            "client_secret": kc_config["client_secret"],
        }

        kc_client = _get_keycloak_client()
        token_response = await kc_client.post(
            kc_config["token_endpoint"],
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        token_response.raise_for_status()
        tokens = token_response.json()

        access_token = tokens.get("access_token")
        if not access_token:
            _emit_oauth_audit(
                request,
                action="oauth_callback",
                outcome="error",
                reason="missing_access_token",
                provider="keycloak",
                flow_target="callback",
            )
            return RedirectResponse(url="/login?message=oauth_error", status_code=302)

        # Get user info
        kc_client = _get_keycloak_client()
        userinfo_response = await kc_client.get(
            kc_config["userinfo_endpoint"],
            headers={"Authorization": f"Bearer {access_token}"}
        )
        userinfo_response.raise_for_status()
        userinfo = userinfo_response.json()

        # Extract user information from Keycloak userinfo
        email = userinfo.get("email", "")
        username = userinfo.get("preferred_username") or userinfo.get("sub", "")
        display_name = userinfo.get("name") or userinfo.get("given_name", "") or username
        userinfo.get("given_name", "")
        userinfo.get("family_name", "")

        # Get roles from token or userinfo
        roles = []
        if "realm_access" in userinfo and "roles" in userinfo["realm_access"]:
            roles = userinfo["realm_access"]["roles"]
        elif "resource_access" in userinfo:
            for resource, access in userinfo["resource_access"].items():
                if "roles" in access:
                    roles.extend(access["roles"])

        # Map Keycloak roles to local roles
        # Check for notification_server_admin and notification_server_user roles
        local_role = "viewer"  # Default role
        if "notification_server_admin" in roles:
            local_role = "admin"
        elif "notification_server_user" in roles:
            local_role = "editor"

        # Extract preferences from Keycloak attributes (if configured)
        # Get field mapping configuration
        fetch_preferences = config.get("idp.keycloak.fetch_preferences", False)
        language = None
        preferred_channel = None
        content_style = None

        if fetch_preferences:
            # Get attribute mappings from config
            attr_mapping_lang = config.get("idp.keycloak.field_mapping.language", "")
            attr_mapping_channel = config.get("idp.keycloak.field_mapping.preferred_channel", "")
            attr_mapping_style = config.get("idp.keycloak.field_mapping.content_style", "")

            # Extract from userinfo attributes
            attributes = userinfo.get("attributes", {})

            # Language mapping
            if attr_mapping_lang:
                # Support nested paths like "attributes.locale"
                if attr_mapping_lang.startswith("attributes."):
                    attr_key = attr_mapping_lang.replace("attributes.", "")
                    language = attributes.get(attr_key) if isinstance(attributes, dict) else None
                else:
                    language = userinfo.get(attr_mapping_lang)

            # Preferred channel mapping
            if attr_mapping_channel:
                if attr_mapping_channel.startswith("attributes."):
                    attr_key = attr_mapping_channel.replace("attributes.", "")
                    preferred_channel = attributes.get(attr_key) if isinstance(attributes, dict) else None
                else:
                    preferred_channel = userinfo.get(attr_mapping_channel)

            # Content style mapping
            if attr_mapping_style:
                if attr_mapping_style.startswith("attributes."):
                    attr_key = attr_mapping_style.replace("attributes.", "")
                    content_style = attributes.get(attr_key) if isinstance(attributes, dict) else None
                else:
                    content_style = userinfo.get(attr_mapping_style)

        # If no language from mapping, try locale field
        if not language:
            language = userinfo.get("locale") or userinfo.get("language")

        # Create or update user in local database
        db_uri = _require_config(config.get("db.uri"), "db.uri")
        db = get_db_manager(db_uri)
        db.connect()

        try:
            user_repo = UserRepository(db)
            existing_user = user_repo.get_by_email(email) if email else user_repo.get_by_username(username)

            # Generate a random password hash for OAuth2 users (they won't use it)
            dummy_password_hash = idam_runtime.hash_password("oauth2_user_no_password")

            if existing_user:
                # Update existing user
                user_id = existing_user["id"]

                # Update user preferences if they were extracted
                if language or preferred_channel or content_style:
                    user_repo.update_preferences(
                        user_id,
                        language=language,
                        preferred_channel=preferred_channel,
                        content_style=content_style
                    )

                # Update role if changed
                if existing_user.get("role") != local_role:
                    db.execute(
                        "UPDATE users SET role = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (local_role, user_id)
                    )
                    db.commit()

                # Update display name if available
                if display_name and display_name != existing_user.get("display_name"):
                    db.execute(
                        "UPDATE users SET display_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (display_name, user_id)
                    )
                    db.commit()

                # Update last login
                user_repo.update_last_login(user_id)

                logger.info(f"Updated existing user from Keycloak: {email} (role: {local_role})")
            else:
                # Create new user
                user_id = user_repo.create(
                    username=username,
                    email=email,
                    password_hash=dummy_password_hash,
                    role=local_role,
                    display_name=display_name,
                    user_type="real",
                    language=language,
                    preferred_channel=preferred_channel,
                    content_style=content_style
                )
                logger.info(f"Created new user from Keycloak: {email} (role: {local_role})")

            # Store user info in session
            request.session["user"] = username
            request.session["user_email"] = email
            request.session["user_id"] = user_id
            request.session["role"] = local_role
            request.session["oauth_provider"] = "keycloak"
            request.session["oauth_roles"] = roles

            _emit_login_audit(
                request,
                username,
                outcome="success",
                auth_method="oauth2",
                provider="keycloak",
            )
            return RedirectResponse(url="/dashboard", status_code=302)

        finally:
            pass  # DatabaseManager doesn't need explicit close

    except HTTPStatusError as e:
        _emit_oauth_audit(
            request,
            action="oauth_callback",
            outcome="error",
            reason="provider_http_error",
            provider="keycloak",
            flow_target="callback",
            status_code=int(e.response.status_code),
        )
        return RedirectResponse(url="/login?message=oauth_error", status_code=302)
    except Exception as e:
        _emit_oauth_audit(
            request,
            action="oauth_callback",
            outcome="error",
            reason=type(e).__name__,
            provider="keycloak",
            flow_target="callback",
        )
        return RedirectResponse(url="/login?message=oauth_error", status_code=302)


# Base layout helper function with left menu
