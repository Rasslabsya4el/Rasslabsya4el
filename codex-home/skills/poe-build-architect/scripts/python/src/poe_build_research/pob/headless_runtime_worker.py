"""Child-process worker that boots pinned PoB through the local headless wrapper."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from .proof_blank_state import EXPECTED_GEAR_SLOT_ORDER
from .proof_boots_item import EXPECTED_BOOTS_SLOT, EXPECTED_EXPLICIT_AFFIX

_CANONICAL_BLANK_CLASS_ID = 3
_CANONICAL_BLANK_ASCENDANCY_ID = 0
_CANONICAL_BLANK_SECONDARY_ASCENDANCY_ID = 0
_CANONICAL_ITEM_SET_ID = "itemset.main"
_CANONICAL_SPEC_ID = "spec.main"
_CANONICAL_SKILLS_ID = "skills.main"
_CANONICAL_CONFIG_ID = "config.main"
_SUPPORTED_BANDIT_CHOICES = frozenset({"None", "Oak", "Kraityn", "Alira"})
_SUPPORTED_MAJOR_PANTHEONS = frozenset({"None", "TheBrineKing", "Lunaris", "Solaris", "Arakaali"})
_SUPPORTED_MINOR_PANTHEONS = frozenset(
    {"None", "Gruthkul", "Yugul", "Abberath", "Tukohama", "Garukhan", "Ralakesh", "Ryslatha", "Shakari"}
)
_SUPPORTED_ENEMY_BOSS_STATES = frozenset({"None", "Boss", "Pinnacle", "Uber"})
_CONFIG_DEFAULT_INPUTS: dict[str, str | bool | int | None] = {
    "bandit": "None",
    "pantheonMajorGod": "None",
    "pantheonMinorGod": "None",
    "enemyIsBoss": "Pinnacle",
    "buffOnslaught": False,
    "buffFortification": False,
    "conditionUsingFlask": False,
    "conditionEnemyShocked": False,
    "conditionEnemyIgnited": False,
    "conditionShockEffect": None,
}
_CONFIG_ENABLED_CONDITION_IDS = {
    "buffOnslaught": "buff.onslaught",
    "buffFortification": "buff.fortification",
    "conditionUsingFlask": "combat.using_flask",
    "conditionEnemyShocked": "enemy.shocked",
    "conditionEnemyIgnited": "enemy.ignited",
}
_CONFIG_CUSTOM_VALUE_KEYS = {
    "enemyIsBoss": "enemy_is_boss",
    "conditionEnemyIgnited": "enemy_ignited",
    "conditionShockEffect": "enemy_shock_effect",
}
_SUPPORTED_GEM_LEVEL_MODES = frozenset(
    {
        "normalMaximum",
        "corruptedMaximum",
        "awakenedMaximum",
        "characterLevel",
        "levelOne",
    }
)
_SUPPORTED_SUPPORT_GEM_TYPES = frozenset({"ALL", "NORMAL", "EXCEPTIONAL"})
_SUPPORTED_SORT_GEM_FIELDS = frozenset(
    {
        "FullDPS",
        "CombinedDPS",
        "TotalDPS",
        "AverageDamage",
        "TotalDot",
        "BleedDPS",
        "IgniteDPS",
        "TotalPoisonDPS",
        "TotalEHP",
    }
)
_POB_HEADLESS_NODE_POWER_REPORT_SCHEMA_VERSION = "1.0.0"
_POB_HEADLESS_NODE_POWER_REPORT_RECORD_KIND = "pob_headless_node_power_report"
_POB_NATIVE_NODE_POWER_REPORT_SOURCE_KIND = "pob_native_node_power_report"
_POB_NATIVE_NODE_POWER_REPORT_SUPPORTED_PATH = "pob_native_node_power_report_hint_v1"
_DEFAULT_NODE_POWER_METRIC_STAT = "FullDPS"
_DEFAULT_NODE_POWER_METRIC_LANE = "baseline"
_DEFAULT_NODE_POWER_MAX_DEPTH = 5
_DEFAULT_NODE_POWER_MAX_ROWS = 200
_NODE_POWER_DEFENSE_STATS = frozenset(
    {
        "Life",
        "LifeRegen",
        "LifeLeechRate",
        "Armour",
        "Evasion",
        "EnergyShield",
        "EnergyShieldRecoveryCap",
        "EnergyShieldRegen",
        "EnergyShieldLeechRate",
        "Mana",
        "ManaRegen",
        "ManaLeechRate",
        "Ward",
        "BlockChance",
        "SpellBlockChance",
        "SpellSuppressionChance",
        "MeleeAvoidChance",
        "SpellAvoidChance",
        "ProjectileAvoidChance",
        "TotalEHP",
        "SecondMinimalMaximumHitTaken",
        "PhysicalTakenHit",
        "LightningTakenHit",
        "ColdTakenHit",
        "FireTakenHit",
        "ChaosTakenHit",
    }
)
_CALC_DISPLAY_FAMILY_ORDER = (
    "offense",
    "requirements",
    "defense",
    "resources",
    "resistances",
    "movement",
    "utility",
    "other",
)
_CALC_DISPLAY_FAMILY_BY_STAT = {
    "ActiveMinionLimit": "utility",
    "Str": "requirements",
    "ReqStr": "requirements",
    "Dex": "requirements",
    "ReqDex": "requirements",
    "Int": "requirements",
    "ReqInt": "requirements",
    "Omni": "requirements",
    "ReqOmni": "requirements",
    "Devotion": "requirements",
    "TotalEHP": "defense",
    "PhysicalMaximumHitTaken": "defense",
    "FireMaximumHitTaken": "defense",
    "ColdMaximumHitTaken": "defense",
    "LightningMaximumHitTaken": "defense",
    "ChaosMaximumHitTaken": "defense",
    "MainHand": "defense",
    "OffHand": "defense",
    "Evasion": "defense",
    "MeleeEvadeChance": "defense",
    "ProjectileEvadeChance": "defense",
    "Armour": "defense",
    "PhysicalDamageReduction": "defense",
    "EffectiveBlockChance": "defense",
    "EffectiveSpellBlockChance": "defense",
    "AttackDodgeChance": "defense",
    "SpellDodgeChance": "defense",
    "EffectiveSpellSuppressionChance": "defense",
    "Life": "resources",
    "LifeUnreserved": "resources",
    "LifeRecoverable": "resources",
    "LifeUnreservedPercent": "resources",
    "LifeRegenRecovery": "resources",
    "LifeRecharge": "resources",
    "LifeLeechGainRate": "resources",
    "LifeLeechGainPerHit": "resources",
    "Mana": "resources",
    "ManaUnreserved": "resources",
    "ManaUnreservedPercent": "resources",
    "ManaRegenRecovery": "resources",
    "ManaLeechGainRate": "resources",
    "ManaLeechGainPerHit": "resources",
    "EnergyShield": "resources",
    "EnergyShieldRecoveryCap": "resources",
    "EnergyShieldRegenRecovery": "resources",
    "EnergyShieldLeechGainRate": "resources",
    "EnergyShieldLeechGainPerHit": "resources",
    "Ward": "resources",
    "Rage": "resources",
    "RageRegenRecovery": "resources",
    "TotalBuildDegen": "resources",
    "TotalNetRegen": "resources",
    "NetLifeRegen": "resources",
    "NetManaRegen": "resources",
    "NetEnergyShieldRegen": "resources",
    "FireResist": "resistances",
    "FireResistOverCap": "resistances",
    "ColdResist": "resistances",
    "ColdResistOverCap": "resistances",
    "LightningResist": "resistances",
    "LightningResistOverCap": "resistances",
    "ChaosResist": "resistances",
    "ChaosResistOverCap": "resistances",
    "EffectiveMovementSpeedMod": "movement",
    "AreaOfEffectRadiusMetres": "utility",
    "BrandAttachmentRangeMetre": "utility",
    "BrandTicks": "utility",
    "Cooldown": "utility",
    "SealCooldown": "utility",
    "SealMax": "utility",
    "TimeMaxSeals": "utility",
}
_PROOF_RUNTIME_ITEM_RAW = (
    "Rarity: Rare\n"
    "Run Spur\n"
    "Rawhide Boots\n"
    "--------\n"
    "30% increased Movement Speed"
)


class WorkerContractError(RuntimeError):
    """Raised when the headless worker cannot satisfy a command."""

    def __init__(self, failure_state: str, message: str) -> None:
        super().__init__(message)
        self.failure_state = failure_state


def _lua_long_string(value: str) -> str:
    delimiter = "="
    while f"]{delimiter}]" in value:
        delimiter += "="
    return f"[{delimiter}[{value}]{delimiter}]"


def _lua_json_literal(payload: Any) -> str:
    try:
        return _lua_long_string(json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True))
    except (TypeError, ValueError) as exc:
        raise WorkerContractError("runtime_protocol_failed", "Lua JSON literal payload must be JSON-serializable.") from exc


def _slot_order_literal() -> str:
    return "{" + ", ".join(_lua_long_string(slot) for slot in EXPECTED_GEAR_SLOT_ORDER) + "}"


def _require_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkerContractError("runtime_protocol_failed", f"{field_name} must be an object.")
    return dict(value)


def _require_array(value: Any, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise WorkerContractError("runtime_protocol_failed", f"{field_name} must be an array.")
    return list(value)


def _require_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise WorkerContractError("runtime_protocol_failed", f"{field_name} must be a boolean.")
    return value


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkerContractError("runtime_protocol_failed", f"{field_name} must be a non-empty string.")
    return value.strip()


def _require_optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty_string(value, field_name)


def _require_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise WorkerContractError("runtime_protocol_failed", f"{field_name} must be an integer.")
    return value


def _normalize_skill_set_index(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise WorkerContractError("runtime_protocol_failed", f"{field_name} must reference skills.main or skills.<positive-index>.")
    if isinstance(value, int):
        index = value
    elif isinstance(value, str):
        raw_value = value.strip()
        if raw_value == _CANONICAL_SKILLS_ID:
            return 1
        match = re.fullmatch(r"skills\.(\d+)", raw_value)
        if match is None:
            raise WorkerContractError(
                "runtime_protocol_failed",
                f"{field_name} must reference skills.main or skills.<positive-index>.",
            )
        index = int(match.group(1))
    else:
        raise WorkerContractError(
            "runtime_protocol_failed",
            f"{field_name} must reference skills.main or skills.<positive-index>.",
        )
    if index < 1:
        raise WorkerContractError(
            "runtime_protocol_failed",
            f"{field_name} must reference skills.main or skills.<positive-index>.",
        )
    return index


def _normalize_skill_set_id(index: int) -> str:
    return _CANONICAL_SKILLS_ID if index == 1 else f"skills.{index}"


def _normalize_item_set_index(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise WorkerContractError("runtime_protocol_failed", f"{field_name} must reference itemset.main or itemset.<positive-index>.")
    if isinstance(value, int):
        index = value
    elif isinstance(value, str):
        raw_value = value.strip()
        if raw_value == _CANONICAL_ITEM_SET_ID:
            return 1
        match = re.fullmatch(r"itemset\.(\d+)", raw_value)
        if match is None:
            raise WorkerContractError(
                "runtime_protocol_failed",
                f"{field_name} must reference itemset.main or itemset.<positive-index>.",
            )
        index = int(match.group(1))
    else:
        raise WorkerContractError(
            "runtime_protocol_failed",
            f"{field_name} must reference itemset.main or itemset.<positive-index>.",
        )
    if index < 1:
        raise WorkerContractError(
            "runtime_protocol_failed",
            f"{field_name} must reference itemset.main or itemset.<positive-index>.",
        )
    return index


def _normalize_config_set_index(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise WorkerContractError("runtime_protocol_failed", f"{field_name} must reference config.main or config.<positive-index>.")
    if isinstance(value, int):
        index = value
    elif isinstance(value, str):
        raw_value = value.strip()
        if raw_value == _CANONICAL_CONFIG_ID:
            return 1
        match = re.fullmatch(r"config\.(\d+)", raw_value)
        if match is None:
            raise WorkerContractError(
                "runtime_protocol_failed",
                f"{field_name} must reference config.main or config.<positive-index>.",
            )
        index = int(match.group(1))
    else:
        raise WorkerContractError(
            "runtime_protocol_failed",
            f"{field_name} must reference config.main or config.<positive-index>.",
        )
    if index < 1:
        raise WorkerContractError(
            "runtime_protocol_failed",
            f"{field_name} must reference config.main or config.<positive-index>.",
        )
    return index


def _normalize_config_set_id(index: int) -> str:
    return _CANONICAL_CONFIG_ID if index == 1 else f"config.{index}"


def _normalize_socket_group_index(
    value: Any,
    *,
    field_name: str,
    expected_skill_set_id: str,
) -> int:
    if isinstance(value, bool):
        raise WorkerContractError("runtime_protocol_failed", f"{field_name} must reference {expected_skill_set_id}.socket_group.<positive-index>.")
    if isinstance(value, int):
        index = value
    elif isinstance(value, str):
        raw_value = value.strip()
        if raw_value.isdigit():
            index = int(raw_value)
        else:
            match = re.fullmatch(r"(skills\.(?:main|\d+))\.socket_group\.(\d+)", raw_value)
            if match is None or match.group(1) != expected_skill_set_id:
                raise WorkerContractError(
                    "runtime_protocol_failed",
                    f"{field_name} must reference {expected_skill_set_id}.socket_group.<positive-index>.",
                )
            index = int(match.group(2))
    else:
        raise WorkerContractError(
            "runtime_protocol_failed",
            f"{field_name} must reference {expected_skill_set_id}.socket_group.<positive-index>.",
        )
    if index < 1:
        raise WorkerContractError(
            "runtime_protocol_failed",
            f"{field_name} must reference {expected_skill_set_id}.socket_group.<positive-index>.",
        )
    return index


def _bool_xml(value: bool) -> str:
    return "true" if value else "false"


def _set_optional_attr(node: ElementTree.Element, key: str, value: Any) -> None:
    if value is None:
        node.attrib.pop(key, None)
        return
    node.set(key, str(value))


def _serialize_xml(root: ElementTree.Element) -> str:
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8")


def _json_clone(payload: Any, *, field_name: str) -> Any:
    try:
        return json.loads(json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True))
    except (TypeError, ValueError) as exc:
        raise WorkerContractError("runtime_protocol_failed", f"{field_name} must be JSON-serializable.") from exc


def _normalize_node_power_report_request(value: Any) -> dict[str, Any]:
    payload = {} if value is None else _require_mapping(value, "node_power_request")
    allowed_keys = {
        "report_id",
        "metric_stat",
        "metric_lane",
        "config_set_id",
        "max_depth",
        "max_rows",
    }
    extra_keys = sorted(set(payload) - allowed_keys)
    if extra_keys:
        raise WorkerContractError(
            "runtime_protocol_failed",
            "Unsupported node_power_request field(s): " + ", ".join(extra_keys),
        )

    report_id = _require_optional_string(payload.get("report_id"), "node_power_request.report_id")
    metric_stat = _require_optional_string(payload.get("metric_stat"), "node_power_request.metric_stat")
    metric_lane = _require_optional_string(payload.get("metric_lane"), "node_power_request.metric_lane")
    config_set_id = _require_optional_string(payload.get("config_set_id"), "node_power_request.config_set_id")
    if metric_lane is not None and metric_lane not in {"baseline", "conditional", "active"}:
        raise WorkerContractError("runtime_protocol_failed", "node_power_request.metric_lane must be baseline, conditional, or active.")

    max_depth = payload.get("max_depth", _DEFAULT_NODE_POWER_MAX_DEPTH)
    if max_depth is not None:
        max_depth = _require_int(max_depth, "node_power_request.max_depth")
        if max_depth < 1:
            raise WorkerContractError("runtime_protocol_failed", "node_power_request.max_depth must be >= 1.")
    max_rows = payload.get("max_rows", _DEFAULT_NODE_POWER_MAX_ROWS)
    if max_rows is not None:
        max_rows = _require_int(max_rows, "node_power_request.max_rows")
        if max_rows < 1:
            raise WorkerContractError("runtime_protocol_failed", "node_power_request.max_rows must be >= 1.")

    return {
        "report_id": report_id or "pob.headless.node-power.active",
        "metric_stat": metric_stat or _DEFAULT_NODE_POWER_METRIC_STAT,
        "metric_lane": metric_lane or _DEFAULT_NODE_POWER_METRIC_LANE,
        "config_set_id": config_set_id,
        "max_depth": max_depth,
        "max_rows": max_rows,
    }


def _slug_warning_code(line: str) -> str | None:
    lowered = re.sub(r"[^a-z0-9]+", "_", line.lower()).strip("_")
    return lowered or None


def _warning_code_from_line(line: str) -> str | None:
    lowered = line.strip().lower()
    if not lowered:
        return None
    if lowered.startswith("you do not meet the strength requirement"):
        return "unmet_strength_requirement"
    if lowered.startswith("you do not meet the dexterity requirement"):
        return "unmet_dexterity_requirement"
    if lowered.startswith("you do not meet the intelligence requirement"):
        return "unmet_intelligence_requirement"
    if lowered.startswith("you do not meet the omniscience requirement"):
        return "unmet_omniscience_requirement"
    if lowered.startswith("you do not have enough energy shield and mana to use:"):
        return "mana_cost_pool_exhausted"
    if lowered.startswith("you do not have enough mana to use:"):
        return "mana_cost_pool_exhausted"
    if lowered.startswith("you do not have enough life to use:"):
        return "life_cost_pool_exhausted"
    if lowered.startswith("you do not have enough rage to use:"):
        return "rage_cost_pool_exhausted"
    if lowered.startswith("you do not have enough energy shield to use:"):
        return "energy_shield_cost_pool_exhausted"
    if lowered.startswith("you do not have enough unreserved life% to use:"):
        return "life_percent_cost_pool_exhausted"
    if lowered.startswith("you do not have enough unreserved mana% to use:"):
        return "mana_percent_cost_pool_exhausted"
    if "your unreserved life is below 1" in lowered:
        return "life_unreserved_below_one"
    if "your unreserved mana is negative" in lowered:
        return "mana_unreserved_negative"
    if lowered.startswith("you are exceeding jewel limit with the jewel "):
        return "jewel_limit_exceeded"
    if lowered.startswith("you have too many gems in your "):
        return "socket_limit_exceeded"
    if "you have eligible items missing an anoint" in lowered:
        return "missing_anoint_warning"
    if "you have more than one aspect skill active" in lowered:
        return "multiple_aspects_active"
    if "too much cast speed or too little cooldown reduction" in lowered:
        return "vixens_cooldown_warning"
    if "vixen's calculation mode" in lowered:
        return "vixens_gloves_missing"
    if "accuracy for precise technique" in lowered:
        return "precise_technique_accuracy_unmet"
    if "bleed dps exceeds in game limit" in lowered:
        return "bleed_dps_exceeds_game_limit"
    if "corrupting blood dps exceeds in game limit" in lowered:
        return "corrupting_blood_dps_exceeds_game_limit"
    if "ignite dps exceeds in game limit" in lowered:
        return "ignite_dps_exceeds_game_limit"
    if "burning ground dps exceeds in game limit" in lowered:
        return "burning_ground_dps_exceeds_game_limit"
    if "caustic ground dps exceeds in game limit" in lowered:
        return "caustic_ground_dps_exceeds_game_limit"
    if "poison dps exceeds in game limit" in lowered:
        return "poison_dps_exceeds_game_limit"
    if "dot dps exceeds in game limit" in lowered:
        return "dot_dps_exceeds_game_limit"
    return _slug_warning_code(lowered)


def _warning_codes_from_lines(lines: list[str]) -> list[str]:
    codes = {code for line in lines if (code := _warning_code_from_line(line)) is not None}
    return sorted(codes)


def _parse_positive_int_attr(raw_value: str | None, *, field_name: str, default: int = 1) -> int:
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise WorkerContractError("runtime_protocol_failed", f"{field_name} must be an integer.") from exc
    if value < 1:
        raise WorkerContractError("runtime_protocol_failed", f"{field_name} must be >= 1.")
    return value


class LuaJITBridge:
    """Very small Lua 5.1 / LuaJIT bridge over the pinned `lua51.dll`."""

    def __init__(self, dll_path: Path) -> None:
        if not dll_path.is_file():
            raise WorkerContractError("runtime_dependency_missing", f"Missing lua runtime DLL: {dll_path}")

        self._dll = ctypes.CDLL(str(dll_path))
        self._state = self._configure_api()

    def _configure_api(self) -> ctypes.c_void_p:
        lua_state_p = ctypes.c_void_p
        size_ptr = ctypes.POINTER(ctypes.c_size_t)

        self._dll.luaL_newstate.restype = lua_state_p
        self._dll.luaL_openlibs.argtypes = [lua_state_p]
        self._dll.lua_close.argtypes = [lua_state_p]
        self._dll.luaL_loadstring.argtypes = [lua_state_p, ctypes.c_char_p]
        self._dll.luaL_loadstring.restype = ctypes.c_int
        self._dll.luaL_loadfile.argtypes = [lua_state_p, ctypes.c_char_p]
        self._dll.luaL_loadfile.restype = ctypes.c_int
        self._dll.lua_pcall.argtypes = [lua_state_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        self._dll.lua_pcall.restype = ctypes.c_int
        self._dll.lua_tolstring.argtypes = [lua_state_p, ctypes.c_int, size_ptr]
        self._dll.lua_tolstring.restype = ctypes.c_void_p
        self._dll.lua_settop.argtypes = [lua_state_p, ctypes.c_int]

        state = self._dll.luaL_newstate()
        if not state:
            raise WorkerContractError("runtime_launch_failed", "Could not allocate a Lua state for the pinned PoB runtime.")
        self._dll.luaL_openlibs(state)
        return state

    def _clear_stack(self) -> None:
        self._dll.lua_settop(self._state, 0)

    def _stack_string(self, index: int) -> str | None:
        size = ctypes.c_size_t()
        raw = self._dll.lua_tolstring(self._state, index, ctypes.byref(size))
        if not raw:
            return None
        return ctypes.string_at(raw, size.value).decode("utf-8", "replace")

    def execute(self, code: str, *, nret: int = 0) -> list[str | None]:
        self._clear_stack()
        rc = self._dll.luaL_loadstring(self._state, code.encode("utf-8"))
        if rc != 0:
            message = self._stack_string(-1) or "Unknown Lua load error."
            self._clear_stack()
            raise WorkerContractError("runtime_protocol_failed", message)

        rc = self._dll.lua_pcall(self._state, 0, nret, 0)
        if rc != 0:
            message = self._stack_string(-1) or "Unknown Lua execution error."
            self._clear_stack()
            raise WorkerContractError("runtime_protocol_failed", message)

        results = [self._stack_string(index) for index in range(1, nret + 1)]
        self._clear_stack()
        return results

    def load_file(self, path: Path) -> None:
        self._clear_stack()
        rc = self._dll.luaL_loadfile(self._state, str(path).encode("utf-8"))
        if rc != 0:
            message = self._stack_string(-1) or f"Could not load Lua file {path}."
            self._clear_stack()
            raise WorkerContractError("runtime_launch_failed", message)

        rc = self._dll.lua_pcall(self._state, 0, 0, 0)
        if rc != 0:
            message = self._stack_string(-1) or f"Could not execute Lua file {path}."
            self._clear_stack()
            raise WorkerContractError("runtime_launch_failed", message)

    def close(self) -> None:
        if self._state:
            self._dll.lua_close(self._state)
            self._state = ctypes.c_void_p()


class HeadlessLuaRuntime:
    """Persistent headless PoB runtime living inside one worker process."""

    def __init__(self, *, runtime_root: Path, session_root: Path, wrapper_path: Path) -> None:
        self.runtime_root = runtime_root
        self.session_root = session_root
        self.wrapper_path = wrapper_path
        self._previous_cwd = Path.cwd()
        self._bridge = LuaJITBridge(runtime_root / "lua51.dll")

        self._validate_runtime()
        self._bootstrap()

    def _validate_runtime(self) -> None:
        required_paths = (
            self.runtime_root / "Launch.lua",
            self.runtime_root / "manifest.xml",
            self.runtime_root / "lua51.dll",
            self.wrapper_path,
        )
        missing = [str(path) for path in required_paths if not path.is_file()]
        if missing:
            raise WorkerContractError(
                "runtime_dependency_missing",
                "Pinned PoB runtime is missing required files: " + ", ".join(missing),
            )

    def _bootstrap(self) -> None:
        os.chdir(self.runtime_root)
        bootstrap = "\n".join(
            (
                "print = function(...) end",
                "arg = {}",
                "package.path = package.path"
                f" .. ';{self.runtime_root.as_posix()}/?.lua'"
                f" .. ';{self.runtime_root.as_posix()}/?/init.lua'"
                f" .. ';{self.runtime_root.as_posix()}/lua/?.lua'"
                f" .. ';{self.runtime_root.as_posix()}/lua/?/init.lua'"
                f" .. ';{self.runtime_root.as_posix()}/lua/?/?.lua'",
                f"package.cpath = package.cpath .. ';{self.runtime_root.as_posix()}/?.dll'",
            )
        )
        self._bridge.execute(bootstrap)
        self._bridge.load_file(self.wrapper_path)
        prompt_message = self._bridge.execute("return mainObject and mainObject.promptMsg or nil", nret=1)[0]
        if prompt_message:
            raise WorkerContractError("runtime_launch_failed", prompt_message)

    def create_blank_build(self) -> None:
        self._bridge.execute(
            "\n".join(
                (
                    "newBuild()",
                    f"build.spec:SelectClass({_CANONICAL_BLANK_CLASS_ID})",
                    "runCallback('OnFrame')",
                )
            )
        )

    def apply_identity_state(self, identity_payload: dict[str, Any]) -> None:
        payload = _require_mapping(identity_payload, "identity_payload")
        allowed_keys = {"level", "character_level_auto_mode"}
        extra_keys = sorted(set(payload) - allowed_keys)
        if extra_keys:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "Unsupported identity_payload field(s): " + ", ".join(extra_keys),
            )
        level = _require_int(payload.get("level"), "identity_payload.level")
        if level < 1 or level > 100:
            raise WorkerContractError("runtime_protocol_failed", "identity_payload.level must be between 1 and 100.")
        character_level_auto_mode = payload.get("character_level_auto_mode", False)
        if character_level_auto_mode is not None:
            character_level_auto_mode = _require_bool(
                character_level_auto_mode,
                "identity_payload.character_level_auto_mode",
            )
        else:
            character_level_auto_mode = False

        self._bridge.execute(
            "\n".join(
                (
                    f"build.characterLevel = {level}",
                    f"build.characterLevelAutoMode = {_bool_xml(character_level_auto_mode)}",
                    "if build.controls and build.controls.characterLevel then",
                    f"  build.controls.characterLevel:SetText({level})",
                    "end",
                    "if build.controls and build.controls.levelScalingButton then",
                    "  build.controls.levelScalingButton.label = build.characterLevelAutoMode and 'Auto' or 'Manual'",
                    "end",
                    "runCallback('OnFrame')",
                )
            )
        )

    def load_reopen_source(self, xml_text: str) -> None:
        self._bridge.execute(
            "\n".join(
                (
                    f"loadBuildFromXML({_lua_long_string(xml_text)}, 'Reopened Headless Proof Build')",
                    "runCallback('OnFrame')",
                )
            )
        )

    def equip_boots_item(self) -> None:
        self.apply_item_state(
            {
                "active_item_set_id": _CANONICAL_ITEM_SET_ID,
                "item_sets": [
                    {
                        "item_set_id": _CANONICAL_ITEM_SET_ID,
                        "use_second_weapon_set": False,
                        "slots": [
                            {
                                "slot": EXPECTED_BOOTS_SLOT,
                                "raw_item_text": _PROOF_RUNTIME_ITEM_RAW,
                            }
                        ],
                    }
                ],
            }
        )

    def apply_item_state(self, item_payload: dict[str, Any]) -> None:
        try:
            payload_json = json.dumps(item_payload, ensure_ascii=False, allow_nan=False, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise WorkerContractError("runtime_protocol_failed", "item_payload must be JSON-serializable.") from exc

        self._bridge.execute(
            "\n".join(
                (
                    "local json = require('dkjson')",
                    f"local payload_json = {_lua_long_string(payload_json)}",
                    "local payload, _, decode_err = json.decode(payload_json, 1, nil)",
                    "if type(payload) ~= 'table' then",
                    "  error('item_payload must decode to a Lua table: ' .. tostring(decode_err or 'unknown error'))",
                    "end",
                    "local allowed_keys = {",
                    "  active_item_set_id = true,",
                    "  item_sets = true,",
                    "}",
                    "for key, _ in pairs(payload) do",
                    "  if not allowed_keys[key] then",
                    "    error('Unsupported item_payload field: ' .. tostring(key))",
                    "  end",
                    "end",
                    "local function require_array(value, field_name)",
                    "  if type(value) ~= 'table' then",
                    "    error(field_name .. ' must be an array.')",
                    "  end",
                    "  return value",
                    "end",
                    "local function require_object(value, field_name)",
                    "  if type(value) ~= 'table' then",
                    "    error(field_name .. ' must be an object.')",
                    "  end",
                    "  return value",
                    "end",
                    "local function require_string(value, field_name)",
                    "  if type(value) ~= 'string' or value == '' then",
                    "    error(field_name .. ' must be a non-empty string.')",
                    "  end",
                    "  return value",
                    "end",
                    "local function require_bool(value, field_name)",
                    "  if type(value) ~= 'boolean' then",
                    "    error(field_name .. ' must be a boolean.')",
                    "  end",
                    "  return value",
                    "end",
                    "local function normalize_item_set_index(value, field_name)",
                    "  if type(value) == 'number' then",
                    "    local index = math.floor(value)",
                    "    if index >= 1 then",
                    "      return index",
                    "    end",
                    "  elseif type(value) == 'string' then",
                    "    if value == 'itemset.main' then",
                    "      return 1",
                    "    end",
                    "    local raw_index = value:match('^itemset%.(%d+)$')",
                    "    if raw_index then",
                    "      local index = tonumber(raw_index)",
                    "      if index and index >= 1 then",
                    "        return index",
                    "      end",
                    "    end",
                    "  end",
                    "  error(field_name .. ' must reference itemset.main or itemset.<positive-index>.')",
                    "end",
                    "local function build_item_from_raw(raw_item_text, field_name)",
                    "  local raw_text = require_string(raw_item_text, field_name .. '.raw_item_text')",
                    "  build.itemsTab:CreateDisplayItemFromRaw(raw_text, true)",
                    "  if not build.itemsTab.displayItem then",
                    "    error('Pinned runtime could not parse ' .. field_name .. '.raw_item_text into an item.')",
                    "  end",
                    "  local item = build.itemsTab.displayItem",
                    "  build.itemsTab:AddItem(item, true)",
                    "  build.itemsTab:SetDisplayItem()",
                    "  return item",
                    "end",
                    "local function is_abyss_slot(slot_name)",
                    "  return type(slot_name) == 'string' and slot_name:find('Abyssal Socket', 1, true) ~= nil",
                    "end",
                    "local function is_swap_slot(slot_name)",
                    "  return slot_name == 'Weapon 1 Swap' or slot_name == 'Weapon 2 Swap'",
                    "end",
                    "local function slot_has_active_carrier(item_set, slot)",
                    "  if slot.weaponSet == 2 and not item_set.useSecondWeaponSet then",
                    "    return false",
                    "  end",
                    "  if slot.parentSlot and slot.slotNum then",
                    "    local parent_slot_name = slot.parentSlot.slotName",
                    "    local parent_state = item_set[parent_slot_name]",
                    "    local parent_item_id = parent_state and parent_state.selItemId or 0",
                    "    local parent_item = build.itemsTab.items[parent_item_id]",
                    "    local abyssal_socket_count = parent_item and tonumber(parent_item.abyssalSocketCount or 0) or 0",
                    "    return abyssal_socket_count >= tonumber(slot.slotNum)",
                    "  end",
                    "  return true",
                    "end",
                    "local function reset_item_sets_preserving_tree_jewels()",
                    "  local protected_items = {}",
                    "  for _, item_id in pairs(build.spec.jewels or {}) do",
                    "    if type(item_id) == 'number' and item_id > 0 and build.itemsTab.items[item_id] then",
                    "      protected_items[item_id] = build.itemsTab.items[item_id]",
                    "    end",
                    "  end",
                    "  wipeTable(build.itemsTab.items)",
                    "  wipeTable(build.itemsTab.itemOrderList)",
                    "  for item_id, item in pairs(protected_items) do",
                    "    build.itemsTab.items[item_id] = item",
                    "    table.insert(build.itemsTab.itemOrderList, item_id)",
                    "  end",
                    "  table.sort(build.itemsTab.itemOrderList)",
                    "  wipeTable(build.itemsTab.itemSets)",
                    "  wipeTable(build.itemsTab.itemSetOrderList)",
                    "  build.itemsTab.activeItemSetId = 0",
                    "  build.itemsTab.activeItemSet = nil",
                    "  for slot_name, slot in pairs(build.itemsTab.slots) do",
                    "    if not slot.nodeId then",
                    "      slot.selItemId = 0",
                    "      slot.active = false",
                    "      if slot.controls and slot.controls.activate then",
                    "        slot.controls.activate.state = false",
                    "      end",
                    "    end",
                    "  end",
                    "  build.itemsTab:UpdateSockets()",
                    "end",
                    "local requested_item_sets = {}",
                    "local requested_item_set_lookup = {}",
                    "for index, entry in ipairs(require_array(payload.item_sets, 'item_sets')) do",
                    "  local item_set = require_object(entry, 'item_sets[' .. tostring(index) .. ']')",
                    "  local item_set_index = normalize_item_set_index(item_set.item_set_id, 'item_sets[' .. tostring(index) .. '].item_set_id')",
                    "  if requested_item_set_lookup[item_set_index] then",
                    "    error('item_sets contains duplicate item_set_id ' .. tostring(item_set.item_set_id) .. '.')",
                    "  end",
                    "  local use_second_weapon_set = require_bool(",
                    "    item_set.use_second_weapon_set,",
                    "    'item_sets[' .. tostring(index) .. '].use_second_weapon_set'",
                    "  )",
                    "  local slot_requests = {}",
                    "  local seen_slots = {}",
                    "  for slot_index, slot_entry in ipairs(require_array(item_set.slots, 'item_sets[' .. tostring(index) .. '].slots')) do",
                    "    local slot_payload = require_object(",
                    "      slot_entry,",
                    "      'item_sets[' .. tostring(index) .. '].slots[' .. tostring(slot_index) .. ']'",
                    "    )",
                    "    local slot_name = require_string(",
                    "      slot_payload.slot,",
                    "      'item_sets[' .. tostring(index) .. '].slots[' .. tostring(slot_index) .. '].slot'",
                    "    )",
                    "    if seen_slots[slot_name] then",
                    "      error('item_sets[' .. tostring(index) .. '] contains duplicate slot ' .. slot_name .. '.')",
                    "    end",
                    "    seen_slots[slot_name] = true",
                    "    table.insert(slot_requests, {",
                    "      slot = slot_name,",
                    "      raw_item_text = require_string(",
                    "        slot_payload.raw_item_text,",
                    "        'item_sets[' .. tostring(index) .. '].slots[' .. tostring(slot_index) .. '].raw_item_text'",
                    "      ),",
                    "    })",
                    "  end",
                    "  requested_item_set_lookup[item_set_index] = true",
                    "  table.insert(requested_item_sets, {",
                    "    index = item_set_index,",
                    "    use_second_weapon_set = use_second_weapon_set,",
                    "    slots = slot_requests,",
                    "  })",
                    "end",
                    "if #requested_item_sets == 0 then",
                    "  error('item_sets must contain at least one item set definition.')",
                    "end",
                    "local active_item_set_index = normalize_item_set_index(payload.active_item_set_id, 'active_item_set_id')",
                    "if not requested_item_set_lookup[active_item_set_index] then",
                    "  error('active_item_set_id must reference one of item_sets[].item_set_id.')",
                    "end",
                    "table.sort(requested_item_sets, function(left, right)",
                    "  return left.index < right.index",
                    "end)",
                    "reset_item_sets_preserving_tree_jewels()",
                    "for _, requested in ipairs(requested_item_sets) do",
                    "  local item_set = build.itemsTab:NewItemSet(requested.index)",
                    "  table.insert(build.itemsTab.itemSetOrderList, requested.index)",
                    "  item_set.useSecondWeaponSet = requested.use_second_weapon_set",
                    "  requested.item_set = item_set",
                    "end",
                    "build.itemsTab:SetActiveItemSet(active_item_set_index)",
                    "local function assign_requested_slot(requested, slot_request, field_name)",
                    "  local slot_name = slot_request.slot",
                    "  local slot = build.itemsTab.slots[slot_name]",
                    "  if not slot or slot.nodeId then",
                    "    error(field_name .. ' references an unsupported item slot ' .. tostring(slot_name) .. '.')",
                    "  end",
                    "  if is_swap_slot(slot_name) and not requested.item_set.useSecondWeaponSet then",
                    "    error(field_name .. ' requires use_second_weapon_set=true for slot ' .. slot_name .. '.')",
                    "  end",
                    "  if is_abyss_slot(slot_name) and not slot_has_active_carrier(requested.item_set, slot) then",
                    "    error(field_name .. ' does not have an active abyssal carrier for slot ' .. slot_name .. '.')",
                    "  end",
                    "  local item = build_item_from_raw(slot_request.raw_item_text, field_name)",
                    "  if not build.itemsTab:IsItemValidForSlot(item, slot_name, requested.item_set) then",
                    "    error(field_name .. ' could not equip the parsed item in slot ' .. slot_name .. '.')",
                    "  end",
                    "  if requested.item_set == build.itemsTab.activeItemSet then",
                    "    build.itemsTab.slots[slot_name]:SetSelItemId(item.id)",
                    "  else",
                    "    requested.item_set[slot_name].selItemId = item.id",
                    "  end",
                    "end",
                    "for _, requested in ipairs(requested_item_sets) do",
                    "  for slot_index, slot_request in ipairs(requested.slots) do",
                    "    if not is_abyss_slot(slot_request.slot) then",
                    "      assign_requested_slot(",
                    "        requested,",
                    "        slot_request,",
                    "        'item_sets[' .. tostring(requested.index) .. '].slots[' .. tostring(slot_index) .. ']'",
                    "      )",
                    "    end",
                    "  end",
                    "end",
                    "for _, requested in ipairs(requested_item_sets) do",
                    "  for slot_index, slot_request in ipairs(requested.slots) do",
                    "    if is_abyss_slot(slot_request.slot) then",
                    "      assign_requested_slot(",
                    "        requested,",
                    "        slot_request,",
                    "        'item_sets[' .. tostring(requested.index) .. '].slots[' .. tostring(slot_index) .. ']'",
                    "      )",
                    "    end",
                    "  end",
                    "end",
                    "build.itemsTab:SetActiveItemSet(active_item_set_index)",
                    "build.itemsTab:UpdateSockets()",
                    "runCallback('OnFrame')",
                )
            )
        )

    def apply_skill_state(self, skill_payload: dict[str, Any]) -> None:
        normalized = self._normalize_skill_payload(skill_payload)
        xml_text = self.export_build_xml()
        root = self._parse_build_xml(xml_text)
        build_node = root.find("Build")
        skills_node = root.find("Skills")
        if build_node is None or skills_node is None:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "Pinned PoB export is missing Build or Skills nodes required for skill authoring.",
            )

        build_node.attrib.pop("mainSkillIndex", None)
        _set_optional_attr(build_node, "mainSocketGroup", normalized["main_socket_group_index"])

        skills_node.attrib.clear()
        skills_node.attrib.update(normalized["settings"])
        for child in list(skills_node):
            skills_node.remove(child)

        for skill_set in normalized["skill_sets"]:
            skill_set_node = ElementTree.SubElement(
                skills_node,
                "SkillSet",
                {"id": str(skill_set["skill_set_index"])},
            )
            _set_optional_attr(skill_set_node, "title", skill_set["title"])
            for socket_group in skill_set["socket_groups"]:
                skill_node = ElementTree.SubElement(
                    skill_set_node,
                    "Skill",
                    {
                        "enabled": _bool_xml(socket_group["enabled"]),
                        "includeInFullDPS": _bool_xml(socket_group["include_in_full_dps"]),
                        "groupCount": str(socket_group["group_count"]),
                        "mainActiveSkill": str(socket_group["main_active_skill_index"]),
                        "mainActiveSkillCalcs": str(socket_group["main_active_skill_index"]),
                    },
                )
                _set_optional_attr(skill_node, "label", socket_group["label"])
                _set_optional_attr(skill_node, "slot", socket_group["slot"])
                for gem in socket_group["gems"]:
                    gem_node = ElementTree.SubElement(
                        skill_node,
                        "Gem",
                        {
                            "nameSpec": gem["gem_name"],
                            "level": str(gem["level"]),
                            "quality": str(gem["quality"]),
                            "enabled": _bool_xml(gem["enabled"]),
                            "enableGlobal1": _bool_xml(gem["enable_global_1"]),
                            "enableGlobal2": _bool_xml(gem["enable_global_2"]),
                            "count": str(gem["count"]),
                        },
                    )
                    _set_optional_attr(gem_node, "skillPart", gem["skill_part"])
                    _set_optional_attr(gem_node, "skillPartCalcs", gem["skill_part"])
                    _set_optional_attr(gem_node, "skillStageCount", gem["skill_stage_count"])
                    _set_optional_attr(gem_node, "skillStageCountCalcs", gem["skill_stage_count"])
                    _set_optional_attr(gem_node, "skillMineCount", gem["skill_mine_count"])
                    _set_optional_attr(gem_node, "skillMineCountCalcs", gem["skill_mine_count"])
                    _set_optional_attr(gem_node, "skillMinion", gem["skill_minion"])
                    _set_optional_attr(gem_node, "skillMinionCalcs", gem["skill_minion"])
                    _set_optional_attr(gem_node, "skillMinionItemSet", gem["skill_minion_item_set_index"])
                    _set_optional_attr(gem_node, "skillMinionItemSetCalcs", gem["skill_minion_item_set_index"])
                    _set_optional_attr(gem_node, "skillMinionSkill", gem["skill_minion_skill_index"])
                    _set_optional_attr(gem_node, "skillMinionSkillCalcs", gem["skill_minion_skill_index"])

        self.load_reopen_source(_serialize_xml(root))

    def _parse_build_xml(self, xml_text: str) -> ElementTree.Element:
        try:
            return ElementTree.fromstring(xml_text)
        except ElementTree.ParseError as exc:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "Pinned PoB export did not return parseable XML for skill mutation.",
            ) from exc

    def _normalize_skill_payload(self, skill_payload: dict[str, Any]) -> dict[str, Any]:
        payload = _require_mapping(skill_payload, "skill_payload")
        allowed_keys = {
            "active_skill_set_id",
            "main_socket_group_id",
            "default_gem_level",
            "default_gem_quality",
            "show_legacy_gems",
            "show_support_gem_types",
            "sort_gems_by_dps",
            "sort_gems_by_dps_field",
            "skill_sets",
        }
        extra_keys = sorted(set(payload) - allowed_keys)
        if extra_keys:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "Unsupported skill_payload field(s): " + ", ".join(extra_keys),
            )

        skill_sets: list[dict[str, Any]] = []
        skill_set_index_lookup: dict[int, dict[str, Any]] = {}
        for index, entry in enumerate(_require_array(payload.get("skill_sets"), "skill_payload.skill_sets"), start=1):
            skill_set = _require_mapping(entry, f"skill_payload.skill_sets[{index}]")
            allowed_skill_set_keys = {"skill_set_id", "title", "socket_groups"}
            extra_skill_set_keys = sorted(set(skill_set) - allowed_skill_set_keys)
            if extra_skill_set_keys:
                raise WorkerContractError(
                    "runtime_protocol_failed",
                    f"Unsupported skill set field(s) in skill_payload.skill_sets[{index}]: "
                    + ", ".join(extra_skill_set_keys),
                )
            skill_set_index = _normalize_skill_set_index(
                skill_set.get("skill_set_id"),
                f"skill_payload.skill_sets[{index}].skill_set_id",
            )
            if skill_set_index in skill_set_index_lookup:
                raise WorkerContractError(
                    "runtime_protocol_failed",
                    f"skill_payload.skill_sets[{index}] duplicates skill_set_id {skill_set.get('skill_set_id')!r}.",
                )

            socket_groups: list[dict[str, Any]] = []
            for group_index, group_entry in enumerate(
                _require_array(skill_set.get("socket_groups"), f"skill_payload.skill_sets[{index}].socket_groups"),
                start=1,
            ):
                group_payload = _require_mapping(
                    group_entry,
                    f"skill_payload.skill_sets[{index}].socket_groups[{group_index}]",
                )
                allowed_group_keys = {
                    "label",
                    "slot",
                    "enabled",
                    "include_in_full_dps",
                    "group_count",
                    "main_active_skill_index",
                    "gems",
                }
                extra_group_keys = sorted(set(group_payload) - allowed_group_keys)
                if extra_group_keys:
                    raise WorkerContractError(
                        "runtime_protocol_failed",
                        f"Unsupported socket group field(s) in skill_payload.skill_sets[{index}].socket_groups[{group_index}]: "
                        + ", ".join(extra_group_keys),
                    )
                gems: list[dict[str, Any]] = []
                for gem_index, gem_entry in enumerate(
                    _require_array(
                        group_payload.get("gems"),
                        f"skill_payload.skill_sets[{index}].socket_groups[{group_index}].gems",
                    ),
                    start=1,
                ):
                    gem_payload = _require_mapping(
                        gem_entry,
                        f"skill_payload.skill_sets[{index}].socket_groups[{group_index}].gems[{gem_index}]",
                    )
                    allowed_gem_keys = {
                        "gem_name",
                        "level",
                        "quality",
                        "enabled",
                        "count",
                        "enable_global_1",
                        "enable_global_2",
                        "skill_part",
                        "skill_stage_count",
                        "skill_mine_count",
                        "skill_minion",
                        "skill_minion_item_set_id",
                        "skill_minion_skill_index",
                    }
                    extra_gem_keys = sorted(set(gem_payload) - allowed_gem_keys)
                    if extra_gem_keys:
                        raise WorkerContractError(
                            "runtime_protocol_failed",
                            f"Unsupported gem field(s) in skill_payload.skill_sets[{index}].socket_groups[{group_index}].gems[{gem_index}]: "
                            + ", ".join(extra_gem_keys),
                        )
                    gem_name = _require_non_empty_string(
                        gem_payload.get("gem_name"),
                        f"skill_payload.skill_sets[{index}].socket_groups[{group_index}].gems[{gem_index}].gem_name",
                    )
                    level = _require_int(
                        gem_payload.get("level", 1),
                        f"skill_payload.skill_sets[{index}].socket_groups[{group_index}].gems[{gem_index}].level",
                    )
                    quality = _require_int(
                        gem_payload.get("quality", 0),
                        f"skill_payload.skill_sets[{index}].socket_groups[{group_index}].gems[{gem_index}].quality",
                    )
                    count = _require_int(
                        gem_payload.get("count", 1),
                        f"skill_payload.skill_sets[{index}].socket_groups[{group_index}].gems[{gem_index}].count",
                    )
                    if level < 1 or quality < 0 or count < 1:
                        raise WorkerContractError(
                            "runtime_protocol_failed",
                            f"Gem numeric fields must be positive in skill_payload.skill_sets[{index}].socket_groups[{group_index}].gems[{gem_index}].",
                        )
                    skill_part = gem_payload.get("skill_part")
                    skill_stage_count = gem_payload.get("skill_stage_count")
                    skill_mine_count = gem_payload.get("skill_mine_count")
                    skill_minion_skill_index = gem_payload.get("skill_minion_skill_index")
                    normalized_gem = {
                        "gem_name": gem_name,
                        "level": level,
                        "quality": quality,
                        "enabled": _require_bool(
                            gem_payload.get("enabled", True),
                            f"skill_payload.skill_sets[{index}].socket_groups[{group_index}].gems[{gem_index}].enabled",
                        ),
                        "count": count,
                        "enable_global_1": _require_bool(
                            gem_payload.get("enable_global_1", True),
                            f"skill_payload.skill_sets[{index}].socket_groups[{group_index}].gems[{gem_index}].enable_global_1",
                        ),
                        "enable_global_2": _require_bool(
                            gem_payload.get("enable_global_2", False),
                            f"skill_payload.skill_sets[{index}].socket_groups[{group_index}].gems[{gem_index}].enable_global_2",
                        ),
                        "skill_part": None
                        if skill_part is None
                        else _require_int(
                            skill_part,
                            f"skill_payload.skill_sets[{index}].socket_groups[{group_index}].gems[{gem_index}].skill_part",
                        ),
                        "skill_stage_count": None
                        if skill_stage_count is None
                        else _require_int(
                            skill_stage_count,
                            f"skill_payload.skill_sets[{index}].socket_groups[{group_index}].gems[{gem_index}].skill_stage_count",
                        ),
                        "skill_mine_count": None
                        if skill_mine_count is None
                        else _require_int(
                            skill_mine_count,
                            f"skill_payload.skill_sets[{index}].socket_groups[{group_index}].gems[{gem_index}].skill_mine_count",
                        ),
                        "skill_minion": _require_optional_string(
                            gem_payload.get("skill_minion"),
                            f"skill_payload.skill_sets[{index}].socket_groups[{group_index}].gems[{gem_index}].skill_minion",
                        ),
                        "skill_minion_item_set_index": None
                        if gem_payload.get("skill_minion_item_set_id") is None
                        else _normalize_item_set_index(
                            gem_payload.get("skill_minion_item_set_id"),
                            f"skill_payload.skill_sets[{index}].socket_groups[{group_index}].gems[{gem_index}].skill_minion_item_set_id",
                        ),
                        "skill_minion_skill_index": None
                        if skill_minion_skill_index is None
                        else _require_int(
                            skill_minion_skill_index,
                            f"skill_payload.skill_sets[{index}].socket_groups[{group_index}].gems[{gem_index}].skill_minion_skill_index",
                        ),
                    }
                    for numeric_field in ("skill_part", "skill_stage_count", "skill_mine_count", "skill_minion_skill_index"):
                        numeric_value = normalized_gem[numeric_field]
                        if numeric_value is not None and numeric_value < 1:
                            raise WorkerContractError(
                                "runtime_protocol_failed",
                                f"{numeric_field} must be >= 1 in skill_payload.skill_sets[{index}].socket_groups[{group_index}].gems[{gem_index}].",
                            )
                    gems.append(normalized_gem)

                group_count = _require_int(
                    group_payload.get("group_count", 1),
                    f"skill_payload.skill_sets[{index}].socket_groups[{group_index}].group_count",
                )
                main_active_skill_index = _require_int(
                    group_payload.get("main_active_skill_index", 1),
                    f"skill_payload.skill_sets[{index}].socket_groups[{group_index}].main_active_skill_index",
                )
                if group_count < 1 or main_active_skill_index < 1:
                    raise WorkerContractError(
                        "runtime_protocol_failed",
                        f"Socket group numeric selectors must be >= 1 in skill_payload.skill_sets[{index}].socket_groups[{group_index}].",
                    )
                socket_groups.append(
                    {
                        "label": _require_optional_string(
                            group_payload.get("label"),
                            f"skill_payload.skill_sets[{index}].socket_groups[{group_index}].label",
                        ),
                        "slot": _require_optional_string(
                            group_payload.get("slot"),
                            f"skill_payload.skill_sets[{index}].socket_groups[{group_index}].slot",
                        ),
                        "enabled": _require_bool(
                            group_payload.get("enabled", True),
                            f"skill_payload.skill_sets[{index}].socket_groups[{group_index}].enabled",
                        ),
                        "include_in_full_dps": _require_bool(
                            group_payload.get("include_in_full_dps", False),
                            f"skill_payload.skill_sets[{index}].socket_groups[{group_index}].include_in_full_dps",
                        ),
                        "group_count": group_count,
                        "main_active_skill_index": main_active_skill_index,
                        "gems": gems,
                    }
                )

            normalized_skill_set = {
                "skill_set_index": skill_set_index,
                "skill_set_id": _normalize_skill_set_id(skill_set_index),
                "title": _require_optional_string(
                    skill_set.get("title"),
                    f"skill_payload.skill_sets[{index}].title",
                ),
                "socket_groups": socket_groups,
            }
            skill_sets.append(normalized_skill_set)
            skill_set_index_lookup[skill_set_index] = normalized_skill_set

        if not skill_sets:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "skill_payload.skill_sets must contain at least one skill set definition.",
            )

        active_skill_set_index = _normalize_skill_set_index(
            payload.get("active_skill_set_id"),
            "skill_payload.active_skill_set_id",
        )
        active_skill_set = skill_set_index_lookup.get(active_skill_set_index)
        if active_skill_set is None:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "skill_payload.active_skill_set_id must reference one of skill_payload.skill_sets[].skill_set_id.",
            )

        main_socket_group_index = _normalize_socket_group_index(
            payload.get("main_socket_group_id", 1),
            field_name="skill_payload.main_socket_group_id",
            expected_skill_set_id=active_skill_set["skill_set_id"],
        )
        if active_skill_set["socket_groups"] and main_socket_group_index > len(active_skill_set["socket_groups"]):
            raise WorkerContractError(
                "runtime_protocol_failed",
                "skill_payload.main_socket_group_id must reference one of the active skill set socket groups.",
            )

        default_gem_quality = _require_int(payload.get("default_gem_quality", 0), "skill_payload.default_gem_quality")
        if default_gem_quality < 0:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "skill_payload.default_gem_quality must be >= 0.",
            )
        settings = {
            "sortGemsByDPS": _bool_xml(_require_bool(payload.get("sort_gems_by_dps", True), "skill_payload.sort_gems_by_dps")),
            "sortGemsByDPSField": self._normalize_sort_gems_by_dps_field(payload.get("sort_gems_by_dps_field", "CombinedDPS")),
            "activeSkillSet": str(active_skill_set_index),
            "defaultGemQuality": str(default_gem_quality),
            "defaultGemLevel": self._normalize_default_gem_level(payload.get("default_gem_level", "normalMaximum")),
            "showLegacyGems": _bool_xml(_require_bool(payload.get("show_legacy_gems", False), "skill_payload.show_legacy_gems")),
            "showSupportGemTypes": self._normalize_show_support_gem_types(payload.get("show_support_gem_types", "ALL")),
        }
        return {
            "active_skill_set_index": active_skill_set_index,
            "main_socket_group_index": main_socket_group_index,
            "settings": settings,
            "skill_sets": skill_sets,
        }

    def _normalize_default_gem_level(self, value: Any) -> str:
        normalized = _require_non_empty_string(value, "skill_payload.default_gem_level")
        if normalized not in _SUPPORTED_GEM_LEVEL_MODES:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "skill_payload.default_gem_level must be one of "
                + ", ".join(sorted(_SUPPORTED_GEM_LEVEL_MODES))
                + ".",
            )
        return normalized

    def _normalize_show_support_gem_types(self, value: Any) -> str:
        normalized = _require_non_empty_string(value, "skill_payload.show_support_gem_types")
        if normalized not in _SUPPORTED_SUPPORT_GEM_TYPES:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "skill_payload.show_support_gem_types must be one of "
                + ", ".join(sorted(_SUPPORTED_SUPPORT_GEM_TYPES))
                + ".",
            )
        return normalized

    def _normalize_sort_gems_by_dps_field(self, value: Any) -> str:
        normalized = _require_non_empty_string(value, "skill_payload.sort_gems_by_dps_field")
        if normalized not in _SUPPORTED_SORT_GEM_FIELDS:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "skill_payload.sort_gems_by_dps_field must be one of "
                + ", ".join(sorted(_SUPPORTED_SORT_GEM_FIELDS))
                + ".",
            )
        return normalized

    def apply_config_state(self, config_payload: dict[str, Any]) -> None:
        normalized = self._normalize_config_payload(config_payload)
        xml_text = self.export_build_xml()
        root = self._parse_build_xml(xml_text)
        build_node = root.find("Build")
        config_node = root.find("Config")
        if build_node is None or config_node is None:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "Pinned PoB export is missing Build or Config nodes required for config authoring.",
            )

        active_config_set = normalized["config_sets_by_index"][normalized["active_config_set_index"]]
        build_node.set("bandit", active_config_set["build_attrs"]["bandit"])
        build_node.set("pantheonMajorGod", active_config_set["build_attrs"]["pantheonMajorGod"])
        build_node.set("pantheonMinorGod", active_config_set["build_attrs"]["pantheonMinorGod"])

        config_node.attrib.clear()
        config_node.set("activeConfigSet", str(normalized["active_config_set_index"]))
        for child in list(config_node):
            config_node.remove(child)

        for config_set in normalized["config_sets"]:
            config_set_node = ElementTree.SubElement(
                config_node,
                "ConfigSet",
                {
                    "id": str(config_set["config_set_index"]),
                    "title": config_set["title"],
                },
            )
            for field_name in config_set["xml_input_order"]:
                field_value = config_set["xml_inputs"][field_name]
                input_node = ElementTree.SubElement(config_set_node, "Input", {"name": field_name})
                if isinstance(field_value, bool):
                    input_node.set("boolean", _bool_xml(field_value))
                elif isinstance(field_value, int):
                    input_node.set("number", str(field_value))
                else:
                    input_node.set("string", field_value)

        self.load_reopen_source(_serialize_xml(root))

    def _normalize_config_payload(self, config_payload: dict[str, Any]) -> dict[str, Any]:
        payload = _require_mapping(config_payload, "config_payload")
        allowed_keys = {"active_config_set_id", "config_sets"}
        extra_keys = sorted(set(payload) - allowed_keys)
        if extra_keys:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "Unsupported config_payload field(s): " + ", ".join(extra_keys),
            )

        config_sets: list[dict[str, Any]] = []
        config_sets_by_index: dict[int, dict[str, Any]] = {}
        for index, entry in enumerate(_require_array(payload.get("config_sets"), "config_payload.config_sets"), start=1):
            config_set = _require_mapping(entry, f"config_payload.config_sets[{index}]")
            allowed_set_keys = {
                "config_set_id",
                "title",
                "bandit",
                "pantheon_major",
                "pantheon_minor",
                "buffs",
                "combat_conditions",
                "enemy_state",
            }
            extra_set_keys = sorted(set(config_set) - allowed_set_keys)
            if extra_set_keys:
                raise WorkerContractError(
                    "runtime_protocol_failed",
                    f"Unsupported config set field(s) in config_payload.config_sets[{index}]: "
                    + ", ".join(extra_set_keys),
                )

            config_set_index = _normalize_config_set_index(
                config_set.get("config_set_id"),
                f"config_payload.config_sets[{index}].config_set_id",
            )
            if config_set_index in config_sets_by_index:
                raise WorkerContractError(
                    "runtime_protocol_failed",
                    f"config_payload.config_sets[{index}] duplicates config_set_id {config_set.get('config_set_id')!r}.",
                )

            buffs_payload = _require_mapping(
                config_set.get("buffs", {}),
                f"config_payload.config_sets[{index}].buffs",
            )
            extra_buff_keys = sorted(set(buffs_payload) - {"onslaught", "fortification"})
            if extra_buff_keys:
                raise WorkerContractError(
                    "runtime_protocol_failed",
                    f"Unsupported buffs field(s) in config_payload.config_sets[{index}].buffs: "
                    + ", ".join(extra_buff_keys),
                )

            combat_payload = _require_mapping(
                config_set.get("combat_conditions", {}),
                f"config_payload.config_sets[{index}].combat_conditions",
            )
            extra_combat_keys = sorted(set(combat_payload) - {"using_flask"})
            if extra_combat_keys:
                raise WorkerContractError(
                    "runtime_protocol_failed",
                    f"Unsupported combat_conditions field(s) in config_payload.config_sets[{index}].combat_conditions: "
                    + ", ".join(extra_combat_keys),
                )

            enemy_payload = _require_mapping(
                config_set.get("enemy_state", {}),
                f"config_payload.config_sets[{index}].enemy_state",
            )
            extra_enemy_keys = sorted(set(enemy_payload) - {"is_boss", "is_shocked", "is_ignited", "shock_effect"})
            if extra_enemy_keys:
                raise WorkerContractError(
                    "runtime_protocol_failed",
                    f"Unsupported enemy_state field(s) in config_payload.config_sets[{index}].enemy_state: "
                    + ", ".join(extra_enemy_keys),
                )

            bandit = self._normalize_config_choice(
                config_set.get("bandit"),
                field_name=f"config_payload.config_sets[{index}].bandit",
                allowed_values=_SUPPORTED_BANDIT_CHOICES,
                default_value="None",
            )
            pantheon_major = self._normalize_config_choice(
                config_set.get("pantheon_major"),
                field_name=f"config_payload.config_sets[{index}].pantheon_major",
                allowed_values=_SUPPORTED_MAJOR_PANTHEONS,
                default_value="None",
            )
            pantheon_minor = self._normalize_config_choice(
                config_set.get("pantheon_minor"),
                field_name=f"config_payload.config_sets[{index}].pantheon_minor",
                allowed_values=_SUPPORTED_MINOR_PANTHEONS,
                default_value="None",
            )
            enemy_is_boss = self._normalize_config_choice(
                enemy_payload.get("is_boss"),
                field_name=f"config_payload.config_sets[{index}].enemy_state.is_boss",
                allowed_values=_SUPPORTED_ENEMY_BOSS_STATES,
                default_value="Pinnacle",
            )
            enemy_is_shocked = _require_bool(
                enemy_payload.get("is_shocked", False),
                f"config_payload.config_sets[{index}].enemy_state.is_shocked",
            )
            enemy_is_ignited = _require_bool(
                enemy_payload.get("is_ignited", False),
                f"config_payload.config_sets[{index}].enemy_state.is_ignited",
            )
            shock_effect_raw = enemy_payload.get("shock_effect")
            if shock_effect_raw is None:
                shock_effect = None
            else:
                shock_effect = _require_int(
                    shock_effect_raw,
                    f"config_payload.config_sets[{index}].enemy_state.shock_effect",
                )
                if shock_effect < 0:
                    raise WorkerContractError(
                        "runtime_protocol_failed",
                        f"config_payload.config_sets[{index}].enemy_state.shock_effect must be >= 0.",
                    )
                if not enemy_is_shocked:
                    raise WorkerContractError(
                        "runtime_protocol_failed",
                        f"config_payload.config_sets[{index}].enemy_state.shock_effect requires is_shocked=true.",
                    )

            xml_inputs: dict[str, str | bool | int] = {}
            if bandit != _CONFIG_DEFAULT_INPUTS["bandit"]:
                xml_inputs["bandit"] = bandit
            if pantheon_major != _CONFIG_DEFAULT_INPUTS["pantheonMajorGod"]:
                xml_inputs["pantheonMajorGod"] = pantheon_major
            if pantheon_minor != _CONFIG_DEFAULT_INPUTS["pantheonMinorGod"]:
                xml_inputs["pantheonMinorGod"] = pantheon_minor
            if enemy_is_boss != _CONFIG_DEFAULT_INPUTS["enemyIsBoss"]:
                xml_inputs["enemyIsBoss"] = enemy_is_boss
            if _require_bool(
                buffs_payload.get("onslaught", False),
                f"config_payload.config_sets[{index}].buffs.onslaught",
            ):
                xml_inputs["buffOnslaught"] = True
            if _require_bool(
                buffs_payload.get("fortification", False),
                f"config_payload.config_sets[{index}].buffs.fortification",
            ):
                xml_inputs["buffFortification"] = True
            if _require_bool(
                combat_payload.get("using_flask", False),
                f"config_payload.config_sets[{index}].combat_conditions.using_flask",
            ):
                xml_inputs["conditionUsingFlask"] = True
            if enemy_is_shocked:
                xml_inputs["conditionEnemyShocked"] = True
            if enemy_is_ignited:
                xml_inputs["conditionEnemyIgnited"] = True
            if shock_effect is not None:
                xml_inputs["conditionShockEffect"] = shock_effect

            normalized_config_set = {
                "config_set_index": config_set_index,
                "config_set_id": _normalize_config_set_id(config_set_index),
                "title": _require_optional_string(
                    config_set.get("title"),
                    f"config_payload.config_sets[{index}].title",
                )
                or ("Default" if config_set_index == 1 else f"Config {config_set_index}"),
                "build_attrs": {
                    "bandit": bandit,
                    "pantheonMajorGod": pantheon_major,
                    "pantheonMinorGod": pantheon_minor,
                },
                "xml_inputs": xml_inputs,
                "xml_input_order": sorted(xml_inputs),
            }
            config_sets.append(normalized_config_set)
            config_sets_by_index[config_set_index] = normalized_config_set

        if not config_sets:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "config_payload.config_sets must contain at least one config set definition.",
            )

        active_config_set_index = _normalize_config_set_index(
            payload.get("active_config_set_id"),
            "config_payload.active_config_set_id",
        )
        if active_config_set_index not in config_sets_by_index:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "config_payload.active_config_set_id must reference one of config_payload.config_sets[].config_set_id.",
            )

        return {
            "active_config_set_index": active_config_set_index,
            "active_config_set_id": _normalize_config_set_id(active_config_set_index),
            "config_sets": config_sets,
            "config_sets_by_index": config_sets_by_index,
        }

    def _normalize_config_choice(
        self,
        value: Any,
        *,
        field_name: str,
        allowed_values: frozenset[str],
        default_value: str,
    ) -> str:
        if value is None:
            return default_value
        normalized = _require_non_empty_string(value, field_name)
        if normalized not in allowed_values:
            raise WorkerContractError(
                "runtime_protocol_failed",
                f"{field_name} must be one of {', '.join(sorted(allowed_values))}.",
            )
        return normalized

    def apply_tree_state(self, tree_payload: dict[str, Any]) -> None:
        try:
            payload_json = json.dumps(tree_payload, ensure_ascii=False, allow_nan=False, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise WorkerContractError("runtime_protocol_failed", "tree_payload must be JSON-serializable.") from exc

        self._bridge.execute(
            "\n".join(
                (
                    "local json = require('dkjson')",
                    f"local payload_json = {_lua_long_string(payload_json)}",
                    "local payload, _, decode_err = json.decode(payload_json, 1, nil)",
                    "if type(payload) ~= 'table' then",
                    "  error('tree_payload must decode to a Lua table: ' .. tostring(decode_err or 'unknown error'))",
                    "end",
                    "local allowed_keys = {",
                    "  active_spec_id = true,",
                    "  class_id = true,",
                    "  ascendancy_id = true,",
                    "  secondary_ascendancy_id = true,",
                    "  ascendancy_node_ids = true,",
                    "  ascendancy_notable_node_ids = true,",
                    "  user_allocated_node_ids = true,",
                    "  keystone_node_ids = true,",
                    "  mastery_effect_ids = true,",
                    "  cluster_jewel_socket_ids = true,",
                    "  socketed_jewel_node_ids = true,",
                    "  anoint_allocations = true,",
                    "  override_carrier_node_ids = true,",
                    "  override_carriers = true,",
                    "  cluster_jewel_items = true,",
                    "  socketed_jewel_items = true,",
                    "}",
                    "for key, _ in pairs(payload) do",
                    "  if not allowed_keys[key] then",
                    "    error('Unsupported tree_payload field: ' .. tostring(key))",
                    "  end",
                    "end",
                    "local function is_null(value)",
                    "  return value == nil or value == json.null",
                    "end",
                    "local function require_array(value, field_name)",
                    "  if is_null(value) then",
                    "    return {}",
                    "  end",
                    "  if type(value) ~= 'table' then",
                    "    error(field_name .. ' must be an array.')",
                    "  end",
                    "  return value",
                    "end",
                    "local function require_int(value, field_name)",
                    "  if type(value) ~= 'number' then",
                    "    error(field_name .. ' must be an integer.')",
                    "  end",
                    "  return math.floor(value)",
                    "end",
                    "local function normalize_spec_index(value)",
                    "  if is_null(value) then",
                    "    return 1",
                    "  end",
                    "  if type(value) == 'number' then",
                    "    local index = math.floor(value)",
                    "    if index < 1 then",
                    "      error('active_spec_id must reference spec.main or spec.<positive-index>.')",
                    "    end",
                    "    return index",
                    "  end",
                    "  if type(value) == 'string' then",
                    "    if value == 'spec.main' then",
                    "      return 1",
                    "    end",
                    "    local raw_index = value:match('^spec%.(%d+)$')",
                    "    if raw_index then",
                    "      local index = tonumber(raw_index)",
                    "      if index and index >= 1 then",
                    "        return index",
                    "      end",
                    "    end",
                    "  end",
                    "  error('active_spec_id must reference spec.main or spec.<positive-index>.')",
                    "end",
                    "local function normalize_optional_node_ids(value, field_name)",
                    "  local normalized = {}",
                    "  for index, raw_value in ipairs(require_array(value, field_name)) do",
                    "    normalized[index] = require_int(raw_value, field_name .. '[' .. tostring(index) .. ']')",
                    "  end",
                    "  return normalized",
                    "end",
                    "local function resolve_class_id(value)",
                    "  if is_null(value) then",
                    "    return build.spec.curClassId or " + str(_CANONICAL_BLANK_CLASS_ID),
                    "  end",
                    "  if type(value) == 'number' then",
                    "    local class_id = math.floor(value)",
                    "    if build.spec.tree.classes[class_id] then",
                    "      return class_id",
                    "    end",
                    "  elseif type(value) == 'string' then",
                    "    for class_id, class in pairs(build.spec.tree.classes) do",
                    "      if class.name == value or tostring(class_id) == value then",
                    "        return tonumber(class_id)",
                    "      end",
                    "    end",
                    "  end",
                    "  error('Unknown passive-tree class reference: ' .. tostring(value))",
                    "end",
                    "local function resolve_ascendancy_id(value, class_id)",
                    "  if is_null(value) then",
                    "    return 0",
                    "  end",
                    "  local class = build.spec.tree.classes[class_id]",
                    "  if not class or type(class.classes) ~= 'table' then",
                    "    error('Could not resolve ascendancy because class ' .. tostring(class_id) .. ' is unavailable.')",
                    "  end",
                    "  if type(value) == 'number' then",
                    "    local ascendancy_id = math.floor(value)",
                    "    if class.classes[ascendancy_id] then",
                    "      return ascendancy_id",
                    "    end",
                    "  elseif type(value) == 'string' then",
                    "    if value == '' or value == 'None' then",
                    "      return 0",
                    "    end",
                    "    for ascendancy_id, ascendancy in pairs(class.classes) do",
                    "      if ascendancy.name == value or ascendancy.id == value or tostring(ascendancy_id) == value then",
                    "        return tonumber(ascendancy_id)",
                    "      end",
                    "    end",
                    "  end",
                    "  error('Unknown ascendancy reference for class ' .. tostring(class_id) .. ': ' .. tostring(value))",
                    "end",
                    "local function resolve_secondary_ascendancy_id(value)",
                    "  if is_null(value) then",
                    "    return 0",
                    "  end",
                    "  if type(value) == 'number' then",
                    "    local ascendancy_id = math.floor(value)",
                    "    if ascendancy_id == 0 then",
                    "      return 0",
                    "    end",
                    "    if build.spec.tree.alternate_ascendancies and build.spec.tree.alternate_ascendancies[ascendancy_id] then",
                    "      return ascendancy_id",
                    "    end",
                    "  elseif type(value) == 'string' then",
                    "    if value == '' or value == 'None' then",
                    "      return 0",
                    "    end",
                    "    if build.spec.tree.alternate_ascendancies then",
                    "      for ascendancy_id, ascendancy in pairs(build.spec.tree.alternate_ascendancies) do",
                    "        if ascendancy.name == value or tostring(ascendancy_id) == value then",
                    "          return tonumber(ascendancy_id)",
                    "        end",
                    "      end",
                    "    end",
                    "  end",
                    "  error('Unknown secondary ascendancy reference: ' .. tostring(value))",
                    "end",
                    "local function ensure_spec(index)",
                    "  while #build.treeTab.specList < index do",
                    "    local source_spec = build.treeTab.specList[#build.treeTab.specList]",
                    "    local new_spec = new('PassiveSpec', build, source_spec.treeVersion)",
                    "    new_spec:RestoreUndoState(source_spec:CreateUndoState(), source_spec.treeVersion)",
                    "    table.insert(build.treeTab.specList, new_spec)",
                    "  end",
                    "  build.treeTab:SetActiveSpec(index)",
                    "  build.itemsTab:UpdateSockets()",
                    "end",
                    "local function clear_tree_socket_items()",
                    "  if type(build.itemsTab.sockets) ~= 'table' then",
                    "    build.spec.jewels = {}",
                    "    build.spec:BuildClusterJewelGraphs()",
                    "    return",
                    "  end",
                    "  for _, socket in pairs(build.itemsTab.sockets) do",
                    "    if socket and socket.selItemId and socket.selItemId ~= 0 then",
                    "      socket:SetSelItemId(0)",
                    "    end",
                    "  end",
                    "  build.spec.jewels = {}",
                    "  build.spec:BuildClusterJewelGraphs()",
                    "  build.itemsTab:UpdateSockets()",
                    "end",
                    "local function rebuild_blank_tree(class_id, ascendancy_id, secondary_ascendancy_id)",
                    "  build.spec:ResetNodes()",
                    "  build.spec.hashOverrides = {}",
                    "  wipeTable(build.spec.masterySelections)",
                    "  build.spec:SelectClass(class_id)",
                    "  build.spec:SelectAscendClass(ascendancy_id)",
                    "  build.spec:SelectSecondaryAscendClass(secondary_ascendancy_id)",
                    "  build.spec:BuildAllDependsAndPaths()",
                    "  build.itemsTab:UpdateSockets()",
                    "end",
                    "local function node_display_name(node)",
                    "  return tostring(node.dn or node.name or node.label or 'unknown node')",
                    "end",
                    "local function node_ascendancy_name(node)",
                    "  local value = node.ascendancyName or node.ascendancy_name",
                    "  if type(value) == 'string' and value ~= '' then",
                    "    return value",
                    "  end",
                    "  return nil",
                    "end",
                    "local function node_is_ascendancy_start(node)",
                    "  return node.isAscendancyStart == true or node.ascendancyStart == true",
                    "end",
                    "local function node_is_notable(node)",
                    "  return node.isNotable == true or node.notable == true or node.type == 'Notable'",
                    "end",
                    "local function validate_ascendancy_nodes(node_ids, field_name, expected_ascendancy_name, require_notable)",
                    "  if #node_ids == 0 then",
                    "    return",
                    "  end",
                    "  if type(expected_ascendancy_name) ~= 'string' or expected_ascendancy_name == '' or expected_ascendancy_name == 'None' then",
                    "    error(field_name .. ' requires a selected ascendancy_id.')",
                    "  end",
                    "  for index, node_id in ipairs(node_ids) do",
                    "    local node = build.spec.nodes[node_id]",
                    "    if not node then",
                    "      error(field_name .. '[' .. tostring(index) .. '] references node ' .. tostring(node_id) .. ' which is unavailable in the selected class/ascendancy tree.')",
                    "    end",
                    "    local ascendancy_name = node_ascendancy_name(node)",
                    "    if ascendancy_name ~= expected_ascendancy_name or node_is_ascendancy_start(node) then",
                    "      error(field_name .. '[' .. tostring(index) .. '] references node ' .. tostring(node_id) .. ' outside selected ascendancy ' .. tostring(expected_ascendancy_name) .. '.')",
                    "    end",
                    "    if require_notable and not node_is_notable(node) then",
                    "      error(field_name .. '[' .. tostring(index) .. '] references non-notable ascendancy node ' .. tostring(node_id) .. ' (' .. node_display_name(node) .. ').')",
                    "    end",
                    "  end",
                    "end",
                    "local function apply_override_carriers(entries)",
                    "  for index, entry in ipairs(require_array(entries, 'override_carriers')) do",
                    "    if type(entry) ~= 'table' then",
                    "      error('override_carriers[' .. tostring(index) .. '] must be an object.')",
                    "    end",
                    "    local node_id = require_int(entry.node_id or entry.id, 'override_carriers[' .. tostring(index) .. '].node_id')",
                    "    local tattoo_name = entry.tattoo_name or entry.display_name or entry.name or entry.dn",
                    "    if type(tattoo_name) ~= 'string' or tattoo_name == '' then",
                    "      error('override_carriers[' .. tostring(index) .. '] must include a non-empty tattoo_name.')",
                    "    end",
                    "    local source = build.spec.tree.tattoo and build.spec.tree.tattoo.nodes and build.spec.tree.tattoo.nodes[tattoo_name]",
                    "    if not source then",
                    "      error('Pinned runtime could not resolve tattoo override ' .. tattoo_name .. '.')",
                    "    end",
                    "    local override = copyTable(source, true)",
                    "    override.id = node_id",
                    "    build.spec.hashOverrides[node_id] = override",
                    "    local live_node = build.spec.nodes[node_id]",
                    "    if live_node then",
                    "      build.spec:ReplaceNode(live_node, override)",
                    "    end",
                    "  end",
                    "  build.spec:BuildAllDependsAndPaths()",
                    "end",
                    "local function apply_masteries(entries)",
                    "  for index, entry in ipairs(require_array(entries, 'mastery_effect_ids')) do",
                    "    local node_id = nil",
                    "    local effect_id = nil",
                    "    if type(entry) == 'string' then",
                    "      local raw_node_id, raw_effect_id = entry:match('^(%d+):(%d+)$')",
                    "      if not raw_node_id or not raw_effect_id then",
                    "        error('mastery_effect_ids[' .. tostring(index) .. '] must encode node_id:effect_id.')",
                    "      end",
                    "      node_id = tonumber(raw_node_id)",
                    "      effect_id = tonumber(raw_effect_id)",
                    "    elseif type(entry) == 'table' then",
                    "      node_id = require_int(entry.node_id or entry.id, 'mastery_effect_ids[' .. tostring(index) .. '].node_id')",
                    "      effect_id = require_int(entry.effect_id or entry.effect, 'mastery_effect_ids[' .. tostring(index) .. '].effect_id')",
                    "    else",
                    "      error('mastery_effect_ids[' .. tostring(index) .. '] must be a node_id:effect_id string or object.')",
                    "    end",
                    "    local node = build.spec.nodes[node_id]",
                    "    if not node or node.type ~= 'Mastery' then",
                    "      error('Mastery node ' .. tostring(node_id) .. ' is unavailable in the active passive tree.')",
                    "    end",
                    "    local effect = build.spec.tree.masteryEffects[effect_id]",
                    "    if not effect then",
                    "      error('Mastery effect ' .. tostring(effect_id) .. ' is unavailable in the active passive tree.')",
                    "    end",
                    "    build.spec.masterySelections[node_id] = effect_id",
                    "    node.sd = effect.sd",
                    "    node.allMasteryOptions = false",
                    "    node.reminderText = { 'Tip: Right click to select a different effect' }",
                    "    build.spec.tree:ProcessStats(node)",
                    "  end",
                    "end",
                    "local function finalize_masteries(entries)",
                    "  for index, entry in ipairs(require_array(entries, 'mastery_effect_ids')) do",
                    "    local node_id = nil",
                    "    local effect_id = nil",
                    "    if type(entry) == 'string' then",
                    "      local raw_node_id, raw_effect_id = entry:match('^(%d+):(%d+)$')",
                    "      if not raw_node_id or not raw_effect_id then",
                    "        error('mastery_effect_ids[' .. tostring(index) .. '] must encode node_id:effect_id.')",
                    "      end",
                    "      node_id = tonumber(raw_node_id)",
                    "      effect_id = tonumber(raw_effect_id)",
                    "    elseif type(entry) == 'table' then",
                    "      node_id = require_int(entry.node_id or entry.id, 'mastery_effect_ids[' .. tostring(index) .. '].node_id')",
                    "      effect_id = require_int(entry.effect_id or entry.effect, 'mastery_effect_ids[' .. tostring(index) .. '].effect_id')",
                    "    else",
                    "      error('mastery_effect_ids[' .. tostring(index) .. '] must be a node_id:effect_id string or object.')",
                    "    end",
                    "    local node = build.spec.nodes[node_id]",
                    "    local effect = build.spec.tree.masteryEffects[effect_id]",
                    "    if not node or node.type ~= 'Mastery' then",
                    "      error('Mastery node ' .. tostring(node_id) .. ' is unavailable in the active passive tree.')",
                    "    end",
                    "    if not effect then",
                    "      error('Mastery effect ' .. tostring(effect_id) .. ' is unavailable in the active passive tree.')",
                    "    end",
                    "    build.spec.masterySelections[node_id] = effect_id",
                    "    node.sd = effect.sd",
                    "    node.allMasteryOptions = false",
                    "    node.reminderText = { 'Tip: Right click to select a different effect' }",
                    "    build.spec.tree:ProcessStats(node)",
                    "    if not node.alloc then",
                    "      build.spec:AllocNode(node)",
                    "    end",
                    "  end",
                    "  build.spec:BuildAllDependsAndPaths()",
                    "  build.itemsTab:UpdateSockets()",
                    "end",
                    "local function allocate_nodes(node_ids, field_name, allow_missing)",
                    "  for index, node_id in ipairs(node_ids) do",
                    "    local node = build.spec.nodes[node_id]",
                    "    if node then",
                    "      build.spec:AllocNode(node)",
                    "    elseif not allow_missing then",
                    "      error(field_name .. '[' .. tostring(index) .. '] references node ' .. tostring(node_id) .. ' which is unavailable in the active passive tree.')",
                    "    end",
                    "  end",
                    "  build.itemsTab:UpdateSockets()",
                    "end",
                    "local function build_item_from_raw(raw_item_text, field_name)",
                    "  if type(raw_item_text) ~= 'string' or raw_item_text == '' then",
                    "    error(field_name .. '.raw_item_text must be a non-empty string.')",
                    "  end",
                    "  build.itemsTab:CreateDisplayItemFromRaw(raw_item_text, true)",
                    "  if not build.itemsTab.displayItem then",
                    "    error('Pinned runtime could not parse ' .. field_name .. '.raw_item_text into an item.')",
                    "  end",
                    "  local item = build.itemsTab.displayItem",
                    "  build.itemsTab:AddItem(item, true)",
                    "  build.itemsTab:SetDisplayItem()",
                    "  return item",
                    "end",
                    "local function assign_socket_item(node_id, raw_item_text, field_name)",
                    "  build.itemsTab:UpdateSockets()",
                    "  local socket = build.itemsTab.sockets[node_id]",
                    "  if not socket then",
                    "    error(field_name .. ' references node ' .. tostring(node_id) .. ' which is not an active jewel socket.')",
                    "  end",
                    "  local item = build_item_from_raw(raw_item_text, field_name)",
                    "  socket:SetSelItemId(item.id)",
                    "  build.itemsTab:UpdateSockets()",
                    "  return item",
                    "end",
                    "local function apply_cluster_jewels(entries)",
                    "  for index, entry in ipairs(require_array(entries, 'cluster_jewel_items')) do",
                    "    if type(entry) ~= 'table' then",
                    "      error('cluster_jewel_items[' .. tostring(index) .. '] must be an object.')",
                    "    end",
                    "    local node_id = require_int(entry.node_id or entry.socket_node_id, 'cluster_jewel_items[' .. tostring(index) .. '].node_id')",
                    "    local node = build.spec.nodes[node_id]",
                    "    if not node then",
                    "      error('cluster_jewel_items[' .. tostring(index) .. '] references unavailable node ' .. tostring(node_id) .. '.')",
                    "    end",
                    "    build.spec:AllocNode(node)",
                    "    local item = assign_socket_item(node_id, entry.raw_item_text, 'cluster_jewel_items[' .. tostring(index) .. ']')",
                    "    if not (item.clusterJewel or (item.jewelData and item.jewelData.clusterJewelValid)) then",
                    "      error('cluster_jewel_items[' .. tostring(index) .. '] did not materialize a valid cluster jewel.')",
                    "    end",
                    "  end",
                    "  build.spec:BuildClusterJewelGraphs()",
                    "  build.itemsTab:UpdateSockets()",
                    "end",
                    "local function apply_socketed_jewels(entries)",
                    "  for index, entry in ipairs(require_array(entries, 'socketed_jewel_items')) do",
                    "    if type(entry) ~= 'table' then",
                    "      error('socketed_jewel_items[' .. tostring(index) .. '] must be an object.')",
                    "    end",
                    "    local node_id = require_int(entry.node_id or entry.socket_node_id, 'socketed_jewel_items[' .. tostring(index) .. '].node_id')",
                    "    local node = build.spec.nodes[node_id]",
                    "    if not node then",
                    "      error('socketed_jewel_items[' .. tostring(index) .. '] references unavailable node ' .. tostring(node_id) .. '.')",
                    "    end",
                    "    build.spec:AllocNode(node)",
                    "    assign_socket_item(node_id, entry.raw_item_text, 'socketed_jewel_items[' .. tostring(index) .. ']')",
                    "  end",
                    "end",
                    "local function validate_exact_ids(field_name, expected_ids, observed_ids)",
                    "  table.sort(expected_ids)",
                    "  table.sort(observed_ids)",
                    "  if #expected_ids ~= #observed_ids then",
                    "    error(field_name .. ' did not materialize the requested node set.')",
                    "  end",
                    "  for index, node_id in ipairs(expected_ids) do",
                    "    if observed_ids[index] ~= node_id then",
                    "      error(field_name .. ' did not materialize the requested node set.')",
                    "    end",
                    "  end",
                    "end",
                    "local function validate_present_ids(field_name, expected_ids, observed_ids)",
                    "  local observed_lookup = {}",
                    "  for _, node_id in ipairs(observed_ids) do",
                    "    observed_lookup[node_id] = true",
                    "  end",
                    "  local missing_ids = {}",
                    "  for _, node_id in ipairs(expected_ids) do",
                    "    if not observed_lookup[node_id] then",
                    "      table.insert(missing_ids, node_id)",
                    "    end",
                    "  end",
                    "  if #missing_ids > 0 then",
                    "    table.sort(missing_ids)",
                    "    error(field_name .. ' did not materialize requested node(s): ' .. table.concat(missing_ids, ', '))",
                    "  end",
                    "end",
                    "local function import_available_nodes(node_ids, class_id, ascendancy_id, secondary_ascendancy_id)",
                    "  local import_node_ids = {}",
                    "  for _, node_id in ipairs(node_ids) do",
                    "    if build.spec.nodes[node_id] then",
                    "      table.insert(import_node_ids, node_id)",
                    "    end",
                    "  end",
                    "  local mastery_effects = {}",
                    "  for mastery_node_id, effect_id in pairs(build.spec.masterySelections) do",
                    "    mastery_effects[mastery_node_id] = effect_id",
                    "  end",
                    "  local hash_overrides = {}",
                    "  for node_id, override in pairs(build.spec.hashOverrides) do",
                    "    hash_overrides[node_id] = override",
                    "  end",
                    "  build.spec:ImportFromNodeList(",
                    "    class_id,",
                    "    ascendancy_id,",
                    "    secondary_ascendancy_id,",
                    "    import_node_ids,",
                    "    hash_overrides,",
                    "    mastery_effects",
                    "  )",
                    "  build.itemsTab:UpdateSockets()",
                    "end",
                    "local target_spec_index = normalize_spec_index(payload.active_spec_id)",
                    "ensure_spec(target_spec_index)",
                    "clear_tree_socket_items()",
                    "local class_id = resolve_class_id(payload.class_id)",
                    "local ascendancy_id = resolve_ascendancy_id(payload.ascendancy_id, class_id)",
                    "local secondary_ascendancy_id = resolve_secondary_ascendancy_id(payload.secondary_ascendancy_id)",
                    "rebuild_blank_tree(class_id, ascendancy_id, secondary_ascendancy_id)",
                    "if #require_array(payload.anoint_allocations, 'anoint_allocations') > 0 then",
                    "  error('anoint_allocations are not repo-owned in this tree-local proof slice.')",
                    "end",
                    "apply_override_carriers(payload.override_carriers)",
                    "apply_masteries(payload.mastery_effect_ids)",
                    "local requested_user_nodes = normalize_optional_node_ids(payload.user_allocated_node_ids, 'user_allocated_node_ids')",
                    "local requested_ascendancy_nodes = normalize_optional_node_ids(payload.ascendancy_node_ids, 'ascendancy_node_ids')",
                    "local requested_ascendancy_notables = normalize_optional_node_ids(payload.ascendancy_notable_node_ids, 'ascendancy_notable_node_ids')",
                    "validate_ascendancy_nodes(requested_ascendancy_nodes, 'ascendancy_node_ids', build.spec.curAscendClassName, false)",
                    "validate_ascendancy_nodes(requested_ascendancy_notables, 'ascendancy_notable_node_ids', build.spec.curAscendClassName, true)",
                    "local requested_keystones = normalize_optional_node_ids(payload.keystone_node_ids, 'keystone_node_ids')",
                    "local requested_cluster_sockets = normalize_optional_node_ids(payload.cluster_jewel_socket_ids, 'cluster_jewel_socket_ids')",
                    "local requested_socketed_nodes = normalize_optional_node_ids(payload.socketed_jewel_node_ids, 'socketed_jewel_node_ids')",
                    "local requested_override_nodes = normalize_optional_node_ids(payload.override_carrier_node_ids, 'override_carrier_node_ids')",
                    "local merged_node_ids = {}",
                    "local seen_node_ids = {}",
                    "local function merge_nodes(node_ids)",
                    "  for _, node_id in ipairs(node_ids) do",
                    "    if not seen_node_ids[node_id] then",
                    "      seen_node_ids[node_id] = true",
                    "      table.insert(merged_node_ids, node_id)",
                    "    end",
                    "  end",
                    "end",
                    "merge_nodes(requested_user_nodes)",
                    "merge_nodes(requested_ascendancy_nodes)",
                    "merge_nodes(requested_ascendancy_notables)",
                    "merge_nodes(requested_keystones)",
                    "merge_nodes(requested_cluster_sockets)",
                    "merge_nodes(requested_socketed_nodes)",
                    "merge_nodes(requested_override_nodes)",
                    "for _, entry in ipairs(require_array(payload.mastery_effect_ids, 'mastery_effect_ids')) do",
                    "  if type(entry) == 'string' then",
                    "    local raw_node_id = entry:match('^(%d+):%d+$')",
                    "    if raw_node_id then",
                    "      merge_nodes({ tonumber(raw_node_id) })",
                    "    end",
                    "  elseif type(entry) == 'table' then",
                    "    merge_nodes({ require_int(entry.node_id or entry.id, 'mastery_effect_ids.node_id') })",
                    "  end",
                    "end",
                    "for _, entry in ipairs(require_array(payload.override_carriers, 'override_carriers')) do",
                    "  if type(entry) == 'table' then",
                    "    merge_nodes({ require_int(entry.node_id or entry.id, 'override_carriers.node_id') })",
                    "  end",
                    "end",
                    "import_available_nodes(merged_node_ids, class_id, ascendancy_id, secondary_ascendancy_id)",
                    "apply_cluster_jewels(payload.cluster_jewel_items)",
                    "allocate_nodes(merged_node_ids, 'user_allocated_node_ids', false)",
                    "finalize_masteries(payload.mastery_effect_ids)",
                    "apply_socketed_jewels(payload.socketed_jewel_items)",
                    "local observed_cluster_sockets = {}",
                    "local observed_socketed_nodes = {}",
                    "for node_id, item_id in pairs(build.spec.jewels) do",
                    "  if type(item_id) == 'number' and item_id > 0 then",
                    "    table.insert(observed_socketed_nodes, node_id)",
                    "    local item = build.itemsTab.items[item_id]",
                    "    if item and (item.clusterJewel or (item.jewelData and item.jewelData.clusterJewelValid)) then",
                    "      table.insert(observed_cluster_sockets, node_id)",
                    "    end",
                    "  end",
                    "end",
                    "if #requested_cluster_sockets > 0 then",
                    "  validate_exact_ids('cluster_jewel_socket_ids', requested_cluster_sockets, observed_cluster_sockets)",
                    "end",
                    "if #requested_socketed_nodes > 0 then",
                    "  validate_exact_ids('socketed_jewel_node_ids', requested_socketed_nodes, observed_socketed_nodes)",
                    "end",
                    "if #requested_override_nodes > 0 then",
                    "  local observed_override_nodes = {}",
                    "  for node_id, _ in pairs(build.spec.hashOverrides) do",
                    "    table.insert(observed_override_nodes, node_id)",
                    "  end",
                    "  validate_exact_ids('override_carrier_node_ids', requested_override_nodes, observed_override_nodes)",
                    "end",
                    "if #requested_ascendancy_nodes > 0 or #requested_ascendancy_notables > 0 then",
                    "  local observed_ascendancy_nodes = {}",
                    "  local observed_ascendancy_notables = {}",
                    "  for node_id, node in pairs(build.spec.allocNodes) do",
                    "    if node_ascendancy_name(node) == build.spec.curAscendClassName and not node_is_ascendancy_start(node) then",
                    "      table.insert(observed_ascendancy_nodes, node_id)",
                    "      if node_is_notable(node) then",
                    "        table.insert(observed_ascendancy_notables, node_id)",
                    "      end",
                    "    end",
                    "  end",
                    "  validate_present_ids('ascendancy_node_ids', requested_ascendancy_nodes, observed_ascendancy_nodes)",
                    "  validate_present_ids('ascendancy_notable_node_ids', requested_ascendancy_notables, observed_ascendancy_notables)",
                    "end",
                    "runCallback('OnFrame')",
                )
            )
        )

    def export_build_xml(self) -> str:
        xml_text = self._bridge.execute("return build:SaveDB('code')", nret=1)[0]
        if not xml_text or not xml_text.strip():
            raise WorkerContractError("missing_export_payload", "PoB did not return a non-empty XML export payload.")
        return xml_text

    def verify_pob_import_code_string(self, import_code: str) -> dict[str, Any]:
        if not isinstance(import_code, str):
            raise WorkerContractError("runtime_protocol_failed", "import_code must be a string.")
        payload = self._bridge.execute(
            "\n".join(
                (
                    "local json = require('dkjson')",
                    f"local result = verifyImportCodeString({_lua_long_string(import_code)})",
                    "return json.encode(result)",
                )
            ),
            nret=1,
        )[0]
        if payload is None:
            raise WorkerContractError("runtime_protocol_failed", "Native import-code verifier returned no payload.")
        result = json.loads(payload)
        if not isinstance(result, dict):
            raise WorkerContractError("runtime_protocol_failed", "Native import-code verifier returned a non-object payload.")
        missing_input = result.pop("missing_input", "")
        invalid_reason = result.pop("invalid_reason", "")
        result["missing_inputs"] = (
            [missing_input] if isinstance(missing_input, str) and missing_input.strip() else []
        )
        result["invalid_reasons"] = (
            [invalid_reason] if isinstance(invalid_reason, str) and invalid_reason.strip() else []
        )
        return result

    def read_node_power_report(self, node_power_request: dict[str, Any] | None = None) -> dict[str, Any]:
        request = _normalize_node_power_report_request(node_power_request)
        config_set_id = request["config_set_id"]
        if config_set_id is not None:
            self._set_active_config_set(config_set_id)

        config_set_literal = "json.null" if config_set_id is None else _lua_long_string(config_set_id)
        max_depth_literal = "nil" if request["max_depth"] is None else str(request["max_depth"])
        max_rows_literal = "nil" if request["max_rows"] is None else str(request["max_rows"])
        family_by_stat = {stat: "defense" for stat in _NODE_POWER_DEFENSE_STATS}
        payload = self._bridge.execute(
            "\n".join(
                (
                    "local json = require('dkjson')",
                    f"local report_id = {_lua_long_string(request['report_id'])}",
                    f"local metric_stat = {_lua_long_string(request['metric_stat'])}",
                    f"local metric_lane = {_lua_long_string(request['metric_lane'])}",
                    f"local requested_config_set_id = {config_set_literal}",
                    f"local max_depth = {max_depth_literal}",
                    f"local max_rows = {max_rows_literal}",
                    f"local family_by_stat_json = {_lua_json_literal(family_by_stat)}",
                    "local family_by_stat, _, family_decode_err = json.decode(family_by_stat_json, 1, nil)",
                    "if type(family_by_stat) ~= 'table' then",
                    "  error('node-power metric family mapping must decode to a table: ' .. tostring(family_decode_err or 'unknown error'))",
                    "end",
                    "local function encode_null(value)",
                    "  if value == nil then return json.null end",
                    "  return value",
                    "end",
                    "local function empty_object()",
                    "  return setmetatable({}, { __jsontype = 'object' })",
                    "end",
                    "local function scalar_number(value)",
                    "  if type(value) == 'number' and value == value and value ~= math.huge and value ~= -math.huge then",
                    "    return value",
                    "  end",
                    "  return json.null",
                    "end",
                    "local function string_array(value)",
                    "  local result = {}",
                    "  if type(value) ~= 'table' then",
                    "    return result",
                    "  end",
                    "  for _, item in ipairs(value) do",
                    "    if type(item) == 'string' and item ~= '' then",
                    "      table.insert(result, item)",
                    "    end",
                    "  end",
                    "  return result",
                    "end",
                    "local source_refs = {",
                    "  {",
                    "    ref_id = 'pob.source.CalcsTab.PowerBuilder',",
                    "    ref_kind = 'pinned_pob_source',",
                    "    locator = 'vendor/pob/source/src/Classes/CalcsTab.lua:474-612',",
                    "    json_pointer = '/CalcsTabClass/PowerBuilder',",
                    "    summary = 'Pinned PoB PowerBuilder computes node.power for passive nodes.',",
                    "  },",
                    "  {",
                    "    ref_id = 'pob.source.TreeTab.BuildPowerReportList',",
                    "    ref_kind = 'pinned_pob_source',",
                    "    locator = 'vendor/pob/source/src/Classes/TreeTab.lua:1052-1165',",
                    "    json_pointer = '/TreeTabClass/BuildPowerReportList',",
                    "    summary = 'Pinned PoB BuildPowerReportList emits node-power report rows.',",
                    "  },",
                    "  {",
                    "    ref_id = 'pob.source.Data.powerStatList',",
                    "    ref_kind = 'pinned_pob_source',",
                    "    locator = 'vendor/pob/source/src/Modules/Data.lua:111-161',",
                    "    json_pointer = '/data/powerStatList',",
                    "    summary = 'Pinned PoB powerStatList defines node-power metric selectors.',",
                    "  },",
                    "}",
                    "local function active_config_set_id()",
                    "  local index = build and build.configTab and tonumber(build.configTab.activeConfigSetId) or 1",
                    "  if index == 1 then return 'config.main' end",
                    "  return 'config.' .. tostring(index)",
                    "end",
                    "local function selected_metric_payload(stat_data)",
                    "  if type(stat_data) ~= 'table' then",
                    "    return {",
                    "      stat = metric_stat,",
                    "      label = metric_stat,",
                    "      metric_family = 'unavailable',",
                    "      display_format = json.null,",
                    "      lower_is_better = false,",
                    "      percent_scaling = false,",
                    "    }",
                    "  end",
                    "  local stat = tostring(stat_data.stat or metric_stat)",
                    "  return {",
                    "    stat = stat,",
                    "    label = tostring(stat_data.label or stat),",
                    "    metric_family = family_by_stat[stat] or 'offense',",
                    "    display_format = stat_data.fmt or json.null,",
                    "    lower_is_better = stat_data.lowerIsBetter == true,",
                    "    percent_scaling = (stat_data.pc == true or stat_data.mod == true),",
                    "  }",
                    "end",
                    "local function unavailable(failure_state, summary)",
                    "  return {",
                    f"    schema_version = {_lua_long_string(_POB_HEADLESS_NODE_POWER_REPORT_SCHEMA_VERSION)},",
                    f"    record_kind = {_lua_long_string(_POB_HEADLESS_NODE_POWER_REPORT_RECORD_KIND)},",
                    "    status = 'unavailable',",
                    "    failure_state = failure_state,",
                    "    report_id = report_id,",
                    f"    source_kind = {_lua_long_string(_POB_NATIVE_NODE_POWER_REPORT_SOURCE_KIND)},",
                    f"    supported_path = {_lua_long_string(_POB_NATIVE_NODE_POWER_REPORT_SUPPORTED_PATH)},",
                    "    active_config_set_id = active_config_set_id(),",
                    "    metric_lane = metric_lane,",
                    "    selected_metric = selected_metric_payload(nil),",
                    "    max_depth = encode_null(max_depth),",
                    "    max_rows = encode_null(max_rows),",
                    "    row_count = 0,",
                    "    raw_report_row_count = 0,",
                    "    truncated = false,",
                    "    rows = {},",
                    "    source_refs = source_refs,",
                    "    limitations = { summary },",
                    "    unavailable_metrics = { metric_stat },",
                    "    boundary = {",
                    "      final_build_authority = false,",
                    "      final_tree_authority = false,",
                    "      passive_budget_authority = false,",
                    "      node_power_calculator_authority = false,",
                    "      publication_artifact_emitted = false,",
                    "    },",
                    "  }",
                    "end",
                    "if not (build and build.treeTab and build.calcsTab and data and data.powerStatList) then",
                    "  return json.encode(unavailable(",
                    "    'pob_native_node_power_report_unavailable_in_headless_runtime',",
                    "    'Pinned runtime is missing build.treeTab, build.calcsTab, or data.powerStatList.'",
                    "  ))",
                    "end",
                    "local selected_metric = nil",
                    "for _, stat_data in ipairs(data.powerStatList or {}) do",
                    "  if not stat_data.ignoreForNodes and tostring(stat_data.stat or '') == metric_stat then",
                    "    selected_metric = stat_data",
                    "    break",
                    "  end",
                    "end",
                    "if not selected_metric then",
                    "  local failure = metric_stat == 'HitChance'",
                    "    and 'pob_native_hit_chance_node_power_metric_unavailable'",
                    "    or 'pob_native_node_power_metric_unavailable'",
                    "  return json.encode(unavailable(failure, 'Pinned PoB powerStatList exposes no node-power metric named ' .. metric_stat .. '.'))",
                    "end",
                    "build.calcsTab.nodePowerMaxDepth = max_depth",
                    "build.treeTab:SetPowerCalc(selected_metric)",
                    "runCallback('OnFrame')",
                    "local guard = 0",
                    "while build.calcsTab.powerBuildFlag or build.calcsTab.powerBuilder do",
                    "  build.calcsTab:BuildPower()",
                    "  guard = guard + 1",
                    "  if guard > 100000 then",
                    "    error('Pinned PoB node-power builder did not finish within the bounded headless guard.')",
                    "  end",
                    "end",
                    "local native_rows = build.treeTab:BuildPowerReportList(selected_metric)",
                    "if type(native_rows) ~= 'table' then",
                    "  error('Pinned PoB BuildPowerReportList did not return a table.')",
                    "end",
                    "local selected_payload = selected_metric_payload(selected_metric)",
                    "local function node_for_row(row)",
                    "  if type(row) ~= 'table' or row.id == nil then",
                    "    return nil",
                    "  end",
                    "  local direct = build.spec and build.spec.nodes and build.spec.nodes[row.id] or nil",
                    "  if direct then return direct end",
                    "  if build.spec and build.spec.tree and build.spec.tree.clusterNodeMap then",
                    "    for _, node in pairs(build.spec.tree.clusterNodeMap) do",
                    "      if node.id == row.id then return node end",
                    "    end",
                    "  end",
                    "  return nil",
                    "end",
                    "local function target_kind(row, node)",
                    "  local row_type = tostring(row.type or (node and node.type) or 'passive')",
                    "  if row_type == 'Keystone' then return 'keystone' end",
                    "  if row_type == 'Notable' then",
                    "    if node and node.clusterJewel then return 'cluster_notable' end",
                    "    return 'notable'",
                    "  end",
                    "  if row_type == 'Normal' then return 'small_passive' end",
                    "  return row_type",
                    "end",
                    "local rows = {}",
                    "local total_rows = 0",
                    "for index, row in ipairs(native_rows) do",
                    "  total_rows = total_rows + 1",
                    "  if not max_rows or #rows < max_rows then",
                    "    local node = node_for_row(row)",
                    "    local path_dist = row.pathDist",
                    "    local point_cost = type(path_dist) == 'number' and path_dist > 0 and path_dist or json.null",
                    "    local path_power = scalar_number(row.pathPower)",
                    "    local value_per_point = path_power",
                    "    local node_power = scalar_number(row.power)",
                    "    local node_id = tonumber(row.id)",
                    "    local row_id = 'pob.node-power.' .. tostring(node_id or index) .. '.' .. metric_stat",
                    "    table.insert(rows, {",
                    "      row_id = row_id,",
                    "      source_id = node_id and ('passives:' .. tostring(node_id)) or ('passives:unknown.' .. tostring(index)),",
                    "      node_id = node_id or 0,",
                    "      node_name = tostring(row.name or (node and node.dn) or 'unknown node'),",
                    "      name = tostring(row.name or (node and node.dn) or 'unknown node'),",
                    "      target_kind = target_kind(row, node),",
                    "      metric_lane = metric_lane,",
                    "      metric_name = selected_payload.stat,",
                    "      metric_label = selected_payload.label,",
                    "      metric_family = selected_payload.metric_family,",
                    "      node_power_score = node_power,",
                    "      power = node_power,",
                    "      powerStr = row.powerStr or json.null,",
                    "      path_power_score = path_power,",
                    "      pathPower = path_power,",
                    "      pathPowerStr = row.pathPowerStr or json.null,",
                    "      path_dist = encode_null(path_dist),",
                    "      pathDist = encode_null(path_dist),",
                    "      point_cost = point_cost,",
                    "      value_per_point = value_per_point,",
                    "      allocated = row.allocated == true,",
                    "      source_locator = 'vendor/pob/source/src/Classes/TreeTab.lua:1052-1165#/BuildPowerReportList/rows/' .. tostring(index),",
                    "      source_context = {",
                    "        is_mastery = false,",
                    "        is_notable = row.type == 'Notable',",
                    "        is_keystone = row.type == 'Keystone',",
                    "        pob_row_type = tostring(row.type or ''),",
                    "        x = row.x or json.null,",
                    "        y = row.y or json.null,",
                    "      },",
                    "      display_stat = {",
                    "        stat = selected_payload.stat,",
                    "        label = selected_payload.label,",
                    "        lower_is_better = selected_payload.lower_is_better,",
                    "        percent_scaling = selected_payload.percent_scaling,",
                    "      },",
                    "      stats_or_supporting_text = node and string_array(node.sd) or {},",
                    "      metric_tags = {},",
                    "      facets = {},",
                    "      matched_branch_axes = {},",
                    "    })",
                    "  end",
                    "end",
                    "local limitations = {",
                    "  'The action reads one active PoB config/set lane at a time and reports metric_lane without mixing baseline and conditional states.',",
                    "}",
                    "if max_depth then",
                    "  table.insert(limitations, 'Pinned PoB nodePowerMaxDepth was bounded to ' .. tostring(max_depth) .. ' for this headless read.')",
                    "end",
                    "if max_rows and total_rows > max_rows then",
                    "  table.insert(limitations, 'Report rows were truncated from ' .. tostring(total_rows) .. ' to ' .. tostring(max_rows) .. ' after PoB-native sorting.')",
                    "end",
                    "local result = {",
                    f"  schema_version = {_lua_long_string(_POB_HEADLESS_NODE_POWER_REPORT_SCHEMA_VERSION)},",
                    f"  record_kind = {_lua_long_string(_POB_HEADLESS_NODE_POWER_REPORT_RECORD_KIND)},",
                    "  status = 'accepted',",
                    "  report_id = report_id,",
                    f"  source_kind = {_lua_long_string(_POB_NATIVE_NODE_POWER_REPORT_SOURCE_KIND)},",
                    f"  supported_path = {_lua_long_string(_POB_NATIVE_NODE_POWER_REPORT_SUPPORTED_PATH)},",
                    "  active_config_set_id = requested_config_set_id ~= json.null and requested_config_set_id or active_config_set_id(),",
                    "  metric_lane = metric_lane,",
                    "  selected_metric = selected_payload,",
                    "  max_depth = encode_null(max_depth),",
                    "  max_rows = encode_null(max_rows),",
                    "  row_count = #rows,",
                    "  raw_report_row_count = total_rows,",
                    "  truncated = max_rows ~= nil and total_rows > max_rows,",
                    "  rows = rows,",
                    "  source_refs = source_refs,",
                    "  limitations = limitations,",
                    "  unavailable_metrics = metric_stat == 'HitChance' and { 'HitChance' } or {},",
                    "  boundary = {",
                    "    final_build_authority = false,",
                    "    final_tree_authority = false,",
                    "    passive_budget_authority = false,",
                    "    node_power_calculator_authority = false,",
                    "    publication_artifact_emitted = false,",
                    "  },",
                    "}",
                    "return json.encode(result)",
                )
            ),
            nret=1,
        )[0]
        if payload is None:
            raise WorkerContractError("runtime_protocol_failed", "Pinned runtime returned no node-power report payload.")
        try:
            result = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise WorkerContractError("runtime_protocol_failed", "Pinned runtime returned invalid node-power report JSON.") from exc
        if not isinstance(result, dict):
            raise WorkerContractError("runtime_protocol_failed", "Pinned runtime node-power report payload must decode to an object.")
        return result

    def read_ascendancy_node_report(self) -> dict[str, Any]:
        payload = self._bridge.execute(
            "\n".join(
                (
                    "local json = require('dkjson')",
                    "local function encode_null(value)",
                    "  if value == nil or value == '' or value == 'None' then return json.null end",
                    "  return value",
                    "end",
                    "local function string_array(values)",
                    "  local result = {}",
                    "  if type(values) ~= 'table' then return result end",
                    "  for _, value in ipairs(values) do",
                    "    if type(value) == 'string' and value ~= '' then table.insert(result, value) end",
                    "  end",
                    "  return result",
                    "end",
                    "local function node_display_name(node)",
                    "  return tostring(node.dn or node.name or node.label or 'unknown node')",
                    "end",
                    "local function node_ascendancy_name(node)",
                    "  local value = node.ascendancyName or node.ascendancy_name",
                    "  if type(value) == 'string' and value ~= '' then return value end",
                    "  return nil",
                    "end",
                    "local function node_is_ascendancy_start(node)",
                    "  return node.isAscendancyStart == true or node.ascendancyStart == true",
                    "end",
                    "local function node_is_notable(node)",
                    "  return node.isNotable == true or node.notable == true or node.type == 'Notable'",
                    "end",
                    "local function node_id_value(node_id, node)",
                    "  return tonumber(node.id or node.nodeId or node_id)",
                    "end",
                    "local function collect_link_ids(node)",
                    "  local result = {}",
                    "  local seen = {}",
                    "  local function add(value)",
                    "    local numeric = tonumber(value)",
                    "    if numeric and not seen[numeric] then",
                    "      seen[numeric] = true",
                    "      table.insert(result, numeric)",
                    "    end",
                    "  end",
                    "  local fields = { 'out', 'outNodes', 'outs', 'links', 'connections' }",
                    "  for _, field_name in ipairs(fields) do",
                    "    local values = node[field_name]",
                    "    if type(values) == 'table' then",
                    "      for key, entry in pairs(values) do",
                    "        if type(entry) == 'table' then",
                    "          add(entry.id or entry.nodeId or entry[1])",
                    "        elseif type(entry) == 'number' or type(entry) == 'string' then",
                    "          add(entry)",
                    "        else",
                    "          add(key)",
                    "        end",
                    "      end",
                    "    end",
                    "  end",
                    "  table.sort(result)",
                    "  return result",
                    "end",
                    "local active_ascendancy = build.spec.curAscendClassName",
                    "local rows = {}",
                    "for node_id, node in pairs(build.spec.tree.nodes or {}) do",
                    "  if node_ascendancy_name(node) == active_ascendancy and not node_is_ascendancy_start(node) then",
                    "    local numeric_id = node_id_value(node_id, node)",
                    "    table.insert(rows, {",
                    "      row_id = 'pob.ascendancy-node.' .. tostring(numeric_id),",
                    "      node_id = numeric_id,",
                    "      node_name = node_display_name(node),",
                    "      ascendancy_name = active_ascendancy,",
                    "      target_kind = node_is_notable(node) and 'ascendancy_notable' or 'ascendancy_small_passive',",
                    "      is_notable = node_is_notable(node),",
                    "      is_ascendancy_start = node_is_ascendancy_start(node),",
                    "      allocated = build.spec.allocNodes[numeric_id] ~= nil,",
                    "      stats_or_supporting_text = string_array(node.sd),",
                    "      connected_node_ids = collect_link_ids(node),",
                    "      source_locator = 'pinned_pob_runtime.build.spec.tree.nodes/' .. tostring(numeric_id),",
                    "    })",
                    "  end",
                    "end",
                    "table.sort(rows, function(left, right)",
                    "  if left.is_notable ~= right.is_notable then return left.is_notable end",
                    "  return tostring(left.node_name) < tostring(right.node_name)",
                    "end)",
                    "local result = {",
                    "  schema_version = '0.1.0',",
                    "  record_kind = 'pob_ascendancy_node_report',",
                    "  status = 'accepted',",
                    "  source_kind = 'pinned_pob_runtime_ascendancy_tree_readback',",
                    "  active_class_id = encode_null(build.spec.curClassName),",
                    "  active_ascendancy_id = encode_null(active_ascendancy),",
                    "  row_count = #rows,",
                    "  rows = rows,",
                    "  boundary = {",
                    "    final_build_authority = false,",
                    "    final_tree_authority = false,",
                    "    ascendancy_selection_authority = false,",
                    "    publication_artifact_emitted = false,",
                    "  },",
                    "  warnings = {},",
                    "}",
                    "return json.encode(result)",
                )
            ),
            nret=1,
        )[0]
        if payload is None:
            raise WorkerContractError("runtime_protocol_failed", "Ascendancy node report returned no payload.")
        try:
            result = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise WorkerContractError("runtime_protocol_failed", "Ascendancy node report returned invalid JSON.") from exc
        if not isinstance(result, dict):
            raise WorkerContractError("runtime_protocol_failed", "Ascendancy node report payload must decode to an object.")
        return result

    def _extract_skill_set_indices(self, xml_text: str) -> tuple[int, list[int]]:
        root = self._parse_build_xml(xml_text)
        skills_node = root.find("Skills")
        if skills_node is None:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "Pinned PoB export is missing the Skills node required for skill read-back.",
            )
        try:
            active_skill_set_index = int(skills_node.attrib.get("activeSkillSet", "1"))
        except ValueError as exc:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "Pinned PoB export recorded a non-integer activeSkillSet value.",
            ) from exc
        skill_set_indices: list[int] = []
        for index, skill_set_node in enumerate(skills_node.findall("SkillSet"), start=1):
            raw_id = skill_set_node.attrib.get("id", str(index))
            try:
                skill_set_index = int(raw_id)
            except ValueError as exc:
                raise WorkerContractError(
                    "runtime_protocol_failed",
                    "Pinned PoB export recorded a non-integer SkillSet id.",
                ) from exc
            if skill_set_index < 1:
                raise WorkerContractError(
                    "runtime_protocol_failed",
                    "Pinned PoB export recorded a SkillSet id below 1.",
                )
            skill_set_indices.append(skill_set_index)
        if not skill_set_indices:
            skill_set_indices = [1]
        if active_skill_set_index not in skill_set_indices:
            skill_set_indices.insert(0, active_skill_set_index)
        return active_skill_set_index, skill_set_indices

    def _xml_with_active_skill_set(self, xml_text: str, skill_set_index: int) -> str:
        root = self._parse_build_xml(xml_text)
        skills_node = root.find("Skills")
        if skills_node is None:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "Pinned PoB export is missing the Skills node required for skill read-back.",
            )
        skills_node.set("activeSkillSet", str(skill_set_index))
        return _serialize_xml(root)

    def _snapshot_rich_skill_state(self) -> dict[str, Any]:
        export_xml = self.export_build_xml()
        active_skill_set_index, skill_set_indices = self._extract_skill_set_indices(export_xml)
        skill_sets: list[dict[str, Any]] = []
        active_skill_set_state: dict[str, Any] | None = None
        try:
            for skill_set_index in skill_set_indices:
                self.load_reopen_source(self._xml_with_active_skill_set(export_xml, skill_set_index))
                skill_set_state = self._snapshot_active_skill_set_state()
                skill_sets.append(skill_set_state)
                if skill_set_index == active_skill_set_index:
                    active_skill_set_state = skill_set_state
        finally:
            self.load_reopen_source(export_xml)

        if active_skill_set_state is None:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "Could not observe the active skill set during skill read-back.",
            )

        nondefault_state = len(skill_sets) > 1 or any(
            int(skill_set["socket_group_count"]) > 0 for skill_set in skill_sets
        )
        payload = {
            "state_kind": "nondefault" if nondefault_state else "empty",
            "active_skill_set_id": active_skill_set_state["skill_set_id"],
            "socket_group_count": active_skill_set_state["socket_group_count"],
            "socket_groups": active_skill_set_state["socket_groups"],
            "main_socket_group_id": active_skill_set_state["main_socket_group_id"],
            "main_active_skill_id": active_skill_set_state["main_active_skill_id"],
        }
        if nondefault_state:
            payload["skill_set_count"] = len(skill_sets)
            payload["skill_set_ids"] = [skill_set["skill_set_id"] for skill_set in skill_sets]
            payload["skill_sets"] = skill_sets
        return payload

    def _snapshot_active_skill_set_state(self) -> dict[str, Any]:
        chunk = "\n".join(
            (
                "local json = require('dkjson')",
                "local function encode_null(value)",
                "  if value == nil or value == '' or value == 'None' then",
                "    return json.null",
                "  end",
                "  return tostring(value)",
                "end",
                "local function normalize_skill_set_id(index)",
                f"  if tonumber(index) == 1 then return {_lua_long_string(_CANONICAL_SKILLS_ID)} end",
                "  return 'skills.' .. tostring(index)",
                "end",
                "local function normalize_item_set_id(index)",
                "  if type(index) ~= 'number' then",
                "    return json.null",
                "  end",
                "  index = math.floor(index)",
                "  if index < 1 then",
                "    return json.null",
                "  end",
                f"  if index == 1 then return {_lua_long_string(_CANONICAL_ITEM_SET_ID)} end",
                "  return 'itemset.' .. tostring(index)",
                "end",
                "local function normalize_socket_group_id(skill_set_id, index)",
                "  return tostring(skill_set_id) .. '.socket_group.' .. tostring(index)",
                "end",
                "local function normalize_gem_entry_id(socket_group_id, index)",
                "  return tostring(socket_group_id) .. '.gem.' .. tostring(index)",
                "end",
                "local function normalize_active_skill_id(socket_group_id, index)",
                "  return tostring(socket_group_id) .. '.active_skill.' .. tostring(index)",
                "end",
                "local function source_kind(socket_group)",
                "  if socket_group.sourceItem then return 'item' end",
                "  if socket_group.sourceNode then return 'node' end",
                "  if socket_group.source == 'Explode' then return 'explode' end",
                "  if socket_group.source ~= nil then return 'other' end",
                "  return 'manual'",
                "end",
                "local function source_label(socket_group)",
                "  if socket_group.sourceItem and socket_group.sourceItem.name then",
                "    return socket_group.sourceItem.name",
                "  end",
                "  if socket_group.sourceNode and socket_group.sourceNode.name then",
                "    return socket_group.sourceNode.name",
                "  end",
                "  if socket_group.source ~= nil then",
                "    return tostring(socket_group.source)",
                "  end",
                "  return json.null",
                "end",
                "local function collect_support_links(active_skill, gem_entry_lookup)",
                "  local result = {}",
                "  if type(active_skill.effectList) ~= 'table' then",
                "    return result",
                "  end",
                "  for _, effect in ipairs(active_skill.effectList) do",
                "    local granted_effect = effect and effect.grantedEffect or nil",
                "    if granted_effect and granted_effect.support then",
                "      table.insert(result, {",
                "        name = encode_null(granted_effect.name),",
                "        skill_id = encode_null(granted_effect.id),",
                "        from_item = (granted_effect.fromItem == true)",
                "          or (effect.srcInstance and effect.srcInstance.fromItem == true)",
                "          or false,",
                "        source_gem_entry_id = (effect.srcInstance and gem_entry_lookup[effect.srcInstance]) or json.null,",
                "      })",
                "    end",
                "  end",
                "  return result",
                "end",
                "local function serialize_active_skill(socket_group_id, index, active_skill, gem_entry_lookup)",
                "  local active_effect = active_skill and active_skill.activeEffect or nil",
                "  local src_instance = active_effect and active_effect.srcInstance or nil",
                "  local granted_effect = active_effect and active_effect.grantedEffect or nil",
                "  local support_links = collect_support_links(active_skill, gem_entry_lookup)",
                "  local minion_skill_name = json.null",
                "  local minion_skill_index = src_instance and src_instance.skillMinionSkill or nil",
                "  if active_skill and active_skill.minion and type(active_skill.minion.activeSkillList) == 'table' then",
                "    local selected_skill = active_skill.minion.activeSkillList[minion_skill_index or 1]",
                "    local minion_effect = selected_skill and selected_skill.activeEffect or nil",
                "    if minion_effect and minion_effect.grantedEffect and minion_effect.grantedEffect.name then",
                "      minion_skill_name = minion_effect.grantedEffect.name",
                "    end",
                "  end",
                "  local part_name = json.null",
                "  if granted_effect and type(granted_effect.parts) == 'table' and src_instance and src_instance.skillPart and granted_effect.parts[src_instance.skillPart] then",
                "    part_name = encode_null(granted_effect.parts[src_instance.skillPart].name)",
                "  end",
                "  return {",
                "    active_skill_id = normalize_active_skill_id(socket_group_id, index),",
                "    name = granted_effect and encode_null(granted_effect.name) or json.null,",
                "    triggered = ((src_instance and src_instance.triggered == true)",
                "      or (active_skill.skillData and active_skill.skillData.triggered)",
                "      or (active_skill.skillFlags and active_skill.skillFlags.triggered)) and true or false,",
                "    trigger_chance = src_instance and src_instance.triggerChance or json.null,",
                "    trigger_label = active_skill.infoTrigger or active_skill.trigger or json.null,",
                "    part_index = src_instance and src_instance.skillPart or json.null,",
                "    part_name = part_name,",
                "    stage_count = src_instance and src_instance.skillStageCount or json.null,",
                "    mine_count = src_instance and src_instance.skillMineCount or json.null,",
                "    minion_id = src_instance and src_instance.skillMinion or json.null,",
                "    minion_item_set_id = src_instance and normalize_item_set_id(src_instance.skillMinionItemSet) or json.null,",
                "    minion_skill_index = minion_skill_index or json.null,",
                "    minion_skill_name = minion_skill_name,",
                "    support_link_count = #support_links,",
                "    support_links = support_links,",
                "  }",
                "end",
                "local function serialize_gem(socket_group_id, index, gem_instance)",
                "  local granted_effect = (gem_instance.gemData and gem_instance.gemData.grantedEffect) or gem_instance.grantedEffect",
                "  return {",
                "    gem_entry_id = normalize_gem_entry_id(socket_group_id, index),",
                "    socket_index = index,",
                "    gem_name = encode_null(gem_instance.nameSpec),",
                "    skill_id = encode_null(gem_instance.skillId),",
                "    gem_id = (gem_instance.gemData and encode_null(gem_instance.gemData.gameId)) or json.null,",
                "    is_support = (granted_effect and granted_effect.support == true) or false,",
                "    level = tonumber(gem_instance.level) or 0,",
                "    quality = tonumber(gem_instance.quality) or 0,",
                "    enabled = gem_instance.enabled == true,",
                "    count = tonumber(gem_instance.count) or 1,",
                "    enable_global_1 = gem_instance.enableGlobal1 ~= false,",
                "    enable_global_2 = gem_instance.enableGlobal2 == true,",
                "    skill_part = gem_instance.skillPart or json.null,",
                "    skill_stage_count = gem_instance.skillStageCount or json.null,",
                "    skill_mine_count = gem_instance.skillMineCount or json.null,",
                "    skill_minion = gem_instance.skillMinion or json.null,",
                "    skill_minion_item_set_id = normalize_item_set_id(gem_instance.skillMinionItemSet),",
                "    skill_minion_skill_index = gem_instance.skillMinionSkill or json.null,",
                "    triggered = gem_instance.triggered == true,",
                "    trigger_chance = gem_instance.triggerChance or json.null,",
                "  }",
                "end",
                "local function serialize_socket_group(skill_set_id, index, socket_group)",
                "  local socket_group_id = normalize_socket_group_id(skill_set_id, index)",
                "  local gems = {}",
                "  local gem_entry_lookup = {}",
                "  for gem_index, gem_instance in ipairs(socket_group.gemList or {}) do",
                "    local gem_payload = serialize_gem(socket_group_id, gem_index, gem_instance)",
                "    gems[gem_index] = gem_payload",
                "    gem_entry_lookup[gem_instance] = gem_payload.gem_entry_id",
                "  end",
                "  local active_skill_entries = {}",
                "  for active_skill_index, active_skill in ipairs(socket_group.displaySkillList or {}) do",
                "    active_skill_entries[active_skill_index] = serialize_active_skill(",
                "      socket_group_id,",
                "      active_skill_index,",
                "      active_skill,",
                "      gem_entry_lookup",
                "    )",
                "  end",
                "  local main_active_skill_index = tonumber(socket_group.mainActiveSkill) or 1",
                "  return {",
                "    socket_group_id = socket_group_id,",
                "    label = encode_null(socket_group.label),",
                "    slot = encode_null(socket_group.slot),",
                "    slot_enabled = socket_group.slotEnabled ~= false,",
                "    source = encode_null(socket_group.source),",
                "    source_kind = source_kind(socket_group),",
                "    source_label = source_label(socket_group),",
                "    enabled = socket_group.enabled == true,",
                "    include_in_full_dps = socket_group.includeInFullDPS == true,",
                "    group_count = tonumber(socket_group.groupCount) or 1,",
                "    gem_count = #gems,",
                "    gems = gems,",
                "    active_skill_entry_count = #active_skill_entries,",
                "    active_skill_entries = active_skill_entries,",
                "    main_active_skill_index = main_active_skill_index,",
                "    main_active_skill_id = active_skill_entries[main_active_skill_index]",
                "      and active_skill_entries[main_active_skill_index].active_skill_id",
                "      or json.null,",
                "  }",
                "end",
                "local active_skill_set_index = tonumber(build.skillsTab.activeSkillSetId) or 1",
                "local active_skill_set = build.skillsTab.skillSets[active_skill_set_index] or {}",
                "local skill_set_id = normalize_skill_set_id(active_skill_set_index)",
                "local socket_groups = {}",
                "local socket_group_ids = {}",
                "for socket_group_index, socket_group in ipairs(build.skillsTab.socketGroupList or {}) do",
                "  local socket_group_payload = serialize_socket_group(skill_set_id, socket_group_index, socket_group)",
                "  socket_groups[socket_group_index] = socket_group_payload",
                "  socket_group_ids[socket_group_index] = socket_group_payload.socket_group_id",
                "end",
                "local main_socket_group_index = tonumber(build.mainSocketGroup) or 1",
                "local main_socket_group = socket_groups[main_socket_group_index]",
                "return json.encode({",
                "  skill_set_id = skill_set_id,",
                "  title = encode_null(active_skill_set.title),",
                "  socket_group_count = #socket_groups,",
                "  socket_group_ids = socket_group_ids,",
                "  socket_groups = socket_groups,",
                "  main_socket_group_id = main_socket_group and main_socket_group.socket_group_id or json.null,",
                "  main_active_skill_id = main_socket_group and main_socket_group.main_active_skill_id or json.null,",
                "})",
            )
        )
        payload = self._bridge.execute(chunk, nret=1)[0]
        if payload is None:
            raise WorkerContractError("runtime_protocol_failed", "PoB skill snapshot returned no payload.")
        return json.loads(payload)

    def _snapshot_config_state(self) -> dict[str, Any]:
        return self._config_state_from_xml(self.export_build_xml())

    def _config_state_from_xml(self, xml_text: str) -> dict[str, Any]:
        root = self._parse_build_xml(xml_text)
        build_node = root.find("Build")
        config_node = root.find("Config")
        if build_node is None or config_node is None:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "Pinned PoB export is missing Build or Config nodes required for config read-back.",
            )

        raw_config_sets = self._collect_raw_config_sets(config_node)
        raw_config_sets_by_index = {
            config_set["config_set_index"]: config_set for config_set in raw_config_sets
        }
        active_config_set_index = _parse_positive_int_attr(
            config_node.attrib.get("activeConfigSet"),
            field_name="Config.activeConfigSet",
            default=1,
        )
        if active_config_set_index not in raw_config_sets_by_index:
            active_config_set_index = raw_config_sets[0]["config_set_index"]

        is_nondefault = len(raw_config_sets) > 1 or any(
            self._config_set_has_nondefault_state(
                config_set,
                build_node=build_node,
                is_active=config_set["config_set_index"] == active_config_set_index,
            )
            for config_set in raw_config_sets
        )
        if not is_nondefault:
            return {
                "state_kind": "default",
                "active_config_set_id": _CANONICAL_CONFIG_ID,
                "enabled_conditions": [],
                "custom_values": {},
                "notes": None,
                "bandit": None,
                "pantheon_major": None,
                "pantheon_minor": None,
                "engine_default_fields": {},
            }

        config_set_summaries: dict[str, dict[str, Any]] = {}
        config_set_ids: list[str] = []
        baseline_config_set_id: str | None = None
        conditional_config_set_id: str | None = None
        for config_set in raw_config_sets:
            summary = self._build_config_state_summary(
                config_set,
                build_node=build_node,
                is_active=config_set["config_set_index"] == active_config_set_index,
                include_default_enemy_state=True,
                config_set_count=len(raw_config_sets),
            )
            config_set_ids.append(summary["config_set_id"])
            config_set_summaries[summary["config_set_id"]] = summary
            if summary["state_role"] == "baseline" and baseline_config_set_id is None:
                baseline_config_set_id = summary["config_set_id"]
            if summary["state_role"] == "conditional" and conditional_config_set_id is None:
                conditional_config_set_id = summary["config_set_id"]

        active_config_set_id = _normalize_config_set_id(active_config_set_index)
        active_summary = config_set_summaries[active_config_set_id]
        state = {
            "state_kind": "nondefault",
            "active_config_set_id": active_config_set_id,
            "enabled_conditions": list(active_summary["enabled_conditions"]),
            "custom_values": dict(active_summary["custom_values"]),
            "notes": active_summary["notes"],
            "bandit": active_summary["bandit"],
            "pantheon_major": active_summary["pantheon_major"],
            "pantheon_minor": active_summary["pantheon_minor"],
            "engine_default_fields": dict(active_summary["engine_default_fields"]),
            "config_set_ids": config_set_ids,
            "config_sets": config_set_summaries,
        }
        if baseline_config_set_id is not None:
            state["baseline_config_set_id"] = baseline_config_set_id
        if conditional_config_set_id is not None:
            state["conditional_config_set_id"] = conditional_config_set_id
        return state

    def _collect_raw_config_sets(self, config_node: ElementTree.Element) -> list[dict[str, Any]]:
        config_set_nodes = [child for child in list(config_node) if child.tag == "ConfigSet"]
        if not config_set_nodes:
            return [
                {
                    "config_set_index": 1,
                    "config_set_id": _CANONICAL_CONFIG_ID,
                    "title": "Default",
                    "inputs": self._collect_supported_config_inputs(config_node, field_prefix="Config"),
                }
            ]

        raw_config_sets: list[dict[str, Any]] = []
        for ordinal, config_set_node in enumerate(config_set_nodes, start=1):
            config_set_index = _parse_positive_int_attr(
                config_set_node.attrib.get("id"),
                field_name=f"ConfigSet[{ordinal}].id",
                default=ordinal,
            )
            raw_config_sets.append(
                {
                    "config_set_index": config_set_index,
                    "config_set_id": _normalize_config_set_id(config_set_index),
                    "title": (config_set_node.attrib.get("title") or "Default").strip() or "Default",
                    "inputs": self._collect_supported_config_inputs(
                        config_set_node,
                        field_prefix=f"ConfigSet[{config_set_index}]",
                    ),
                }
            )
        raw_config_sets.sort(key=lambda entry: int(entry["config_set_index"]))
        return raw_config_sets

    def _collect_supported_config_inputs(
        self,
        parent_node: ElementTree.Element,
        *,
        field_prefix: str,
    ) -> dict[str, str | bool | int]:
        supported_inputs: dict[str, str | bool | int] = {}
        for child_index, child in enumerate(list(parent_node), start=1):
            if child.tag != "Input":
                continue
            input_name = child.attrib.get("name")
            if input_name not in _CONFIG_DEFAULT_INPUTS:
                continue
            supported_inputs[input_name] = self._decode_supported_config_input(
                child,
                field_name=f"{field_prefix}.Input[{child_index}]",
            )
        return supported_inputs

    def _decode_supported_config_input(
        self,
        input_node: ElementTree.Element,
        *,
        field_name: str,
    ) -> str | bool | int:
        input_name = input_node.attrib.get("name")
        if not input_name:
            raise WorkerContractError("runtime_protocol_failed", f"{field_name} is missing a name attribute.")
        if "boolean" in input_node.attrib:
            raw_value = input_node.attrib["boolean"]
            if raw_value not in {"true", "false"}:
                raise WorkerContractError(
                    "runtime_protocol_failed",
                    f"{field_name}.{input_name} must encode a true/false boolean value.",
                )
            return raw_value == "true"
        if "number" in input_node.attrib:
            try:
                return int(input_node.attrib["number"])
            except ValueError as exc:
                raise WorkerContractError(
                    "runtime_protocol_failed",
                    f"{field_name}.{input_name} must encode an integer number.",
                ) from exc
        if "string" in input_node.attrib:
            return input_node.attrib["string"]
        raise WorkerContractError(
            "runtime_protocol_failed",
            f"{field_name}.{input_name} must encode a string, number, or boolean value.",
        )

    def _config_set_has_nondefault_state(
        self,
        config_set: dict[str, Any],
        *,
        build_node: ElementTree.Element,
        is_active: bool,
    ) -> bool:
        if config_set["title"] != "Default":
            return True
        for input_name in _CONFIG_DEFAULT_INPUTS:
            resolved_value, _ = self._resolve_config_input_value(
                config_set["inputs"],
                input_name,
                build_node=build_node,
                is_active=is_active,
            )
            if resolved_value != _CONFIG_DEFAULT_INPUTS[input_name]:
                return True
        return False

    def _resolve_config_input_value(
        self,
        input_values: dict[str, Any],
        input_name: str,
        *,
        build_node: ElementTree.Element,
        is_active: bool,
    ) -> tuple[str | bool | int | None, bool]:
        if input_name in input_values:
            return input_values[input_name], False
        if is_active and input_name in {"bandit", "pantheonMajorGod", "pantheonMinorGod"}:
            build_value = build_node.attrib.get(input_name)
            if build_value is not None:
                return build_value, build_value == _CONFIG_DEFAULT_INPUTS[input_name]
        return _CONFIG_DEFAULT_INPUTS[input_name], True

    def _build_config_state_summary(
        self,
        config_set: dict[str, Any],
        *,
        build_node: ElementTree.Element,
        is_active: bool,
        include_default_enemy_state: bool,
        config_set_count: int,
    ) -> dict[str, Any]:
        bandit_raw, _ = self._resolve_config_input_value(
            config_set["inputs"],
            "bandit",
            build_node=build_node,
            is_active=is_active,
        )
        pantheon_major_raw, _ = self._resolve_config_input_value(
            config_set["inputs"],
            "pantheonMajorGod",
            build_node=build_node,
            is_active=is_active,
        )
        pantheon_minor_raw, _ = self._resolve_config_input_value(
            config_set["inputs"],
            "pantheonMinorGod",
            build_node=build_node,
            is_active=is_active,
        )
        enemy_is_boss_raw, enemy_is_boss_defaulted = self._resolve_config_input_value(
            config_set["inputs"],
            "enemyIsBoss",
            build_node=build_node,
            is_active=is_active,
        )
        buff_onslaught_raw, _ = self._resolve_config_input_value(
            config_set["inputs"],
            "buffOnslaught",
            build_node=build_node,
            is_active=is_active,
        )
        buff_fortification_raw, _ = self._resolve_config_input_value(
            config_set["inputs"],
            "buffFortification",
            build_node=build_node,
            is_active=is_active,
        )
        using_flask_raw, _ = self._resolve_config_input_value(
            config_set["inputs"],
            "conditionUsingFlask",
            build_node=build_node,
            is_active=is_active,
        )
        enemy_shocked_raw, _ = self._resolve_config_input_value(
            config_set["inputs"],
            "conditionEnemyShocked",
            build_node=build_node,
            is_active=is_active,
        )
        enemy_ignited_raw, _ = self._resolve_config_input_value(
            config_set["inputs"],
            "conditionEnemyIgnited",
            build_node=build_node,
            is_active=is_active,
        )
        shock_effect_raw, _ = self._resolve_config_input_value(
            config_set["inputs"],
            "conditionShockEffect",
            build_node=build_node,
            is_active=is_active,
        )

        bandit = None if bandit_raw in (None, "None") else str(bandit_raw)
        pantheon_major = None if pantheon_major_raw in (None, "None") else str(pantheon_major_raw)
        pantheon_minor = None if pantheon_minor_raw in (None, "None") else str(pantheon_minor_raw)
        enemy_is_boss = str(enemy_is_boss_raw or _CONFIG_DEFAULT_INPUTS["enemyIsBoss"])
        buffs = {
            "onslaught": bool(buff_onslaught_raw),
            "fortification": bool(buff_fortification_raw),
        }
        combat_conditions = {
            "using_flask": bool(using_flask_raw),
        }
        enemy_state = {
            "is_boss": enemy_is_boss,
            "is_shocked": bool(enemy_shocked_raw),
            "is_ignited": bool(enemy_ignited_raw),
            "shock_effect": None if shock_effect_raw is None else int(shock_effect_raw),
        }

        enabled_conditions = sorted(
            condition_id
            for input_name, condition_id in _CONFIG_ENABLED_CONDITION_IDS.items()
            if (
                (input_name == "buffOnslaught" and buffs["onslaught"])
                or (input_name == "buffFortification" and buffs["fortification"])
                or (input_name == "conditionUsingFlask" and combat_conditions["using_flask"])
                or (input_name == "conditionEnemyShocked" and enemy_state["is_shocked"])
                or (input_name == "conditionEnemyIgnited" and enemy_state["is_ignited"])
            )
        )
        custom_values: dict[str, Any] = {}
        engine_default_fields: dict[str, Any] = {}
        if include_default_enemy_state or enemy_state["is_boss"] != _CONFIG_DEFAULT_INPUTS["enemyIsBoss"]:
            custom_values[_CONFIG_CUSTOM_VALUE_KEYS["enemyIsBoss"]] = enemy_state["is_boss"]
            if enemy_is_boss_defaulted:
                engine_default_fields[_CONFIG_CUSTOM_VALUE_KEYS["enemyIsBoss"]] = enemy_state["is_boss"]
        if enemy_state["shock_effect"] is not None:
            custom_values[_CONFIG_CUSTOM_VALUE_KEYS["conditionShockEffect"]] = enemy_state["shock_effect"]
        if enemy_state["is_ignited"]:
            custom_values[_CONFIG_CUSTOM_VALUE_KEYS["conditionEnemyIgnited"]] = True

        return {
            "config_set_id": config_set["config_set_id"],
            "title": config_set["title"],
            "state_role": self._config_state_role(
                config_set_id=config_set["config_set_id"],
                title=config_set["title"],
                config_set_count=config_set_count,
            ),
            "enabled_conditions": enabled_conditions,
            "custom_values": custom_values,
            "notes": None,
            "bandit": bandit,
            "pantheon_major": pantheon_major,
            "pantheon_minor": pantheon_minor,
            "engine_default_fields": engine_default_fields,
            "buffs": buffs,
            "combat_conditions": combat_conditions,
            "enemy_state": enemy_state,
        }

    def _config_state_role(
        self,
        *,
        config_set_id: str,
        title: str,
        config_set_count: int,
    ) -> str | None:
        normalized_title = title.strip().lower()
        if normalized_title == "baseline":
            return "baseline"
        if normalized_title == "conditional":
            return "conditional"
        if config_set_count == 2 and config_set_id == _CANONICAL_CONFIG_ID:
            return "baseline"
        if config_set_count == 2 and config_set_id == "config.2":
            return "conditional"
        return None

    def _set_active_config_set(self, config_set_id: str) -> None:
        config_set_index = _normalize_config_set_index(config_set_id, "config_set_id")
        self._bridge.execute(
            "\n".join(
                (
                    f"local config_set_index = {config_set_index}",
                    "if not build or not build.configTab then",
                    "  error('Pinned runtime is missing build.configTab during calc snapshot read-back.')",
                    "end",
                    "if not build.configTab.configSets or not build.configTab.configSets[config_set_index] then",
                    "  error('Pinned runtime is missing config set ' .. tostring(config_set_index) .. ' during calc snapshot read-back.')",
                    "end",
                    "build.configTab:SetActiveConfigSet(config_set_index)",
                    "runCallback('OnFrame')",
                )
            )
        )

    def _snapshot_calc_section(
        self,
        *,
        config_set_id: str,
        state_role: str,
        config_summary: dict[str, Any],
    ) -> dict[str, Any]:
        self._set_active_config_set(config_set_id)
        chunk = "\n".join(
            (
                "local json = require('dkjson')",
                f"local family_by_stat_json = {_lua_json_literal(_CALC_DISPLAY_FAMILY_BY_STAT)}",
                f"local family_order_json = {_lua_json_literal(list(_CALC_DISPLAY_FAMILY_ORDER))}",
                "local family_by_stat, _, family_decode_err = json.decode(family_by_stat_json, 1, nil)",
                "if type(family_by_stat) ~= 'table' then",
                "  error('family_by_stat mapping must decode to a table: ' .. tostring(family_decode_err or 'unknown error'))",
                "end",
                "local family_order, _, order_decode_err = json.decode(family_order_json, 1, nil)",
                "if type(family_order) ~= 'table' then",
                "  error('family_order mapping must decode to a table: ' .. tostring(order_decode_err or 'unknown error'))",
                "end",
                "local function empty_object()",
                "  return setmetatable({}, { __jsontype = 'object' })",
                "end",
                "local function scalar_value(value)",
                "  local value_type = type(value)",
                "  if value_type == 'number' then",
                "    if value == value and value ~= math.huge and value ~= -math.huge then",
                "      return value",
                "    end",
                "    return nil",
                "  end",
                "  if value_type == 'string' or value_type == 'boolean' then",
                "    return value",
                "  end",
                "  return nil",
                "end",
                "local function collect_scalar_output(output)",
                "  local result = empty_object()",
                "  if type(output) ~= 'table' then",
                "    return result",
                "  end",
                "  local keys = {}",
                "  for key, value in pairs(output) do",
                "    if type(key) == 'string' and scalar_value(value) ~= nil then",
                "      table.insert(keys, key)",
                "    end",
                "  end",
                "  table.sort(keys)",
                "  for _, key in ipairs(keys) do",
                "    result[key] = output[key]",
                "  end",
                "  return result",
                "end",
                "local function family_id_for_stat(stat_name)",
                "  return family_by_stat[stat_name] or 'offense'",
                "end",
                "local function one_flag_matches(flag, skill_flags)",
                "  if flag == nil then",
                "    return true",
                "  end",
                "  if type(flag) == 'table' then",
                "    for _, item in ipairs(flag) do",
                "      if not one_flag_matches(item, skill_flags) then",
                "        return false",
                "      end",
                "    end",
                "    return true",
                "  end",
                "  return skill_flags and skill_flags[flag] == true",
                "end",
                "local function matches_flags(flag, not_flag, skill_flags)",
                "  if not one_flag_matches(flag, skill_flags) then",
                "    return false",
                "  end",
                "  if not_flag == nil then",
                "    return true",
                "  end",
                "  if type(not_flag) == 'table' then",
                "    for _, item in ipairs(not_flag) do",
                "      if one_flag_matches(item, skill_flags) then",
                "        return false",
                "      end",
                "    end",
                "    return true",
                "  end",
                "  return not one_flag_matches(not_flag, skill_flags)",
                "end",
                "local function collect_display_rows(stat_list, actor, output, source_output)",
                "  local family_rows = {}",
                "  for _, family_id in ipairs(family_order) do",
                "    family_rows[family_id] = { family_id = family_id, rows = {} }",
                "  end",
                "  if type(stat_list) ~= 'table' or type(actor) ~= 'table' or type(output) ~= 'table' then",
                "    return {}",
                "  end",
                "  local main_skill = actor.mainSkill or {}",
                "  local skill_flags = main_skill.skillFlags or {}",
                "  for _, statData in ipairs(stat_list) do",
                "    if matches_flags(statData.flag, statData.notFlag, skill_flags) then",
                "      if statData.stat and statData.stat ~= 'SkillDPS' then",
                "        local stat_val = output[statData.stat]",
                "        if stat_val ~= nil and statData.childStat and type(stat_val) == 'table' then",
                "          stat_val = stat_val[statData.childStat]",
                "        end",
                "        local visible = false",
                "        if stat_val ~= nil then",
                "          if statData.condFunc then",
                "            visible = statData.condFunc(stat_val, output) and true or false",
                "          else",
                "            visible = stat_val ~= 0",
                "          end",
                "        end",
                "        if visible and not statData.hideStat then",
                "          local scalar_stat = scalar_value(stat_val)",
                "          if scalar_stat ~= nil then",
                "            local overcap_value = json.null",
                "            if statData.overCapStat then",
                "              local scalar_overcap = scalar_value(output[statData.overCapStat])",
                "              if scalar_overcap ~= nil then",
                "                overcap_value = scalar_overcap",
                "              end",
                "            end",
                "            local warning_value = json.null",
                "            if statData.warnFunc then",
                "              local warning_text = statData.warnFunc(stat_val, output)",
                "              if type(warning_text) == 'string' and warning_text ~= '' then",
                "                warning_value = warning_text",
                "              end",
                "            end",
                "            table.insert(family_rows[family_id_for_stat(statData.stat)].rows, {",
                "              stat_key = statData.childStat and (tostring(statData.stat) .. '.' .. tostring(statData.childStat)) or tostring(statData.stat),",
                "              label = tostring(statData.label or statData.stat),",
                "              value = scalar_stat,",
                "              overcap_value = overcap_value,",
                "              warning = warning_value,",
                "              lower_is_better = statData.lowerIsBetter == true,",
                "              source_output = source_output,",
                "            })",
                "          end",
                "        end",
                "      end",
                "    end",
                "  end",
                "  local families = {}",
                "  for _, family_id in ipairs(family_order) do",
                "    if #family_rows[family_id].rows > 0 then",
                "      table.insert(families, family_rows[family_id])",
                "    end",
                "  end",
                "  return families",
                "end",
                "local function collect_warning_lines(lines)",
                "  local result = {}",
                "  local seen = {}",
                "  if type(lines) ~= 'table' then",
                "    return result",
                "  end",
                "  for _, entry in pairs(lines) do",
                "    local line = entry",
                "    if type(entry) == 'table' then",
                "      line = entry.line",
                "    end",
                "    if type(line) == 'string' and line ~= '' and not seen[line] then",
                "      seen[line] = true",
                "      table.insert(result, line)",
                "    end",
                "  end",
                "  table.sort(result)",
                "  return result",
                "end",
                "if not build or not build.calcsTab or not build.controls then",
                "  error('Pinned runtime is missing build.calcsTab or build.controls during calc snapshot read-back.')",
                "end",
                "build:RefreshStatList()",
                "local player_actor = build.calcsTab.mainEnv and build.calcsTab.mainEnv.player or nil",
                "if type(player_actor) ~= 'table' then",
                "  error('Pinned runtime is missing player actor during calc snapshot read-back.')",
                "end",
                "local player_output = build.calcsTab.mainOutput",
                "local calcs_output = build.calcsTab.calcsOutput",
                "if type(player_output) ~= 'table' or type(calcs_output) ~= 'table' then",
                "  error('Pinned runtime is missing mainOutput or calcsOutput during calc snapshot read-back.')",
                "end",
                "local payload = {",
                "  main_output = collect_scalar_output(player_output),",
                "  calcs_output = collect_scalar_output(calcs_output),",
                "  display_families = {",
                "    player = collect_display_rows(build.displayStats or {}, player_actor, player_output, 'main_output'),",
                "    minion = {},",
                "  },",
                "  warnings = collect_warning_lines(build.controls.warnings and build.controls.warnings.lines or nil),",
                "}",
                "if build.calcsTab.mainEnv and type(build.calcsTab.mainEnv.minion) == 'table' and type(player_output.Minion) == 'table' then",
                "  payload.display_families.minion = collect_display_rows(",
                "    build.minionDisplayStats or {},",
                "    build.calcsTab.mainEnv.minion,",
                "    player_output.Minion,",
                "    'main_output.minion'",
                "  )",
                "end",
                "return json.encode(payload)",
            )
        )
        payload_raw = self._bridge.execute(chunk, nret=1)[0]
        if payload_raw is None:
            raise WorkerContractError("runtime_protocol_failed", "Pinned runtime returned no calc snapshot payload.")
        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError as exc:
            raise WorkerContractError("runtime_protocol_failed", "Pinned runtime returned invalid calc snapshot JSON.") from exc
        if not isinstance(payload, dict):
            raise WorkerContractError("runtime_protocol_failed", "Pinned runtime calc snapshot payload must decode to an object.")
        main_output = payload.get("main_output")
        calcs_output = payload.get("calcs_output")
        display_families = payload.get("display_families")
        warnings = payload.get("warnings")
        if not isinstance(main_output, dict) or not isinstance(calcs_output, dict):
            raise WorkerContractError("runtime_protocol_failed", "Pinned runtime calc snapshot must expose main_output and calcs_output objects.")
        if not isinstance(display_families, dict):
            raise WorkerContractError("runtime_protocol_failed", "Pinned runtime calc snapshot must expose display_families.")
        if not isinstance(warnings, list) or any(not isinstance(line, str) or not line.strip() for line in warnings):
            raise WorkerContractError("runtime_protocol_failed", "Pinned runtime calc snapshot warnings must stay a string array.")

        return {
            "config_set_id": config_set_id,
            "state_role": state_role,
            "config_summary": _json_clone(config_summary, field_name=f"{state_role}.config_summary"),
            "main_output": _json_clone(main_output, field_name=f"{state_role}.main_output"),
            "calcs_output": _json_clone(calcs_output, field_name=f"{state_role}.calcs_output"),
            "display_families": _json_clone(display_families, field_name=f"{state_role}.display_families"),
            "warnings": [line.strip() for line in warnings],
            "warning_codes": _warning_codes_from_lines([line.strip() for line in warnings]),
        }

    def snapshot_calc_packet(self) -> dict[str, Any]:
        config_state = self._snapshot_config_state()
        if config_state.get("state_kind") != "nondefault":
            raise WorkerContractError(
                "runtime_protocol_failed",
                "Calc snapshot requires explicit nondefault config state with separate baseline and conditional lanes.",
            )
        config_sets = config_state.get("config_sets")
        if not isinstance(config_sets, dict):
            raise WorkerContractError("runtime_protocol_failed", "Config state must expose repo-owned config_sets for calc snapshot.")

        active_config_set_id = config_state.get("active_config_set_id")
        baseline_config_set_id = config_state.get("baseline_config_set_id")
        conditional_config_set_id = config_state.get("conditional_config_set_id")
        if not isinstance(active_config_set_id, str) or not active_config_set_id:
            raise WorkerContractError("runtime_protocol_failed", "Config state must expose active_config_set_id for calc snapshot.")
        if not isinstance(baseline_config_set_id, str) or not baseline_config_set_id:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "Config state must expose baseline_config_set_id for calc snapshot.",
            )
        if not isinstance(conditional_config_set_id, str) or not conditional_config_set_id:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "Config state must expose conditional_config_set_id for calc snapshot.",
            )
        if baseline_config_set_id == conditional_config_set_id:
            raise WorkerContractError(
                "runtime_protocol_failed",
                "Calc snapshot requires distinct baseline and conditional config sets.",
            )

        baseline_summary = config_sets.get(baseline_config_set_id)
        conditional_summary = config_sets.get(conditional_config_set_id)
        if not isinstance(baseline_summary, dict) or not isinstance(conditional_summary, dict):
            raise WorkerContractError(
                "runtime_protocol_failed",
                "Config state must expose baseline and conditional config summaries for calc snapshot.",
            )

        primary_error: Exception | None = None
        try:
            return {
                "active_config_set_id": active_config_set_id,
                "baseline": self._snapshot_calc_section(
                    config_set_id=baseline_config_set_id,
                    state_role="baseline",
                    config_summary=baseline_summary,
                ),
                "conditional": self._snapshot_calc_section(
                    config_set_id=conditional_config_set_id,
                    state_role="conditional",
                    config_summary=conditional_summary,
                ),
            }
        except Exception as exc:
            primary_error = exc
        finally:
            try:
                self._set_active_config_set(active_config_set_id)
            except Exception:
                if primary_error is None:
                    raise
        if primary_error is not None:
            raise primary_error

    def snapshot_state(self) -> dict[str, Any]:
        chunk = "\n".join(
            (
                "local json = require('dkjson')",
                f"local slot_order = {_slot_order_literal()}",
                "local function encode_null(value)",
                "  if value == nil or value == '' or value == 'None' then",
                "    return json.null",
                "  end",
                "  return tostring(value)",
                "end",
                "local function normalize_rarity(value)",
                "  if value == nil then",
                "    return 'Rare'",
                "  end",
                "  local lowered = tostring(value):lower()",
                "  return lowered:sub(1, 1):upper() .. lowered:sub(2)",
                "end",
                "local function collect_line_list(lines)",
                "  local result = {}",
                "  if type(lines) ~= 'table' then",
                "    return result",
                "  end",
                "  for _, entry in ipairs(lines) do",
                "    local line = entry",
                "    if type(entry) == 'table' then",
                "      line = entry.line",
                "    end",
                "    if type(line) == 'string' and line ~= '' then",
                "      table.insert(result, line)",
                "    end",
                "  end",
                "  return result",
                "end",
                "local function collect_sorted_node_ids(mapping)",
                "  local result = {}",
                "  if type(mapping) ~= 'table' then",
                "    return result",
                "  end",
                "  for node_id, _ in pairs(mapping) do",
                "    table.insert(result, node_id)",
                "  end",
                "  table.sort(result)",
                "  return result",
                "end",
                "local function node_display_name(node)",
                "  return tostring(node.dn or node.name or node.label or 'unknown node')",
                "end",
                "local function node_ascendancy_name(node)",
                "  local value = node.ascendancyName or node.ascendancy_name",
                "  if type(value) == 'string' and value ~= '' then",
                "    return value",
                "  end",
                "  return nil",
                "end",
                "local function node_is_ascendancy_start(node)",
                "  return node.isAscendancyStart == true or node.ascendancyStart == true",
                "end",
                "local function node_is_notable(node)",
                "  return node.isNotable == true or node.notable == true or node.type == 'Notable'",
                "end",
                "local function list_has_entries(values)",
                "  return type(values) == 'table' and #values > 0",
                "end",
                "local function empty_object()",
                "  return setmetatable({}, { __jsontype = 'object' })",
                "end",
                "local function count_links(sockets)",
                "  if type(sockets) ~= 'table' then",
                "    return 0",
                "  end",
                "  local group_counts = {}",
                "  local max_links = 0",
                "  for _, socket in ipairs(sockets) do",
                "    local group = tonumber(socket.group) or 0",
                "    group_counts[group] = (group_counts[group] or 0) + 1",
                "    if group_counts[group] > max_links then",
                "      max_links = group_counts[group]",
                "    end",
                "  end",
                "  return max_links",
                "end",
                "local function collect_socket_list(item)",
                "  local result = {}",
                "  if type(item.sockets) ~= 'table' then",
                "    return result",
                "  end",
                "  for _, socket in ipairs(item.sockets) do",
                "    table.insert(result, {",
                "      color = tostring(socket.color or ''),",
                "      group = tonumber(socket.group) or 0,",
                "    })",
                "  end",
                "  return result",
                "end",
                "local function collect_influences(item)",
                "  local result = {}",
                "  if item.shaper then",
                "    table.insert(result, 'Shaper')",
                "  end",
                "  if item.elder then",
                "    table.insert(result, 'Elder')",
                "  end",
                "  if item.crusader then",
                "    table.insert(result, 'Crusader')",
                "  end",
                "  if item.hunter then",
                "    table.insert(result, 'Hunter')",
                "  end",
                "  if item.redeemer then",
                "    table.insert(result, 'Redeemer')",
                "  end",
                "  if item.warlord then",
                "    table.insert(result, 'Warlord')",
                "  end",
                "  if item.exarch then",
                "    table.insert(result, 'Exarch')",
                "  end",
                "  if item.eater then",
                "    table.insert(result, 'Eater')",
                "  end",
                "  if item.synthesis then",
                "    table.insert(result, 'Synthesised')",
                "  end",
                "  table.sort(result)",
                "  return result",
                "end",
                "local function serialize_item(slot_name, item)",
                "  return {",
                "    rarity = normalize_rarity(item.rarity),",
                "    slot = tostring(slot_name),",
                "    type_label = tostring(item.type or slot_name),",
                "    base_type = tostring(item.baseName or (item.base and item.base.name) or item.type or slot_name),",
                "    explicit_affixes = collect_line_list(item.explicitModLines),",
                "    implicit_affixes = collect_line_list(item.implicitModLines),",
                "    crafted = item.crafted == true,",
                "    enchanted = type(item.enchantModLines) == 'table' and #item.enchantModLines > 0 or false,",
                "    fractured = item.fractured == true,",
                "    veiled = item.veiled == true,",
                "    influences = collect_influences(item),",
                "    corrupted = item.corrupted == true or item.scourge == true,",
                "    sockets = collect_socket_list(item),",
                "    links = count_links(item.sockets),",
                "  }",
                "end",
                "local function strip_minimal_proof_item(item_payload)",
                "  if type(item_payload) ~= 'table' then",
                "    return item_payload",
                "  end",
                "  item_payload.base_type = nil",
                "  item_payload.sockets = {}",
                "  item_payload.links = 0",
                "  return item_payload",
                "end",
                "local function normalize_item_set_id(item_set_id)",
                "  local numeric_id = tonumber(item_set_id) or 1",
                "  if numeric_id == 1 then",
                "    return " + _lua_long_string(_CANONICAL_ITEM_SET_ID),
                "  end",
                "  return 'itemset.' .. tostring(numeric_id)",
                "end",
                "local function serialize_slot_payload(item_set, slot_name)",
                "  local slot_state = item_set[slot_name]",
                "  local sel_item_id = slot_state and slot_state.selItemId or 0",
                "  if type(sel_item_id) ~= 'number' or sel_item_id == 0 then",
                "    return { occupied = false, item = json.null }",
                "  end",
                "  local item = build.itemsTab.items[sel_item_id]",
                "  if not item then",
                "    error('Item slot ' .. tostring(slot_name) .. ' references missing item id ' .. tostring(sel_item_id) .. '.')",
                "  end",
                "  return { occupied = true, item = serialize_item(slot_name, item) }",
                "end",
                "local base_slot_lookup = {}",
                "for _, slot_name in ipairs(slot_order) do",
                "  base_slot_lookup[slot_name] = true",
                "end",
                "local function slot_has_visible_carrier(item_set, slot)",
                "  if slot.weaponSet == 2 and not item_set.useSecondWeaponSet then",
                "    return false",
                "  end",
                "  if slot.parentSlot and slot.slotNum then",
                "    local parent_slot_name = slot.parentSlot.slotName",
                "    local parent_state = item_set[parent_slot_name]",
                "    local parent_item_id = parent_state and parent_state.selItemId or 0",
                "    local parent_item = build.itemsTab.items[parent_item_id]",
                "    local abyssal_socket_count = parent_item and tonumber(parent_item.abyssalSocketCount or 0) or 0",
                "    return abyssal_socket_count >= tonumber(slot.slotNum)",
                "  end",
                "  return true",
                "end",
                "local function collect_extra_slot_names(item_set)",
                "  local result = {}",
                "  for slot_name, slot in pairs(build.itemsTab.slots) do",
                "    if not slot.nodeId and not base_slot_lookup[slot_name] then",
                "      local slot_state = item_set[slot_name]",
                "      local sel_item_id = slot_state and slot_state.selItemId or 0",
                "      if slot_has_visible_carrier(item_set, slot) or (type(sel_item_id) == 'number' and sel_item_id > 0) then",
                "        table.insert(result, slot_name)",
                "      end",
                "    end",
                "  end",
                "  table.sort(result)",
                "  return result",
                "end",
                "local function serialize_item_set(item_set_id)",
                "  local item_set = build.itemsTab.itemSets[item_set_id]",
                "  if not item_set then",
                "    error('Missing item set ' .. tostring(item_set_id) .. ' while snapshotting state.')",
                "  end",
                "  local extra_slot_names = collect_extra_slot_names(item_set)",
                "  local slots = {}",
                "  local nonempty_slot_count = 0",
                "  local function record_slot(slot_name)",
                "    local slot_payload = serialize_slot_payload(item_set, slot_name)",
                "    if slot_payload.occupied then",
                "      nonempty_slot_count = nonempty_slot_count + 1",
                "    end",
                "    slots[slot_name] = slot_payload",
                "  end",
                "  for _, slot_name in ipairs(slot_order) do",
                "    record_slot(slot_name)",
                "  end",
                "  for _, slot_name in ipairs(extra_slot_names) do",
                "    record_slot(slot_name)",
                "  end",
                "  return {",
                "    item_set_id = normalize_item_set_id(item_set_id),",
                "    use_second_weapon_set = item_set.useSecondWeaponSet == true,",
                "    extra_slots = extra_slot_names,",
                "    slots = slots,",
                "    nonempty_slot_count = nonempty_slot_count,",
                "  }",
                "end",
                "local socket_groups = {}",
                "for _, socket_group in ipairs(build.skillsTab.socketGroupList) do",
                "  table.insert(socket_groups, {",
                "    label = socket_group.label or json.null,",
                "    slot = socket_group.slot or json.null,",
                "    source = socket_group.source or json.null,",
                "    gem_count = #socket_group.gemList,",
                "  })",
                "end",
                "local engine_default_lookup = {}",
                "local function mark_engine_default(node_id)",
                "  if node_id and build.spec.allocNodes[node_id] then",
                "    engine_default_lookup[node_id] = true",
                "  end",
                "end",
                "mark_engine_default(build.spec.curClass and build.spec.curClass.startNodeId or nil)",
                "mark_engine_default(build.spec.curAscendClass and build.spec.curAscendClass.startNodeId or nil)",
                "mark_engine_default(build.spec.curSecondaryAscendClass and build.spec.curSecondaryAscendClass.startNodeId or nil)",
                "local engine_default_node_ids = {}",
                "for node_id, _ in pairs(engine_default_lookup) do",
                "  table.insert(engine_default_node_ids, node_id)",
                "end",
                "table.sort(engine_default_node_ids)",
                "local user_allocated_node_ids = {}",
                "local keystone_node_ids = {}",
                "local allocated_ascendancy_node_ids = {}",
                "local allocated_ascendancy_notable_node_ids = {}",
                "local allocated_ascendancy_notable_entries = {}",
                "for node_id, node in pairs(build.spec.allocNodes) do",
                "  if not engine_default_lookup[node_id] then",
                "    table.insert(user_allocated_node_ids, node_id)",
                "    if node.isKeystone or node.type == 'Keystone' then",
                "      table.insert(keystone_node_ids, node_id)",
                "    end",
                "    if node_ascendancy_name(node) == build.spec.curAscendClassName and not node_is_ascendancy_start(node) then",
                "      table.insert(allocated_ascendancy_node_ids, node_id)",
                "      if node_is_notable(node) then",
                "        table.insert(allocated_ascendancy_notable_node_ids, node_id)",
                "        table.insert(allocated_ascendancy_notable_entries, { node_id = node_id, name = node_display_name(node) })",
                "      end",
                "    end",
                "  end",
                "end",
                "table.sort(user_allocated_node_ids)",
                "table.sort(keystone_node_ids)",
                "table.sort(allocated_ascendancy_node_ids)",
                "table.sort(allocated_ascendancy_notable_node_ids)",
                "table.sort(allocated_ascendancy_notable_entries, function(left, right)",
                "  return left.node_id < right.node_id",
                "end)",
                "local allocated_ascendancy_notables = {}",
                "for _, entry in ipairs(allocated_ascendancy_notable_entries) do",
                "  table.insert(allocated_ascendancy_notables, entry.name)",
                "end",
                "local ascendancy_readback = {",
                "  source_kind = 'pinned_pob_alloc_nodes_readback',",
                "  class_id = encode_null(build.spec.curClassName),",
                "  ascendancy_id = encode_null(build.spec.curAscendClassName),",
                "  allocated_ascendancy_points = #allocated_ascendancy_node_ids,",
                "  allocated_ascendancy_node_ids = allocated_ascendancy_node_ids,",
                "  allocated_ascendancy_notable_count = #allocated_ascendancy_notable_node_ids,",
                "  allocated_ascendancy_notable_node_ids = allocated_ascendancy_notable_node_ids,",
                "  allocated_ascendancy_notables = allocated_ascendancy_notables,",
                "}",
                "local mastery_effect_ids = {}",
                "for mastery_node_id, effect_id in pairs(build.spec.masterySelections or {}) do",
                "  table.insert(mastery_effect_ids, tostring(mastery_node_id) .. ':' .. tostring(effect_id))",
                "end",
                "table.sort(mastery_effect_ids)",
                "local cluster_jewel_socket_ids = {}",
                "local socketed_jewel_node_ids = {}",
                "for node_id, item_id in pairs(build.spec.jewels or {}) do",
                "  if type(item_id) == 'number' and item_id > 0 then",
                "    table.insert(socketed_jewel_node_ids, node_id)",
                "    local item = build.itemsTab.items[item_id]",
                "    if item and (item.clusterJewel or (item.jewelData and item.jewelData.clusterJewelValid)) then",
                "      table.insert(cluster_jewel_socket_ids, node_id)",
                "    end",
                "  end",
                "end",
                "table.sort(cluster_jewel_socket_ids)",
                "table.sort(socketed_jewel_node_ids)",
                "local cluster_jewel_items = {}",
                "local socketed_jewel_items = {}",
                "for node_id, item_id in pairs(build.spec.jewels or {}) do",
                "  if type(item_id) == 'number' and item_id > 0 then",
                "    local item = build.itemsTab.items[item_id]",
                "    if not item then",
                "      error('Tree jewel socket ' .. tostring(node_id) .. ' references missing item id ' .. tostring(item_id) .. '.')",
                "    end",
                "    local entry = {",
                "      node_id = node_id,",
                "      item = serialize_item('Jewel', item),",
                "    }",
                "    if item.clusterJewel or (item.jewelData and item.jewelData.clusterJewelValid) then",
                "      table.insert(cluster_jewel_items, entry)",
                "    else",
                "      table.insert(socketed_jewel_items, entry)",
                "    end",
                "  end",
                "end",
                "table.sort(cluster_jewel_items, function(left, right)",
                "  return left.node_id < right.node_id",
                "end)",
                "table.sort(socketed_jewel_items, function(left, right)",
                "  return left.node_id < right.node_id",
                "end)",
                "local override_carrier_node_ids = collect_sorted_node_ids(build.spec.hashOverrides)",
                "local active_spec_index = tonumber(build.treeTab.activeSpec) or 1",
                "local active_spec_id = active_spec_index == 1 and " + _lua_long_string(_CANONICAL_SPEC_ID) + " or ('spec.' .. tostring(active_spec_index))",
                "local active_item_set_index = tonumber(build.itemsTab.activeItemSetId) or 1",
                "local active_item_set = serialize_item_set(active_item_set_index)",
                "local include_item_sets = (#build.itemsTab.itemSetOrderList > 1)",
                "  or active_item_set.use_second_weapon_set",
                "  or #active_item_set.extra_slots > 0",
                "local item_set_ids = {}",
                "local item_sets = empty_object()",
                "local total_nonempty_slot_count = active_item_set.nonempty_slot_count",
                "if include_item_sets then",
                "  total_nonempty_slot_count = 0",
                "  for _, item_set_id in ipairs(build.itemsTab.itemSetOrderList) do",
                "    local serialized_item_set = serialize_item_set(tonumber(item_set_id) or item_set_id)",
                "    table.insert(item_set_ids, serialized_item_set.item_set_id)",
                "    item_sets[serialized_item_set.item_set_id] = serialized_item_set",
                "    total_nonempty_slot_count = total_nonempty_slot_count + serialized_item_set.nonempty_slot_count",
                "  end",
                "end",
                "local gear_state_kind = 'nondefault'",
                "if total_nonempty_slot_count == 0 then",
                "  gear_state_kind = 'empty'",
                "elseif not include_item_sets",
                "  and active_item_set.nonempty_slot_count == 1",
                "  and active_item_set.slots['Boots']",
                "  and active_item_set.slots['Boots'].occupied then",
                "  local boots_only = true",
                "  for _, slot_name in ipairs(slot_order) do",
                "    if slot_name ~= 'Boots' and active_item_set.slots[slot_name] and active_item_set.slots[slot_name].occupied then",
                "      boots_only = false",
                "      break",
                "    end",
                "  end",
                "  if boots_only and #active_item_set.extra_slots == 0 then",
                "    gear_state_kind = 'boots_only'",
                "  end",
                "end",
                "local skills_state_kind = (#socket_groups == 0) and 'empty' or 'nondefault'",
                "local config_state_kind = 'default'",
                "local active_class_id = tonumber(build.spec.curClassId) or 0",
                "local active_ascendancy_id = tonumber(build.spec.curAscendClassId) or 0",
                "local active_secondary_ascendancy_id = tonumber(build.spec.curSecondaryAscendClassId) or 0",
                "local tree_state_kind = 'nondefault'",
                "if active_spec_id == " + _lua_long_string(_CANONICAL_SPEC_ID),
                "  and active_class_id == " + str(_CANONICAL_BLANK_CLASS_ID),
                "  and active_ascendancy_id == " + str(_CANONICAL_BLANK_ASCENDANCY_ID),
                "  and active_secondary_ascendancy_id == " + str(_CANONICAL_BLANK_SECONDARY_ASCENDANCY_ID),
                "  and #user_allocated_node_ids == 0",
                "  and #mastery_effect_ids == 0",
                "  and #cluster_jewel_socket_ids == 0",
                "  and #socketed_jewel_node_ids == 0",
                "  and #override_carrier_node_ids == 0 then",
                "  tree_state_kind = 'default'",
                "end",
                "local payload = {",
                "  identity_state = {",
                "    level = tonumber(build.characterLevel) or json.null,",
                "    character_level_auto_mode = build.characterLevelAutoMode == true,",
                "    active_spec_id = active_spec_id,",
                "    class_id = encode_null(build.spec.curClassName),",
                "    ascendancy_id = encode_null(build.spec.curAscendClassName),",
                "    secondary_ascendancy_id = encode_null(build.spec.curSecondaryAscendClassName),",
                "  },",
                "  gear_slots = {",
                "    state_kind = gear_state_kind,",
                "    active_item_set_id = active_item_set.item_set_id,",
                "    use_second_weapon_set = active_item_set.use_second_weapon_set,",
                "    slot_order = slot_order,",
                "    extra_slots = active_item_set.extra_slots,",
                "    slots = active_item_set.slots,",
                "    nonempty_slot_count = active_item_set.nonempty_slot_count,",
                "  },",
                "  tree_state = {",
                "    state_kind = tree_state_kind,",
                "    active_spec_id = active_spec_id,",
                "    class_id = encode_null(build.spec.curClassName),",
                "    ascendancy_id = encode_null(build.spec.curAscendClassName),",
                "    secondary_ascendancy_id = encode_null(build.spec.curSecondaryAscendClassName),",
                "    default_root_state_present = #engine_default_node_ids > 0,",
                "    engine_default_node_ids = engine_default_node_ids,",
                "    user_allocated_node_ids = user_allocated_node_ids,",
                "    keystone_node_ids = keystone_node_ids,",
                "    ascendancy_readback = ascendancy_readback,",
                "    allocated_ascendancy_points = ascendancy_readback.allocated_ascendancy_points,",
                "    allocated_ascendancy_node_ids = allocated_ascendancy_node_ids,",
                "    allocated_ascendancy_notable_count = ascendancy_readback.allocated_ascendancy_notable_count,",
                "    allocated_ascendancy_notable_node_ids = allocated_ascendancy_notable_node_ids,",
                "    allocated_ascendancy_notables = allocated_ascendancy_notables,",
                "    mastery_effect_ids = mastery_effect_ids,",
                "    cluster_jewel_socket_ids = cluster_jewel_socket_ids,",
                "    socketed_jewel_node_ids = socketed_jewel_node_ids,",
                "    anoint_allocations = {},",
                "  },",
                "  skills_state = {",
                "    state_kind = skills_state_kind,",
                f"    active_skill_set_id = {_lua_long_string(_CANONICAL_SKILLS_ID)},",
                "    socket_group_count = #socket_groups,",
                "    socket_groups = socket_groups,",
                "    main_socket_group_id = (#socket_groups == 0) and json.null or tostring(build.mainSocketGroup),",
                "    main_active_skill_id = json.null,",
                "  },",
                "  config_state = {",
                "    state_kind = config_state_kind,",
                f"    active_config_set_id = {_lua_long_string(_CANONICAL_CONFIG_ID)},",
                "    enabled_conditions = {},",
                "    custom_values = empty_object(),",
                "    notes = json.null,",
                "    bandit = json.null,",
                "    pantheon_major = json.null,",
                "    pantheon_minor = json.null,",
                "    engine_default_fields = empty_object(),",
                "  },",
                "}",
                "payload.ascendancy_readback = ascendancy_readback",
                "if gear_state_kind == 'boots_only'",
                "  and payload.gear_slots.slots['Boots']",
                "  and payload.gear_slots.slots['Boots'].occupied",
                "  and payload.gear_slots.slots['Boots'].item then",
                "  payload.gear_slots.slots['Boots'].item = strip_minimal_proof_item(payload.gear_slots.slots['Boots'].item)",
                "end",
                "if include_item_sets then",
                "  payload.gear_slots.item_set_ids = item_set_ids",
                "  payload.gear_slots.item_sets = item_sets",
                "end",
                "if list_has_entries(override_carrier_node_ids) then",
                "  payload.tree_state.override_carrier_node_ids = override_carrier_node_ids",
                "end",
                "if list_has_entries(cluster_jewel_items) then",
                "  payload.tree_state.cluster_jewel_items = cluster_jewel_items",
                "end",
                "if list_has_entries(socketed_jewel_items) then",
                "  payload.tree_state.socketed_jewel_items = socketed_jewel_items",
                "end",
                "return json.encode(payload)",
            )
        )
        payload = self._bridge.execute(chunk, nret=1)[0]
        if payload is None:
            raise WorkerContractError("runtime_protocol_failed", "PoB state snapshot returned no payload.")
        state = json.loads(payload)
        if not isinstance(state, dict):
            raise WorkerContractError("runtime_protocol_failed", "PoB state snapshot did not decode to an object.")
        gear_slots = state.get("gear_slots")
        if not isinstance(gear_slots, dict):
            raise WorkerContractError("runtime_protocol_failed", "PoB state snapshot is missing the repo-owned gear_slots object.")
        state["items_state"] = json.loads(json.dumps(gear_slots, ensure_ascii=False, allow_nan=False, sort_keys=True))
        state["state_contract_version"] = "pob_unified_state_snapshot.v1"
        state["skills_state"] = self._snapshot_rich_skill_state()
        state["config_state"] = self._snapshot_config_state()
        return state

    def close(self) -> None:
        try:
            self._bridge.close()
        finally:
            os.chdir(self._previous_cwd)


def _read_json_line() -> dict[str, Any] | None:
    line = sys.stdin.readline()
    if not line:
        return None
    stripped = line.strip()
    if not stripped:
        return {}
    return json.loads(stripped)


def _write_message(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _success(**payload: Any) -> None:
    message = {"ok": True}
    message.update(payload)
    _write_message(message)


def _failure(exc: Exception) -> None:
    if isinstance(exc, WorkerContractError):
        payload = {"ok": False, "failure_state": exc.failure_state, "message": str(exc)}
    else:
        payload = {"ok": False, "failure_state": "runtime_protocol_failed", "message": str(exc)}
    _write_message(payload)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--session-root", required=True)
    parser.add_argument("--wrapper-path", required=True)
    parser.add_argument("--session-role", required=True, choices=("normal", "reopen"))
    parser.add_argument("--reopen-source", default=None)
    return parser


def _run_worker(args: argparse.Namespace) -> int:
    runtime_root = Path(args.runtime_root).resolve(strict=False)
    session_root = Path(args.session_root).resolve(strict=False)
    wrapper_path = Path(args.wrapper_path).resolve(strict=False)
    reopen_source = None if args.reopen_source is None else Path(args.reopen_source).resolve(strict=False)

    os.environ["POB_RUNTIME_ROOT"] = runtime_root.as_posix()
    os.environ["POB_HEADLESS_USER_PATH"] = session_root.as_posix()
    os.environ["POB_HEADLESS_WORKDIR"] = session_root.as_posix()
    os.environ.setdefault("CI", "1")

    runtime = HeadlessLuaRuntime(runtime_root=runtime_root, session_root=session_root, wrapper_path=wrapper_path)
    try:
        if args.session_role == "reopen":
            if reopen_source is None or not reopen_source.is_file():
                raise WorkerContractError("reopen_source_missing", f"Missing reopen source XML: {reopen_source}")
            runtime.load_reopen_source(reopen_source.read_text(encoding="utf-8"))

        _write_message({"status": "ready"})

        while True:
            command = _read_json_line()
            if command is None:
                return 0
            if not command:
                continue

            action = command.get("action")
            try:
                if action == "create_blank_build":
                    runtime.create_blank_build()
                    _success()
                    continue
                if action == "apply_identity_state":
                    identity_payload = command.get("identity_payload")
                    if not isinstance(identity_payload, dict):
                        raise WorkerContractError("runtime_protocol_failed", "apply_identity_state requires identity_payload to be an object.")
                    runtime.apply_identity_state(identity_payload)
                    _success()
                    continue
                if action == "read_state":
                    _success(result=runtime.snapshot_state())
                    continue
                if action == "read_calc_snapshot":
                    _success(result=runtime.snapshot_calc_packet())
                    continue
                if action == "read_node_power_report":
                    node_power_request = command.get("node_power_request")
                    if node_power_request is not None and not isinstance(node_power_request, dict):
                        raise WorkerContractError(
                            "runtime_protocol_failed",
                            "read_node_power_report requires node_power_request to be an object when provided.",
                        )
                    _success(result=runtime.read_node_power_report(node_power_request))
                    continue
                if action == "read_ascendancy_node_report":
                    _success(result=runtime.read_ascendancy_node_report())
                    continue
                if action == "equip_boots_item":
                    runtime.equip_boots_item()
                    _success()
                    continue
                if action == "apply_tree_state":
                    tree_payload = command.get("tree_payload")
                    if not isinstance(tree_payload, dict):
                        raise WorkerContractError("runtime_protocol_failed", "apply_tree_state requires tree_payload to be an object.")
                    runtime.apply_tree_state(tree_payload)
                    _success()
                    continue
                if action == "apply_item_state":
                    item_payload = command.get("item_payload")
                    if not isinstance(item_payload, dict):
                        raise WorkerContractError("runtime_protocol_failed", "apply_item_state requires item_payload to be an object.")
                    runtime.apply_item_state(item_payload)
                    _success()
                    continue
                if action == "apply_skill_state":
                    skill_payload = command.get("skill_payload")
                    if not isinstance(skill_payload, dict):
                        raise WorkerContractError("runtime_protocol_failed", "apply_skill_state requires skill_payload to be an object.")
                    runtime.apply_skill_state(skill_payload)
                    _success()
                    continue
                if action == "apply_config_state":
                    config_payload = command.get("config_payload")
                    if not isinstance(config_payload, dict):
                        raise WorkerContractError("runtime_protocol_failed", "apply_config_state requires config_payload to be an object.")
                    runtime.apply_config_state(config_payload)
                    _success()
                    continue
                if action == "export_build_xml":
                    _success(result=runtime.export_build_xml())
                    continue
                if action == "verify_pob_import_code_string":
                    import_code = command.get("import_code")
                    if not isinstance(import_code, str):
                        raise WorkerContractError(
                            "runtime_protocol_failed",
                            "verify_pob_import_code_string requires import_code to be a string.",
                        )
                    _success(result=runtime.verify_pob_import_code_string(import_code))
                    continue
                if action == "shutdown":
                    _success(termination="process_exit_observed", exit_code=0)
                    return 0
                raise WorkerContractError("runtime_protocol_failed", f"Unsupported worker action: {action}")
            except Exception as exc:  # pragma: no cover - fail-closed protocol surface
                _failure(exc)
    finally:
        runtime.close()


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return _run_worker(args)
    except Exception as exc:  # pragma: no cover - startup failures stay explicit
        _failure(exc)
        return 1


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess
    raise SystemExit(main())
