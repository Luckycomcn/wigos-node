"""Node user administration: accounts and passwords.

A WIGOS node has no self-service sign-up — accounts are created by the node
administrator (``is_staff``), who also resets passwords when somebody forgets
one. Everyone else may only change their own password, and must prove the
current one first.

Everything an administrator does here is written to the NF-6 audit log, next to
the publishing entries: who created an account and who deleted one is exactly
the kind of thing that has to be reconstructable after the fact.
"""

import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import WIGOSNodeGroup
from .registry import audit

logger = logging.getLogger(__name__)

User = get_user_model()

# Actions recorded in the audit log. Kept in one place so the frontend and the
# audit view can filter on the same strings.
ACTION_CREATE = "user_create"
ACTION_UPDATE = "user_update"
ACTION_DELETE = "user_delete"
ACTION_PASSWORD_RESET = "user_password_reset"
ACTION_PASSWORD_CHANGE = "user_password_change"


# --------------------------------------------------------------------------- #
# Pure helpers (no database access — these are the parts that can be unit
# tested without a database, which is the only thing this project can run
# off-line).
# --------------------------------------------------------------------------- #
def password_errors(password, user=None):
    """Return a list of problems with ``password``; empty means it is accepted.

    The rules themselves live in ``settings.AUTH_PASSWORD_VALIDATORS`` (length,
    common passwords, similarity to the user's own attributes) so an operator
    can tighten them without touching this file.
    """
    if not isinstance(password, str) or not password:
        return ["A password is required."]
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        return [str(message) for message in exc.messages]
    return []


def account_payload(data, partial=False):
    """Pick the editable fields out of a request body.

    Returns ``(payload, errors)``. Unknown keys are ignored rather than
    rejected: the frontend sends the whole user object back on save and a
    strict schema here would only get in the way.
    """
    data = data if isinstance(data, dict) else {}
    payload = {}
    errors = []

    if "username" in data:
        username = str(data.get("username") or "").strip()
        if username:
            payload["username"] = username

    if "email" in data:
        email = str(data.get("email") or "").strip()
        if email:
            payload["email"] = email

    # Creating an account needs both: email is the login identifier and
    # username is what the record is listed under.
    if not partial:
        if not payload.get("username"):
            errors.append("A username is required.")
        if not payload.get("email"):
            errors.append("An email address is required.")

    if "is_staff" in data:
        payload["is_staff"] = bool(data.get("is_staff"))
    if "is_active" in data:
        payload["is_active"] = bool(data.get("is_active"))

    if "groups" in data:
        groups = data.get("groups")
        if isinstance(groups, str):
            groups = [groups]
        if groups is None:
            payload["groups"] = []
        elif isinstance(groups, list):
            payload["groups"] = [
                str(name).strip() for name in groups if name is not None and str(name).strip()
            ]
        else:
            errors.append("'groups' must be a list of group names.")

    if not partial and not payload:
        errors.append("Nothing to create: provide at least a username and an email address.")

    return payload, errors


def guard_self(actor, target, action):
    """Refuse the two changes that would lock the administrator out.

    Deactivating or deleting your own account (or dropping your own staff flag)
    leaves nobody able to undo it, and the request is far more likely to be a
    slip of the mouse than a deliberate handover. Returns an error string, or
    None when the action is allowed.
    """
    if not getattr(actor, "is_authenticated", False) or target is None:
        return None
    if actor.pk != target.pk:
        return None
    if action == "delete":
        return "You cannot delete your own account."
    if action == "deactivate":
        return "You cannot deactivate your own account."
    if action == "unstaff":
        return "You cannot remove your own node administrator role."
    return None


# --------------------------------------------------------------------------- #
# Serialisation
# --------------------------------------------------------------------------- #
def user_row(user):
    """One user as the frontend wants it.

    ``can_delete`` is computed here rather than in the UI so the button is
    hidden for the one account that cannot be deleted, instead of failing after
    the click.
    """
    groups = list(user.groups.values_list("name", flat=True))
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
        "is_staff": user.is_staff,
        "is_superuser": user.is_superuser,
        "groups": groups,
        "last_login": user.last_login,
        "date_joined": user.date_joined,
        "can_delete": not user.is_superuser,
    }


def group_options():
    """Django groups available for assignment, with their centre-id if any.

    Node groups such as ``nfps_Switzerland`` carry the issuer they may publish
    for, which is what an administrator actually picks by.
    """
    issuers = {profile.group_id: profile.issuer_identifier for profile in WIGOSNodeGroup.objects.all()}
    from django.contrib.auth.models import Group

    return [
        {"id": group.id, "name": group.name, "issuer": issuers.get(group.id)}
        for group in Group.objects.order_by("name")
    ]


def _resolve_groups(names, errors):
    """Map group names to Group objects; unknown names are reported, not ignored."""
    from django.contrib.auth.models import Group

    resolved = []
    for name in names:
        try:
            resolved.append(Group.objects.get(name=name))
        except Group.DoesNotExist:
            errors.append(f"Unknown group '{name}'.")
    return resolved


# --------------------------------------------------------------------------- #
# Views
# --------------------------------------------------------------------------- #
class UserListCreateView(APIView):
    """``GET /api/users/`` lists accounts, ``POST`` creates one. Staff only."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return Response({"detail": "User administration is restricted to node administrators."}, status=403)
        return Response([user_row(user) for user in User.objects.order_by("username")])

    def post(self, request):
        if not request.user.is_staff:
            return Response({"detail": "User administration is restricted to node administrators."}, status=403)

        payload, errors = account_payload(request.data)
        password = (request.data or {}).get("password")
        errors.extend(password_errors(password))
        if errors:
            return Response({"detail": errors[0], "errors": errors}, status=400)

        email = payload.get("email")
        username = payload.get("username")
        if User.objects.filter(email__iexact=email).exists():
            return Response({"detail": f"A user with the email address '{email}' already exists."}, status=409)
        if username and User.objects.filter(username__iexact=username).exists():
            return Response({"detail": f"The username '{username}' is already taken."}, status=409)

        group_errors = []
        groups = _resolve_groups(payload.get("groups", []), group_errors)
        if group_errors:
            return Response({"detail": group_errors[0], "errors": group_errors}, status=400)

        with transaction.atomic():
            user = User(
                username=username or email,
                email=email,
                is_staff=payload.get("is_staff", False),
                is_active=payload.get("is_active", True),
            )
            user.set_password(password)
            user.save()
            if groups:
                user.groups.set(groups)

        audit(
            ACTION_CREATE,
            user=request.user,
            username=user.get_username(),
            is_staff=user.is_staff,
            groups=[group.name for group in groups],
        )
        return Response(user_row(user), status=201)


class UserGroupOptionsView(APIView):
    """``GET /api/users/groups/`` — the groups an account can be put in."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return Response({"detail": "User administration is restricted to node administrators."}, status=403)
        return Response(group_options())


class UserDetailView(APIView):
    """``PATCH`` edits an account, ``DELETE`` removes it. Staff only."""

    permission_classes = [IsAuthenticated]

    def _target(self, user_id):
        try:
            return User.objects.get(pk=user_id), None
        except (User.DoesNotExist, ValueError):
            return None, Response({"detail": "User not found."}, status=404)

    def patch(self, request, user_id):
        if not request.user.is_staff:
            return Response({"detail": "User administration is restricted to node administrators."}, status=403)
        user, error = self._target(user_id)
        if error:
            return error

        payload, errors = account_payload(request.data, partial=True)
        if errors:
            return Response({"detail": errors[0], "errors": errors}, status=400)

        # Refuse the self-inflicted lockouts before touching anything.
        if payload.get("is_active") is False:
            blocked = guard_self(request.user, user, "deactivate")
            if blocked:
                return Response({"detail": blocked}, status=400)
        if payload.get("is_staff") is False and user.is_staff:
            blocked = guard_self(request.user, user, "unstaff")
            if blocked:
                return Response({"detail": blocked}, status=400)

        group_errors = []
        groups = _resolve_groups(payload["groups"], group_errors) if "groups" in payload else None
        if group_errors:
            return Response({"detail": group_errors[0], "errors": group_errors}, status=400)

        if payload.get("email") and User.objects.filter(email__iexact=payload["email"]).exclude(pk=user.pk).exists():
            return Response({"detail": "That email address is already used by another account."}, status=409)

        changes = {}
        with transaction.atomic():
            for field in ("username", "email", "is_staff", "is_active"):
                if field in payload and getattr(user, field) != payload[field]:
                    changes[field] = payload[field]
                    setattr(user, field, payload[field])
            if changes:
                user.save()
            if groups is not None:
                changes["groups"] = [group.name for group in groups]
                user.groups.set(groups)

        audit(ACTION_UPDATE, user=request.user, username=user.get_username(), changes=changes)
        return Response(user_row(user))

    def delete(self, request, user_id):
        if not request.user.is_staff:
            return Response({"detail": "User administration is restricted to node administrators."}, status=403)
        user, error = self._target(user_id)
        if error:
            return error
        blocked = guard_self(request.user, user, "delete")
        if blocked:
            return Response({"detail": blocked}, status=400)

        username = user.get_username()
        user.delete()
        audit(ACTION_DELETE, user=request.user, username=username)
        return Response(status=204)


class UserPasswordView(APIView):
    """``POST /api/users/<id>/password`` — an administrator resets somebody's
    password without knowing the old one."""

    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        if not request.user.is_staff:
            return Response({"detail": "User administration is restricted to node administrators."}, status=403)
        try:
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError):
            return Response({"detail": "User not found."}, status=404)

        password = (request.data or {}).get("password")
        errors = password_errors(password, user)
        if errors:
            return Response({"detail": errors[0], "errors": errors}, status=400)

        user.set_password(password)
        user.save()
        audit(ACTION_PASSWORD_RESET, user=request.user, username=user.get_username())
        return Response({"detail": "Password updated."})


class SelfPasswordView(APIView):
    """``POST /api/password/change`` — change your own password.

    The current password is required: a stolen session (or a browser left open
    at a shared workstation) must not be enough to take over the account.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        old_password = data.get("old_password")
        new_password = data.get("new_password")

        if not old_password or not new_password:
            return Response({"detail": "Both the current password and the new password are required."}, status=400)
        if not request.user.check_password(old_password):
            return Response({"detail": "The current password is not correct."}, status=403)
        if old_password == new_password:
            return Response({"detail": "The new password must differ from the current one."}, status=400)

        errors = password_errors(new_password, request.user)
        if errors:
            return Response({"detail": errors[0], "errors": errors}, status=400)

        request.user.set_password(new_password)
        request.user.save()
        # Without this Django's session auth hash no longer matches and the user
        # is silently logged out by their own password change.
        from django.contrib.auth import update_session_auth_hash

        update_session_auth_hash(request, request.user)
        audit(ACTION_PASSWORD_CHANGE, user=request.user, username=request.user.get_username())
        return Response({"detail": "Password updated."})
