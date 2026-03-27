from nanobot.agent.skills import SkillsLoader


def test_builtin_ipinfo_skill_is_listed_and_loadable(tmp_path) -> None:
    loader = SkillsLoader(tmp_path)

    skills = loader.list_skills(filter_unavailable=False)
    ipinfo = next((skill for skill in skills if skill["name"] == "ipinfo"), None)

    assert ipinfo is not None
    assert ipinfo["source"] == "builtin"

    content = loader.load_skill("ipinfo")
    assert content is not None
    assert "ipinfo.io/json" in content

    summary = loader.build_skills_summary()
    assert "<name>ipinfo</name>" in summary
