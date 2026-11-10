"""Read-only exact-marker discovery. Fail closed on partial/incomplete search.
No network POST, no DB side effects. Older Jira description is ADF JSON.
"""
import httpx
from integrations.publishing import provenance, validate_target

class ReconciliationError(Exception):pass

def _strings(value):
    if isinstance(value,str):
        yield value
    elif isinstance(value,list):
        for part in value:
            yield from _strings(part)
    elif isinstance(value,dict):
        for k,v in value.items():
            if k=='text' and isinstance(v,str): yield v
            else: yield from _strings(v)

def _github_issues(client,config,marker):
    target=validate_target('github',config)
    owner,repo=target.split('/')
    headers={'Authorization':'Bearer '+config['github_token'],'Accept':'application/vnd.github+json',
             'X-GitHub-Api-Version':'2022-11-28'}
    url=f'https://api.github.com/repos/{owner}/{repo}/issues'
    found=[]
    # Explicit, finite scan limit: if hit, refuse to assert absence.
    for page in range(1,201):
        response=client.get(url,headers=headers,params={'state':'all','per_page':100,'page':page})
        response.raise_for_status()
        data=response.json()
        if not isinstance(data,list):raise ReconciliationError('GitHub returned non-list issues payload')
        for issue in data:
            if 'pull_request' not in issue and marker in (issue.get('body') or ''):
                found.append({'external_id':str(issue['number']),'external_url':issue['html_url']})
        if len(data)<100:
            return found
    raise ReconciliationError('GitHub search exceeded 20,000 issues; absence unverified')

def _jira_issues(client,config,marker,story_key):
    target=validate_target('jira',config)
    site,project_key=target.rsplit('/',1)
    headers={'Accept':'application/json'}
    auth=(config['jira_email'],config['jira_api_token'])
    # Search the ENTIRE Jira project (including resolved issues) rather than trusting
    # Jira full-text indexing of the provenance marker. Fail closed if truncated.
    next_token=None
    matches=[]
    for _ in range(100):
        params={'jql':f'project = "{project_key}" ORDER BY created DESC',
                'maxResults':100,'fields':'summary,description'}
        if next_token:params['nextPageToken']=next_token
        response=client.get(site+'/rest/api/3/search/jql',params=params,auth=auth,headers=headers)
        response.raise_for_status()
        data=response.json()
        if not isinstance(data,dict) or not isinstance(data.get('issues'),list):
            raise ReconciliationError('Jira returned unexpected search payload; absence unverified')
        for issue in data['issues']:
            # Join ADF text nodes; formatting cannot split a marker across nodes in ReqFlow-generated ADF.
            description='\n'.join(_strings(issue.get('fields',{}).get('description')))
            if marker in description:
                matches.append({'external_id':issue['key'], 'external_url':site+'/browse/'+issue['key']})
        next_token=data.get('nextPageToken')
        if data.get('isLast') is False and not next_token:
            raise ReconciliationError('Jira pagination incomplete; absence unverified')
        if not next_token:
            return matches
    raise ReconciliationError('Jira candidate search truncated; absence unverified')

def scan(provider,config,project_id,backlog_id,story_key):
    marker=provenance(str(project_id),str(backlog_id),story_key)
    try:
        with httpx.Client(timeout=httpx.Timeout(30.0,connect=8.0), follow_redirects=False) as client:
            result=(_github_issues(client,config,marker) if provider=='github'
                    else _jira_issues(client,config,marker,story_key) if provider=='jira'
                    else None)
        if result is None:raise ReconciliationError('Unsupported provider')
        return {'marker':marker,'matches':result,'complete':True}
    except (httpx.HTTPError,KeyError,ValueError) as exc:
        raise ReconciliationError('Remote search failed or incomplete; retain reservation') from exc
