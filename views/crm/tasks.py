from fastapi import Depends, Request
from sqlalchemy.orm import aliased
from sqlmodel import Session, select

from core.auth import resolve_authenticated_access
from db.database import get_session
from models.task import Task
from models.task_status import TaskStatus
from models.users import User
from views.base import render_page


def tasks_page(request: Request, session: Session = Depends(get_session)):
    state, current_user = resolve_authenticated_access(request, session)

    if state == "login":
        return render_page(request, "admin/login.html", "Вход", "crm", {"next": "/crm/tasks"})

    Assignee = aliased(User)
    Author = aliased(User)

    authored_rows = session.exec(
        select(Task, Assignee.fullname, TaskStatus.name)
        .join(Assignee, Assignee.id == Task.assignee_id)
        .join(TaskStatus, TaskStatus.id == Task.status_id)
        .where(Task.author_id == current_user.id)
        .order_by(Task.id.desc())
    ).all()
    authored_tasks = [
        {"task": t, "other_name": fullname, "status_name": status_name}
        for t, fullname, status_name in authored_rows
    ]

    assigned_rows = session.exec(
        select(Task, Author.fullname, TaskStatus.name)
        .join(Author, Author.id == Task.author_id)
        .join(TaskStatus, TaskStatus.id == Task.status_id)
        .where(Task.assignee_id == current_user.id)
        .order_by(Task.id.desc())
    ).all()
    assigned_tasks = [
        {"task": t, "other_name": fullname, "status_name": status_name}
        for t, fullname, status_name in assigned_rows
    ]

    users = session.exec(
        select(User).where(User.isactive.is_(True)).order_by(User.fullname)
    ).all()
    statuses = session.exec(select(TaskStatus).order_by(TaskStatus.id)).all()

    return render_page(
        request,
        "crm/tasks.html",
        "Мои задачи",
        "crm",
        {
            "authored_tasks": authored_tasks,
            "assigned_tasks": assigned_tasks,
            "users": users,
            "statuses": statuses,
        },
    )
