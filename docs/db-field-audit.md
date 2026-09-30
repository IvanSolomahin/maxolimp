# Кандидаты на удаление полей БД задач

Аудит основан на использовании полей кодом на 30 сентября 2026 года. Значения в рабочей БД не проверены: в локальной среде нет подключения к PostgreSQL. Перед удалением нужно проверить данные и внешних потребителей БД. Поля из этой таблицы текущая миграция не меняет.

| Поля | Наблюдение | Проверка перед удалением |
| --- | --- | --- |
| `solutions.author` | Присутствует в схеме и ORM, но сервис его не читает и не записывает. | Число непустых значений и использование внешними потребителями. |
| `embedding`, `embedding_model`, `embedding_model_version` в `solution_methods`, `topics`, `olympiads` | Сервис хранит рабочие векторы задач в `task_embeddings`; обращения к этим девяти полям в коде нет. | Число ненулевых значений каждой таблицы; удалить вместе с ограничениями `*_embedding_meta_check`. |
| `task_topics.weight` | API принимает и сохраняет вес, но поиск и карточка задачи его не используют. | Число значений, отличных от `1.0`; изменение контракта API. |
| `task_sources.scraped_at` | Время сбора записывает импорт, но API его не возвращает. | Число ненулевых значений и необходимость хранить дату происхождения данных. |

Запрос для проверки данных (выполнять в БД `task-db`, без изменения данных):

```sql
BEGIN READ ONLY;
SELECT count(*) FILTER (WHERE author IS NOT NULL) AS solutions_with_author FROM solutions;
SELECT 'solution_methods' AS source, count(*) FILTER (WHERE embedding IS NOT NULL OR embedding_model IS NOT NULL OR embedding_model_version IS NOT NULL) AS rows_with_embedding_data FROM solution_methods
UNION ALL SELECT 'topics', count(*) FILTER (WHERE embedding IS NOT NULL OR embedding_model IS NOT NULL OR embedding_model_version IS NOT NULL) FROM topics
UNION ALL SELECT 'olympiads', count(*) FILTER (WHERE embedding IS NOT NULL OR embedding_model IS NOT NULL OR embedding_model_version IS NOT NULL) FROM olympiads;
SELECT count(*) FILTER (WHERE weight <> 1.0) AS nondefault_weights FROM task_topics;
SELECT count(*) FILTER (WHERE scraped_at IS NOT NULL) AS sources_with_scraped_at FROM task_sources;
COMMIT;
```
