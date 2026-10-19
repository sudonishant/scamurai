"""Photo-to-location analysis from background clues (section 11 / report ch.48).

Hard rules:
* EXIF GPS is presented as 'location recorded in the file', never as visual proof;
* missing GPS means 'no usable metadata', never 'hidden location';
* without a configured vision/OCR provider the system records observations and
  'insufficient evidence' — it never invents a university name or city-center pin;
* candidate regions are labeled as candidates, not calibrated error boundaries.
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from ..models import AnalysisRun, LocationFinding, MediaAsset, Place
from ..registry import MEDIA, PLACE
from . import graph, images, storage


def analyze_media(db: Session, case_id: str, media: MediaAsset,
                  analysis_run: AnalysisRun) -> LocationFinding:
    exif = json.loads(media.exif_gps) if media.exif_gps else None
    data = storage.get_object(media.object_key)
    observations = images.visual_clue_observations(data)

    if exif and "latitude" in exif and "longitude" in exif:
        place = Place(
            case_id=case_id,
            name=f"GPS metadata point ({exif['latitude']:.4f}, {exif['longitude']:.4f})",
            precision="camera_position",
            geometry=json.dumps({"type": "candidate_region", "point": {
                "latitude": exif["latitude"], "longitude": exif["longitude"]},
                "label": "location recorded in file — metadata can be edited"}),
            role="camera_position",
        )
        db.add(place)
        db.flush()
        graph.upsert_node(db, case_id, PLACE, place.id, place.name,
                          {"precision": place.precision, "status": "metadata_reported"})
        graph.add_edge(db, case_id, MEDIA, media.id, PLACE, place.id,
                       "GPS_METADATA_REPORTS", statement="Coordinates read from file metadata")
        finding = LocationFinding(
            case_id=case_id, media_asset_id=media.id, place_id=place.id,
            status="metadata_reported",
            evidence_ids=json.dumps([media.id]),
            observations=json.dumps(observations),
        )
    else:
        # No provider may invent a named place; record what is observable and abstain.
        observations.append("no configured vision/OCR provider for sign/landmark interpretation")
        observations.append("generic cultural-event backgrounds must not resolve to a named institution")
        finding = LocationFinding(
            case_id=case_id, media_asset_id=media.id, place_id=None,
            status="insufficient",
            evidence_ids=json.dumps([media.id]),
            observations=json.dumps(observations),
        )
    db.add(finding)
    db.flush()
    return finding
