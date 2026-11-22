# Sherlock AI — аудит структуры репозитория

**Ветка:** `refactor/secure-local-assistant-foundation`  
**Аудит:** 22 ноября 2026  
**Цель:** убрать подтверждённый мусор, снизить путаницу и не повредить работающие сценарии.

## 1. Точки входа

| Файл | Роль | Решение |
|---|---|---|
| `desktop_app.py` | Основное desktop-приложение | Сохранить |
| `offline_workspace_app.py` | Отдельное рабочее пространство без ИИ-чата | Сохранить как самостоятельный режим |
| `secretary.py` | Telegram-сервис/секретарь | Сохранить как отдельную интеграцию |
| `chat_cli.py` | Минимальный CLI-режим локального чата | Сохранить как диагностический режим |
| `doctor.py` | Диагностика окружения | Сохранить |
| `telegram_setup.py` | Локальная настройка MTProto | Сохранить |
| `telegram_check.py` | Проверка авторизованной Telegram-сессии | Сохранить |
| `telegram_connection_probe.py` | Проверка сетевого соединения без авторизации | Сохранить |
| `simulate_reply_flow.py` | Безопасная симуляция черновиков | Сохранить как тестовый инструмент |

## 2. Группы модулей

- **Desktop и рабочее пространство:** `desktop_app.py`, `desktop_logic.py`, `offline_workspace.py`, `offline_workspace_app.py`.
- **ИИ и контекст:** `local_ai.py`, `model_selection.py`, `conversation_context.py`, `personality.py`, `memory_suggestions.py`.
- **Данные и доступ:** `database.py`, `security.py`, `assistant_access.py`, `local_action_policy.py`.
- **Файлы:** `local_folder_search.py`, `local_recent_files.py`, `local_file_preview.py`, `local_document_analysis.py`.
- **Задачи и планирование:** `task_planner.py`, `task_scheduler.py`, `task_reminders.py`, `task_overview.py`, `task_daily_briefing.py`, `day_overview.py`, `focus_session.py`.
- **Telegram:** `secretary.py`, `telegram_network.py`, `telegram_setup.py`, `telegram_check.py`, `telegram_connection_probe.py`, `draft_queue.py`, `reply_drafts.py`, `contact_style.py`, `style_examples.py`, `local_commands.py`, `filters.py`, `keyboards.py`, `integrations.py`, `scheduler.py`, `analytics.py`.

## 3. Что найдено и исправлено в рамках уборки

1. README смешивал несколько способов запуска, называл desktop ранним прототипом и содержал повторяющиеся инструкции. Перестроен в короткую главную инструкцию с таблицей точек входа и ссылками на проектную документацию.
2. `.gitignore` не исключал стандартные PyInstaller build-артефакты, SQLite-файлы с расширением `.sqlite3`, временные файлы и логи. Добавлены правила.
3. `.dockerignore` не исключал все локальные SQLite/build/cache артефакты. Синхронизированы правила исключения секретов, пользовательских данных и временных файлов; тесты и документация исключены из Docker build context, поскольку контейнер запускает Telegram-сервис.
4. В `tests/test_telegram_mtproto.py` класс назывался `TelegramNetworkTests`, хотя файл проверяет MTProto proxy и подсказки доставки кода. Имя класса уточнено.

## 4. Дополнительная безопасная чистка кода

- Повторные локальные импорты `datetime.timedelta`, `statistics.median`, `re` и `datetime.datetime` перенесены в единый блок импортов модулей `offline_workspace.py` и `task_scheduler.py`. Поведение функций не менялось.
- `task_planner.py` и `task_scheduler.py` не объединялись: первый формирует приоритетные списки и блоки дня, второй рассчитывает конкретные временные интервалы. Это разные ответственности.

## 5. Дополнительная декомпозиция desktop

- Настройки вынесены из `desktop_app.py` в `desktop_settings.py`: загрузка, валидация и сохранение не зависят от Tkinter. Конфигурация загружается до создания Tk-переменных.
- В `desktop_logic.py` вынесены чистые функции `conversation_title()` и `context_window()`; интерфейс делегирует им выбор заголовка и подготовку ограниченного контекста.
- Генерация вынесена в `desktop_generation.py`. `GenerationWorker` владеет daemon-потоком, запускает async-функцию локальной модели и отправляет события `chunk`/`answer` в очередь. Worker не импортирует и не вызывает Tkinter.
- Добавлены тесты для streaming, безопасного fallback при исключении и защиты от одновременного запуска двух запросов.
- Windows Preview на commit `26df6dc` прошёл все этапы после исправления настроек.
- После выделения generation worker commit `565e48e` прошёл 134 Python-теста и полный Windows Preview: GUI self-test, PyInstaller build, EXE verification, packaged smoke-test и artifact upload.
- Первоначальный тестовый вариант generation worker содержал синтаксическую ошибку; она исправлена до успешного Python CI на commit `565e48e`.

## 6. Что намеренно НЕ удалено

- Не удалялись отдельные точки входа: у них разные пользовательские сценарии.
- Не удалялись `tests/test_telegram_network.py` и `tests/test_telegram_mtproto.py`: тесты частично пересекаются по базовым параметрам, но второй покрывает MTProto proxy, secret format и защиту чувствительного payload.
- Не удалялись модули планировщика, аналитики и интеграций: по одному только дереву файлов нельзя доказать, что они не используются.
- Не выполнялось массовое перемещение модулей: оно меняет импорты и повышает риск регрессии перед 1.0.

## 7. Остаточные задачи

- [ ] Проверить граф импортов и подтвердить неиспользуемые функции/модули статическим анализом и тестами.
- [ ] Разделить `desktop_app.py` и `offline_workspace_app.py` только если будет доказано, что дублирование мешает сопровождению.
- [ ] Проверить содержимое PyInstaller package и исключить dev-only файлы.
- [ ] Добавить линтер/форматтер только после согласования минимального набора правил; не запускать массовое форматирование всего репозитория перед релизом.
- [ ] Провести secret scanning по текущему дереву и отдельно решить вопрос с секретами в Git-истории.

## 8. Проверки CI, известные на момент аудита

- Python checks: успешно на commit `6c86c56073643f7a76b8f642113eb87da0ed4a9b` (22.11.2026), после уточнения имени тестового класса.
- Python checks также успешно завершились на последующих документационных/конфигурационных коммитах `fb42d19`, `aa608d5` и `a48eb30`.
- Windows preview: успешно на commit `131f91dad5b2d9b9c54255f1098a02934ad96008` (18.11.2026); включал тесты, GUI self-test, PyInstaller build, EXE smoke-test и загрузку артефакта.
- Эти результаты относятся к указанным commit SHA. Они не доказывают, что новые изменения уборки уже прошли CI.
