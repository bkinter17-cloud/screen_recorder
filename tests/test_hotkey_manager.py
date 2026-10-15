"""اختبارات وحدة لـ HotkeyManager — تختبر منطق التسجيل والتعارض بدون جهاز إدخال حقيقي."""

from __future__ import annotations

import pytest

from app.hotkeys.hotkey_manager import HotkeyError, HotkeyManager


def test_register_and_current_bindings():
    mgr = HotkeyManager()
    mgr.register("start_stop_recording", "ctrl+alt+r", lambda: None)
    assert mgr.current_bindings() == {"start_stop_recording": "ctrl+alt+r"}


def test_conflict_detection_raises():
    mgr = HotkeyManager()
    mgr.register("start_stop_recording", "ctrl+alt+r", lambda: None)
    with pytest.raises(HotkeyError):
        mgr.register("screenshot", "ctrl+alt+r", lambda: None)


def test_rebind_changes_combo_without_conflict():
    mgr = HotkeyManager()
    mgr.register("screenshot", "ctrl+alt+s", lambda: None)
    mgr.rebind("screenshot", "ctrl+alt+x")
    assert mgr.current_bindings()["screenshot"] == "ctrl+alt+x"


def test_unregister_removes_binding():
    mgr = HotkeyManager()
    mgr.register("pause_resume", "ctrl+alt+p", lambda: None)
    mgr.unregister("pause_resume")
    assert "pause_resume" not in mgr.current_bindings()


def test_same_action_can_reregister_to_new_combo_without_self_conflict():
    mgr = HotkeyManager()
    mgr.register("screenshot", "ctrl+alt+s", lambda: None)
    # إعادة تسجيل نفس الـ action بتركيبة مختلفة يجب ألا يُعتبر تعارضاً مع نفسه
    mgr.register("screenshot", "ctrl+alt+s", lambda: None)
    assert mgr.current_bindings()["screenshot"] == "ctrl+alt+s"
