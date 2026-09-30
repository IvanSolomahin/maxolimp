# Gazprompt

Мини-приложение MAX для поиска и решения олимпиадных задач, подбора олимпиад и просмотра учебных сообществ. В репозитории два FastAPI-сервиса с отдельными базами PostgreSQL и статический интерфейс на Nginx.

## Состав репозитория

| Путь | Назначение |
| --- | --- |
| [task_find_service/](task_find_service/README.md) | Задачи, поиск, проверка решений, вход через MAX и персональная статистика. Использует `task-db` с pgvector. |
| [olymp_find_service/](olymp_find_service/README.md) | Каталог олимпиад, вузов и программ, рекомендации и сообщества. Использует отдельную `olymp-db`. |
| [ui/](ui/README.md) | Статические HTML, CSS и JS страницы; Nginx отдаёт файлы и проксирует запросы к API. |
| `docker-compose.yml` | Контейнеры `frontend`, `task-app`, `task-db`, `olymp-app`, `olymp-db`, сеть и постоянные тома. |
| `scripts/deploy.sh`, `.github/workflows/deploy.yml` | Обновление контейнеров на сервере после изменений в `main`. |
| `docs/` | Подробные требования и заметки по отдельным сценариям. |
| `DATA-API.yaml`, `tasks-openapi.json`, `olymp-openapi.json` | Описание и сохранённые снимки API; актуальные схемы доступны у запущенных сервисов. |

Compose задаёт сервисам внутренние адреса друг друга (`OLYMP_FIND_SERVICE_URL` и `TASK_FIND_SERVICE_URL`), хотя текущий код их не использует. Внешний трафик принимает `frontend`; базы и API дополнительно доступны только через loopback сервера.

## Первый запуск через Docker Compose

Команды выполняются из корня репозитория. Нужны Docker с Compose v2, доступ к реестрам образов и пакетам Python, домен с настроенным DNS и сертификат TLS. Текущая конфигурация рассчитана на `gazprompt.duckdns.org`.

1. Создайте `.env` и замените примерные значения. Файл не отслеживается Git:

   ```bash
   cp .env.example .env
   ```

   | Переменные | Для чего нужны |
   | --- | --- |
   | `TASK_DB_USER`, `TASK_DB_PASSWORD`, `TASK_DB_NAME` | База задач. |
   | `OLYMP_DB_USER`, `OLYMP_DB_PASSWORD`, `OLYMP_DB_NAME` | База каталога. |
   | `MAX_BOT_TOKEN` | Бот MAX и проверка данных входа в мини-приложение. |
   | `AITUNNEL_API_KEY`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSION` | Семантический поиск и создание векторов задач. Модель и размерность должны соответствовать уже сохранённым векторам. |
   | `GIGACHAT_CREDENTIALS`, `GIGACHAT_SCOPE` | Проверка и генерация решений через GigaChat. |
   | `FRONTEND_PORT` | Необязательный HTTP-порт на сервере; по умолчанию `8080`. HTTPS занимает `443`. |
   | `FRONTEND_URL`, `MAX_WEBHOOK_SECRET` | Передаются в `task-app`; текущий код не использует их для настройки домена Nginx или регистрации webhook. |

   Для функций, использующих внешние API, нужны действительные ключи. Не публикуйте `.env`.

2. Подготовьте сертификаты **до сборки**. `task_find_service/Dockerfile` копирует `*.crt` из локальной папки `certs/`; папка игнорируется Git. В текущем Compose `task-app` ищет внутри образа конкретный файл `certs/russian_trusted_root_ca_pem.crt`. Поместите под этим именем доверенный корневой сертификат, который нужен для внешних запросов, либо согласованно измените `Dockerfile` и переменные `SSL_CERT_FILE`/`REQUESTS_CA_BUNDLE` в Compose. Nginx ожидает на сервере файлы `/root/.acme.sh/gazprompt.duckdns.org_ecc/fullchain.cer` и `/root/.acme.sh/gazprompt.duckdns.org_ecc/gazprompt.duckdns.org.key`: Compose монтирует эту папку в `/etc/nginx/ssl` контейнера. При запуске от другого пользователя или на другом домене измените путь тома в `docker-compose.yml`, `server_name` и пути к сертификату в `ui/nginx.conf`. Одного изменения `FRONTEND_URL` недостаточно.

3. Запустите обе базы. SQL-файлы, подключённые в Compose, выполняются PostgreSQL **только при создании пустых томов**: для `task-db` это `task_find_service/sql/init.sql`, для `olymp-db` — `olymp_find_service/sql/init.sql` и `seed.sql`.

   ```bash
   docker compose up -d task-db olymp-db
   docker compose ps
   ```

4. Добавьте таблицы и начальные данные сообществ. Они пока не входят в `olymp_find_service/sql/init.sql`; `add_communities.sql` создаёт таблицы `clubs` и `sources` и рассчитан на однократное применение к базе без этих таблиц.

   ```bash
   docker compose exec -T olymp-db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < olymp_find_service/sql/add_communities.sql
   docker compose exec -T olymp-db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < olymp_find_service/sql/add_online_communities.sql
   ```

5. Соберите и запустите приложения и Nginx:

   ```bash
   docker compose up -d --build
   docker compose ps
   ```

   Новая база задач содержит схему, но не набор олимпиадных задач; данные загружаются отдельно из внешнего источника. Каталог олимпиад наполняется `seed.sql` при первом создании `olymp-db`.

## Проверка

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8001/health
curl -I https://gazprompt.duckdns.org/
docker compose logs --tail=100 task-app olymp-app frontend
```

Страницы Swagger UI: `https://gazprompt.duckdns.org/tasks-docs` и `https://gazprompt.duckdns.org/olymp-docs`. Соответствующие схемы: `/tasks-openapi.json` и `/olymp-openapi.json`. Маршруты задач снаружи доступны через `/api/tasks/`, маршруты каталога — через `/api/olympiads/`, прогресс — через `/api/progress/`. Схемы API используют внутренние пути сервисов; правила преобразования внешних URL находятся в `ui/nginx.conf`.

`FRONTEND_PORT` открывает HTTP с перенаправлением на HTTPS. По умолчанию это порт `8080`, поэтому для стандартного HTTP на порту 80 задайте `FRONTEND_PORT=80` и убедитесь, что порт свободен.

## Обновление существующей установки

Постоянные данные находятся в томах `pgdata` и `olymp-pgdata`. Повторный `docker compose up` не применяет изменённые `init.sql` и `seed.sql` к этим томам. Перед запуском версии с новой схемой выполните нужные SQL-миграции вручную и сделайте резервную копию базы. Порядок и последствия миграций описаны в [документации сервиса задач](task_find_service/README.md) и [документации каталога](olymp_find_service/README.md). Не запускайте `seed.sql` повторно без проверки: он очищает каталог перед загрузкой данных.

При обновлении базы каталога, созданной до удаления избранного, примените `olymp_find_service/sql/remove_favorites.sql`. Скрипт удаляет таблицу и сохранённые в ней записи; каталог олимпиад не затрагивает. Для новой базы он не нужен.

```bash
docker compose exec -T olymp-db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < olymp_find_service/sql/remove_favorites.sql
```

После миграций обновите контейнеры:

```bash
docker compose up -d --build
```

Push в `main` запускает `.github/workflows/deploy.yml`: он подключается к серверу по SSH, обновляет чистый checkout ветки `main` и вызывает `scripts/deploy.sh`. Для workflow нужны GitHub Secrets `SSH_HOST`, `SSH_USER`, `SSH_PRIVATE_KEY`, `SSH_KNOWN_HOSTS`, `DEPLOY_PATH`; `SSH_PORT` необязателен. Скрипт пересобирает изменённые сервисы, а изменения в `ui/public/` видны через подключённый том без перезапуска. Изменения документации и SQL-файлов сами по себе не применяют миграции к существующим базам.

## Дополнительная документация

- [Архитектура и внешние провайдеры](docs/architecture.md)
- [Сервис задач: API и данные](task_find_service/README.md)
- [Сервис олимпиад: каталог и сообщества](olymp_find_service/README.md)
- [Статический интерфейс](ui/README.md)
- [Сценарий решения задач и статистика](docs/task-solving-and-statistics.md)
