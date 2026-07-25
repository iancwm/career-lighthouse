from pathlib import Path
import tomllib


API_ROOT = Path(__file__).resolve().parents[1]


def test_locked_torch_build_is_cpu_only():
    lock_data = tomllib.loads((API_ROOT / "uv.lock").read_text(encoding="utf-8"))
    packages = {package["name"]: package for package in lock_data["package"]}

    assert packages["torch"]["source"]["registry"].rstrip("/") == (
        "https://download.pytorch.org/whl/cpu"
    )
    assert not {
        name
        for name in packages
        if name == "triton" or name.startswith(("cuda-", "nvidia-"))
    }


def test_dockerfile_does_not_redownload_or_copy_dependencies():
    dockerfile = (API_ROOT / "Dockerfile").read_text(encoding="utf-8")
    entrypoint = (API_ROOT / "entrypoint.sh").read_text(encoding="utf-8")

    assert "SentenceTransformer('all-MiniLM-L6-v2')" not in dockerfile
    assert "COPY --chown=appuser:appgroup . ." in dockerfile
    assert "RUN chown -R appuser:appgroup /app" not in dockerfile
    assert "uv run --no-sync uvicorn" in entrypoint


def test_compose_maps_all_ontology_storage_to_the_knowledge_volume():
    compose = (API_ROOT.parent / "docker-compose.yml").read_text(encoding="utf-8")

    for assignment in (
        "ONTOLOGY_ENTITIES_DIR=/app/knowledge/entities",
        "ONTOLOGY_CLAIMS_DIR=/app/knowledge/claims",
        "ONTOLOGY_EVIDENCE_DIR=/app/knowledge/evidence",
    ):
        assert assignment in compose
