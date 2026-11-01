"""All 22 role-specific tests are queued without automatic provider calls."""
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from agents import catalog
from agent_benchmark_campaign import campaign_report, task_for_agent, SCENARIOS
from console_api import make_handler
from paired_review_benchmark import prepare


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.agents=[meta for meta,_ in catalog()]
    def test_full_agent_catalog_covered_with_a_distinct_role_scenario(self):
        self.assertEqual(22,len(self.agents))
        self.assertEqual({x['name'] for x in self.agents},set(SCENARIOS))
        prompts=set()
        for meta in self.agents:
            mode,topic=SCENARIOS[meta['name']]
            self.assertIn(mode,('review','architecture','fix-plan'))
            self.assertGreater(len(topic),25)
            prompt=task_for_agent(meta['name'],mode,'Base review task')
            self.assertIn('Base review task',prompt)
            self.assertIn(topic,prompt)
            prompts.add(prompt)
        self.assertEqual(22,len(prompts))
    def test_campaign_only_advances_when_latest_agent_completed_and_compared(self):
        report=campaign_report([],[],agents=self.agents)
        self.assertEqual(22,report['total_agents'])
        self.assertEqual(0,report['provisionally_assessed'])
        self.assertFalse(report['provider_calls_started'])
        self.assertFalse(report['rules_modified'])
        first=self.agents[0]['name']
        self.assertEqual(first,report['next_agent'])
        current={'run_id':'a'*32,'agent':first,'status':'completed'}
        score={'run_id':'a'*32,'agent':first,'status':'completed',
               'evaluation_status':'provisional_traceability',
               'baseline_score':60,'daeloryn_score':12,
               'provisional_evidence_lead':'baseline'}
        report=campaign_report([current],[score],agents=self.agents)
        self.assertEqual(1,report['provisionally_assessed'])
        self.assertEqual(self.agents[1]['name'],report['next_agent'])
        item=report['entries'][0]
        self.assertEqual(first,item['agent'])
        self.assertEqual('assessed_provisionally',item['state'])
        self.assertEqual({'baseline':60,'daeloryn':12},item['traceability_scores'])
        self.assertIsNone(item['verified_winner'])
        self.assertGreaterEqual(len(item['candidate_rule_improvements']),2)
        self.assertEqual(1,report['weaker_traceability_agents'])
        self.assertEqual(0,report['independently_verified_winners'])
    def test_unknown_results_are_not_scored_and_prior_evidence_cannot_advance_newer_run(self):
        a=self.agents[0]['name']
        report=campaign_report([{'run_id':'b'*32,'agent':a,'status':'failed'},
                                {'run_id':'a'*32,'agent':a,'status':'completed'}],
            [{'run_id':'a'*32,'agent':a,'status':'completed',
              'evaluation_status':'provisional_traceability','baseline_score':90,
              'daeloryn_score':50,'provisional_evidence_lead':'baseline'}],
            agents=self.agents)
        self.assertEqual(a,report['next_agent'])
        self.assertEqual('incomplete',report['entries'][0]['state'])
        self.assertEqual([],report['entries'][0]['candidate_rule_improvements'])
        report=campaign_report([{'run_id':'b'*32,'agent':a,'status':'completed'}],
            [{'run_id':'b'*32,'agent':a,'status':'completed',
              'evaluation_status':'source_evidence_unavailable','baseline_score':None,
              'daeloryn_score':None,'provisional_evidence_lead':'not_determined'}],
            agents=self.agents)
        self.assertEqual('needs_evaluation',report['entries'][0]['state'])
    def test_paired_prepare_uses_identical_specialist_question_for_both_arms(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            project=root/'demo'
            (project/'.git').mkdir(parents=True)
            (project/'App.java').write_text('class App { void run() {} }')
            java=prepare(root,'demo','review','test-model','java-reviewer')
            spring=prepare(root,'demo','review','test-model','spring-data-engineer')
            self.assertEqual(java['baseline']['files'],java['daeloryn']['files'])
            self.assertEqual(java['task'],java['task']) # both arms share same task
            self.assertIn('Java concurrency',java['task'])
            self.assertIn('JPA queries',spring['task'])
            self.assertNotEqual(java['sha256'],spring['sha256'])
            self.assertIn(java['task'],java['baseline']['prompt'])
            self.assertIn(java['task'],java['daeloryn']['prompt'])
            self.assertTrue(java['approval_required'])
    def test_project_scoped_java_spring_react_and_mixed_agent_queues(self):
        java = {"name":"java-app","technologies":["java","java-maven"]}
        spring = {"name":"spring-service","technologies":["java","java-maven","spring"]}
        react = {"name":"react-ui","technologies":["node","react","typescript"]}
        mixed = {"name":"fullstack","technologies":["java","spring","node","react","docker"]}
        runs = [{"run_id":"a"*32,"repository":"java-app","agent":"java-architect",
                 "status":"completed"}]
        comparisons = [{"run_id":"a"*32,"repository":"java-app","agent":"java-architect",
                        "status":"completed","evaluation_status":"provisional_traceability",
                        "baseline_score":20,"daeloryn_score":32,
                        "provisional_evidence_lead":"daeloryn"}]
        report = campaign_report(runs, comparisons, agents=self.agents,
                                 projects=[java,spring,react,mixed])
        entries = {row["repository"]:row for row in report["project_campaigns"]}
        self.assertEqual(4,len(entries))
        self.assertEqual("java-developer",entries["java-app"]["next_agent"])
        self.assertEqual(1,entries["java-app"]["provisionally_assessed"])
        self.assertEqual(0,entries["spring-service"]["provisionally_assessed"])
        self.assertEqual("java-architect",entries["spring-service"]["next_agent"])
        self.assertEqual("react-architect",entries["react-ui"]["next_agent"])
        self.assertEqual("java-architect",entries["fullstack"]["next_agent"])
        java_names = {x["agent"] for x in entries["java-app"]["entries"] if x["applicable"]}
        spring_names = {x["agent"] for x in entries["spring-service"]["entries"] if x["applicable"]}
        react_names = {x["agent"] for x in entries["react-ui"]["entries"] if x["applicable"]}
        mixed_names = {x["agent"] for x in entries["fullstack"]["entries"] if x["applicable"]}
        self.assertIn("java-reviewer",java_names)
        self.assertNotIn("spring-boot-engineer",java_names)
        self.assertNotIn("react-reviewer",java_names)
        self.assertIn("spring-boot-engineer",spring_names)
        self.assertIn("react-testing",react_names)
        self.assertIn("reliability-engineer",react_names)
        # Specialized React reviewers are scheduled first, even when
        # shared/platform reliability work is also applicable.
        self.assertEqual("react-architect",entries["react-ui"]["next_agent"])
        self.assertNotIn("java-reviewer",react_names)
        self.assertNotIn("spring-framework-expert",react_names)
        self.assertIn("java-reviewer",mixed_names)
        self.assertIn("spring-framework-expert",mixed_names)
        self.assertIn("react-reviewer",mixed_names)
        self.assertIn("docker-engineer",mixed_names)
        skipped = [row for row in entries["react-ui"]["entries"] if row["agent"]=="java-reviewer"][0]
        self.assertEqual("not_applicable",skipped["state"])
        self.assertIsNone(skipped["traceability_scores"])

    def test_http_campaign_endpoint_is_read_only_and_has_all_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            httpd=ThreadingHTTPServer(('127.0.0.1',0),
                make_handler(benchmark_runs_dir=Path(directory)/'runs'))
            thread=threading.Thread(target=httpd.serve_forever,daemon=True)
            thread.start()
            try:
                connection=http.client.HTTPConnection('127.0.0.1',httpd.server_port,timeout=4)
                connection.request('GET','/api/benchmark/campaign',headers={
                    'Host':'127.0.0.1:'+str(httpd.server_port),
                    'Origin':'http://127.0.0.1:5173'})
                response=connection.getresponse()
                self.assertEqual(200,response.status)
                report=json.loads(response.read())
                connection.close()
                self.assertEqual(22,report['total_agents'])
                self.assertEqual(22,len(report['entries']))
                self.assertEqual(0,report['provisionally_assessed'])
                self.assertFalse(report['provider_calls_started'])
            finally:
                httpd.shutdown()
                thread.join(3)
                httpd.server_close()


if __name__=='__main__':
    unittest.main()
