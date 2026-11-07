# Shelter Humanizer на Apple Silicon

Эта ветка добавляет macOS; Intel Mac не проверен и не заявлен. Интерфейс русский.
Локальная проверка: macOS 27.0 (26A428), arm64, Homebrew Python 3.14.8_2,
Tcl/Tk 9.1.0, PyInstaller 6.22.3. Системный `/usr/bin/python3` не меняется.
Homebrew при установке Tk обновил собственный Python 3.14.6 до 3.14.8.

## Из исходников

```sh
brew install python@3.14 python-tk@3.14
cd /path/to/Shelter-Humanizer
python3.14 -m tkinter  # должно открыться тестовое окно
python3.14 -m venv .venv
.venv/bin/python -m pip install -e . -r requirements-dev.txt
.venv/bin/python launcher.py
```

Создавайте `.venv` после установки совместимых Python/Tk. При смене версии Python
пересоздайте окружение. Установка Ollama через Homebrew может добавить новый Python
(здесь добавлен 3.15.0); используйте именно `python3.14` и `.venv/bin/python`,
а не меняющийся `python3`. Исходники требуют Python >=3.11, но это не означает, что
каждая комбинация Python/Tk/macOS прошла приёмку. Runtime-зависимостей из PyPI нет.
Если `_tkinter` отсутствует, CLI остаётся доступен:

```sh
.venv/bin/python launcher.py analyze examples/post_before.txt
.venv/bin/python launcher.py clean examples/post_before.txt -o /tmp/clean.txt --report /tmp/report.json
```

## Внешняя Ollama

Установите [официальную Ollama для macOS](https://ollama.com/download/mac) и откройте её.
Shelter не скачивает Ollama/модели на Mac и не завершает внешний сервис при выходе.

```sh
ollama list
curl http://localhost:11434/api/tags
```

Если сервиса нет, откройте Ollama.app или запустите `ollama serve` отдельно.
Сначала проверьте уже установленные модели. Если моделей нет, выберите подходящую
в [каталоге](https://ollama.com/search), проверьте размер и требования к памяти,
затем самостоятельно выполните `ollama pull ИМЯ`. Загрузка больших моделей не нужна
для офлайн-функций и не запускается автоматически.

В Shelter: «Выбрать ИИ» → «Подключить Ollama» → «Показать доступные модели» →
выберите модель → «Применить». URL по умолчанию `http://localhost:11434`.
HTTP разрешён только для loopback; для внешнего сервера нужен HTTPS.
Адрес, модель и подбор контекста сохраняются в
`~/Library/Application Support/ShelterHumanizer/editor-preferences.json`.
API-ключи, тексты и временный режим «Только процессор» не сохраняются.
Сохранённое внешнее подключение восстанавливается без запуска процессов и загрузок.
Файл можно удалить для сброса настроек. Диагностика хранится в памяти и экспортируется
только явно; автоматических логов/истории текстов нет.

Генерация потоковая: прогресс показывает этап, время и число символов; результат
применяется после завершения ответа и проверок. «Отмена» закрывает соединение этого
запроса и сохраняет исходник/предыдущий результат; это не команда остановки Ollama.

## Управление

⌘A/C/V/X/Z, ⇧⌘Z работают в текстовых полях; английские и русские обозначения
клавиш распознаются. Отмена/повтор доступны в многострочных редакторах; Entry/Combobox
сохраняют стандартное поведение Tk для редактирования однострочного значения.
Контекстное меню: правый клик или Control-click. Диалоги прокручиваются трекпадом;
текстовые поля используют нативную прокрутку Tk. Масштаб Retina берётся у Tk.

## Сборка и запуск .app

Собирайте на Apple Silicon в графической сессии (self-test создаёт настоящее окно Tk):

```sh
.venv/bin/python tools/build_release.py
shasum -a 256 -c dist/darwin/SHA256SUMS.txt
open dist/darwin/Shelter-Humanizer.app
```

Результат: `dist/darwin/Shelter-Humanizer.app` и
`Shelter-Humanizer-1.1.1-darwin-arm64.zip`. Архив включает лицензии, сведения о сборке,
офлайн SELFTEST.json и эту инструкцию. Python, Tcl/Tk и ресурсы находятся внутри `.app`;
для готовой сборки отдельный Python не нужен. Перенесите приложение в выбранную папку
и откройте двойным кликом в Finder. Настройки находятся вне bundle и не зависят от cwd.
Иконка `.icns` — конверсия существующего логотипа IT Shelter, без изменения бренда.

Сборка **не подписана Developer ID и не notarized**. PyInstaller/codesign создаёт
только ad-hoc подпись для целостности ARM-бинарников; это не подтверждение Apple.
Скачанный архив может быть заблокирован Gatekeeper. Сверьте источник/хеш и используйте
штатное разрешение открытия в настройках macOS только если доверяете сборке.
Не отключайте Gatekeeper и не удаляйте quarantine массово. Если политика Mac запрещает
неподписанное ПО, потребуется Developer ID/notarization от владельца сертификата.

Для подписанного выпуска: подпишите вложенные Mach-O/frameworks и затем весь bundle
Developer ID Application с hardened runtime и timestamp, выполните `notarytool submit`
для ZIP, `stapler staple` для `.app`, проверьте `codesign --verify --deep --strict` и
`spctl --assess`, затем заново создайте ZIP и SHA256. Учетные данные в репозиторий не
добавляются. Этот этап локально не проверен и автоматически не выполняется.

## Проверки

```sh
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
SHELTER_REQUIRE_GUI_TESTS=1 .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python launcher.py --self-test /tmp/shelter-source-selftest.json
```

Результаты реальной приёмки и ограничения записаны в [MACOS_VALIDATION.md](MACOS_VALIDATION.md).
