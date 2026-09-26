# Maxolimp

Основная база приложения — PostgreSQL: сервисы читают задачи и решения оттуда.
ETL/SQLite использовались для первоначального импорта данных в PostgreSQL и не
являются источником данных для текущей работы приложения. Детали схемы и
истории импорта описаны в [README сервиса поиска задач](task_find_service/README.md).

## Локальный просмотр экранов

После настройки корневого `.env` запустите `docker compose up --build -d`.
Frontend доступен на `http://localhost:8080/` (поиск задач) и
`http://localhost:8080/olympiad-onboarding.html` (подбор олимпиад).
Порт меняется через `FRONTEND_PORT` в `.env`. Чтобы открыть экраны из интернета,
направьте домен или внешний reverse proxy на этот порт и настройте HTTPS.

Контейнер Nginx раздаёт HTML и JS, а также проксирует только GET-запросы,
которые используют экраны. API и базы доступны с хоста лишь через localhost.
Избранное на обоих экранах сохраняется в браузере: у сервисов пока нет
пользовательской аутентификации для публичного доступа.

Формулы в поиске задач отображаются через MathML. Разборщик
`ui/math-render.js` понимает основные русские словесные конструкции из базы
(дроби, корни, скобки, степени, знаки операций) и ряд команд LaTeX. Если запись
неполная или содержит неподдерживаемую команду, интерфейс показывает её
исходный текст. Заголовки и поисковые фрагменты не обрываются внутри `$...$`.

## Автоматический деплой

После push в `main` GitHub Actions подключается к серверу по SSH, обновляет
существующую копию репозитория и пересобирает изменившиеся сервисы. Изменения
в `ui/`, `task_find_service/` и `olymp_find_service/` обновляют соответственно
`frontend`, `task-app` и `olymp-app`. Изменение `docker-compose.yml` обновляет
весь стек. Коммит только с документацией не перезапускает контейнеры.

Ниже `SERVER_HOST`, `SERVER_USER` и `/opt/maxolimp` — примеры. Замените их на
адрес, пользователя и каталог вашего сервера. Выполняйте шаги по порядку.

### 1. Проверьте серверную копию

На сервере должны быть установлены Git, Docker и Docker Compose. Подключитесь
тем пользователем, от имени которого будет идти деплой:

```bash
ssh SERVER_USER@SERVER_HOST
cd /opt/maxolimp
git branch --show-current
git status --short
docker compose ps
```

Ветка должна называться `main`; `git status --short` не должен показывать
изменённые отслеживаемые файлы. Убедитесь, что в каталоге уже есть заполненный
`.env` и запущенный Compose-стек. Не выполняйте `git pull` вручную после
настройки автоматического деплоя: скрипт использует текущий commit как основу
для определения изменённых сервисов.

Если сервер ещё не имеет checkout, создайте его до настройки workflow:

```bash
sudo mkdir -p /opt/maxolimp
sudo chown "$USER":"$USER" /opt/maxolimp
git clone https://github.com/IvanSolomahin/maxolimp.git /opt/maxolimp
cd /opt/maxolimp
cp .env.example .env
chmod 600 .env
nano .env
docker compose up --build -d
docker compose ps
```

Заполните `.env` реальными значениями до запуска Compose. Если репозиторий
закрытый, настройте серверу read-only доступ к GitHub перед `git clone`
(например, отдельным deploy key).

Пользователю деплоя нужны права на checkout и Docker. Если Docker требует членства
в группе `docker`, выполните от администратора сервера:

```bash
sudo usermod -aG docker SERVER_USER
```

После этого пользователь должен заново войти по SSH. Доступ к группе `docker`
даёт широкие права на сервере.

### 2. Создайте SSH-ключ для GitHub Actions

На своём компьютере выполните команды. На вопрос о passphrase нажмите Enter,
чтобы GitHub Actions мог использовать ключ без интерактивного ввода:

```bash
ssh-keygen -t ed25519 -C "github-actions-maxolimp-deploy" -f ~/.ssh/maxolimp_deploy
```

Добавьте публичную часть ключа на сервер (укажите тот же SSH-порт, если он не
стандартный):

```bash
ssh-copy-id -i ~/.ssh/maxolimp_deploy.pub -p 22 SERVER_USER@SERVER_HOST
```

Проверьте, что вход по новому ключу работает:

```bash
ssh -i ~/.ssh/maxolimp_deploy -p 22 SERVER_USER@SERVER_HOST 'cd /opt/maxolimp && git branch --show-current && docker compose ps'
```

### 3. Подготовьте проверенный ключ SSH-сервера

На сервере узнайте отпечаток публичного ключа SSH-сервера:

```bash
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

На своём компьютере получите запись для `known_hosts` и отпечаток этой записи:

```bash
ssh-keyscan -t ed25519 -H -p 22 SERVER_HOST > ~/.ssh/maxolimp_known_hosts
ssh-keygen -lf ~/.ssh/maxolimp_known_hosts
```

Сравните отпечатки. Продолжайте, только если они совпадают. При нестандартном
SSH-порте замените `22` в командах на фактический порт.

### 4. Добавьте GitHub Secrets

Установите [GitHub CLI](https://cli.github.com/) и войдите в аккаунт, имеющий
доступ к репозиторию. В терминале компьютера, где созданы ключи, задайте
переменные и замените примеры:

```bash
export GH_REPO=IvanSolomahin/maxolimp
export SERVER_HOST=example.com
export SERVER_USER=deploy
export SERVER_PORT=22
export DEPLOY_PATH=/opt/maxolimp
```

Запишите значения в Actions Secrets командами:

```bash
gh secret set SSH_HOST --repo "$GH_REPO" --body "$SERVER_HOST"
gh secret set SSH_USER --repo "$GH_REPO" --body "$SERVER_USER"
gh secret set SSH_PORT --repo "$GH_REPO" --body "$SERVER_PORT"
gh secret set SSH_PRIVATE_KEY --repo "$GH_REPO" < ~/.ssh/maxolimp_deploy
gh secret set SSH_KNOWN_HOSTS --repo "$GH_REPO" < ~/.ssh/maxolimp_known_hosts
gh secret set DEPLOY_PATH --repo "$GH_REPO" --body "$DEPLOY_PATH"
```

Если используется порт `22`, `SSH_PORT` можно не добавлять. Secrets также можно
создать на странице репозитория: **Settings → Secrets and variables → Actions**.
Имена должны в точности совпадать с именами выше.

### 5. Запустите и проверьте деплой

Теперь отправьте обычный коммит в ветку `main`. Откройте вкладку **Actions** в
GitHub, выберите запуск **Deploy** и проверьте, что он завершился успешно.
Затем на сервере проверьте контейнеры и страницу приложения:

```bash
ssh -i ~/.ssh/maxolimp_deploy -p "$SERVER_PORT" "$SERVER_USER@$SERVER_HOST" \
  'cd /opt/maxolimp && docker compose ps && curl -fsS http://localhost:8080/ >/dev/null'
```

Для первой принудительной пересборки всех сервисов выполните на сервере:

```bash
cd /opt/maxolimp
docker compose up --build -d
```

`docker compose up` сохраняет именованные тома PostgreSQL и кэша. Изменения
`sql/init.sql` не применяются к существующей базе: для них нужна отдельная
миграция.
