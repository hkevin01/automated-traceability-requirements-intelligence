class GapDetectionService:
    def detect(self, artifacts: list[dict], links: list[dict]) -> list[dict]:
        linked_sources = {item["source_id"] for item in links}
        linked_targets = {item["target_id"] for item in links}

        findings: list[dict] = []
        for artifact in artifacts:
            aid = artifact["artifact_id"]
            atype = artifact["artifact_type"]
            if atype == "requirement" and aid not in linked_sources:
                findings.append(
                    {
                        "artifact_id": aid,
                        "finding_type": "orphan_requirement",
                        "severity": "high",
                        "rationale": "Requirement has no downstream links",
                    }
                )
            if atype == "test" and aid not in linked_targets:
                findings.append(
                    {
                        "artifact_id": aid,
                        "finding_type": "orphan_test",
                        "severity": "medium",
                        "rationale": "Test has no upstream trace link",
                    }
                )
        return findings
