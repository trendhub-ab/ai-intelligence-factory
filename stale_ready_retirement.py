"""Safe retirement contract for unrecoverable legacy Ready inventory."""
from __future__ import annotations


def classify(*,stale:bool,current:bool,published:bool,recoverable:bool)->str:
    if published: return "protected_published"
    if current or not stale: return "protected_current"
    if recoverable: return "recoverable"
    return "retirable"


def retirement_patch()->dict:
    # Keep page/audit history. Demotion makes it ineligible for note Ready sync.
    return {"archived":False,"properties":{"記事状態":{"select":{"name":"Not Planned"}},"コンテンツ状態":{"select":{"name":"Deep Dive"}}}}
