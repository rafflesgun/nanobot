from nanobot.agent.skill_proposal_metadata import ProposalMetadataStore


def test_metadata_store_creates_pending_entry(tmp_path) -> None:
    store = ProposalMetadataStore(tmp_path)

    store.record_created(name="deploy-check", source="dream")

    entry = store.get("deploy-check")
    assert entry is not None
    assert entry["status"] == "pending"
    assert entry["source"] == "dream"
    assert "created_at" in entry


def test_metadata_store_marks_rejected(tmp_path) -> None:
    store = ProposalMetadataStore(tmp_path)
    store.record_created(name="deploy-check", source="dream")

    store.record_rejected("deploy-check")

    entry = store.get("deploy-check")
    assert entry["status"] == "rejected"
    assert "rejected_at" in entry
