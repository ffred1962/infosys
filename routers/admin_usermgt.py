from fastapi import APIRouter

from views.admin.usermgt import (
    assign_role,
    change_password,
    create_role,
    create_user,
    edit_user,
    remove_role,
    toggle_active,
)


router = APIRouter(prefix="/admin/usermgt")

router.add_api_route("/new", create_user, methods=["POST"], name="admin_usermgt_create_user")
router.add_api_route("/{user_id}/toggle-active", toggle_active, methods=["POST"], name="admin_usermgt_toggle_active")
router.add_api_route("/{user_id}/assign-role", assign_role, methods=["POST"], name="admin_usermgt_assign_role")
router.add_api_route("/{user_id}/remove-role", remove_role, methods=["POST"], name="admin_usermgt_remove_role")
router.add_api_route("/{user_id}/new-role", create_role, methods=["POST"], name="admin_usermgt_new_role")
router.add_api_route("/{user_id}/edit", edit_user, methods=["POST"], name="admin_usermgt_edit_user")
router.add_api_route(
    "/{user_id}/change-password", change_password, methods=["POST"], name="admin_usermgt_change_password"
)
