"""Real MCP stdio client for *read-only* tool discovery and preview.

Inside backend container:
  python /app/scripts/demo_mcp_client.py --project-id UUID --backlog-id UUID --story-key US-001
Requires explicitly enabled trusted MCP and valid provider configuration.
Never accepts a publishing key or invokes a live publishing tool.
"""
import argparse
import asyncio
import json
import os
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main(args):
    if os.getenv('PHASE6_ENABLE_TRUSTED_MCP','false').lower() != 'true':
        raise SystemExit('Enable PHASE6_ENABLE_TRUSTED_MCP=true only in a trusted local Docker environment.')
    # MCP's stdio launcher may provide a restricted default environment.
    # Explicitly pass PYTHONPATH so the subprocess can import the project modules.
    child_env = os.environ.copy()
    child_env['PYTHONPATH'] = os.pathsep.join(
        p for p in ['/app', '/app/backend', child_env.get('PYTHONPATH', '')] if p
    )
    proc = StdioServerParameters(
        command=sys.executable,
        args=['-m', 'mcp_servers.publishing_server'],
        env=child_env,
        cwd='/app',
    )
    async with stdio_client(proc) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            listing=await session.list_tools()
            names=[tool.name for tool in listing.tools]
            print('MCP server tools:',', '.join(names))
            required='preview_quality_cleared_story'
            if required not in names:
                raise RuntimeError('Expected preview tool missing')
            if not args.project_id or not args.backlog_id or not args.story_key:
                print('Discovery completed. For dry-run preview pass --project-id, --backlog-id and --story-key.')
                return
            result=await session.call_tool(required,{'project_id':args.project_id,
                          'backlog_id':args.backlog_id,'story_key':args.story_key,
                          'provider':args.provider})
            print(json.dumps({'tool':required,'is_error':bool(result.isError),
                              'content':[getattr(c,'text','') for c in result.content]},indent=2))
            if result.isError:
                raise RuntimeError('MCP preview reported an error')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--project-id')
    parser.add_argument('--backlog-id')
    parser.add_argument('--story-key')
    parser.add_argument('--provider',choices=['github','jira'],default='github')
    asyncio.run(main(parser.parse_args()))
