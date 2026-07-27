from fastapi import Request

from views.base import render_page


def contacts_page(request: Request):
    return render_page(request, "contacts.html", "Контакты", "contacts")