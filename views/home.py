from fastapi import Request

from views.base import render_page


def home_page(request: Request):
    return render_page(request, "index.html", "Infosys Demo", "home")