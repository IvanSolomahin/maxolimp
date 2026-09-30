# Кандидаты на удаление полей БД задач

Аудит основан на использовании полей кодом и чтении агрегированных значений в рабочей БД 30 сентября 2026 года. [Ручной read-only запуск](https://github.com/IvanSolomahin/maxolimp/actions/runs/36671854396) выполнил запросы в одной транзакции. Перед удалением полей нужно проверить внешних потребителей БД. Поля из этой таблицы текущая миграция не меняет.

| Поля | Наблюдение | Значения в продовой БД | Вывод |
| --- | --- | --- | --- |
| `solutions.author` | Присутствует в схеме и ORM, но сервис его не читает и не записывает. | Ненулевых значений: **0**. | Кандидат на удаление после проверки внешних потребителей. |
| `embedding`, `embedding_model`, `embedding_model_version` в `solution_methods`, `topics`, `olympiads` | Сервис хранит рабочие векторы задач в `task_embeddings`; обращения к этим девяти полям в коде нет. | Строк с хотя бы одним заполненным полем: **0** в каждой таблице. | Кандидаты на удаление вместе с ограничениями `*_embedding_meta_check` после проверки внешних потребителей. |
| `task_topics.weight` | API принимает и сохраняет вес, но поиск и карточка задачи его не используют. | Значений, отличных от `1.0`: **0**. | Кандидат на удаление после изменения контракта API и проверки внешних потребителей. |
| `task_sources.scraped_at` | Время сбора записывает импорт, но API его не возвращает. | Ненулевых значений: **19 631**. | Сохранять: поле содержит данные о происхождении задач. |

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
