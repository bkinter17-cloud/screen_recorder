"""
مدير الاختصارات العامة (Global Hotkeys) — Phase 6.

يعتمد على مكتبة `keyboard`، وهي المكتبة الأكثر موثوقية لالتقاط اختصارات
تعمل حتى عندما تكون نافذة البرنامج غير نشطة على Windows (وهو المطلوب
تحديداً في المواصفات، البند 11).

ملاحظة بيئة التطوير: هذه المكتبة تحتاج الوصول إلى أجهزة الإدخال
(`/dev/input` على Linux، أو صلاحيات مدير على بعض الإعدادات). في بيئة
الحاويات المستخدمة للتطوير/الاختبار هنا لا يوجد جهاز إدخال فعلي، لذلك
لا يمكن اختبار الالتقاط الفعلي لضغطة مفتاح حقيقية، لكن API التسجيل/الإلغاء
وكشف التعارضات مُختبَران بالكامل دون الحاجة لجهاز إدخال حقيقي.
على Windows (البيئة المستهدفة فعلياً) تعمل هذه المكتبة بشكل موثوق.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.utils.logger import get_logger

logger = get_logger(__name__)


class HotkeyError(Exception):
    pass


@dataclass
class HotkeyBinding:
    action: str  # مثال: "start_stop_recording"
    combo: str  # مثال: "ctrl+alt+r"
    callback: Callable[[], None]


class HotkeyManager:
    """
    يحافظ على تسجيل مركزي لكل الاختصارات النشطة، ويمنع تعارض اختصارين على
    نفس التركيبة (البند 11: "تعامل مع تعارض الاختصارات بطريقة صحيحة").
    """

    def __init__(self) -> None:
        self._bindings: dict[str, HotkeyBinding] = {}  # action -> binding
        self._registered_handles: dict[str, object] = {}  # action -> keyboard hook handle
        self._backend_available = self._check_backend()

    @staticmethod
    def _check_backend() -> bool:
        try:
            import keyboard  # noqa: F401
            return True
        except ImportError:
            logger.error("مكتبة keyboard غير مثبتة — لن تعمل الاختصارات العامة")
            return False

    def find_conflict(self, combo: str, exclude_action: str | None = None) -> str | None:
        """يعيد اسم الـ action الذي يستخدم نفس التركيبة حالياً، إن وُجد."""
        normalized = combo.strip().lower()
        for action, binding in self._bindings.items():
            if action == exclude_action:
                continue
            if binding.combo.strip().lower() == normalized:
                return action
        return None

    def register(self, action: str, combo: str, callback: Callable[[], None]) -> None:
        """
        يسجل اختصاراً جديداً. إذا كانت نفس التركيبة مستخدمة بالفعل لعملية
        أخرى، تُرفض العملية برسالة واضحة بدل الكتابة فوقها بصمت.
        """
        conflict = self.find_conflict(combo, exclude_action=action)
        if conflict:
            raise HotkeyError(
                f"التركيبة '{combo}' مستخدمة بالفعل للعملية '{conflict}'. "
                "الرجاء اختيار اختصار مختلف."
            )

        # إذا كان لهذا الـ action اختصار سابق، ألغِه أولاً قبل التسجيل الجديد
        self.unregister(action)

        if self._backend_available:
            try:
                import keyboard
                handle = keyboard.add_hotkey(combo, callback)
                self._registered_handles[action] = handle
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "تعذر تسجيل الاختصار الفعلي '%s' لـ %s (%s) — "
                    "سيُحفظ في الإعدادات لكنه لن يعمل في هذه البيئة.",
                    combo, action, exc,
                )
        else:
            logger.warning("لم يتم تسجيل اختصار فعلي (backend غير متاح): %s", combo)

        self._bindings[action] = HotkeyBinding(action, combo, callback)
        logger.info("تم تسجيل اختصار: %s -> %s", action, combo)

    def unregister(self, action: str) -> None:
        if action not in self._bindings:
            return
        handle = self._registered_handles.pop(action, None)
        if handle is not None and self._backend_available:
            try:
                import keyboard
                keyboard.remove_hotkey(handle)
            except (KeyError, ValueError):
                pass
        self._bindings.pop(action, None)
        logger.info("تم إلغاء اختصار: %s", action)

    def rebind(self, action: str, new_combo: str) -> None:
        """يُستخدم من صفحة Settings لتغيير اختصار موجود."""
        if action not in self._bindings:
            raise HotkeyError(f"لا يوجد اختصار مسجل باسم: {action}")
        callback = self._bindings[action].callback
        self.register(action, new_combo, callback)

    def current_bindings(self) -> dict[str, str]:
        return {action: b.combo for action, b in self._bindings.items()}

    def unregister_all(self) -> None:
        for action in list(self._bindings.keys()):
            self.unregister(action)
