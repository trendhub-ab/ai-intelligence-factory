from pathlib import Path

path = Path("pipeline.py")
text = path.read_text(encoding="utf-8")
old = r'(?<=[。！？.!?])\s+|\n+'
new = r'(?<=[。！？])|(?<=[.!?])\s+|\n+'
count = text.count(old)
if count < 3:
    raise SystemExit(f"expected at least 3 Run157 sentence split patterns, found {count}")
# Limit this change to the newly inserted Run157 helper region only.
start = text.index("# Run157: high-precision guard")
end = text.index("\ndef validate_fact_gate(", start)
region = text[start:end]
region_count = region.count(old)
if region_count != 3:
    raise SystemExit(f"expected exactly 3 Run157 sentence split patterns, found {region_count}")
region = region.replace(old, new)
text = text[:start] + region + text[end:]
path.write_text(text, encoding="utf-8")
print("Run157 Japanese sentence boundary patch applied")
