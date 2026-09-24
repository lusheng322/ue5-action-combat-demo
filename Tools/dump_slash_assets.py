# -*- coding: utf-8 -*-
"""
Slash 资产配置导出脚本（只读 / READ-ONLY）
=========================================

用途
----
C++ 源码可以被人直接阅读，但蓝图/蒙太奇是二进制资产，肉眼看不了"这个组件到底用什么碰撞预设、
蒙太奇用的是哪个 Slot、动画通知在什么时间点触发"。这个脚本把这些信息导出成 JSON，方便
排查问题（例如：敌人尸体能不能被武器打到、受击打断后状态机为什么卡死）。

它做三件事
----------
1. 遍历蓝图（默认只看 /Game/BluePrint 下的 BP_/ABP_/WBP_），导出**每个组件**的：
   Collision Enabled / Collision Profile / Object Type / 各通道响应 / Generate Overlap Events
   以及骨架网格、静态网格的资产路径。
2. 导出蓝图 CDO 上的简单类型默认值（伤害、半径、血量、速度等），用来核对蓝图有没有覆盖 C++ 默认值。
3. 导出动画蒙太奇的 **Slot 名称**、长度，以及动画通知（AnimNotify / AnimNotifyState）的名称与触发时间点。

它**不会**做什么
----------------
- 不修改任何 .uasset / .umap（脚本内没有任何 Save / SavePackage / SaveAsset 调用）。
- 不创建、不删除、不重命名资产。
- 只往 <项目>/Saved/SlashAssetDump/ 写一个 JSON 文件，并在日志里打印结论。

怎么运行（把路径换成你自己的引擎路径）
--------------------------------------
"C:\\1\\UE_5.6\\Engine\\Binaries\\Win64\\UnrealEditor-Cmd.exe" ^
  "D:\\UE_project\\Slash\\Slash.uproject" ^
  -run=pythonscript ^
  -script="D:\\UE_project\\Slash\\Tools\\dump_slash_assets.py" ^
  -unattended -nosplash -nopause -nullrhi

注意
----
- 用 UnrealEditor-Cmd 运行会**加载项目**（因此会在 Saved/Intermediate/DerivedDataCache 里
  产生日志与缓存文件，这是编辑器本来就会写的目录，通常在 .gitignore 里）。资产本身不会被改。
- 如果提示找不到 Python，请在编辑器 Plugins 里勾选 "Python Editor Script Plugin"
  （或命令行加 -EnablePlugins=PythonScriptPlugin）。
- 脚本需要项目已经编译出二进制（Binaries/Win64 存在）。
"""

import json
import os
import unreal

# ----------------------------------------------------------------------------
# 配置
# ----------------------------------------------------------------------------
OUT_DIR = os.path.join(unreal.Paths.project_dir(), "Saved", "SlashAssetDump")
OUT_FILE = os.path.join(OUT_DIR, "asset_dump.json")

# 只看这些目录（避免加载 Marketplace 里成千上万的资产，慢且没必要）
PATH_FILTERS = ["/Game/BluePrint"]

# 要导出的蒙太奇目录
MONTAGE_FILTERS = ["/Game/BluePrint"]

CHANNELS = [
    "ECC_Visibility", "ECC_Camera", "ECC_WorldStatic", "ECC_WorldDynamic",
    "ECC_Pawn", "ECC_PhysicsBody", "ECC_Vehicle", "ECC_Destructible",
]

# 重点核对的对象：名字里包含这些关键字的蓝图会在日志里单独打印碰撞结论
KEY_ACTORS = ["Enemy", "SlashCharacter", "Weapon", "BreakableActor"]

# 想额外导出的默认值属性名（Python 里是 snake_case）
PROP_HINTS = [
    "damage", "combat_radius", "attack_radius", "patrol_radius", "death_life_span",
    "health", "max_health", "stamina", "max_stamina", "gold", "souls", "dodge_cost",
    "attack_min", "attack_max", "patrolling_speed", "chasing_speed", "sight_radius",
    "peripheral_vision_angle", "patrol_wait_min", "patrol_wait_max",
    "amplitude", "time_constant", "box_trace_extent", "show_box_debug",
    "collision_profile_name", "generate_overlap_events",
]


def safe(fn, default=None):
    """任何属性读取失败都不要中断整个导出。"""
    try:
        return fn()
    except Exception:
        return default


def asset_class_name(path):
    data = safe(lambda: unreal.EditorAssetLibrary.find_asset_data(path))
    if data is None:
        return "Unknown"
    name = safe(lambda: data.asset_class_path.asset_name)
    if name:
        return str(name)
    return str(safe(lambda: data.asset_class, "Unknown"))


def dump_component(comp):
    info = {
        "name": safe(lambda: comp.get_name()),
        "class": safe(lambda: comp.get_class().get_name()),
        # 这三项是核心：碰撞是否开启、用的什么预设、是否产生重叠事件
        "collision_enabled": str(safe(lambda: comp.get_collision_enabled(), "n/a")),
        "collision_profile_name": str(safe(lambda: comp.get_editor_property("collision_profile_name"), "n/a")),
        "collision_object_type": str(safe(lambda: comp.get_collision_object_type(), "n/a")),
        "generate_overlap_events": safe(lambda: bool(comp.get_editor_property("generate_overlap_events"))),
        "responses": {},
    }
    for ch in CHANNELS:
        enum_val = safe(lambda ch=ch: getattr(unreal.CollisionChannel, ch))
        if enum_val is None:
            continue
        info["responses"][ch] = str(safe(lambda ev=enum_val: comp.get_collision_response_to_channel(ev), "n/a"))

    sm = safe(lambda: comp.get_editor_property("skeletal_mesh"))
    if sm is not None:
        info["skeletal_mesh"] = safe(lambda: sm.get_path_name())
    st = safe(lambda: comp.get_editor_property("static_mesh"))
    if st is not None:
        info["static_mesh"] = safe(lambda: st.get_path_name())
    return info


def dump_defaults(cdo):
    """导出 CDO 上的简单类型默认值（只记录能读出来的）。"""
    out = {}
    simple_types = ("bool", "int", "float", "str", "Name", "EnumType", "Vector", "Rotator", "LinearColor")

    names = set()
    # 1) 指定关心的属性
    names.update(PROP_HINTS)
    # 2) 兜底：扫描对象上所有小写开头的名字（UE Python 属性都是 snake_case）
    names.update(n for n in dir(cdo) if n and n[0].islower() and not n.startswith("_"))

    for name in sorted(names):
        value = safe(lambda n=name: cdo.get_editor_property(n), None)
        if value is None:
            continue
        if type(value).__name__ in simple_types:
            out[name] = str(value)
    return out


def dump_montage(montage):
    info = {
        "path": safe(lambda: montage.get_path_name()),
        "length": safe(lambda: float(montage.get_editor_property("sequence_length"))),
        "slots": [],
        "notifies": [],
    }
    tracks = safe(lambda: montage.get_editor_property("slot_anim_tracks")) or []
    for track in tracks:
        slot = safe(lambda t=track: t.get_editor_property("slot_name"))
        if slot is not None:
            info["slots"].append(str(slot))

    notifies = safe(lambda: montage.get_editor_property("notifies")) or []
    for n in notifies:
        entry = {
            "notify_name": str(safe(lambda n=n: n.get_editor_property("notify_name"), "")),
            "time": safe(lambda n=n: float(n.get_editor_property("trigger_time"))),
            "duration": safe(lambda n=n: float(n.get_editor_property("duration"))),
            "notify_class": str(safe(
                lambda n=n: n.get_editor_property("notify").get_class().get_name()
                if n.get_editor_property("notify") else "", "")),
        }
        info["notifies"].append(entry)
    return info


def collision_verdict(bp_path, bp_entry):
    """打印结论：这个蓝图的骨骼网格能不能被 Visibility 射线打到 / 能不能产生重叠。"""
    lines = []
    for comp in bp_entry.get("components", []):
        if comp.get("class") != "SkeletalMeshComponent":
            continue
        enabled = comp.get("collision_enabled", "n/a")
        vis = comp.get("responses", {}).get("ECC_Visibility", "n/a")
        overlap = comp.get("generate_overlap_events")
        lines.append(
            "    [%s] CollisionEnabled=%s | Visibility=%s | GenerateOverlapEvents=%s | Profile=%s"
            % (comp.get("name"), enabled, vis, overlap, comp.get("collision_profile_name"))
        )
        hittable = ("NoCollision" not in str(enabled)) and ("Block" in str(vis))
        lines.append("    => 可被武器 Visibility 射线命中: %s" % ("是" if hittable else "否"))
    return lines


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    all_assets = safe(lambda: unreal.EditorAssetLibrary.list_assets("/Game", recursive=True, include_folder=False)) or []
    result = {
        "project_dir": unreal.Paths.project_dir(),
        "engine_version": safe(lambda: unreal.SystemLibrary.get_engine_version()),
        "total_assets_scanned": len(all_assets),
        "blueprints": {},
        "montages": {},
    }

    bp_paths = [p for p in all_assets
                if any(p.startswith(f) for f in PATH_FILTERS) and asset_class_name(p) in ("Blueprint", "WidgetBlueprint")]
    montage_paths = [p for p in all_assets
                     if any(p.startswith(f) for f in MONTAGE_FILTERS) and asset_class_name(p) == "AnimMontage"]

    unreal.log("[SlashDump] 蓝图 %d 个，蒙太奇 %d 个" % (len(bp_paths), len(montage_paths)))

    # ---- 蓝图 ----
    for path in bp_paths:
        bp = safe(lambda p=path: unreal.EditorAssetLibrary.load_asset(p))
        if bp is None:
            continue
        gen_class = safe(lambda: bp.generated_class())
        cdo = None
        if gen_class is not None:
            cdo = safe(lambda: unreal.get_default_object(gen_class))
            if cdo is None:
                cdo = safe(lambda: gen_class.get_default_object())
        if cdo is None:
            continue

        entry = {
            "path": path,
            "native_class": safe(lambda: cdo.get_class().get_name()),
            "components": [dump_component(c) for c in
                           (safe(lambda: cdo.get_components_by_class(unreal.PrimitiveComponent)) or [])],
            "defaults": dump_defaults(cdo),
        }
        result["blueprints"][path] = entry

        if any(k.lower() in path.lower() for k in KEY_ACTORS):
            unreal.log("[SlashDump] ===== %s (native: %s) =====" % (path, entry["native_class"]))
            for line in collision_verdict(path, entry):
                unreal.log(line)

    # ---- 蒙太奇 ----
    for path in montage_paths:
        montage = safe(lambda p=path: unreal.EditorAssetLibrary.load_asset(p))
        if montage is None:
            continue
        result["montages"][path] = dump_montage(montage)
        info = result["montages"][path]
        unreal.log("[SlashDump] Montage %s | Slot=%s | Notifies=%s"
                   % (os.path.basename(path), info.get("slots"), [n.get("notify_name") or n.get("notify_class")
                                                                  for n in info.get("notifies", [])]))

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    unreal.log("[SlashDump] 导出完成：%s" % OUT_FILE)
    unreal.log("[SlashDump] 本脚本为只读脚本，未修改任何资产。")


main()
