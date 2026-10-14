"""Small HTML report renderer; escapes all supplied data."""
import html, json
from pathlib import Path

def report(path, title, subtitle, rows, metrics):
    cards=''.join('<div class="metric"><strong>'+html.escape(str(v))+'</strong><span>'+html.escape(k)+'</span></div>' for k,v in metrics.items())
    headers=list(rows[0]) if rows else []
    table='<tr>'+''.join('<th>'+html.escape(str(k))+'</th>' for k in headers)+'</tr>'
    for row in rows:
        table+='<tr>'+''.join('<td>'+html.escape(str(row.get(k,'')))+'</td>' for k in headers)+'</tr>'
    text="""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>TITLE</title><style>body{background:#0b1324;color:#eaf1ff;font:16px system-ui;margin:0}main{max-width:1150px;padding:60px 32px;margin:auto}small{color:#70ddc2;letter-spacing:3px}h1{font-size:48px;letter-spacing:-2px;margin-bottom:12px}p{color:#a9bad1;line-height:1.7}.metrics{display:flex;gap:16px;flex-wrap:wrap;margin:36px 0}.metric{background:#17253c;border:1px solid #2d425f;border-radius:16px;padding:25px;min-width:130px;flex:1}.metric strong{display:block;font-size:38px;color:#70ddc2}.metric span{display:block;margin-top:8px;color:#b6c7de}.table{overflow:auto;background:#142037;border:1px solid #2d425f;border-radius:16px}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:18px;border-bottom:1px solid #2d425f;vertical-align:top;font-size:14px}th{color:#70ddc2;white-space:nowrap}footer{margin-top:36px;color:#8399b8;font-size:12px}</style><main><small>USMAN SALEEM BHATTI / AUTOMATION LAB</small><h1>TITLE</h1><p>SUBTITLE</p><section class="metrics">CARDS</section><section class="table"><table>TABLE</table></section><footer>Portfolio demonstration · synthetic sample data · not a client deployment</footer></main></html>"""
    text=text.replace('TITLE',html.escape(title)).replace('SUBTITLE',html.escape(subtitle)).replace('CARDS',cards).replace('TABLE',table)
    Path(path).parent.mkdir(parents=True,exist_ok=True);Path(path).write_text(text,encoding='utf-8')
