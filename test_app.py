import unittest,json
from unittest.mock import patch
from app import offline,triage,parse_response,validate_result,openai_classify
class TriageTests(unittest.TestCase):
 def test_billing_route(self):self.assertEqual(offline('invoice please')['category'],'billing')
 def test_urgent_technical_route(self):self.assertEqual(offline('outage error')['priority'],'urgent')
 def test_every_result_requires_review(self):self.assertTrue(triage([{'id':'1','text':'hello'}])[0]['review_required'])
 def test_invalid_tickets_do_not_stop_batch(self):self.assertEqual(triage([{'id':'1','text':''},{'id':'2','text':'hello'}])[1]['status'],'awaiting_review')
 def test_duplicate_ticket_routes_to_manual_review(self):self.assertEqual(triage([{'id':'1','text':'a'},{'id':'1','text':'b'}])[1]['status'],'manual_review')
 def test_provider_failure_falls_back_to_review(self):
  def bad(_):raise RuntimeError('Unavailable')
  self.assertEqual(triage([{'id':'1','text':'hi'}],bad)[0]['status'],'manual_review')
 def test_schema_rejects_invalid_category(self):
  with self.assertRaises(ValueError):validate_result({**offline('hi'),'category':'other'})
 def test_parses_response_api_output(self):self.assertEqual(parse_response({'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(offline('invoice'))}]}]})['category'],'billing')
 def test_incomplete_or_refused_output_fails_closed(self):
  for data in [{'status':'incomplete'},{'status':'completed','output':[{'content':[{'type':'refusal'}]}]}]:
   with self.assertRaises(ValueError):parse_response(data)
 def test_no_implicit_live_calls(self):
  with patch.dict('os.environ',{},clear=True),self.assertRaises(ValueError):openai_classify('hello')
if __name__=='__main__':unittest.main()
