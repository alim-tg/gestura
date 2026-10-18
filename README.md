# gestura

Распознавание жестов рук с веб-камеры: видео с разметкой и трекингом в браузере, лента событий, и любой жест можно привязать к HTTP-запросу (например, убавить свет через Home Assistant).

```
веб-камера ─► MediaPipe (21 точка кисти + жест) ─► трекер (id рук, траектории, свайпы, щипок) ─► браузер
                                                                   │
                                                                   └─► actions.json ─► HTTP ─► ваш сервер / Home Assistant
```

## Что распознаётся

| Жест | Имя события |
|---|---|
| 🖐 ✊ ☝️ 👍 👎 ✌️ 🤟 | `Open_Palm`, `Closed_Fist`, `Pointing_Up`, `Thumb_Up`, `Thumb_Down`, `Victory`, `ILoveYou` |
| 🤏 щипок (большой + указательный) | `Pinch` |
| ⬅️ ➡️ ⬆️ ⬇️ взмах рукой | `swipe_left`, `swipe_right`, `swipe_up`, `swipe_down` |
| рука вошла / ушла из кадра | `hand_enter`, `hand_leave` |

У каждой руки свой постоянный id и цвет, за ладонью тянется траектория. Жест засчитывается, когда неподвижная рука держит его 5 кадров подряд; событие приходит один раз на смену жеста. Пока рука движется быстро (машете), статичные жесты не распознаются — на смазанных кадрах модель ошибается, — а свайпы работают.

## Установка

```powershell
cd C:\Users\nevil\Desktop\Work\PersonalProjects\gestura
uv venv .venv --python 3.12
uv pip install --python .venv\Scripts\python.exe -e .
```

При первом запуске скачивается модель MediaPipe `gesture_recognizer.task` (~8 МБ, storage.googleapis.com) в `models/`.

## Запуск

```powershell
.venv\Scripts\gestura serve                       # http://127.0.0.1:8800
.venv\Scripts\gestura serve --camera 1 --hands 1  # другая камера, одна рука
.venv\Scripts\gestura serve --host 0.0.0.0        # открыть в локальной сети
```

## Действия на жесты

```powershell
copy actions.example.json actions.json
$env:HA_TOKEN = "долгоживущий токен Home Assistant"
.venv\Scripts\gestura serve
```

В `actions.json` ключ — имя события, значение — запрос: `url`, `method` (по умолчанию POST), `headers`, `json` (если не указать, уйдёт само событие). `${VAR}` подставляется из переменных окружения. Результат каждого запроса виден в ленте событий.

Подробности: [spec/architecture.md](spec/architecture.md), [spec/gestures.md](spec/gestures.md).
