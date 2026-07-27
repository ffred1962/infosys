from fastapi import Request

from views.base import render_page


def about_page(request: Request):
    return render_page(request, "about.html", "О проекте", "about")