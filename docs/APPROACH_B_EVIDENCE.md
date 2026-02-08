# Approach B Evidence Simulation

This project uses **Approach B** for damage evidence handling:

1. `product catalog images` (normal references)
2. `anomaly/defect images` (damaged examples)

For portfolio scope, current validation is deterministic and lightweight:
- checks image MIME type
- checks file size plausibility
- checks filename defect keywords
- boosts confidence when both reference dirs exist

The backend records:
- uploaded evidence metadata + storage path (`evidence_records`)
- validation output (`evidence_validations`)

## Directory Hooks

Configure in `.env`:

```bash
APPROACH_B_CATALOG_DIR=data/raw/product_catalog_images
APPROACH_B_ANOMALY_DIR=data/raw/anomaly_images
EVIDENCE_STORAGE_DIR=data/evidence
```

## Future Upgrade Path

- Replace deterministic scorer with learned anomaly model.
- Compare uploaded embedding vs reference catalog embeddings.
- Add per-category thresholds and calibration set metrics.
