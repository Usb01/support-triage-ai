"""Local FAQ chat demonstration. Extractive retrieval, not an LLM or vector RAG."""
import json
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from app import offline

FAQ = [
    {'id': 'demo-billing', 'title': 'Sample billing policy', 'keywords': {'invoice','billing','payment','receipt'}, 'answer': 'In this fictional service, invoices are available in Billing > Documents. A human support agent handles payment disputes.'},
    {'id': 'demo-access', 'title': 'Sample account access guide', 'keywords': {'login','password','access','account'}, 'answer': 'For this fictional service, use the password-reset option on the sign-in page. Never share your password with support.'},
    {'id': 'demo-refund', 'title': 'Sample refund policy', 'keywords': {'refund','cancel','cancellation'}, 'answer': 'Refund requests require human review in this demo. The assistant cannot approve a refund or cancel a subscription.'},
]

def answer(question):
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 2000:
        raise ValueError('Enter a question between 1 and 2000 characters.')
    tokens = set(re.findall(r'[a-z]+', question.lower()))
    ranked = sorted(((len(tokens & item['keywords']), item) for item in FAQ), key=lambda pair: pair[0], reverse=True)
    score, item = ranked[0]
    ambiguous = score > 0 and score == ranked[1][0]
    found = score > 0 and not ambiguous
    return {'answer': item['answer'] if found else 'I could not identify one matching FAQ. Please clarify your question or request human review.', 'source': {'id': item['id'], 'title': item['title']} if found else None, 'review_required': not found or item['id'] == 'demo-refund', 'triage': offline(question), 'mode': 'offline keyword retrieval; synthetic policies'}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path != '/':
            self.send_error(404)
            return
        content = Path(__file__).with_name('chatbot.html').read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        if self.path != '/chat':
            self.send_error(404)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 8192:
                raise ValueError('Invalid request size.')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('Expected an object.')
            result = answer(body.get('question'))
            code = 200
        except (ValueError, TypeError):
            result, code = {'error': 'Provide a JSON question of 1–2000 characters.'}, 400
        payload = json.dumps(result).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

if __name__ == '__main__':
    print('Open http://127.0.0.1:8765 — local synthetic demo, no external calls.', flush=True)
    HTTPServer(('127.0.0.1', 8765), Handler).serve_forever()
