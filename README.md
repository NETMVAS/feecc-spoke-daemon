<h2 align="center">Feecc Spoke Daemon</h2>

<p align="center">
    <img alt="Workflow status" src="https://img.shields.io/github/workflow/status/NETMVAS/feecc-spoke-daemon/Python%20CI">
    <img alt="GitHub License" src="https://img.shields.io/github/license/NETMVAS/feecc-spoke-daemon">
    <img alt="Maintenance" src="https://img.shields.io/maintenance/yes/2021">
    <img alt="Black" src="https://img.shields.io/badge/code%20style-black-000000.svg">
</p>

> Daemon of the Spoke device of the Feecc QA system. With headless compatibility (automatic fallback).

<h2 align="center">Установка и запуск</h2>

> Для подробной инструкции обратитесь к документации Feecc.


> Предполагаем, что вы уже установили Raspbian (или другой Debian-based дистрибутив Linux) и Python3.

Установка Poetry:

`curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python3 -`

Установим зависимости, необходимые для сборки некоторых используемых модулей:

`sudo apt update && sudo apt install -y zlib1g libjpeg-dev`

Склонируем репозиторий:

`git clone https://github.com/NETMVAS/feecc-spoke-daemon.git`

Установим все необходимые зависимости и активируем виртуальное окружение:

`poetry install && poetry shell`

Поменяем конфигурацию Spoke, файлы которой находятся в `config.yaml`

Установим все компоненты Spoke:

`python install.py`

Перезагрузите устройство. Теперь Spoke готов к работе.

<h2 align="center">Тестирование приложения</h2>

Для запуска тестов выполните:

`pytest .`
