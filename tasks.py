from invoke import task


@task
def deps(c):
    """Установить системные GIR-типелибы GTK4 (нужен sudo)"""
    c.run("sudo apt-get install -y gir1.2-gtk-4.0 gir1.2-graphene-1.0")


@task
def venv(c):
    """Пересоздать окружение на системном Python 3.12 (PyGObject из system-site-packages)"""
    c.run("uv venv --clear --system-site-packages --python /usr/bin/python3.12")
    c.run("uv sync")


@task
def hooks(c):
    """Включить git-хуки из .githooks (один раз после клонирования).
    Отключить: `git config --unset core.hooksPath`.
    """
    c.run("git config core.hooksPath .githooks")


@task
def check(c):
    """Проверка кода (ruff)"""
    c.run("uv run ruff check")


@task
def fmt(c):
    """Форматирование кода (ruff)"""
    c.run("uv run ruff format")


@task
def types(c):
    """Проверка типов (mypy, strict)"""
    c.run("uv run mypy")


@task
def testing(c):
    """Запуск тестов"""
    c.run("uv run pytest")


@task(pre=[check, types])
def static(c):
    """Статический гейт: линт, формат, типы (без тестов)"""
    c.run("uv run ruff format --check")


@task(pre=[static])
def verify(c):
    """Полный гейт: статика и тесты — то, что должен пройти каждый пуш"""
    c.run("uv run pytest")
