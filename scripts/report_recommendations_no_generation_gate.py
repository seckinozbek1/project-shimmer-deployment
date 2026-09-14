"""Ordinary mechanism and safe legacy checks, with model/network access blocked."""
import builtins
import socket
import sys
import unittest
import threading


def main():
    original=builtins.__import__
    def guarded(name,*args,**kwargs):
        if name.split(".")[0] in {"torch","transformers","sentence_transformers","anthropic","openai","easyocr"}:
            raise AssertionError("Model/provider import prohibited in deterministic gate")
        return original(name,*args,**kwargs)
    def denied(*args,**kwargs):raise AssertionError("Network prohibited")
    # Windows asyncio builds its internal wakeup socketpair on loopback. Permit
    # only that stdlib operation, while every ordinary connection stays blocked.
    original_pair, original_connect = socket.socketpair, socket.socket.connect
    pairing=threading.local()
    def pair(*args,**kwargs):
        pairing.active=True
        try:return original_pair(*args,**kwargs)
        finally:pairing.active=False
    def connect(self,address):
        if getattr(pairing,"active",False):return original_connect(self,address)
        return denied()
    builtins.__import__=guarded
    socket.create_connection=denied
    socket.socketpair=pair
    socket.socket.connect=connect
    import agent_wrapper
    agent_wrapper.load_api_keys=lambda:{}
    import report_recommendations_checks
    import execution_topology_checks
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m)
                             for m in [report_recommendations_checks,execution_topology_checks])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    import verify_session1 as legacy
    counts={"PASS":result.testsRun-len(result.errors)-len(result.failures),"FAIL":len(result.errors)+len(result.failures),"SKIP":0}
    for title,check in legacy.CHECKS:
        if title.split()[0] not in {"00","01","02","03","04","07","21","22","29","260"}:continue
        status,detail=check();print(title.split()[0],status,detail)
        counts[status]=counts.get(status,0)+1
    print("ORDINARY_SAFE_GATE",counts)
    print("Full legacy/model gate and multi-round execution: NOT RUN")
    return 1 if counts["FAIL"] else 0


if __name__=="__main__":sys.exit(main())
