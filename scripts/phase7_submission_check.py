#!/usr/bin/env python3
"""Phase 7: read-only capstone submission checks; Python 3.10+, stdlib only.
Usage: python scripts/phase7_submission_check.py --root . --backlog path/to/export.json
Never runs destructive Docker or DB operations. Does not send network requests.
"""
import argparse, json, pathlib, sys

REQUIRED=[
 'docker-compose.yml','.env.example','.gitignore','.dockerignore',
 'backend/app/main.py','backend/app/services/story_clearance.py',
 'backend/app/api/v1/clarifications.py','frontend/src/App.tsx',
 'frontend/src/Phase61Clarifications.tsx','frontend/src/Phase7Readiness.tsx',
 'integrations/publishing.py','mcp_servers/publishing_server.py',
 'database/init/008_phase61_clarifications.sql',
 'data/sample_brd/student-attendance-management.md',
 'docs/REQFLOW_IMPLEMENTATION_GUIDE.md',
 'agents/orchestrator/graph.py', 'agents/orchestrator/nodes.py',
 'backend/app/api/v1/delivery.py', 'database/init/009_phase7_delivery.sql',
 'frontend/src/Phase7Delivery.tsx', 'scripts/demo_mcp_client.py',
 'scripts/phase7_live_smoke.py', 'tests/test_phase7_delivery.py', 'evidence/phase7_delivery_audit.json',
 'data/screenshots/unit_tests_passed.png'
]
EXCLUDED=['.env','frontend/node_modules','frontend/dist','backend/app/services/evaluation_old.py']

def verify_files(root):
    missing=[path for path in REQUIRED if not (root/path).is_file()]
    included=[path for path in EXCLUDED if (root/path).exists()]
    # Uploads are runtime data and should not be shipped in a submission.
    uploads=root/'data/uploads'
    leaked_uploads=[p.relative_to(root).as_posix() for p in uploads.rglob('*') if p.is_file() and p.name!='.gitkeep'] if uploads.exists() else []
    return {'required_files_present':not missing,'missing_files':missing,
            'local_artifacts_excluded':not (included or leaked_uploads),
            'unexpected_local_artifacts':included+leaked_uploads}

def backlog_metrics(backlog):
    stories=backlog.get('stories',[])
    clearances=backlog.get('story_clearances') or {}
    tally={'quality_cleared':0,'review_required':0,'blocked':0,'unknown':0}
    approved=eligible=0
    for story in stories:
        key=story.get('story_key')
        state=(clearances.get(key) or {}).get('status','unknown')
        if state not in tally: state='unknown'
        tally[state]+=1
        po=story.get('approval_status')=='approved'
        approved+=int(po)
        eligible+=int(po and state=='quality_cleared')
    return {'story_count':len(stories),'clearance_counts':tally,
            'product_owner_approved':approved,'clearance_and_approval_eligible':eligible,
            'acceptance_criteria_count':len(backlog.get('acceptance_criteria',[])),
            'source_requirement_ids':len(backlog.get('source_requirement_ids',[])),
            'partial_demo':tally['quality_cleared']<len(stories)}

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parents[1])
    parser.add_argument('--mode',choices=['working','submission'],default='working',
                        help='working: required files only, reports local artifacts; submission: also requires zero excluded artifacts')
    parser.add_argument('--backlog',type=pathlib.Path,help='Backlog JSON exported from the React UI (optional)')
    parser.add_argument('--output',type=pathlib.Path,help='Write local JSON report (optional; never upload automatically)')
    args=parser.parse_args(argv)
    root=args.root.resolve()
    files=verify_files(root)
    report={'check':'reqflow-phase7-scope-completion-v1','mode':args.mode,'files':files,
      'working_checkout_ok':files['required_files_present'],
      'submission_ready':files['required_files_present'] and files['local_artifacts_excluded'],
      'caveats':['No Docker, database, Ollama or live publishing test is performed by this script.',
                 'Requirement-ID evaluation metrics do not establish semantic correctness.',
                 'A partial quality-cleared backlog is acceptable only when disclosed as partial.']}
    if args.backlog:
        data=json.loads(args.backlog.read_text(encoding='utf-8'))
        if not isinstance(data,dict): parser.error('Backlog export must be a JSON object')
        report['backlog']=backlog_metrics(data)
    message=json.dumps(report,indent=2)
    print(message)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(message+'\n',encoding='utf-8')
    return 0 if (report['submission_ready'] if args.mode=='submission' else report['working_checkout_ok']) else 1

if __name__=='__main__': sys.exit(main())
