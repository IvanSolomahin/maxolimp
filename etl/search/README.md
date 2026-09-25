# Поиск

`task_search.py` ищет задачи в общей базе SQLite двумя способами:

- **По словам** — находит совпадения в теме, условии и решении. Работает без
  сети.
- **По смыслу** — сравнивает числовые представления текста, построенные через
  OpenRouter. Например, находит похожие задачи с другими формулировками.

Режим `hybrid` объединяет оба способа. Для темы используются классификатор
и условие, для решения — текст решения. При изменении этих текстов повторите
индексацию; неизменённые представления будут пропущены.

```bash
./search/run_search_index.sh
python3 -m search.task_search --api-key-file olimpiads_data_v2/openrouter.key search \
  'закон сохранения импульса' --mode topic --method hybrid --subject physics -k 5
```

`search_labels.json` содержит примеры запросов с известными ответами.
Проверить качество поиска можно командой:

```bash
python3 -m search.evaluate_search search/search_labels.json \
  --api-key-file olimpiads_data_v2/openrouter.key -k 10
```

`benchmark_batch_sizes.py` сравнивает скорость индексации с разными пакетами.
Запустить его можно командой `python3 -m search.benchmark_batch_sizes`.
Не запускайте два индексатора одновременно на одной базе.
