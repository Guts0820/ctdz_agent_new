"""Versioned knowledge-to-ability mappings used by growth-report aggregation."""

import sqlite3
from pathlib import Path

from backend.shared.config import DATABASE_PATH


ABILITY_DIMENSIONS = (
    ("operation", "运算能力"),
    ("logic", "数感与逻辑"),
    ("spatial", "图形与空间"),
    ("application", "应用理解"),
    ("resilience", "学习韧性"),
)

MAPPING_VERSION = "ability-map-v1"

# This seed is deliberate, versioned curriculum metadata rather than a runtime title-keyword rule.
CORE_ABILITY_MAPPINGS = (
    ("K001", "logic", 1.0), ("K002", "logic", 1.0),
    ("K003", "logic", 1.0), ("K004", "operation", 1.0),
    ("K005", "spatial", 1.0), ("K006", "logic", 1.0),
    ("K007", "operation", 1.0), ("K008", "operation", 1.0),
    ("K009", "operation", 1.0), ("K010", "logic", 1.0),
    ("K011", "application", 1.0), ("K012", "operation", 1.0),
    ("K013", "operation", 1.0), ("K014", "operation", 1.0),
    ("K015", "application", 1.0), ("K016", "spatial", 1.0),
    ("K017", "operation", 1.0), ("K018", "operation", 1.0),
    ("K019", "operation", 1.0), ("K020", "operation", 1.0),
    ("K021", "logic", 1.0), ("K022", "logic", 1.0),
    ("K023", "logic", 1.0), ("K024", "logic", 1.0),
    ("K025", "application", 1.0), ("K026", "application", 1.0),
    ("K027", "operation", 1.0), ("K028", "operation", 1.0),
    ("K029", "operation", 1.0), ("K030", "operation", 1.0),
    ("K031", "logic", 1.0), ("K032", "spatial", 1.0),
    ("K033", "operation", 1.0), ("K034", "operation", 1.0),
    ("K035", "operation", 1.0), ("K036", "operation", 1.0),
    ("K037", "operation", 1.0), ("K038", "operation", 1.0),
    ("K039", "operation", 1.0), ("K040", "spatial", 1.0),
    ("K041", "operation", 1.0), ("K042", "operation", 1.0),
    ("K043", "operation", 1.0), ("K044", "spatial", 1.0),
    ("K166", "operation", 1.0), ("K167", "operation", 1.0),
    ("K168", "operation", 1.0), ("K169", "operation", 1.0),
    ("K170", "operation", 1.0), ("K171", "operation", 1.0),
    ("K172", "operation", 1.0),
)


def ensure_ability_mapping_schema(database_path: str | Path = DATABASE_PATH) -> None:
    """Create and seed the mapping table without changing existing mapping versions."""
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS knowledge_ability_mapping (
                knowledge_id VARCHAR(32) NOT NULL,
                dimension VARCHAR(32) NOT NULL,
                weight FLOAT NOT NULL DEFAULT 1.0,
                mapping_version VARCHAR(32) NOT NULL,
                source VARCHAR(32) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (knowledge_id, dimension, mapping_version),
                CHECK (dimension IN ('operation', 'logic', 'spatial', 'application')),
                CHECK (weight > 0)
            );
            CREATE INDEX IF NOT EXISTS idx_knowledge_ability_mapping_dimension
                ON knowledge_ability_mapping (dimension, mapping_version);
            """
        )
        connection.executemany(
            """INSERT OR IGNORE INTO knowledge_ability_mapping
               (knowledge_id, dimension, weight, mapping_version, source)
               VALUES (?, ?, ?, ?, 'seed')""",
            [(*mapping, MAPPING_VERSION) for mapping in CORE_ABILITY_MAPPINGS],
        )
