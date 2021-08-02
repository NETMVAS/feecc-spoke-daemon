from __future__ import annotations

import typing as tp

from PIL import ImageFont

from .ViewBase import Alert, FONT_PATH, Icon, SMALL_FONT_SIZE

if tp.TYPE_CHECKING:
    from PIL.ImageFont import FreeTypeFont
    from Display import Display


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
        worker_short_name: str = context.associated_worker.short_name()
        alert_message: str = f"Авторизован\n{worker_position}\n{worker_short_name}"
        font: FreeTypeFont = ImageFont.truetype(FONT_PATH, SMALL_FONT_SIZE)
        super().__init__(context, image_path, alert_message, font)


class AuthorizeFirstAlert(Alert):
    """display a message about authorization needed to scan barcode"""

    def __init__(self, context: Display) -> None:
        image_path: str = Icon.cross
        alert_message: str = "Необходима\nавторизация"
        super().__init__(context, image_path, alert_message)


class BackendUnreachableAlert(Alert):
    """display a message about broken backend connectivity"""

    def __init__(self, context: Display) -> None:
        image_path: str = Icon.warning
        alert_message: str = "Нет связи\nс сервером"
        super().__init__(context, image_path, alert_message)