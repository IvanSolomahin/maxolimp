# База сервиса поиска задач

PostgreSQL хранит задачи, их источник и поисковые индексы. Новая база создаётся
из `sql/init.sql` при первом запуске `docker compose up --build`. Для уже
существующей базы v1 сначала выполните `sql/migrate_v2.sql` через `psql`.
Миграция сохраняет старые столбцы и данные; код v2 читает новые таблицы.

```bash
docker compose exec -T db psql -U gazprompt -d gazprompt < sql/migrate_v2.sql
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
`classifier` не превращается автоматически в темы или методы решения.

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
