from fastapi import Request

from views.base import render_page


def calculator_page(request: Request):
    return render_page(
        request,
        "calculator.html",
        "Калькулятор",
        "calculator",
    )
