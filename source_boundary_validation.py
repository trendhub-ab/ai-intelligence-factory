from __future__ import annotations
import re

_RUNTIME_KEYS=set()
def bind_runtime(**deps):
    globals().update(deps); _RUNTIME_KEYS.update(deps)

def _expand_evidence_aliases(source_context: str) -> str:
    """Add canonical aliases only when one member is already present in the evidence.

    This prevents a primary source that says ``MCP`` from making the public expansion
    ``Model Context Protocol`` look like an unsupported named fact.  The helper does not
    infer products, actors, versions, or capabilities.
    """
    raw = source_context or ""
    normalized = _normalized_evidence_text(raw)
    additions: list[str] = []

    def alias_present(alias: str) -> bool:
        # Short all-caps aliases must be token matches.  Plain substring matching would,
        # for example, find RAG inside the ordinary word "storage" and fabricate support.
        if alias.isupper() and len(alias) <= 6:
            return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", raw, re.I))
        return _normalized_evidence_text(alias) in normalized

    for group in _EVIDENCE_ALIAS_GROUPS:
        if any(alias_present(alias) for alias in group):
            additions.extend(group)
    return raw + (("\n" + " ".join(dict.fromkeys(additions))) if additions else "")

def _find_source_boundary_violations(draft: str, source_context: str, repo_name: str = "") -> list[str]:
    """Source Context外の「固有製品/企業/モデルに関する事実補完」だけを止める補助Gate。

    一般技術用語・略語・固定見出し・Decision語は対象外。さらに、単に未知の英字語が
    出たという理由だけではFailにせず、現在仕様/導入/比較/価格/公開/サポート等を
    断定する文でのみ判定する。これにより Cursor/Copilot の無根拠補完は止めつつ、
    PoC / What / API / SaaS 等の誤検知を避ける。
    """
    alias_expanded_context = _expand_evidence_aliases(source_context)
    evidence = _normalized_evidence_text(alias_expanded_context)
    if not draft or not evidence:
        return []

    failures: list[str] = []
    sentences = re.split(r"(?<=[。！？])\s*", draft)
    factual_cue = re.compile(
        r"(?:比較|一方で|に比べ|よりも|公式|サポート|対応|提供|採用|導入|標準|管理|利用|使える|使えない|"
        r"必須|要求|実装|公開|発表|提案|開発|著者|研究者|開発元|料金|価格|シェア|市場|クラウド|オンプレ|セルフホスト|発売|リリース|"
        r"統合|搭載|廃止|終了|互換|移行|採用され|導入され|提供され|サポートされ|発表した|開発した|提案した)"
    )
    inference = re.compile(
        r"(?:一般論として|私の推論|ここからは.{0,20}推論|推論に基づ|可能性がある|可能性があります|"
        r"考えられる|考えられます|仮説|例として|たとえば|例えば|想定|元記事(?:の記述|公開時点|によれば)|"
        r"一次情報では確認できない|一次情報からは確認できない|未確認|不明|推測)"
    )

    # 固有製品名ではない一般用語・略語・記事テンプレート語。
    ignore = {
        "ARTICLE","MANAGEMENT","DATA","WATCH","TRY","NOW","WAIT","AVOID","What","Decision","Score",
        "GitHub","HackerNews","ProductHunt","ArXiv","Source","Summary","Action","Future","Scenario",
        "API","AI","LLM","MCP","GPU","CPU","OSS","URL","HTTP","HTTPS","PDF","HTML","JSON","XML",
        "Linux","Wayland","Python","Markdown","VAE","RAG","RLHF","SFT","PR","PoC","POC","CTO","PM",
        "SaaS","Web API","RPA","UI","UX","DOM","Webhook","Webhooks","Cookie","Cookies","ID","ACL","2FA","MFA",
        "CLI","SDK","REST","GraphQL","SQL","NoSQL","CI","CD","DevOps","MLOps","AIOps","VPS","VM",
        "AWS","GCP","Azure","KPI","ROI","TCO","SLA","SSO","RBAC","OAuth","JWT","TLS","SSH","TCP",
        "UDP","DNS","CDN","NAT","VPN","VPC","RAM","SSD","HDD","GB","MB","TB","ms","RPM","TPM",
        "RPD","VCS","IDE","OS","Web","Bot","Bots","Agent","Agents","Auditability","Inference",
        "Schema","Format","Protocol","Specification"
    }

    def _is_name_candidate(name: str) -> bool:
        if name in ignore:
            return False
        parts = name.split()
        # `LLM API`のように一般略語だけを連結した語は固有製品名ではない。
        if parts and all(part in ignore or part.upper() in ignore for part in parts):
            return False
        # ALL-CAPS略語は原則一般技術語扱い。固有名として厳格に見るのは通常語形の製品名。
        if len(parts) == 1 and name.isupper():
            return False
        # 3文字以下の単語はノイズが多い。
        if len(name) <= 3:
            return False
        return True

    low_risk_action_cue = re.compile(
        r"(?:監査|確認|検索|スキャン|チェック|検証|比較|試す|試したい|見直|隔離|制限|拒否|"
        r"ホワイトリスト|回帰テスト|PoC|CI|私なら|推奨|すべき|必要があります|命じます)", re.I
    )

    def _looks_like_operational_artifact(name: str) -> bool:
        """LOW RISK Actionで使うローカル成果物/設定ファイル名だけを限定的に許容する。

        `Cargo.lock` のような監査手段はSource本文への逐語一致を要求しない一方、
        `Enterprise Sync` のような未確認の外部製品機能は、Action文であっても許容しない。
        """
        token = (name or "").strip()
        lowered = token.lower()
        if not token:
            return False
        if "/" in token or "\\" in token:
            return True
        if re.search(r"\.(?:lock|toml|ya?ml|json|jsonl|log|env|ini|cfg|conf|txt|csv|tsv|md|xml)$", lowered):
            return True
        return False

    for sent in sentences:
        if not factual_cue.search(sent) or inference.search(sent):
            continue
        is_low_risk_action = bool(
            low_risk_action_cue.search(sent) and classify_action_risk_tier(sent) == "LOW"
        )
        # CamelCase/TitleCase製品名候補。2語製品名も拾う。
        names = re.findall(r"(?<![A-Za-z0-9_])[A-Z][A-Za-z0-9.+_-]{2,}(?:\s+[A-Z][A-Za-z0-9.+_-]{2,})?(?![A-Za-z0-9_])", sent)
        unsupported = []
        for name in dict.fromkeys(names):
            if not _is_name_candidate(name):
                continue
            # PDF抽出で ``DiffVG`` が ``Diff VG`` / ``DiﬀVG`` になるケースを
            # 文字列一致だけで一次資料外と誤判定しない。
            compact_name = _normalized_named_fact(name)
            compact_evidence = _normalized_named_fact(alias_expanded_context)
            if _normalized_evidence_text(name) not in evidence and compact_name not in compact_evidence:
                if is_low_risk_action and _looks_like_operational_artifact(name):
                    continue
                # Run122: the current target entity plus a generic technical descriptor (SDK/API/CLI)
                # is not a newly invented third-party product name. Require both the entity identity
                # and descriptor to already exist in evidence; this cannot bootstrap an unsupported entity.
                descriptor_match = re.fullmatch(r"(.+?)\s+(SDK|API|CLI)", name, re.I)
                if descriptor_match and repo_name:
                    entity_part, descriptor = descriptor_match.group(1).strip(), descriptor_match.group(2)
                    repo_norm = _normalized_evidence_text(repo_name)
                    entity_norm = _normalized_evidence_text(entity_part)
                    if (entity_norm and (entity_norm == repo_norm or entity_norm in repo_norm or repo_norm in entity_norm)
                            and entity_norm in evidence and re.search(rf"(?<![A-Za-z0-9]){re.escape(descriptor)}(?![A-Za-z0-9])", alias_expanded_context, re.I)):
                        continue
                unsupported.append(name)
        if unsupported:
            failures.append("source-boundary unsupported named fact: " + ", ".join(unsupported[:4]))
    return list(dict.fromkeys(failures))[:6]
