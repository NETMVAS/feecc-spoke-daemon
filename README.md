# Feecc-Spoke Daemon
Daemon of the Spoke device of the Feecc QA system. With headless compatibility (automatic fallback).

## Installation:

Install needed packages:

`sudo apt install -y python3 vim git`

Clone the repository:

`git clone https://github.com/NETMVAS/feecc-spoke-daemon`

Edit the configuration file:

```
cd feecc-spoke-daemon
vim config.yaml
```

Install Poetry:

`pip3 install poetry`

Run the installation script:

`sudo python install.py`
