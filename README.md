# Feecc-Spoke Daemon
Daemon of the Spoke device of the Feecc QA system. With headless compatibility (automatic fallback).

---

## Installation:

Install needed packages:

`$ sudo apt install -y python3 vim git zlib libjpeg`

Clone the repository:

`$ git clone https://github.com/NETMVAS/feecc-spoke-daemon.git`

Edit the configuration file:

```
$ cd feecc-spoke-daemon
$ vim config.yaml
```

Install Poetry:

`$ curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python3 -`

Run the installation script:

`$ sudo python3 install.py`
