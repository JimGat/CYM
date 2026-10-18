#!/usr/bin/env python3
"""CYM FSD USB operator driver v3.0.19, based on co-developer @birolt29's fsd.py.
Normal Development console firmware includes FSD. No flashing, reset, GPS relay,
affirmative popup dismissal, or transmitting automation. Artifacts next to script.
"""
import argparse, base64, datetime, json, re, threading, time
from pathlib import Path
VERSION = "3.0.19"
BOARDS = {"nm-cyd-c5", "ws-c5-28", "ws-c5-35", "pancake-c5", "hosyond-s3-35", "ws-s3-5b"}
UNSUPPORTED = {"cyd-2432s028", "hackerbox-cyd"}
TOOLS = "Tools \u0026 System"
# Reviewed menu-only edges. Validate WHOLE route before serial is even opened.
# Neither tile discovery nor a label denylist grants permission to transmit.
SAFE_ROUTES = {(), ("Settings",), (TOOLS,), (TOOLS, "Settings")}
CRASH = re.compile(rb"Guru Meditation|abort\(\) was called|rst:0x|ESP-ROM:|Backtrace:|panic", re.I)
class FsdError(RuntimeError): pass
class Unsupported(FsdError): pass
class Unavailable(FsdError): pass

def route_for(suite, scope):
    route = tuple(x.strip() for x in scope.split(">")) if scope else ()
    if any(not x or any(c in x for c in "\r\n\x00") for x in route): raise FsdError("invalid route")
    if suite != "smoke" and not route: raise FsdError("path/menu requires reviewed route")
    if suite == "smoke" and route: raise FsdError("smoke does not take route")
    if route not in SAFE_ROUTES: raise FsdError("route not reviewed as menu-only; no command sent")
    return route

def decode_shot(raw):
    """Only complete framed rows; never pad or filter arbitrary text into base64."""
    if "unsupported: no PSRAM" in raw: raise Unsupported("screenshot unsupported: no PSRAM")
    headers=list(re.finditer(r"<<<SHOT w=(\d+) h=(\d+) fmt=rgb888>>>\r?\n",raw))
    if len(headers)!=1 or "<<<SHOTERR" in raw or "shot error:" in raw: raise FsdError("invalid screenshot header/error")
    m=headers[0]; w,h=map(int,m.groups())
    if not (1<=w<=800 and 1<=h<=800): raise FsdError("screenshot dimensions outside bounds")
    end=raw.find("<<<ENDSHOT>>>",m.end())
    if end<0 or raw.count("<<<ENDSHOT>>>")!=1: raise FsdError("incomplete screenshot")
    rows=[]
    for line in raw[m.end():end].splitlines():
        if not line.startswith("SHOTROW"): continue  # logs retained in serial.raw
        row=re.fullmatch(r"SHOTROW y=(\d+) data=([A-Za-z0-9+/]*={0,2})",line)
        if not row or int(row[1])!=len(rows) or len(rows)>=h: raise FsdError("invalid/duplicate/out-of-order row")
        try: data=base64.b64decode(row[2],validate=True)
        except ValueError as exc: raise FsdError("invalid base64") from exc
        if len(data)!=w*3: raise FsdError("short/oversized screenshot row")
        rows.append(data)
    if len(rows)!=h: raise FsdError("missing rows; no synthetic padding")
    return w,h,b"".join(rows)

class Console:
    """Continuous serial reader; no input reset/discard. Injectable synthetic transport."""
    def __init__(self,port,directory,transport=None):
        self.raw=(Path(directory)/"serial.raw").open("xb",buffering=0)
        if transport is None:
            try:
                import serial
                transport=serial.Serial(port=None,baudrate=115200,timeout=0.1)
                transport.port=port;transport.dtr=False;transport.rts=False;transport.open()
            except (ImportError,OSError) as exc:
                self.raw.close()
                if transport is not None: transport.close()
                raise Unavailable("serial connection unavailable: "+str(exc)) from exc
        self.sp=transport
        self.cv=threading.Condition();self.buffer=bytearray();self.base=0;self.total=0
        self.crashes=[];self.error=None;self.stopped=False
        self.thread=threading.Thread(target=self._reader,daemon=True);self.thread.start()
    def _reader(self):
        tail=b""
        try:
            while not self.stopped:
                chunk=self.sp.read(65536)
                if not chunk: continue
                self.raw.write(chunk)
                with self.cv:
                    scan=tail+chunk
                    if CRASH.search(scan): self.crashes.append({"offset":self.total,"evidence":scan.decode("utf-8","replace")})
                    tail=scan[-128:];self.buffer.extend(chunk);self.total+=len(chunk)
                    if len(self.buffer)>8*1024*1024:
                        drop=len(self.buffer)-8*1024*1024;del self.buffer[:drop];self.base+=drop
                    if self.total>128*1024*1024: self.error="128MiB raw-log limit; stopped";self.stopped=True
                    self.cv.notify_all()
        except Exception as exc:
            with self.cv: self.error=repr(exc);self.cv.notify_all()
    def cmd(self,line,done,max_s=8):
        if any(c in line for c in "\r\n\x00") or len(line.encode())>98: raise FsdError("unsafe/oversized command")
        with self.cv:
            start=self.total
            if self.error or self.crashes: raise FsdError(self.error or "crash evidence; no more commands")
            self.sp.write((line+"\r").encode());deadline=time.monotonic()+max_s
            while True:
                if self.error or self.crashes: raise FsdError(self.error or "crash/reset evidence")
                if start<self.base: raise FsdError("response exceeded bounded receive buffer")
                raw=bytes(self.buffer[start-self.base:]).decode("utf-8","replace")
                if "Unrecognized command" in raw: raise Unavailable(raw)
                if re.search(r"(?:\w+ error:|Console error:)",raw):
                    if "unsupported" in raw: raise Unsupported(raw)
                    raise FsdError(raw)
                if done(raw): return raw
                left=deadline-time.monotonic()
                if left<=0: raise FsdError("timeout; no automatic retry, late outcome indeterminate")
                self.cv.wait(min(left,0.1))
    def where(self):
        raw=self.cmd("where",lambda s: re.search(r"where depth=\d+ back_fn=\w+ stack=\[.*?\]",s) is not None)
        m=re.search(r"where depth=(\d+) back_fn=(\w+) stack=\[(.*?)\]",raw)
        return {"depth":int(m[1]),"back_fn":m[2],"stack":m[3]}
    def heap(self):
        raw=self.cmd("heap",lambda s: re.search(r"psram_largest=\d+\r?\n",s) is not None)
        keys={"internal_free","internal_largest","internal_min","dma_free","dma_largest","psram_free","psram_largest"}
        v={k:int(v) for k,v in re.findall(r"(\w+)=(\d+)",raw) if k in keys}
        if set(v)!=keys: raise FsdError("incomplete heap response")
        return v
    def tree(self):
        raw=self.cmd("tree",lambda s:"<<<ENDTREE>>>" in s,15)
        if "<<<TREE>>>" not in raw: raise FsdError("missing tree start")
        return raw
    def tapt(self,label): return self.cmd("tapt "+label,lambda s:"tapt ok id=" in s)
    def nav(self,name): return self.cmd("nav "+name,lambda s:"nav ok" in s)
    def back(self): return self.cmd("back",lambda s:"back ok" in s)
    def shot(self,path):
        raw=self.cmd("shot",lambda s:"<<<ENDSHOT>>>" in s or "<<<SHOTERR" in s,60)
        w,h,data=decode_shot(raw)
        from PIL import Image
        Image.frombytes("RGB",(w,h),data).save(path)
        return {"width":w,"height":h,"bytes":len(data)}
    def close(self):
        self.stopped=True;self.thread.join(timeout=2);self.sp.close()
        if self.thread.is_alive(): self.thread.join(timeout=2)
        self.raw.close()
        if self.thread.is_alive(): raise FsdError("serial reader did not stop")

class Run:
    def __init__(self,board,suite,args,console_factory=Console):
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        self.dir=Path(__file__).resolve().parent/"fsd-runs"/f"{stamp}_{board}_{suite}"
        self.dir.mkdir(parents=True,exist_ok=False)
        self.board=board;self.suite=suite;self.args=args;self.steps=[];self.c=None
        self.console_factory=console_factory
    def open(self):
        self.c=self.console_factory(self.args.port,self.dir)
    def step(self,action,expected):
        record={"action":action,"expected":expected,"status":"failed"};self.steps.append(record)
        try:
            time.sleep(self.args.settle);record["where"]=self.c.where();record["heap"]=self.c.heap()
            if self.steps[:-1] and self.steps[0].get("heap"):
                record["heap_delta_from_start"]={k:v-self.steps[0]["heap"][k] for k,v in record["heap"].items()}
            record["shot"]=self.c.shot(self.dir/f"{len(self.steps):02d}.png");record["png"]=f"{len(self.steps):02d}.png"
            if record["where"]["stack"]!=expected or record["where"]["depth"]!=(expected.count(" > ")+1 if expected else 0): raise FsdError("unexpected destination; stopped")
            record["status"]="passed"
        except (Unsupported,Unavailable) as exc: record["status"]="unsupported" if isinstance(exc,Unsupported) else "unavailable";record["error"]=str(exc);raise
        except Exception as exc: record["error"]=str(exc);raise
        finally: print(record["status"].upper(),action,flush=True)
        return record
    def report(self):
        close_error=None
        if self.c:
            try: self.c.close()
            except Exception as exc:
                close_error=repr(exc);self.steps.append({"action":"serial cleanup","status":"failed","error":close_error})
        result={"script_version":VERSION,"board":self.board,"suite":self.suite,"steps":self.steps,"crashes":self.c.crashes if self.c else [],"reader_error":self.c.error if self.c else "not opened"}
        statuses={s["status"] for s in self.steps}
        result["status"]="passed" if self.steps and statuses<={"passed","skipped"} and not result["crashes"] and not result["reader_error"] else "failed"
        if not close_error and not result["crashes"] and "failed" not in statuses:
            if "unavailable" in statuses: result["status"]="unavailable"
            elif "unsupported" in statuses: result["status"]="unsupported"
        (self.dir/"report.json").write_text(json.dumps(result,indent=2)+"\n")
        (self.dir/"report.txt").write_text("FSD "+VERSION+": "+result["status"]+"\nRaw serial: serial.raw (privacy-sensitive)\n"+"\n".join(json.dumps(s) for s in self.steps)+"\n")
        print("Artifacts:",self.dir);return result["status"]

def execute(r,route):
    # Operator stops running RF tools and manually returns Home before the run.
    # No automatic escape from an unknown screen and no popup confirmation.
    r.step("initial Home (operator-prepared)","");visited=[]
    for label in route:
        r.c.tapt(label);visited.append(label);r.step("open "+label," > ".join(visited))
    if r.suite=="menu": r.steps.append({"action":"unreviewed child tiles","status":"skipped","reason":"no arbitrary traversal or popup dismissal"})
    r.c.tree()
    while visited:
        r.c.back();visited.pop();r.step("Back"," > ".join(visited))

def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument("board");ap.add_argument("suite",choices=["smoke","path","menu"])
    ap.add_argument("scope",nargs="?",default="");ap.add_argument("--port",required=True);ap.add_argument("--settle",type=float,default=1.0);ap.add_argument("--version",action="version",version=VERSION)
    a=ap.parse_args(argv)
    try:
        if a.board in UNSUPPORTED: raise Unsupported("board console disabled; no FSD")
        if a.board not in BOARDS: raise Unsupported("unknown/unqualified board")
        if not 0<=a.settle<=30: raise FsdError("settle must be 0..30 seconds")
        route=route_for(a.suite,a.scope)
    except FsdError as exc: print(type(exc).__name__+": "+str(exc));return 2
    r=None
    try: r=Run(a.board,a.suite,a);r.open();execute(r,route)
    except Exception as exc:
        print(type(exc).__name__+": "+str(exc))
        if r: r.steps.append({"action":"run aborted","status":"unavailable" if isinstance(exc,Unavailable) else "unsupported" if isinstance(exc,Unsupported) else "failed","error":str(exc)})
        else: return 1
    finally:
        if r: status=r.report()
    return 0 if status=="passed" else 1
if __name__=="__main__": raise SystemExit(main())
