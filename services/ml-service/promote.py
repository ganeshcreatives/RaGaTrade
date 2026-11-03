"""Human-reviewed model promotion. Candidate training never activates a model."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path, help="candidate-*.joblib artifact path")
    parser.add_argument("--reviewer", required=True, help="Human approver's name or operator ID")
    parser.add_argument("--approval-note", required=True, help="Short validation and data-rights review note")
    parser.add_argument("--model-dir", type=Path, default=Path("./models"))
    args = parser.parse_args()
    manifest_path = args.candidate.with_suffix(".json")
    if not args.candidate.is_file() or not manifest_path.is_file():
        parser.error("candidate artifact and matching JSON manifest must both exist")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    metrics = manifest.get("metrics", {})
    if sha256(args.candidate) != manifest.get("artifactSha256"):
        parser.error("candidate artifact SHA-256 does not match the manifest")
    if manifest.get("approval") != "CANDIDATE_NOT_PROMOTED":
        parser.error("manifest is not an unpromoted candidate")
    if metrics.get("validationRows", 0) < 100 or metrics.get("walkForwardFolds", 0) < 3:
        parser.error("candidate needs at least 100 validation rows across three purged folds")
    model_brier = metrics.get("brierScore", 1)
    if model_brier >= 0.25 or model_brier > metrics.get("momentumBaselineBrier", 0) or model_brier > metrics.get("logisticChallengerBrier", 0):
        parser.error("candidate did not beat random, momentum, and logistic-challenger Brier scores")
    if metrics.get("calibrationError10Bins", 1) > 0.10:
        parser.error("calibration error exceeds the configured 0.10 promotion threshold")
    args.model_dir.mkdir(parents=True, exist_ok=True)
    active_artifact = args.model_dir / "active.joblib"
    active_manifest = args.model_dir / "active.json"
    new_manifest = {**manifest, "approval": "HUMAN_APPROVED", "reviewer": args.reviewer.strip(),
                    "approvalNote": args.approval_note.strip()}
    if not new_manifest["reviewer"] or not new_manifest["approvalNote"]:
        parser.error("reviewer and approval note must not be blank")
    staged_artifact = args.model_dir / ".active.joblib.staged"
    staged_manifest = args.model_dir / ".active.json.staged"
    shutil.copyfile(args.candidate, staged_artifact)
    staged_manifest.write_text(json.dumps(new_manifest, indent=2), encoding="utf-8")
    staged_artifact.replace(active_artifact)
    staged_manifest.replace(active_manifest)
    print(json.dumps({"status": "promoted", "modelVersion": new_manifest["modelVersion"],
                      "reviewer": new_manifest["reviewer"], "activeArtifact": str(active_artifact)}, indent=2))


if __name__ == "__main__":
    main()
