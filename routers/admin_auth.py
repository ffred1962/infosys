from fastapi import APIRouter

from views.admin.auth import login, setup_first_user


router = APIRouter(prefix="/admin")

router.add_api_route("/setup", setup_first_user, methods=["POST"], name="admin_setup")
router.add_api_route("/login", login, methods=["POST"], name="admin_login")
