# GeserFlow

Десктопное приложение для трекинга рабочего времени с таймером, проектами, этапами, перерывами и дашбордом статистики.

## Стек

- Python 3.12+
- CustomTkinter (UI)
- SQLite (данные в `data/geserflow.db`)
- pystray (иконка в трее)

## Структура

- `main.py` — точка входа
- `app.py` — главный контроллер (жизненный цикл, трей, попапы, навигация)
- `config.py` — настройки (`settings.json`), дефолты, get/set
- `state.py` — синглтон состояния (статусы: idle / working / paused / on_break)
- `db.py` — все операции с SQLite (projects, stages, sessions, pauses)
- `tray.py` — иконка в системном трее
- `ui/` — окна: main_window, dashboard_window, settings_window, popup_check, popup_break

## Запуск

```bash
python main.py
# или
pythonw main.py   # без консоли
# или
run.bat
```

## Язык

Интерфейс и комментарии на русском. Код (имена переменных, функций) на английском.

## Особенности

- Один экземпляр (lock-файл в temp)
- Dark тема по умолчанию
- Проверка активности по таймеру (popup "Ещё работаешь?")
- Режим перерывов (настраиваемый интервал)
- БД хранится локально в `data/`
## Obsidian Knowledge Vault

Хранилище знаний Gesolutions: C:\Obsidian Claude\gesolutions-vault\

### При старте сессии
1. Прочитай 00-home/index.md и 00-home/текущие-приоритеты.md
2. Если задача касается MAX — прочитай заметки из knowledge/max-api/
3. Если задача касается конкретного проекта — найди его в knowledge/projects/
4. Если задача про архитектуру/инфру — прочитай atlas/

### При завершении (пользователь: «сохрани сессию»)
1. Создай заметку в sessions/ с датой (YYYY-MM-DD-краткое-описание.md)
2. Обнови 00-home/текущие-приоритеты.md
3. Если принято архитектурное решение → создай в knowledge/decisions/
4. Если найден и решён баг → создай в knowledge/debugging/
5. Если выявлен повторяемый паттерн → создай в knowledge/patterns/
6. Обнови 00-home/index.md если добавились новые заметки

### Правила именования заметок
Называй заметки утверждениями, не категориями.
❌ chatplace.md
✅ ChatPlace-синк-через-chats_list-а-не-automations_analytics.md

Используй [[wiki-ссылки]] между связанными заметками.