# База сервиса поиска задач

PostgreSQL — основной источник задач для приложения: сервисы читают задачи и
их решения непосредственно из PostgreSQL. ETL и SQLite использовались для
первоначального наполнения и могут оставаться источниками для отдельных
переимпортов, но не являются текущей рабочей базой приложения.

PostgreSQL хранит задачи, их источник и поисковые индексы. Новая база создаётся
из `sql/init.sql` при первом запуске `docker compose up --build`. Для уже
существующей базы v1 сначала выполните `sql/migrate_v2.sql` через `psql`.
Миграция сохраняет старые столбцы и данные; код v2 читает новые таблицы.
Затем выполните `sql/migrate_v3.sql`: она переносит связь задания с олимпиадой
в `tasks.olympiad_id`. Если у задания было несколько олимпиад, сохраняется одна
(с наименьшим UUID).
После `migrate_v3.sql` выполните `sql/migrate_v4.sql`, чтобы схлопнуть варианты
названий олимпиад с классами и различающейся типографикой, переназначить задачи
на одну запись и удалить дубли.
`sql/migrate_v5.sql` заполняет короткие названия для списка и карточек задач.

Для действующей базы после `migrate_v6.sql` выполните `sql/migrate_v7.sql`:
она добавляет сессии и список решённых задач. Затем выполните `sql/migrate_v8.sql`
перед запуском обновлённого приложения: она удаляет поля email и пароля и
аккаунты без MAX ID. Сессии и решённые задачи таких аккаунтов удаляются по
каскаду. Аккаунты MAX и их данные сохраняются. На новой базе итоговую схему
создаёт `sql/init.sql`.

Перед запуском версии с отдельными тегами выполните `sql/migrate_v9.sql`.
Она разделяет `classifier` по разделителю ` , `, сохраняя запятые внутри
названий тегов, и записывает уникальные имена в
`classifier_tags`, связи с задачами в `task_classifier_tags` и удаляет старый
столбец. Миграцию можно повторить безопасно. На новой базе эти таблицы уже
создаёт `sql/init.sql`.

```bash
docker compose exec -T task-db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < task_find_service/sql/migrate_v9.sql
```

```bash
docker compose exec -T task-db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < task_find_service/sql/migrate_v7.sql
docker compose exec -T task-db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < task_find_service/sql/migrate_v8.sql
```

```bash
docker compose exec -T db psql -U gazprompt -d gazprompt < sql/migrate_v2.sql
docker compose exec -T db psql -U gazprompt -d gazprompt < sql/migrate_v3.sql
docker compose exec -T db psql -U gazprompt -d gazprompt < sql/migrate_v4.sql
docker compose exec -T db psql -U gazprompt -d gazprompt < sql/migrate_v5.sql
```

## Импорт ETL

Импорт читает SQLite без записи и выполняет upsert по постоянному UUID,
выведенному из пары `subject + problem_id`. Повторный запуск не создаёт копий
задач, решений, источников и векторов.

Из этой папки, если PostgreSQL доступен на `localhost:5432`:

```bash
python import_etl.py --sqlite ../etl/olimpiads_data_v2/olimpiads.sqlite3
```

Из контейнера после `docker compose up --build -d`:

```bash
docker compose run --rm \
  -v "$(realpath ../etl/olimpiads_data_v2/olimpiads.sqlite3):/data/olimpiads.sqlite3:ro" \
  app python import_etl.py --sqlite /data/olimpiads.sqlite3
```

Ожидаемый результат для текущего снимка: 19 646 задач и 39 221 вектор.
13 задач без условия остаются черновиками без сложности. Решения ETL
сохраняются как исходные, но не как проверенные человеком. Исходное поле
`classifier` делится на отдельные теги классификатора, но не превращается в
темы или методы решения.

Для поиска по смыслу запрос должен кодироваться моделью Qwen3 Embedding 4B через
[AITunnel](https://aitunnel.ru/models/qwen3-embedding-4b). Установите
`AITUNNEL_API_KEY` в корневом `.env` вместе с
`EMBEDDING_MODEL=qwen/qwen3-embedding-4b` и `EMBEDDING_DIMENSION=2560`.
Полный ID модели сохраняет связь с существующими векторами в БД. Без ключа
`GET /tasks?q=...` работает по словам, а поиск похожих задач использует уже
импортированные векторы. Параметры `subject`, `grade` и `mode` (`topic`,
`solution`, `both`) доступны в `GET /tasks`.

Проверка после импорта:

```sql
SELECT count(*) FROM task_sources WHERE source_system = 'sdamgia';
SELECT kind, count(*) FROM task_embeddings
WHERE model = 'qwen/qwen3-embedding-4b' GROUP BY kind;
SELECT count(*) FROM tasks WHERE subject IN ('math', 'physics') AND difficulty IS NULL;
```

Ожидаемые значения: 19 646; `topic` — 19 633, `solution` — 19 588; 13.
После загрузки стоит отдельно сравнить выдачу с `etl/search/search_labels.json`:
PostgreSQL использует русскую морфологию FTS, а SQLite ETL — токенизацию
`unicode61`, поэтому порядок текстовых совпадений может отличаться.
