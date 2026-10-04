"""Continue four existing smoke policies locally; no Hermes/model-provider calls."""
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen

from backend.learning_protocol import request_body


def api(path, body=None):
    request=Request('http://127.0.0.1:8787/api/'+path,
                    data=json.dumps(body).encode() if body is not None else None,
                    headers={'Content-Type':'application/json'})
    with urlopen(request,timeout=30) as response:return json.load(response)


def main():
    results=[]
    for environment in ('aloha','transfer'):
        for algorithm in ('ppo','sac'):
            source=next(j for j in api('training') if j['policy']==algorithm and j['kind']=='training'
                        and j['status']=='completed' and j['config'].get('environment')==environment
                        and j['config']['mode']=='new')
            body={**request_body(source['config']),'mode':'resume','source_job':source['id']}
            started=api('training',body)
            deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                state=api('training/current')
                if state['status'] not in ('running','stopping'):break
                time.sleep(.5)
            assert state['id']==started['id'] and state['status']=='completed',state.get('logs',[])[-4:]
            info=json.loads((Path('outputs/training')/state['id']/'model/training_info.json').read_text())
            assert info['num_timesteps']==source['config']['steps']*2
            assert info['gradient_updates']>0
            results.append({'environment':environment,'algorithm':algorithm,'job':state['id'],
                            'source':source['id'],'total_steps':info['num_timesteps'],'updates':info['gradient_updates']})
            print(results[-1],flush=True)
    Path('outputs/mujoco-continuation-verification.json').write_text(json.dumps(results,indent=2)+'\n')


if __name__=='__main__':main()
