from dataclasses import dataclass
from typing import Callable

from fastapi import APIRouter, Request

from views.about import about_page
from views.calculator import calculator_page
from views.contacts import contacts_page
from views.home import home_page
from views.request import request_page
from views.root import root_redirect
from views.crm.crm_page import crm_page
from views.crm.tasks import tasks_page
from views.crm.firm_finder import firm_finder_page
from views.crm.firms import firms_page
from views.crm.firm_prices import firm_prices_page
from views.crm.firm_comments import firm_comments_page
from views.admin.admin_page import admin_page
from views.admin.usermgt import new_user_form, usermgt_page
from views.admin.taskstatus import taskstatus_page
from views.admin.city import city_page
from views.admin.firm_type import firm_type_page
from views.admin.unit import unit_page
from views.admin.constants import constants_page
from views.admin.bugs import bugs_page
from views.admin.notifications import notifications_page
from views.admin.login_info import login_info_page


router = APIRouter()


PageHandler = Callable[[Request], object]


@dataclass(frozen=True)
class PageRoute:
    path: str
    handler: PageHandler
    name: str


PAGE_ROUTES = [
    PageRoute("/", root_redirect, "root_page"),
    PageRoute("/proba", home_page, "proba_page"),
    PageRoute("/about", about_page, "about_page"),
    PageRoute("/contacts", contacts_page, "contacts_page"),
    PageRoute("/request", request_page, "request_page"),
    PageRoute("/calculator", calculator_page, "calculator_page"),
    PageRoute("/crm", crm_page, "crm_page"),
    PageRoute("/crm/tasks", tasks_page, "crm_tasks_page"),
    PageRoute("/crm/firm_finder", firm_finder_page, "crm_firm_finder_page"),
    PageRoute("/crm/firms", firms_page, "crm_firms_page"),
    PageRoute("/crm/firms/{firm_id}/prices", firm_prices_page, "crm_firm_prices_page"),
    PageRoute("/crm/firms/{firm_id}/comments", firm_comments_page, "crm_firm_comments_page"),
    PageRoute("/admin", admin_page, "admin_page"),
    PageRoute("/admin/usermgt", usermgt_page, "admin_usermgt_page"),
    PageRoute("/admin/usermgt/new", new_user_form, "admin_usermgt_new_page"),
    PageRoute("/admin/taskstatus", taskstatus_page, "admin_taskstatus_page"),
    PageRoute("/admin/city", city_page, "admin_city_page"),
    PageRoute("/admin/firmtype", firm_type_page, "admin_firmtype_page"),
    PageRoute("/admin/unit", unit_page, "admin_unit_page"),
    PageRoute("/admin/constants", constants_page, "admin_constants_page"),
    PageRoute("/admin/bugs", bugs_page, "admin_bugs_page"),
    PageRoute("/admin/notifications", notifications_page, "admin_notifications_page"),
    PageRoute("/admin/login_info", login_info_page, "admin_login_info_page"),
]


for page_route in PAGE_ROUTES:
    router.add_api_route(
        page_route.path,
        page_route.handler,
        methods=["GET"],
        name=page_route.name,
    )
