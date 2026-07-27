from fastapi import Request
from fastapi.responses import RedirectResponse


def root_redirect(request: Request):
    return RedirectResponse(url="/crm", status_code=307)
