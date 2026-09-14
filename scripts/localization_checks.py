"""Authored presentation fixtures only. No model, provider, server or GPU execution."""
import ast
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import io
import argparse
from contextlib import redirect_stderr
from unittest.mock import patch
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import localization as loc
import run_options
import amendment_render
import summary_generators
import finding_record
import audit_synthesizer
import absence_prediction
import run_context

ROOT = Path(__file__).resolve().parent.parent
SOURCE = "Completed Warning Evidence: exact source 3.5 t/ha [REF-0001]."
PAYLOAD = {"document_id":"DOC-1", "amendments":[{
    "convention_ref":"CONV-001", "location":"REF-0001", "context_refs":["REF-0002"],
    "original_text":SOURCE, "proposed_text":"Önerilen ifade 3.5 t/ha.", "comment":"Gerekçe.",
    "action":"rephrase", "severity":"advisory", "finding_type":"missing_field", "uncertain":True},
    {"convention_ref":"CONV-002", "location":"REF-0002", "original_text":"Unanchored source quotation",
     "comment":"İkinci gerekçe.", "action":"flag", "severity":"high"}], "_validator_errors":[]}


def texts(path):
    with ZipFile(path) as archive:
        return {name:[n.text or "" for n in ET.fromstring(archive.read(name)).iter()
                      if n.tag.rsplit("}",1)[-1] in {"t","delText"}]
                for name in ["word/document.xml","word/comments.xml"]}


def pipeline_function(name):
    tree = ast.parse((ROOT / "scripts/pipeline.py").read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = dict(localization=loc, Path=Path, datetime=datetime, timezone=timezone, json=json,
                 absence_prediction=absence_prediction, run_context_mod=run_context)
    exec(compile(ast.Module(body=[node],type_ignores=[]),name,"exec"),scope)
    return scope[name]


class LocalizationChecks(unittest.TestCase):
    def test_english_identity_and_unknown_fallback(self):
        for value in ["Completed","Output language","REF-0001","extension_token"]:
            self.assertEqual(loc.text(value,"en"),value)
        self.assertEqual(loc.label("concession","en"),"concession")
        self.assertEqual(loc.label("REF-0001","tr"),"REF-0001")

    def test_turkish_known_chrome(self):
        for source in ["Completed","Unavailable","Warning","Recommendation","Evidence","Review findings",
                       "Tracked changes","Output language","No results","Process finished"]:
            self.assertNotEqual(loc.text(source,"tr"),source)

    def test_fixed_validation_and_refusal_messages(self):
        for message in ["invalid token","run_id not found","contract validation failed",
                        "invalid_output_language","no pending approval for this run_id"]:
            self.assertNotEqual(loc.message(message,"tr"),message)
            self.assertEqual(loc.message(message,"en"),message)

    def test_parameterized_errors_preserve_payload(self):
        original='file "Evidence.pdf" is 123 bytes, over the SHIMMER_MAX_UPLOAD_MB (2 MB) per-file cap'
        result=loc.message(original,"tr")
        self.assertIn('"Evidence.pdf"',result); self.assertIn('123 bayt',result);self.assertIn('(2 MB)',result)
        self.assertEqual(loc.message(original,"en"),original)

    def test_docx_real_xml_and_source_preservation(self):
        original=deepcopy(PAYLOAD)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'review.docx'
            amendment_render.render_amendments_docx(PAYLOAD,path,body_text=SOURCE,output_language="tr")
            parts=texts(path);body=parts['word/document.xml'];comments=parts['word/comments.xml']
            self.assertIn(SOURCE,body)
            self.assertIn("İzlenen değişikliklerle kaynak metin",body)
            self.assertIn("Ek değişiklikler (kaynak metinde eşleşen yer bulunamadı)",body)
            self.assertTrue(any("Bağlam kaynakları:" in v for v in comments))
            self.assertTrue(any("CONV-001" in v and "REF-0001" in v for v in comments))
            self.assertTrue(any("Yeniden ifade et" in v for v in body))
            structural="\n".join(v for v in body+comments if v not in {SOURCE,"Unanchored source quotation"})
            for forbidden in ['Source text with tracked changes','Additional amendments','References cited by','Context references:','Convention review','Amendment ']:
                self.assertNotIn(forbidden,structural)
        self.assertEqual(PAYLOAD,original)

    def test_english_docx_has_original_headings(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'review.docx'
            amendment_render.render_amendments_docx(PAYLOAD,path,body_text=SOURCE)
            p=texts(path)
            self.assertIn('Source text with tracked changes',p['word/document.xml'])
            self.assertIn('Additional amendments (no anchor found in source body)',p['word/document.xml'])
            self.assertIn('References cited by the amendments above',p['word/document.xml'])
            self.assertTrue(any('Context references:' in v for v in p['word/comments.xml']))

    def test_saved_run_option_reaches_docx_and_markdown(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'audit').mkdir()
            (root/'audit/run_options.json').write_text(json.dumps(dict(schema_version=1,input_language='auto',output_language='tr',agent_briefs='enabled')))
            result=amendment_render.write_amendment_deliverables(PAYLOAD,deliv_dir=root/'deliverables',doc_id='DOC-1',body_text=SOURCE)
            self.assertFalse(result.get('docx_error'),result.get('docx_error'))
            path=root/'deliverables/DOC-1'
            self.assertIn('İnceleme',(path/run_context.DELIVERABLE_FILENAMES['amendments_md']).read_text(encoding='utf-8'))
            self.assertIn('İzlenen değişikliklerle kaynak metin',texts(path/run_context.DELIVERABLE_FILENAMES['amendments_docx'])['word/document.xml'])
            self.assertEqual(json.loads((path/run_context.DELIVERABLE_FILENAMES['amendments_json']).read_text(encoding='utf-8')),PAYLOAD)

    def test_empty_docx_still_turkish(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'empty.docx'
            amendment_render.render_amendments_docx({'document_id':'DOC-EMPTY','amendments':[]},path,output_language='tr')
            self.assertIn('İzlenen değişikliklerle kaynak metin',texts(path)['word/document.xml'])

    def test_context_report_owned_narrative_and_quotes(self):
        refs=[dict(ref_id='REF-0001',document_name='Evidence.pdf',text_excerpt=SOURCE,location={'page':2,'paragraph':3})]
        args=dict(document_id='DOC-1',document_name='Evidence.pdf',context_refs=refs,
                  body_text='This document was reviewed against 2 conventions. 1 findings were produced by PRACTICE_AUDITOR and STYLE_GUARDIAN. The context references below are filtered for topical relevance to Evidence.pdf.')
        tr=summary_generators.render_context_summary(**args,output_language='tr')
        en=summary_generators.render_context_summary(**args)
        self.assertIn('Bağlam özeti',tr);self.assertIn('Bu belge 2 kurala',tr);self.assertIn(SOURCE,tr)
        self.assertIn('Context summary',en);self.assertIn('This document was reviewed',en)
        self.assertIn('Evidence.pdf',tr);self.assertEqual(refs[0]['text_excerpt'],SOURCE)

    def test_operative_report_source_and_empty_state(self):
        args=dict(document_id='DOC-1',document_name='name.pdf',conventions_by_category={'SOURCE-ID':[]},findings=[],question=SOURCE)
        tr=summary_generators.render_operative_summary(**args,output_language='tr')
        self.assertIn('Belge özeti',tr);self.assertIn('Operatör sorusu',tr);self.assertIn(SOURCE,tr)
        self.assertIn('bu kategoride kural yok',tr)
        self.assertIn('Operative summary',summary_generators.render_operative_summary(**args))

    def test_prior_report_headings_do_not_change_records(self):
        item=dict(relation='absent_since_prior',provenance='computed',value_b=3.5,unit_b='t/ha',unit_id='U-1',rule_id='CONV-1',source_refs=['REF-1'])
        original=deepcopy(item)
        tr='\n'.join(finding_record.render_prior_comparison([item],output_language='tr'))
        self.assertIn('Önceki sürümle karşılaştırma',tr);self.assertIn('3.5t/ha',tr);self.assertNotIn('Moved toward',tr)
        self.assertEqual(item,original)

    def test_audit_summary_localizes_owned_messages(self):
        summary=dict(generated_at='2026-09-14',bus_messages=2,findings=[dict(severity='high',category='governance',summary="escalation topic 'TOPIC-1' recurred 3 times")],delta_proposals=[])
        tr=audit_synthesizer._render_md(summary,output_language='tr')
        self.assertIn('Denetim özeti',tr);self.assertIn('TOPIC-1',tr);self.assertIn('3 kez',tr)
        self.assertNotIn('DELTA proposals',tr)

    def test_run_summary_actual_writer_and_per_agent(self):
        with tempfile.TemporaryDirectory() as d:
            write=pipeline_function('write_deliverables_run_summary')
            p=write(Path(d)/'deliverables',[],{},total_cost_usd=3.5,task='review',question=SOURCE,output_language='tr')
            text=p.read_text(encoding='utf-8');self.assertIn('Çalışma özeti',text);self.assertIn('$3.5000',text);self.assertIn(SOURCE,text)
        render=pipeline_function('_render_per_agent_md')
        result=render({'id':'DOC-1','name':'Evidence.pdf'},[],[],[],output_language='tr')
        self.assertIn('ajan bazında çıktı',result);self.assertIn('ajan çalışmadı',result);self.assertIn('PROCESSOR',result)

    def test_context_isolation_and_english_restoration(self):
        @loc.presentation
        def render():return loc.text('Completed')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda l:render(output_language=l),['tr','en']*10))
        self.assertEqual(results,['Tamamlandı','Completed']*10)
        self.assertEqual(loc.current(),'en')

    def test_console_assets_inlined_without_requests(self):
        result=loc.console_document(ROOT/'scripts/ui/console.html')
        self.assertNotIn('<script src="localization',result)
        self.assertIn('var SHIMMER_TR = ',result);self.assertIn('var ShimmerLocale = ',result)
        self.assertNotIn('T?rk?e',result)

    def test_live_shipped_ui_offline(self):
        result=subprocess.run(['node',str(ROOT/'scripts/ui/localization_checks.js')],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('16 offline localization UI checks',result.stdout)

    def test_localization_failure_is_detected_and_restored(self):
        catalog=loc.catalog();saved=catalog['Completed']
        try:
            catalog['Completed']='Completed'
            self.assertEqual(loc.text('Completed','tr'),'Completed')
            with self.assertRaises(AssertionError):self.assertNotEqual(loc.text('Completed','tr'),'Completed')
        finally:catalog['Completed']=saved
        self.assertEqual(loc.text('Completed','tr'),'Tamamlandı')

    def test_cli_output_progress_and_response_tokens(self):
        @loc.cli_presentation
        def run(argv):
            out=io.StringIO()
            loc.operator_print('  calls: 3  failures: 1',file=out)
            loc.operator_print('[progress] event=complete docs=1 status=done',file=out)
            with patch('builtins.input',return_value='APPROVE') as read:
                self.assertEqual(loc.operator_input('Decision (APPROVE / DENY / DEFER): '),'APPROVE')
                self.assertEqual(read.call_args.args[0],'Karar (APPROVE / DENY / DEFER): ')
            return out.getvalue()
        result=run(['--output-language=tr'])
        self.assertIn('çağrılar: 3  başarısızlıklar: 1',result)
        self.assertIn('[progress] event=complete docs=1 status=done',result)
        self.assertEqual(loc.current(),'en')

    def test_cli_help_keeps_options_and_values(self):
        import agent_activation
        tree=ast.parse((ROOT/'scripts/pipeline.py').read_text(encoding='utf-8'))
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_build_arg_parser')
        scope=dict(argparse=argparse,agent_activation=agent_activation)
        exec(compile(ast.Module(body=[node],type_ignores=[]),'cli','exec'),scope)
        english=scope['_build_arg_parser']().format_help()
        @loc.cli_presentation
        def run(argv):
            parser=loc.localize_parser(scope['_build_arg_parser']())
            args=parser.parse_args(['--output-language','tr'])
            self.assertEqual(args.output_language,'tr');self.assertFalse(args.multi_round)
            return parser.format_help()
        turkish=run(['--output-language','tr'])
        self.assertIn('Execution scheduling',english);self.assertNotIn('Execution scheduling',turkish)
        self.assertIn('yürütme planlaması',' '.join(turkish.split()))
        self.assertIn('--output-language',turkish);self.assertIn('{en,tr}',turkish)

    def test_computed_amendment_comment_is_localized_without_master_change(self):
        from paired_review import amendment_from_finding
        item=dict(rule_id='CONV-001',unit_id='U-1',source_refs=['REF-0001'],relation='above_band',
                  value_a=3.5,unit_a='t/ha',value_b=2,unit_b='t/ha',record_verdict='irregular')
        amendment=amendment_from_finding(item,unit_texts={'U-1':{'text':SOURCE}})
        before=deepcopy(amendment)
        shown=loc.message(amendment['comment'],'tr')
        self.assertIn('Hesaplanan değer 3.5 t/ha',shown)
        self.assertIn('üst sınırı 2 t/ha',shown)
        self.assertIn('model tarafından değerlendirilmedi',shown)
        self.assertIn('CONV-001',shown);self.assertIn('REF-0001',shown)
        self.assertNotIn('Computed in code',shown)
        self.assertEqual(amendment,before)

    def test_parser_error_localizes_but_preserves_invalid_value(self):
        @loc.cli_presentation
        def run(argv):
            parser=loc.localize_parser(argparse.ArgumentParser(prog='shimmer'))
            parser.add_argument('--output-language',choices=['en','tr'])
            stream=io.StringIO()
            with redirect_stderr(stream),self.assertRaises(SystemExit):
                parser.parse_args(['--output-language','INVALID-ID'])
            return stream.getvalue()
        result=run(['--output-language','tr'])
        self.assertIn('kullanım:',result);self.assertIn('geçersiz seçim',result)
        self.assertIn('INVALID-ID',result);self.assertNotIn('invalid choice',result)


if __name__ == '__main__':
    unittest.main()
