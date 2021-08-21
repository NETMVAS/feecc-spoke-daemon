<p align="center">
    <img src="https://netmvas.github.io/icon.png">
</p>

<h2 align="center">Feecc Spoke Daemon</h2>

<p align="center">
    <img alt="Workflow status" src="https://img.shields.io/github/workflow/status/NETMVAS/feecc-spoke-daemon/Python%20CI">
    <img alt="GitHub License" src="https://img.shields.io/github/license/NETMVAS/feecc-spoke-daemon">
    <img alt="Maintenance" src="https://img.shields.io/maintenance/yes/2021">
    <img alt="Black" src="https://img.shields.io/badge/code%20style-black-000000.svg">
</p>

> Daemon of the Spoke device of the Feecc QA system. With headless compatibility (automatic fallback).

## Сборка Spoke

Для сборки вам понадобится:

- Raspberry Pi Zero W
- RFID Reader
- Barcode Reader (поддерживающий EAN13, будет достаточно даже 1D)
- MicroSD-Карта (Рекомендуется 10 class) от 16 ГБ
- [2.13inch e-Paper HAT](https://www.chipdip.ru/product/2.13inch-e-paper-hat-c) (обязательно жёлто-черная)
- [USB HUB HAT](https://www.chipdip.ru/product/usb-hub-hat)
- [PCB Receptacle](https://www.chipdip.ru/product/m20-6102045) ("гребенка")
- [PCB Receptacle](https://www.chipdip.ru/product/pld-40r-ds1022-2x20) ("угловая гребенка, тип 1")
- Корпус (опционально)

### Пример собранного Spoke

<Картинки>

### Корпус Spoke (Опционально)

Файл для печати на 3D принтере: тык

Для сборки Spoke в корпус понадобятся 2 магнита и 4 болта (M3X12)

## Установка ПО для Spoke

### Установка Raspbian

- Загрузить [Raspberry Pi Imager](https://www.raspberrypi.org/software/operating-systems/)
- Записать на MicroSD-карту Raspberry Pi OS Lite
- Заново вставить MicroSD-карту и в корне создать файл **ssh** для доступа по SSH
- Для включения WIFI нужно создать файл **wpa_supplicant.conf** со следующим содержимым:

```json
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=RU

network={
 ssid="SSID вашей сети"
 psk="Пароль вашей сети"
}
```

- Установите MicroSD-карту в Raspberry Pi Zero W и включите устройство, далее подключитесь по ssh к Pi (пароль по умолчанию `raspberry`)

```bash
$ ssh pi@<ip вашего устройства>
```

- Измените hostname устройства

```bash
$ sudo hostnamectl set-hostname feecc000003
```

- Склонируйте репозиторий

```bash
$ git clone https://github.com/NETMVAS/feecc-spoke-daemon
```

- Перейдите в директорию

```bash
$ cd feecc-spoke-daemon
```

- Установите Poetry

```bash
$ curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python3 -
```

- Обновите систему и установите необходимые зависимости для сборки пакетов

```bash
$ sudo apt install tree python3-dev python3-distutils libjpeg-dev git vim python3-pip -y
```

- Установим все необходимые зависимости для запуска проекта

```bash
$ poetry install --nodev && poetry shell
```

- Измените конфигурацию Spoke которая находится в файле `config.yaml`
- Установите Feecc Spoke Daemon

```bash
$ python3 install.py
```

- [Активируйте SPI-интерфейс](https://www.raspberrypi-spy.co.uk/2014/08/enabling-the-spi-interface-on-the-raspberry-pi/)
- Установите EventToInternet

```bash
$ cd ~ && git clone https://github.com/NETMVAS/feecc-hid-reader-daemon && cd feecc-hid-reader-daemon && bash install.sh $$ cd ..
```

- Перезагрузите устройство
- Подключите RFID и Barcode ридеры
