from __future__ import annotations

import typing as tp

from PIL import ImageFont

from .ViewBase import Alert, AlertWithFooter, FONT_PATH, Icon, SMALL_FONT_SIZE

if tp.TYPE_CHECKING:
    from .Display import Display
    from PIL.ImageFont import FreeTypeFont


class FailedAuthorizationAlert(Alert):
    """display a message about failed authorization"""

    def __init__(self, context: Display) -> None:
        image_path: str = Icon.cross
        alert_message: str = "Авторизация\nне пройдена"
        super().__init__(context, image_path, alert_message)


class UnitNotFoundAlert(Alert):
    """display a message about being unable to find the unit"""

    def __init__(self, context: Display) -> None:
        image_path: str = Icon.cross
        alert_message: str = "Изделие\nне найдено"
        super().__init__(context, image_path, alert_message)


class SuccessfulLogOutAlert(Alert):
    """display a message about successful log out"""

    def __init__(self, context: Display) -> None:
        image_path: str = Icon.tick
        alert_message: str = "Сессия\nзавершена"
        super().__init__(context, image_path, alert_message)


class OperationStartedAlert(Alert):
    """display a message about starting operation"""

    def __init__(self, context: Display) -> None:
        image_path: str = Icon.tick
        alert_message: str = "Начало\nсборки"
        super().__init__(context, image_path, alert_message)


class OperationEndedAlert(Alert):
    """display a message about ending operation"""

    def __init__(self, context: Display) -> None:
        image_path: str = Icon.tick
        alert_message: str = "Сборка\nзавершена"
        super().__init__(context, image_path, alert_message)


class SuccessfulAuthorizationAlert(Alert):
    """display a message about successful authorization"""

    def __init__(self, context: Display) -> None:
        image_path: str = Icon.tick
        worker_position: str = context.associated_worker.position
        worker_short_name: str = context.associated_worker.short_name
        alert_message: str = f"Авторизован\n{worker_position}\n{worker_short_name}"
        font: FreeTypeFont = ImageFont.truetype(FONT_PATH, SMALL_FONT_SIZE)
        super().__init__(context, image_path, alert_message, font=font)


class AuthorizeFirstAlert(Alert):
    """display a message about authorization needed to scan barcode"""

    def __init__(self, context: Display) -> None:
        image_path: str = Icon.cross
        alert_message: str = "Необходима\nавторизация"
        super().__init__(context, image_path, alert_message)


class ScanBarcodeAlert(AlertWithFooter):
    """displays the barcode scan prompt"""

    def __init__(self, context: Display) -> None:
        image_path: str = Icon.barcode_scanner
        alert_message: str = "Сканируйте\nштрихкод"
        footer: str = f"Авторизован {context.associated_worker.short_name}"
        super().__init__(context, image_path, alert_message, footer, onscreen_time=0)


class ScanQrCodeAlert(AlertWithFooter):
    """displays the qr code scan prompt"""

    def __init__(self, context: Display) -> None:
        image_path: str = Icon.qrcode
        alert_message: str = "Сканируйте\nQR код"
        footer: str = f"Авторизован {context.associated_worker.short_name}"
        super().__init__(context, image_path, alert_message, footer, onscreen_time=0)


class IdMismatchAlert(Alert):
    """display a message about mismatched id (forbidden log out operation)"""

    def __init__(self, context: Display) -> None:
        image_path: str = Icon.cross
        alert_message: str = "Авторизован\nдругой\nсотрудник"
        super().__init__(context, image_path, alert_message)


class BackendUnreachableAlert(Alert):
    """display a message about broken backend connectivity"""

    def __init__(self, context: Display) -> None:
        image_path: str = Icon.warning
        alert_message: str = "Нет связи\nс сервером"
        super().__init__(context, image_path, alert_message)


class CannotCreateUnitAlert(Alert):
    """display a message about inability to create a new unit"""

    def __init__(self, context: Display) -> None:
        image_path: str = Icon.warning
        alert_message: str = "Не удалось\nсоздать изделие"
        super().__init__(context, image_path, alert_message)


class OperationForbiddenAlert(Alert):
    """display a message about forbidden state transition"""

    def __init__(self, context: Display) -> None:
        image_path: str = Icon.warning
        alert_message: str = "Операция\nне позволена"
        super().__init__(context, image_path, alert_message)


class InvalidQrAlert(Alert):
    """display a message warning that this is not a valid QR code"""

    def __init__(self, context: Display) -> None:
        image_path: str = Icon.warning
        alert_message: str = "Это не\nQR код"
        super().__init__(context, image_path, alert_message)


class ScanNextModuleQr(Alert):
    """display a message about needed to scan a QR code for the module"""

    def __init__(self, context: Display) -> None:
        image_path: str = Icon.qrcode
        alert_message: str = "Сканируйте\nследующий\nQR код"
        super().__init__(context, image_path, alert_message, onscreen_time=0)
