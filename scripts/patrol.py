"""Record one assistant's observed quota and calculate the next suggested wake."""
from pathlib import Path
import argparse,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from board.environment import use_project_environment
if __name__=='__main__':use_project_environment(__file__)
from board.scheduler import report,TIERS
from board.provider_bridge import quota

def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('agent',choices=['Claude','GPT']);p.add_argument('--auto',action='store_true')
    p.add_argument('--tier',choices=list(TIERS),default='plenty');p.add_argument('--remaining',type=float);p.add_argument('--reset-hours',type=float)
    p.add_argument('--before',type=float);p.add_argument('--after',type=float);p.add_argument('--source',default='operator-report')
    p.add_argument('--data-dir',type=Path,default=ROOT/'data');a=p.parse_args(argv)
    if a.auto:value=quota(a.data_dir,a.agent,tier=a.tier,reset_hours=a.reset_hours if a.reset_hours is not None else 24)
    else:
        if a.reset_hours is None:p.error('Provide --reset-hours or use --auto')
        value=dict(tier=a.tier,remaining=a.remaining if a.remaining is not None else TIERS[a.tier],reset_hours=a.reset_hours,
                   precision='exact' if a.remaining is not None else 'band',source=a.source,reset_source='operator estimate or observation')
    if (a.before is None)!=(a.after is None):p.error('Provide --before and --after together')
    if a.before is not None:value.update(before=a.before,after=a.after)
    print(json.dumps(report(a.data_dir.resolve(),a.agent,**value),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
