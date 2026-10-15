"""
اكتشاف أجهزة الصوت — الميكروفونات ومصادر صوت النظام (System Audio Loopback).

القرار التصميمي المهم (البند 5 في المواصفات: "لا تستخدم حلاً وهمياً"):
FFmpeg على Windows عبر dshow لا يوفر التقاط صوت النظام (loopback) بشكل
مباشر وموثوق (يعتمد على "Stereo Mix" غير المتوفر على كثير من الأجهزة
الحديثة). الحل الصحيح المستخدم هنا هو مكتبة `soundcard`، التي تلتقط:
  - على Windows: عبر WASAPI loopback (وهي نفس الآلية التي تستخدمها
    برامج احترافية مثل OBS لالتقاط صوت النظام).
  - على Linux: عبر PulseAudio monitor sources (لأغراض التطوير/الاختبار
    في هذه البيئة).
FFmpeg يبقى مسؤولاً فقط عن التقاط الفيديو والترميز والدمج النهائي،
تماشياً مع "اجعل FFmpeg مكوناً خارجياً واضحاً، ولا تُعِد اختراع محرك
الترميز داخل بايثون" — هنا نحن لا نُعيد اختراع الترميز، فقط الالتقاط
الخام (raw PCM) الذي لا بديل حقيقي عنه عبر FFmpeg نفسه على Windows.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from app.utils.logger import get_logger

logger = get_logger(__name__)

# soundcard على بعض الأنظمة يحتاج sys.argv بعنصر ثانٍ عند تهيئته لأول مرة
if len(sys.argv) < 2:
    sys.argv = sys.argv + ["screen_recorder"]


@dataclass(frozen=True)
class AudioDeviceInfo:
    device_id: str
    name: str
    is_loopback: bool  # True = يمثل مصدر صوت النظام (System Audio)


def list_microphones() -> list[AudioDeviceInfo]:
    """يعيد قائمة الميكروفونات الحقيقية (وليست أجهزة loopback)."""
    try:
        import soundcard as sc
    except Exception:  # noqa: BLE001 — يشمل ImportError وأخطاء اتصال الـ backend الصوتي (مثل عدم عمل pulseaudio)
        logger.error("تعذر تهيئة نظام الصوت — لا يمكن اكتشاف أجهزة الصوت")
        return []

    try:
        mics = sc.all_microphones(include_loopback=False)
        result = [AudioDeviceInfo(m.id, m.name, is_loopback=False) for m in mics]
        logger.info("تم اكتشاف %d ميكروفون", len(result))
        return result
    except Exception:
        logger.exception("فشل اكتشاف الميكروفونات")
        return []


def list_system_audio_devices() -> list[AudioDeviceInfo]:
    """يعيد قائمة مصادر صوت النظام (Loopback) المتاحة للالتقاط."""
    try:
        import soundcard as sc
    except Exception:  # noqa: BLE001
        logger.error("تعذر تهيئة نظام الصوت — لا يمكن اكتشاف صوت النظام")
        return []

    try:
        all_devices = sc.all_microphones(include_loopback=True)
        loopback_only = [d for d in all_devices if getattr(d, "isloopback", False)]
        result = [AudioDeviceInfo(d.id, d.name, is_loopback=True) for d in loopback_only]
        logger.info("تم اكتشاف %d مصدر لصوت النظام", len(result))
        return result
    except Exception:
        logger.exception("فشل اكتشاف مصادر صوت النظام")
        return []


def get_default_microphone_id() -> str | None:
    try:
        import soundcard as sc
        mic = sc.default_microphone()
        return mic.id if mic else None
    except Exception:
        logger.exception("فشل تحديد الميكروفون الافتراضي")
        return None
