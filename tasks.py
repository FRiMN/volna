from invoke import task


@task
def venv(c):
    """Пересоздать окружение на системном Python 3.12 (PyGObject из system-site-packages)"""
    c.run("uv venv --clear --system-site-packages --python /usr/bin/python3.12")
    c.run("uv sync")


@task
def check(c):
    """Проверка кода (ruff)"""
    c.run("uv run ruff check")


@task
def fmt(c):
    """Форматирование кода (ruff)"""
    c.run("uv run ruff format")


@task
def testing(c):
    """Запуск тестов"""
    c.run("uv run pytest")
