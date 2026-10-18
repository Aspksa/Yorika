import json
import sys
import importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
def emit(v):
 print(json.dumps(v,ensure_ascii=False),flush=True)
def main():
 data=json.loads(sys.stdin.read(5000))
 path=Path(__file__).with_name('cloud-ru-model.py')
 spec=importlib.util.spec_from_file_location('yorika_cloud_stream_model',path)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 result=module.answer(data.get('query'),conversation_id=data.get('conversation_id'),stream=True,on_delta=lambda x:emit({'type':'delta','text':x}))
 emit({'type':'done','answer':result['answer']})
if __name__=='__main__':
 try: main()
 except (ValueError,RuntimeError,OSError,TypeError):
  emit({'type':'error','message':'Cloud.ru streaming unavailable'})
  sys.exit(1)
