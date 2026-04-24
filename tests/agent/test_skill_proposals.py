from __future__ import annotations

from nanobot.agent.skill_proposals import SkillProposalStore


def test_proposal_store_writes_under_memory_subdir(tmp_path) -> None:
    store = SkillProposalStore(tmp_path)

    path = store.write(
        "deploy-check",
        "---\nname: deploy-check\ndescription: Check deploy state\n---\n\n# Deploy Check\n",
    )

    assert path == tmp_path / "memory" / "skill-proposals" / "deploy-check.md"
    assert path.exists()


def test_proposal_store_lists_existing_proposals(tmp_path) -> None:
    store = SkillProposalStore(tmp_path)
    store.write(
        "deploy-check",
        "---\nname: deploy-check\ndescription: Check deploy state\n---\n\n# Deploy Check\n",
    )

    proposals = store.list()
    assert [item.name for item in proposals] == ["deploy-check"]


def test_proposal_store_records_metadata_on_write(tmp_path) -> None:
    store = SkillProposalStore(tmp_path)

    store.write(
        "deploy-check",
        "---\nname: deploy-check\ndescription: Check deploy state\n---\n\n# Deploy Check\n",
        source="dream",
    )

    proposals = store.list()
    assert proposals[0].name == "deploy-check"
    assert proposals[0].source == "dream"
    assert proposals[0].status == "pending"
