"""Verify the untouched old runtime can read newly-created SYNTHETIC secrets/tokens."""
import json,subprocess
from pathlib import Path

def main():
    root=Path('F:/PAO-ACOS');candidate=Path('F:/Apex/phase3-candidate')
    new=candidate/'.runtime/backend-security-venv/Scripts/python.exe';old=root/'.venv/Scripts/python.exe'
    producer='''import json,base64,jwt;from cryptography.fernet import Fernet;from importlib.metadata import version
k="synthetic-rollback-only-"+"0"*48;f=base64.urlsafe_b64encode(bytes(range(32)))
assert version("PyJWT")=="2.15.1" and version("cryptography")=="50.0.2"
print(json.dumps({"token":jwt.encode({"sub":"synthetic","iss":"pao-local","aud":"pao-api","exp":4102444800},k,algorithm="HS256"),"cipher":Fernet(f).encrypt(b"synthetic rollback only").decode()}))'''
    consumer='''import sys,json,base64,jwt;from cryptography.fernet import Fernet;from importlib.metadata import version
v=json.load(sys.stdin);k="synthetic-rollback-only-"+"0"*48;f=base64.urlsafe_b64encode(bytes(range(32)))
assert version("PyJWT")=="2.13.0" and version("cryptography")=="49.0.0"
assert jwt.decode(v["token"],k,algorithms=["HS256"],issuer="pao-local",audience="pao-api")["sub"]=="synthetic"
assert Fernet(f).decrypt(v["cipher"].encode())==b"synthetic rollback only"
print(json.dumps({"pass":True,"new_jwt_readable_by_old":True,"new_fernet_readable_by_old":True,"synthetic_only":True,"old_runtime_unchanged":True}))'''
    data=subprocess.run([str(new),'-c',producer],check=True,capture_output=True,text=True,timeout=30).stdout
    checked=subprocess.run([str(old),'-c',consumer],input=data,check=True,capture_output=True,text=True,timeout=30)
    result=json.loads(checked.stdout)
    (root/'.runtime/phase3-crypto-rollback.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()
