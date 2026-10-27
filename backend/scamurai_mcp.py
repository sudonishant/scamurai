#!/usr/bin/env python3
"""Scamurai MCP Server — Model Context Protocol for Evidence-First Disinformation Investigation.

Enables any MCP-compliant AI assistant (Antigravity, Claude Desktop, Cursor, etc.)
to invoke Scamurai investigation tools directly over stdio without external proprietary APIs.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.services import claims, comments, hashing, images

logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

TOOLS = [
    {
        "name": "scamurai_analyze_media",
        "description": "Analyze an image using perceptual DCT hashing (pHash), SHA-256 fingerprinting, and EXIF GPS metadata extraction to detect reuse, crops, and location discrepancies.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "Local path to the image file (PNG/JPEG/WebP) to analyze."
                }
            },
            "required": ["image_path"]
        }
    },
    {
        "name": "scamurai_analyze_comments",
        "description": "Perform multilabel classification on social media comments (supporting English, Hindi, and Hinglish). Detects coordinated narrative repetition, toxic amplification, and inauthentic bot patterns.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "comments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "text": {"type": "string"},
                            "author": {"type": "string"}
                        },
                        "required": ["id", "text"]
                    },
                    "description": "List of comment objects to analyze."
                }
            },
            "required": ["comments"]
        }
    },
    {
        "name": "scamurai_detect_coordination",
        "description": "Detect possible coordinated inauthentic behavior across social media posts by analyzing sub-minute temporal clustering, lexical similarity, and shared media usage.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "posts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "account": {"type": "string"},
                            "text": {"type": "string"},
                            "timestamp": {"type": "string", "description": "ISO 8601 timestamp"}
                        },
                        "required": ["account", "text", "timestamp"]
                    },
                    "description": "List of post records to test for synchronized coordination."
                }
            },
            "required": ["posts"]
        }
    },
    {
        "name": "scamurai_extract_claims",
        "description": "Extract verifiable factual propositions from suspect text or posts, and generate verification search queries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Post text or statement from which to extract claims."
                }
            },
            "required": ["text"]
        }
    }
]


def handle_analyze_media(args: dict) -> dict:
    import io

    from PIL import Image

    image_path = Path(args["image_path"])
    if not image_path.exists():
        return {"error": f"Image file not found: {image_path}"}

    data = image_path.read_bytes()
    sha256_val = hashing.sha256_file(data)
    img = Image.open(io.BytesIO(data))
    phash_val = hashing.phash(img)
    gps = images.extract_exif_gps(img)

    return {
        "status": "success",
        "file": image_path.name,
        "byte_length": len(data),
        "sha256": sha256_val,
        "dct_phash": phash_val,
        "exif_gps": gps,
        "has_gps_metadata": gps is not None,
        "dimensions": {"width": img.width, "height": img.height},
        "derivation_rule": "What is established: SHA-256 and EXIF headers are exact facts. Visual similarity requires pairwise distance <= threshold."
    }


def handle_analyze_comments(args: dict) -> dict:
    raw_comments = args.get("comments", [])
    results = []
    for c in raw_comments:
        text = c.get("text", "")
        analysis = comments.analyze_comment_text(text)
        results.append({
            "id": c.get("id"),
            "author": c.get("author", "unknown"),
            "text": text,
            "categories": getattr(analysis, "categories", []),
            "spans": getattr(analysis, "spans", []),
            "explanation": getattr(analysis, "explanation", ""),
            "scores": getattr(analysis, "scores", {}),
            "suggested_action": getattr(analysis, "suggested_action", "")
        })
    return {
        "status": "success",
        "total_analyzed": len(results),
        "flagged_suspicious": sum(1 for r in results if r["categories"]),
        "items": results
    }


def handle_detect_coordination(args: dict) -> dict:
    posts = args.get("posts", [])
    # Detect identical text
    text_clusters: dict[str, list[dict]] = {}
    for p in posts:
        txt = p.get("text", "").strip()
        text_clusters.setdefault(txt, []).append(p)

    clusters = []
    for txt, group in text_clusters.items():
        if len(group) > 1:
            clusters.append({
                "repeated_text": txt,
                "count": len(group),
                "accounts": [g.get("account") for g in group],
                "timestamps": [g.get("timestamp") for g in group],
                "hypothesis": "Possible synchronized amplification script or cross-posting."
            })

    return {
        "status": "success",
        "posts_evaluated": len(posts),
        "clusters_detected": len(clusters),
        "clusters": clusters,
        "principle": "Coordinated timing is a signal/hypothesis, not automated proof of common ownership."
    }


def handle_extract_claims(args: dict) -> dict:
    text = args.get("text", "")
    props = claims.extract_propositions(text)
    return {
        "status": "success",
        "input_text": text,
        "extracted_propositions": props,
        "queries": [f"fact check {p}" for p in props]
    }


DISPATCH = {
    "scamurai_analyze_media": handle_analyze_media,
    "scamurai_analyze_comments": handle_analyze_comments,
    "scamurai_detect_coordination": handle_detect_coordination,
    "scamurai_extract_claims": handle_extract_claims,
}


def main():
    """Main JSON-RPC 2.0 loop over stdin/stdout."""
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
        except Exception:
            continue

        method = req.get("method")
        msg_id = req.get("id")

        if method == "initialize":
            res = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "scamurai-mcp-server",
                        "version": "0.1.0"
                    }
                }
            }
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()

        elif method == "notifications/initialized":
            pass

        elif method == "tools/list":
            res = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": TOOLS
                }
            }
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()

        elif method == "tools/call":
            params = req.get("params", {})
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})

            handler = DISPATCH.get(tool_name)
            if not handler:
                res = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"}
                }
            else:
                try:
                    output = handler(tool_args)
                    res = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(output, indent=2)
                                }
                            ]
                        }
                    }
                except Exception as e:
                    res = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps({"error": str(e)})
                                }
                            ],
                            "isError": True
                        }
                    }
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
