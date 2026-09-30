# Сервис поиска олимпиад

`olymp_find_service` — FastAPI API для каталога олимпиад, вузов, программ и предметов. Он также хранит данные об офлайн-кружках и онлайн-сообществах. Данные каталога находятся в PostgreSQL; SQLAlchemy подключается асинхронно через `asyncpg`.

## Структура

| Путь | Назначение |
| --- | --- |
| `app/main.py` | Создание FastAPI-приложения, подключение роутеров, проверка соединения с БД при старте и `/health`. |
| `app/config.py` | Настройки приложения из переменных окружения и файла `.env`. |
| `app/db.py` | Асинхронный SQLAlchemy engine и выдача сессии БД для запросов. |
| `app/models.py` | ORM-модели каталога и сообществ. |
| `app/schemas.py` | Pydantic-схемы ответов каталога олимпиад, этапов и льгот. |
| `app/deps.py` | Нормализация типов льгот. |
| `app/routers/catalog.py` | Поиск вузов, программ и предметов. |
| `app/routers/olympiads.py` | Рекомендации олимпиад, карточка олимпиады, этапы и льготы. |
| `app/routers/communities.py` | Поиск и CRUD кружков и онлайн-сообществ, список источников. |
| `sql/init.sql` | Создание основных таблиц каталога для новой БД. |
| `sql/seed.sql` | Начальное наполнение каталога; транзакционно очищает и заменяет записи каталога. |
| `sql/add_communities.sql` | Создание таблиц `clubs` и `sources` и импорт начальных данных. Запускать один раз на БД без этих таблиц. |
| `sql/add_online_communities.sql` | Создание таблицы `online_communities` и индекса. |
| `sql/migrate_subject_identity.sql` | Миграция старой схемы с очисткой старого каталога; используется вместе с `seed.sql` в одной транзакции. |
| `sql/migrate_subject_olympiad_id_preserve_data.sql` | Обновление идентификаторов связей предмета и олимпиады без замены каталога; удаляет старую таблицу избранного. |
| `sql/remove_favorites.sql` | Удаление старой таблицы избранного из существующей БД без изменения каталога. |
| `sql/add_confirmed_subject_links.sql` | Добавление подтверждённых связей предметов с олимпиадами без удаления существующих строк. |
| `import_workbook.py` | Проверка книги Excel и генерация SQL-файла seed. |
| `extract_openapi.py` | Обновление корневого снимка `olymp-openapi.json` или проверка его актуальности с `--check`. |
| `main.py` | Экспорт объекта FastAPI для запуска `uvicorn main:app` из каталога сервиса. |
| `requirements.txt` | Python-зависимости сервиса. |
| `Dockerfile` | Сборка API-контейнера; запускает Uvicorn на порту контейнера `8000`. |

## Функции API

Интерактивная документация доступна по `/olymp-docs`, схема OpenAPI — `/olymp-openapi.json`, ReDoc — `/olymp-redoc`.

| Метод и путь | Назначение и основные параметры |
| --- | --- |
| `GET /health` | Проверка доступности приложения; ответ `{"status":"ok"}`. |
| `GET /universities` | Список вузов с городами. Фильтры `q`, `city_id`; пагинация `page` (по умолчанию 1), `size` (20, максимум 100). Поиск `q` учитывает название вуза и города. |
| `GET /universities/{university_id}/programs` | Программы указанного вуза. Фильтр `q` ищет по названию и коду; есть `page` и `size`. |
| `GET /programs` | Программы с `university_id`. Фильтры `q`, `university_id`; есть `page` и `size`. |
| `GET /subjects` | Список предметов. Фильтр `q`; есть `page` и `size`. |
| `GET /olympiads/recommendations` | Рекомендации с группировкой по олимпиаде. Фильтры `university_id`, `program_id`, `benefit_type`; `sort=complexity` (по умолчанию) или `sort=name`; есть `page` и `size`. Поддерживаются псевдонимы типов льгот `bvi`, `no entrance exams`, `no_entrance_exams`, `100 points`, `100_points`, `additional_points`, `additional points`. |
| `GET /olympiads/{olympiad_id}` | Карточка связи предмета и олимпиады: название, сложность, описание, вуз-организатор и предмет. Идентификатор здесь — `subject_olympiad.id`. |
| `GET /olympiads/{olympiad_id}/stages` | Этапы олимпиады по `subject_olympiad.id`, сортируются по дате начала. |
| `GET /olympiads/{olympiad_id}/benefits` | Льготы олимпиады по `subject_olympiad.id`; фильтры `university_id`, `program_id`. |
| `GET /communities/options` | Доступные города и предметы для фильтра кружков. В текущей реализации город — Санкт-Петербург, предметы — математика и физика. |
| `GET /communities/clubs` | Поиск кружков: фильтры `subject`, `city` (по умолчанию Санкт-Петербург), `q`, `lat`, `lon`, `radius_km`. Координаты используются для расчёта расстояния и сортировки; ограничение радиуса применяется при передаче обеих координат. |
| `GET /communities/clubs/{club_id}` | Получить кружок по ID. |
| `POST /communities/clubs` | Создать кружок. Тело содержит `name`, `address`, `subject`; также принимаются `latitude`, `longitude`, `status`, `note`, `source`. В тестовом режиме предмет должен быть `Физика` или `Математика`. |
| `PUT /communities/clubs/{club_id}` | Полностью обновить поля кружка; тело такое же, как при создании. |
| `DELETE /communities/clubs/{club_id}` | Удалить кружок. |
| `GET /communities/sources` | Список источников данных кружков. |
| `GET /communities/online` | Список онлайн-сообществ; фильтры `subject`, `q`. |
| `POST /communities/online` | Создать онлайн-сообщество. Поля: `name`, `subject`, `platform`, `url`; необязательные `description`, `sort_order`. |
| `PUT /communities/online/{chat_id}` | Полностью обновить онлайн-сообщество. Тело такое же, как при создании. |
| `DELETE /communities/online/{chat_id}` | Удалить онлайн-сообщество. |

## Настройки

Приложение читает `.env` из текущего рабочего каталога. Неизвестные настройки игнорируются.

| Переменная | Значение по умолчанию | Назначение |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://olymp:olymp@localhost:5433/olymp` | Строка подключения SQLAlchemy к PostgreSQL. |
| `TASK_FIND_SERVICE_URL` | `http://task-app:8000` | Адрес task-сервиса, передаваемый настройкам этого приложения. В коде `olymp_find_service` прямого использования этой настройки нет. |

В корневом `.env.example` также перечислены переменные других контейнеров Compose. Для этого сервиса Compose задаёт `DATABASE_URL` и `TASK_FIND_SERVICE_URL`.

## Запуск через Docker Compose

Команды выполняются из корня репозитория. Compose-файл собирает `olymp-app` из этого каталога и поднимает отдельную PostgreSQL 16 (`olymp-db`). Порт API доступен на `127.0.0.1:8001`, порт PostgreSQL — на `127.0.0.1:5433`.

```bash
cp .env.example .env
# Заполните значения в .env; задайте уникальный OLYMP_DB_PASSWORD.
docker compose up --build -d olymp-db olymp-app
```

Compose ждёт успешного healthcheck PostgreSQL перед запуском API. На пустом volume контейнер PostgreSQL выполняет `sql/init.sql`, затем `sql/seed.sql` из каталога `/docker-entrypoint-initdb.d`. Эти init-скрипты автоматически выполняются только при создании пустого `olymp-pgdata`; при уже существующем volume новые или изменённые SQL-файлы автоматически не применяются.

Таблицы сообществ в `init.sql` не входят. После запуска БД и до использования `/communities` выполните `add_communities.sql` и `add_online_communities.sql` по [корневой инструкции](../README.md). Первый скрипт рассчитан только на БД без таблиц `clubs` и `sources`.

Проверить API можно запросами:

```bash
curl http://127.0.0.1:8001/health
curl http://127.0.0.1:8001/olymp-docs
```

Чтобы поднять весь проект, включая интерфейс и task-сервис, используйте из корня:

```bash
docker compose up --build -d
```

## Локальный запуск API

Нужны Python 3.12 и доступный PostgreSQL с созданной схемой и данными. В каталоге `olymp_find_service` создайте виртуальное окружение, установите зависимости и укажите URL БД в `.env` или переменной окружения:

```bash
cd olymp_find_service
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL='postgresql+asyncpg://olymp:olymp@localhost:5433/olymp'
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

При старте приложение проверяет подключение запросом `SELECT 1`. Схема автоматически не создаётся. Запускайте команду из каталога `olymp_find_service`, поскольку импорты в приложении используют пакет `app`.

## Обновление данных каталога

Импортёр читает книгу Excel с ожидаемыми листами и столбцами, проверяет идентификаторы, уникальность пар и ссылки между листами, затем записывает SQL seed. Книга используется только как источник данных.

```bash
python3 olymp_find_service/import_workbook.py INPUT.xlsx olymp_find_service/sql/seed.sql
```

`seed.sql` очищает таблицы каталога, этапов и льгот, а затем загружает содержимое книги в транзакции. На новой БД создание каталога выполняется при создании volume. Для уже запущенной БД применяйте подготовленный SQL к нужной базе через `psql` только после проверки последствий замены каталога.

Для старой схемы используйте миграцию, подходящую к задаче:

- `migrate_subject_identity.sql` вместе с `seed.sql` в одном сеансе `psql`: первая команда открывает транзакцию, `seed.sql` заканчивает её. Эта операция заменяет старый каталог и удаляет старую таблицу избранного.
- `migrate_subject_olympiad_id_preserve_data.sql` сохраняет строки каталога, но удаляет старую таблицу избранного.
- `add_confirmed_subject_links.sql` добавляет только отсутствующие подтверждённые связи предмета и олимпиады.

Для данных сообществ `add_communities.sql` — однократный импорт и создание таблиц `clubs` и `sources`; повторный запуск на существующих таблицах не поддерживается. `add_online_communities.sql` создаёт таблицу и индекс с `IF NOT EXISTS`. При использовании существующего Docker volume запускайте нужные SQL вручную, например:

```bash
docker compose exec -T olymp-db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < olymp_find_service/sql/add_online_communities.sql
```

Для существующей БД, которой не нужны миграции каталога, примените только `sql/remove_favorites.sql`. Он удаляет таблицу и все сохранённые в ней записи:

```bash
docker compose exec -T olymp-db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < olymp_find_service/sql/remove_favorites.sql
```
