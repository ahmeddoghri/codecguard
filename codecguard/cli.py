from __future__ import annotations
import argparse, json
from .core import benchmark, demo
from .server import serve

def main() -> None:
    parser=argparse.ArgumentParser(prog="codecguard"); sub=parser.add_subparsers(dest="command",required=True)
    run=sub.add_parser("benchmark"); run.add_argument("directory"); run.add_argument("--codec",default="aac"); run.add_argument("--bitrate",default="192k")
    sub.add_parser("demo"); server=sub.add_parser("serve"); server.add_argument("--host",default="127.0.0.1"); server.add_argument("--port",type=int,default=8090)
    args=parser.parse_args()
    if args.command=="serve": serve(args.host,args.port); return
    print(json.dumps(demo() if args.command=="demo" else benchmark(args.directory,args.codec,args.bitrate),indent=2))
