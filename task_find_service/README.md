# task_find_service

HTTP API для поиска и работы с задачами олимпиад. Сервис хранит задачи и связанные данные в PostgreSQL с расширениями `vector` и `pg_trgm`. В приложении используются SQLAlchemy async и FastAPI; контейнер запускает Uvicorn на порту 8000.

## Возможности

- Поиск и фильтрация опубликованных задач по тексту, предмету, классу, тегам классификатора, олимпиаде, году, этапу, сложности и методу решения. Гибридный поиск объединяет полнотекстовый поиск PostgreSQL и эмбеддинги. Есть отдельный поиск по списку ключевых слов и поиск похожих задач.
- Получение карточки задачи, её источников, тем, олимпиады, тегов, решения и подсказок. Можно создавать и редактировать задачи, назначать им темы, олимпиаду и метод решения, задавать сложность, пересчитывать эмбеддинг.
- Управление деревьями тем и методов решения, а также справочником олимпиад.
- MAX-аутентификация через `initData`, cookie-сессии и MAX webhook. Пользователь может отмечать опубликованные задачи решёнными и получать список и статистику прогресса.
- Импорт снимка ETL из SQLite в PostgreSQL через `import_etl.py`.

Генерация подсказок и решений в `app/services/llm.py` сейчас возвращает заглушки. Проверка решения в `POST /tasks/{task_id}/check` вызывает GigaChat и поддерживает текст и прикреплённый файл.

## Структура

- `app/main.py` — приложение FastAPI, подключение роутеров, проверка БД при старте, MAX webhook и обработчики сообщений.
- `app/config.py`, `app/db.py`, `app/models.py`, `app/schemas.py`, `app/auth.py` — настройки, подключение к БД, ORM-модели, схемы API и авторизация.
- `app/routers/` — маршруты задач (`tasks.py`), тем (`topics.py`), олимпиад (`olympiads.py`), методов решения (`solution_methods.py`), прогресса (`progress.py`) и административного просмотра отсутствующих эмбеддингов (`admin.py`).
- `app/services/` — поиск (`search.py`), эмбеддинги (`embeddings.py`), иерархии и пути тем/методов решения, классификатор тегов и генерация/проверка решений (`llm.py`).
- `sql/init.sql` — полная схема новой БД, включая таблицы задач, источников, решений, подсказок, таксономий, эмбеддингов и аккаунтов.
- `sql/migrate_v2.sql` … `sql/migrate_v9.sql` — последовательные обновления существующих схем; миграции нужны только для уже созданных баз.
- `import_etl.py` — импорт из SQLite; `extract_openapi.py` — вспомогательный экспорт схемы OpenAPI.
- `Dockerfile`, `requirements.txt` — сборка контейнера и Python-зависимости.
- `tests/` — тесты авторизации/прогресса, тегов классификатора и проверки решения.

## Настройки

Настройки читаются из переменных окружения и `.env` в текущей рабочей папке. `app/config.py` игнорирует неизвестные параметры.

| Переменная | Значение по умолчанию | Назначение |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://gazprompt:gazprompt@localhost:5432/gazprompt` | Асинхронное подключение к PostgreSQL. В Compose формируется из `TASK_DB_*` и указывает на `task-db`. |
| `EMBEDDING_MODEL` | `qwen/qwen3-embedding-4b` | Идентификатор модели эмбеддингов; должен соответствовать модели в сохранённых векторах. |
| `EMBEDDING_DIMENSION` | `2560` | Размерность эмбеддинга, проверяется при получении ответа API и при записи в БД. |
| `AITUNNEL_API_KEY` | не задан | Ключ AITunnel для создания эмбеддингов. Без ключа текстовый поиск доступен, но кодирование запросов и пересчёт эмбеддингов недоступны. |
| `GIGACHAT_CREDENTIALS` | не задан | Учётные данные GigaChat для проверки решения. |
| `GIGACHAT_SCOPE` | `GIGACHAT_API_PERS` | Scope GigaChat. |
| `MAX_BOT_TOKEN` | не задан | Токен MAX-бота: проверка `initData`, MAX webhook и отправка сообщений. |
| `MAX_WEBHOOK_SECRET` | не задан | Секрет передаётся Compose в контейнер; в коде сервиса напрямую не читается. |
| `FRONTEND_URL` | `https://gazprompt.duckdns.org` | Значение по умолчанию в `app/main.py`; Compose передаёт значение из `.env`. |
| `OLYMP_FIND_SERVICE_URL` | `http://olymp-app:8000` | URL сервиса олимпиад; передаётся Compose, в коде `task_find_service` сейчас не используется. |
| `RRF_K` | `60` | Константа слияния рангов при поиске. |

Для Compose корневой `.env` также должен содержать `TASK_DB_USER`, `TASK_DB_PASSWORD`, `TASK_DB_NAME`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION`, `MAX_BOT_TOKEN`, `MAX_WEBHOOK_SECRET` и `FRONTEND_URL`. Значения `GIGACHAT_CREDENTIALS` и `GIGACHAT_SCOPE` нужны для проверки решений. Для семантического поиска и создания эмбеддингов задайте `AITUNNEL_API_KEY`.

## Запуск через Docker Compose

Команды выполняются из корня репозитория, потому что Compose использует корневой `.env`, корневой build context и файлы соседних сервисов.

1. Создайте конфигурацию и укажите секреты и учётные данные:

   ```bash
   cp .env.example .env
   ```

2. Соберите и запустите БД и API:

   Перед сборкой подготовьте `certs/russian_trusted_root_ca_pem.crt` в корне репозитория: `Dockerfile` копирует сертификаты из `certs/`, а Compose указывает на этот файл для HTTPS-запросов. Подробности — в [корневой инструкции](../README.md).

   ```bash
   docker compose up --build -d task-db task-app
   ```

   При первом старте с пустым томом `pgdata` PostgreSQL выполнит `task_find_service/sql/init.sql` и создаст итоговую схему. При последующих стартах init-скрипт повторно не запускается. Приложение ожидает готовности `task-db` и проверяет соединение при старте.

3. Проверьте состояние и API:

   ```bash
   docker compose ps task-db task-app
   curl http://localhost:8000/health
   ```

   Документация API доступна по `http://localhost:8000/tasks-docs`, OpenAPI JSON — `/tasks-openapi.json`, ReDoc — `/tasks-redoc`. Compose публикует API только на `127.0.0.1:8000`.

Для локального запуска без контейнера нужен PostgreSQL с расширениями `vector` и `pg_trgm`, доступный по `DATABASE_URL`. В каталоге сервиса установите зависимости и запустите приложение:

```bash
cd task_find_service
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Основные маршруты

Полная схема запросов и ответов опубликована в OpenAPI (`/tasks-docs`). Основные группы:

| Маршруты | Назначение |
|---|---|
| `GET /health` | Проверка доступности приложения. |
| `GET /tasks` | Поиск с параметрами `q`, `subject`, `olympiad_id`, `classifiers`, `grade`, `mode`, диапазонами сложности и года, `stage`, `solution_method_id`, `sort`, `page`, `size`. `mode`: `topic`, `solution` или `both`; сортировка: `relevance`, `newest`, `difficulty`. |
| `GET /tasks/classifiers`, `/tasks/by-topics`, `/tasks/by-olympiads`, `/tasks/search-by-keywords` | Список тегов и выборки задач по таксономии, олимпиадам или ключевым словам. |
| `GET /tasks/{task_id}`, `/similar`, `/hints`, `/solutions` | Карточка задачи, похожие задачи, подсказка заданного уровня и список решений. |
| `POST /tasks`, `PUT /tasks/{task_id}`, `POST /tasks/{task_id}/topics`, `/olympiads`, `/solution-method`, `/embedding`, `/difficulty`, `/check` | Создание/изменение задачи, назначение связей и сложности, пересчёт эмбеддинга, проверка решения. |
| `/topics`, `/solution-methods`, `/olympiads` | Чтение и изменение соответствующих справочников. Темы и методы решения поддерживают древовидные выборки и изменение родителя. |
| `/api/max/validate`, `/api/auth/me`, `/api/auth/logout`, `/webhook` | Проверка MAX `initData`, текущий пользователь, завершение сессии и webhook MAX. |
| `/progress/tasks/{task_id}`, `/progress/tasks/{task_id}/solved`, `/progress/solved`, `/progress/statistics` | Прогресс пользователя. Требуется действующая сессия; отметка задачи решённой дополнительно проверяет Origin. |
| `GET /admin/embeddings/stale` | Задачи без эмбеддинга текущей модели; необязательный параметр `current_model`. |

## Миграции существующей БД

Для новой базы миграции не нужны: итоговую схему создаёт `sql/init.sql`. Скрипт запускается автоматически только при инициализации пустого тома PostgreSQL.

Для базы, созданной более ранними версиями, применяйте миграции по порядку и только начиная с версии вашей схемы. Сначала сделайте резервную копию. Для старой схемы v1 порядок такой: `migrate_v2.sql`, `migrate_v3.sql`, `migrate_v4.sql`, `migrate_v5.sql`, `migrate_v6.sql`, `migrate_v7.sql`, `migrate_v8.sql`, `migrate_v9.sql`. Некоторые файлы являются переходами между промежуточными состояниями: перед применением проверьте комментарии и SQL в каждом скрипте. Не запускайте старые миграции поверх базы, уже созданной через актуальный `init.sql`.

Пример применения одной миграции к Compose-БД (из корня репозитория):

```bash
docker compose exec -T task-db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < task_find_service/sql/migrate_v9.sql
```

`migrate_v9.sql` создаёт таблицы тегов классификатора. Если старый столбец `tasks.classifier` ещё существует, скрипт переносит его значения и удаляет столбец; при повторном запуске этот этап пропускается. Другие миграции преобразуют схему и данные олимпиад, задач, аккаунтов и прогресса; точные действия описаны внутри SQL-файлов.


