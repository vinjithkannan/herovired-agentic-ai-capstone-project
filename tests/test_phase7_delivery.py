"""Pure-unit regression tests: no DB, Docker or Ollama required."""
import unittest
from agents.orchestrator.nodes import research_agent,story_agent,design_agent,design_gate,planning_agent,planning_gate


def sample():
    return {
        'project_id':'project', 'backlog_id':'backlog', 'project_title':'Attendance',
        'source_requirement_ids':['FR-001','NFR-004'],
        'requirements':[{'temporary_id':'FR-001','statement':'Faculty records attendance'},
                        {'temporary_id':'NFR-004','statement':'Response time requires PO thresholds'}],
        'evidence':{'FR-001':'supported','NFR-004':'supported'},
        'stories':[{'story_key':'US-001','title':'Record attendance','story_text':'As a faculty member, I want to record attendance, so that classes are tracked.',
                    'source_requirement_ids':['FR-001'],'approval_status':'approved','story_points':3,
                    'priority_recommendation':'must'},
                   {'story_key':'US-010','title':'Performance targets','source_requirement_ids':['NFR-004'],
                    'approval_status':'pending','story_points':None,'priority_recommendation':'should'}],
        'story_clearances':{'US-001':{'status':'quality_cleared'},'US-010':{'status':'blocked'}},
        'acceptance_criteria':[{'story_key':'US-001','criterion_key':'AC-001','criterion_text':'Given faculty, when entered, then stored.'}],
        'dependencies':[],
    }


class Phase7DeliveryTests(unittest.TestCase):
    def test_only_evidenced_requirements_researched(self):
        st=sample();out=research_agent(st)
        self.assertEqual(len(out['research_findings']),2)
        st['evidence']['FR-001']='unsupported'
        self.assertEqual([x['id'] for x in research_agent(st)['research_findings']],['NFR-004'])

    def test_blocked_story_is_not_included_even_if_approved(self):
        st=sample();st['stories'][1]['approval_status']='approved'
        st.update(research_agent(st))
        out=story_agent(st)
        self.assertEqual([x['story_key'] for x in out['eligible_stories']],['US-001'])

    def test_unapproved_stories_cannot_pass(self):
        st=sample();st['stories'][0]['approval_status']='pending';st.update(research_agent(st))
        with self.assertRaises(ValueError):story_agent(st)

    def test_design_has_traceability_and_proposals(self):
        st=sample();st.update(research_agent(st));st.update(story_agent(st))
        out=design_agent(st)['solution_design']
        self.assertEqual(out['scope']['story_keys'],['US-001'])
        self.assertTrue(out['api_proposals'])
        self.assertTrue(out['data_model_proposals'])
        self.assertTrue(out['assumptions'])
        self.assertEqual(out['status'],'draft_requires_human_review')

    def test_task_decomposition_and_proposed_estimates(self):
        st=sample();st.update(research_agent(st));st.update(story_agent(st))
        plan=planning_agent(st)['implementation_tasks']
        self.assertEqual(len(plan),3)
        self.assertEqual(plan[1]['depends_on'],['TASK-001-1'])
        self.assertEqual(plan[1]['estimate_story_points'],3)
        self.assertEqual(plan[2]['acceptance_criteria_keys'],['AC-001'])

    def test_gates_are_not_bypassed(self):
        self.assertEqual(design_gate({'design_approval':'draft'})['workflow_status'],'awaiting_design_approval')
        self.assertEqual(planning_gate({'plan_approval':'draft'})['workflow_status'],'awaiting_plan_approval')
        self.assertEqual(planning_gate({'plan_approval':'approved'})['workflow_status'],'ready_for_delivery')

    def test_no_side_effects_in_draft_agents(self):
        st=sample();st.update(research_agent(st));st.update(story_agent(st))
        design_agent(st);planning_agent(st)
        self.assertEqual(st['stories'][1]['approval_status'],'pending')


if __name__=='__main__':unittest.main()
