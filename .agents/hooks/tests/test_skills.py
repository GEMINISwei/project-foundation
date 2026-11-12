"""`.agents/skills/` 是 Claude 與 Codex 共用的唯一一份 skills。

Codex 讀 `.agents/skills/`, Claude 讀 `.claude/skills/`, 兩者格式相同 (Agent Skills 的 `SKILL.md`),
所以 `.claude/skills` 是指向前者的 symlink。symlink 壞掉 (例如在 `core.symlinks=false` 的 Windows
上 clone 成一般檔案) 時, Claude 只是安靜地看不到任何 skill, 不會報錯。

內文提到某一家專屬的工具名稱時, 另一家照著做就會卡住; 「只能手動呼叫」兩家各有各的設定,
只設一邊時, 另一邊會在使用者沒要求的時候自己觸發 (例如發版)。

"""

import os
import re
from pathlib import Path

import pytest
from support import REPO_ROOT

SKILLS_DIR = REPO_ROOT / ".agents" / "skills"
CLAUDE_SKILLS = REPO_ROOT / ".claude" / "skills"
SKILLS = sorted(path for path in SKILLS_DIR.glob("*") if path.is_dir())

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", flags=re.DOTALL)
NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# 只有其中一家有的工具與語法。寫「在背景等 CI 跑完」, 讓各家用自己的工具去做。
AGENT_SPECIFIC = re.compile(
    r"\$ARGUMENTS|\b(run_in_background|ScheduleWakeup|CronCreate|Monitor|TaskCreate|"
    r"AskUserQuestion|ToolSearch|apply_patch|update_plan|request_user_input)\b"
)


def frontmatter(skill: Path) -> dict[str, str]:
    match = FRONTMATTER.match((skill / "SKILL.md").read_text(encoding="utf-8"))
    assert match, f"{skill.name}/SKILL.md 開頭要有 --- 包住的 frontmatter"
    fields = (line.partition(":") for line in match.group(1).splitlines() if ":" in line)
    return {key.strip(): value.strip() for key, _, value in fields}


def test_skills_exist() -> None:
    assert SKILLS, ".agents/skills/ 底下沒有任何 skill"


def test_claude_skills_is_symlink_to_shared_skills() -> None:
    assert CLAUDE_SKILLS.is_symlink(), (
        ".claude/skills 要是 symlink: ln -s ../.agents/skills .claude/skills"
        " (Windows 要先 git config core.symlinks true 再重新 checkout)"
    )
    # 相對路徑: 絕對路徑換一台機器或一個目錄就指不到。
    assert os.readlink(CLAUDE_SKILLS) == "../.agents/skills"
    assert CLAUDE_SKILLS.resolve() == SKILLS_DIR.resolve()


@pytest.mark.parametrize("skill", SKILLS, ids=lambda path: path.name)
def test_skill_frontmatter_matches_directory(skill: Path) -> None:
    fields = frontmatter(skill)
    assert fields.get("name") == skill.name, f"{skill.name}: frontmatter 的 name 要與資料夾同名"
    assert NAME.match(skill.name), f"{skill.name}: 名稱只用小寫英數與 -"
    # 兩家只先載入描述來決定要不要用這個 skill, 空的就永遠不會被選到。
    description = fields.get("description", "")
    assert description, f"{skill.name}: description 不可空白"
    assert len(description) <= 1024, f"{skill.name}: description 超過 1024 字元"


@pytest.mark.parametrize("skill", SKILLS, ids=lambda path: path.name)
def test_skills_do_not_mention_agent_specific_tools(skill: Path) -> None:
    found = {
        f"{path.relative_to(skill)}: {match.group(0)}"
        for path in skill.rglob("*.md")
        for match in AGENT_SPECIFIC.finditer(path.read_text(encoding="utf-8"))
    }
    assert not found, f"{skill.name} 用了只有某一家才有的工具或語法: {sorted(found)}"


def manual_only(skill: Path) -> tuple[bool, bool]:
    """(Claude, Codex) 各自是否關掉了自動觸發。"""
    claude_manual = frontmatter(skill).get("disable-model-invocation") == "true"
    openai_yaml = skill / "agents" / "openai.yaml"
    codex_manual = openai_yaml.exists() and bool(
        re.search(r"^\s*allow_implicit_invocation:\s*false\s*$", openai_yaml.read_text(), re.M)
    )
    return claude_manual, codex_manual


# 會影響這個 repo 以外的 skill: 發版會部署。
# 只檢查兩家一致的話, 兩邊都忘了設也會通過, 所以這幾個要明列並要求一定是手動。
EXTERNAL_EFFECT_SKILLS = ("release",)


@pytest.mark.parametrize("name", EXTERNAL_EFFECT_SKILLS)
def test_skills_with_external_effects_are_manual_only(name: str) -> None:
    skill = SKILLS_DIR / name
    assert (skill / "SKILL.md").exists(), f".agents/skills/{name}/SKILL.md 不存在"
    assert manual_only(skill) == (True, True), (
        f"{name} 會影響 repo 以外的東西, 只能由使用者手動呼叫: SKILL.md 加"
        " disable-model-invocation: true,"
        " agents/openai.yaml 加 policy.allow_implicit_invocation: false"
    )


@pytest.mark.parametrize("skill", SKILLS, ids=lambda path: path.name)
def test_manual_only_skills_are_manual_only_in_both_agents(skill: Path) -> None:
    claude_manual, codex_manual = manual_only(skill)
    assert claude_manual == codex_manual, (
        f"{skill.name}: 只能手動呼叫要兩邊一起設 —— SKILL.md 的 disable-model-invocation: true"
        " 與 agents/openai.yaml 的 policy.allow_implicit_invocation: false"
    )
