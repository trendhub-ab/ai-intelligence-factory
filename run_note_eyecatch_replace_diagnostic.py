#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

import note_draft_automation as note_base
import run190_note_persistent_cloud as run190
import run193_note_official_header_upload as upload
import run_vtcode_existing_draft_repair as repair

def inspect_existing_cover() -> dict:
    run190.install()
    profile = run190._profile_dir()
    with sync_playwright() as p:
        context = run190._launch_persistent_context(p)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            url = repair._open_exact_draft(page, profile)
            title = note_base._find_title(page)
            title_box = title.bounding_box() or {}
            before = page.evaluate("""(titleY) => {
              const out = {buttons:[], images:[]};
              for (const el of document.querySelectorAll('button,[role="button"]')) {
                const r = el.getBoundingClientRect();
                if (!r.width || !r.height || r.top >= titleY || r.top < titleY-900) continue;
                const txt=(el.innerText||'').trim();
                out.buttons.push({
                  tag:el.tagName, text:txt.slice(0,80),
                  aria:el.getAttribute('aria-label')||'',
                  title:el.getAttribute('title')||'',
                  testid:el.getAttribute('data-testid')||'',
                  name:el.getAttribute('name')||'',
                  cls:(el.className||'').toString().slice(0,180),
                  x:Math.round(r.left), y:Math.round(r.top-titleY),
                  w:Math.round(r.width), h:Math.round(r.height),
                  hasSvg:!!el.querySelector('svg'), hasImg:!!el.querySelector('img')
                });
              }
              for (const el of document.querySelectorAll('img')) {
                const r=el.getBoundingClientRect();
                if (r.width>=420 && r.height>=140 && r.top<titleY && r.top>titleY-900) {
                  out.images.push({x:Math.round(r.left),y:Math.round(r.top-titleY),w:Math.round(r.width),h:Math.round(r.height),
                    alt:el.getAttribute('alt')||'', cls:(el.className||'').toString().slice(0,180)});
                }
              }
              return out;
            }""", float(title_box.get("y",0)))
            hovered_error=""
            try:
                hover = upload.run186._candidate_header_control(page)
                hover_found = hover is not None
            except Exception as exc:
                hover_found = False
                hovered_error = type(exc).__name__ + ":" + str(exc)
            page.wait_for_timeout(500)
            after = page.evaluate("""(titleY) => {
              const out=[];
              for (const el of document.querySelectorAll('button,[role="button"]')) {
                const r=el.getBoundingClientRect();
                if (!r.width || !r.height || r.top >= titleY || r.top < titleY-900) continue;
                out.push({
                  tag:el.tagName, text:(el.innerText||'').trim().slice(0,80),
                  aria:el.getAttribute('aria-label')||'', title:el.getAttribute('title')||'',
                  testid:el.getAttribute('data-testid')||'', name:el.getAttribute('name')||'',
                  cls:(el.className||'').toString().slice(0,180),
                  x:Math.round(r.left), y:Math.round(r.top-titleY),
                  w:Math.round(r.width), h:Math.round(r.height),
                  hasSvg:!!el.querySelector('svg'), hasImg:!!el.querySelector('img')
                });
              }
              return out;
            }""", float(title_box.get("y",0)))
            return {
              "status":"read_only_existing_cover_diagnostic",
              "same_edit_route":True,
              "title":repair.audit_base._title_value(page),
              "cover_media_identity":repair._header_media_identity(page)[:16],
              "before":before,
              "hover_candidate_found":hover_found,
              "hover_error":hovered_error,
              "after_hover":after,
              "mutated":False,
              "public_release":False
            }
        finally:
            context.close()

if __name__=="__main__":
    print(json.dumps(inspect_existing_cover(), ensure_ascii=False, sort_keys=True))
