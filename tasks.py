from invoke import task


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
