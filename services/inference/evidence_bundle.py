"""Portable, hash-manifested inspection evidence; source images are analysis-space."""
import base64
import hashlib
import io
import json
import zipfile

import cv2


def build_evidence_bundle(result, session):
    files = {
        "result.json": json.dumps(result, indent=2, allow_nan=False).encode(),
        "policy.json": json.dumps({"measurement_contract": result["measurement_contract"],
                                   "snapshot": result.get("policy_snapshot"),
                                   "snapshot_available": result.get("policy_snapshot") is not None}, indent=2).encode(),
        "capture-session.json": json.dumps({"metadata": session.metadata, "expires_at_epoch": session.expires_at}, indent=2).encode(),
        "README.txt": ("LoopSight inspection evidence\n\n"
                       "Captures are decoded analysis images (current upload limit: 1024 pixels per side), not original upload files.\n"
                       "manifest.json records SHA-256 of file bytes; result frame hashes refer to decoded pixel arrays including shape.\n"
                       "These hashes detect modifications; they do not certify capture identity, time or ground truth.\n"
                       "Image scores are heuristic, not NTU, physical crack widths, safety certification or calibrated confidence.\n"
                       "Same-image processing and new capture evidence are labeled separately.\n"
                       "Downloaded copies are under the recipient's control and do not expire when server evidence expires.\n").encode(),
    }
    for name, frame in [("first.png", session.frame), ("reference.png", session.reference), ("second.png", session.second_frame)]:
        if frame is not None:
            ok, encoded = cv2.imencode(".png", frame)
            if not ok:
                raise ValueError("capture encoding failed")
            files[name] = encoded.tobytes()
    overlay = result.get("overlay_data_url", "")
    if overlay.startswith("data:image/png;base64,"):
        files["overlay.png"] = base64.b64decode(overlay.split(",", 1)[1], validate=True)
    files["manifest.json"] = json.dumps({"schema_version": 1, "job_id": result.get("job_id"), "hash_algorithm": "sha256",
                                         "files": {name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
                                                   for name, data in files.items()}}, indent=2).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as bundle:
        for name, data in files.items():
            bundle.writestr(name, data)
    return output.getvalue()
