"""Public synthetic vectors created with PyJWT2.13/cryptography49, no real keys."""
import unittest
import jwt
from cryptography.fernet import Fernet,InvalidToken

KEY='synthetic-compat-only-'+'0'*48
TOKEN='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIwMDAwMDAwMC0wMDAwLTAwMDAtMDAwMC0wMDAwMDAwMDAwMDAiLCJpc3MiOiJwYW8tbG9jYWwiLCJhdWQiOiJwYW8tYXBpIiwiaWF0IjoxNzAwMDAwMDAwLCJleHAiOjQxMDI0NDQ4MDB9.KvZzy0ykfe-yoO7aAEtxODUE-dl3GbFmqBov3g-fS88'
FERNET_KEY=b'AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8='
CIPHER=b'gAAAAABlU_EAdWPvM3u6rvXl2jcAOHaDJlJSXrJz64TqIDK2BgTu9attQQ0h151uZ9xLn9iv0gRoz-FOD43ApzTGmDCNWPLdaDjiARilLTokHOW-VY616cgJgrZkIGz4HZ4kpgcNGs3D'

class CompatibilityTests(unittest.TestCase):
    def test_old_valid_hs256_token_is_readable(self):
        claims=jwt.decode(TOKEN,KEY,algorithms=['HS256'],issuer='pao-local',audience='pao-api')
        self.assertEqual(claims['sub'],'00000000-0000-0000-0000-000000000000')
    def test_wrong_signature_algorithm_issuer_audience_remain_denied(self):
        for key,options in [(KEY+'wrong',{}),(KEY,{'issuer':'wrong'}),(KEY,{'audience':'wrong'})]:
            args={'issuer':'pao-local','audience':'pao-api',**options}
            with self.assertRaises(jwt.InvalidTokenError):jwt.decode(TOKEN,key,algorithms=['HS256'],**args)
        unsigned=jwt.encode({'sub':'synthetic'},key=None,algorithm='none')
        with self.assertRaises(jwt.InvalidTokenError):jwt.decode(unsigned,KEY,algorithms=['HS256'])
    def test_old_fernet_ciphertext_decrypts_without_rotation(self):
        f=Fernet(FERNET_KEY)
        self.assertEqual(f.decrypt(CIPHER),b'PAO synthetic compatibility only')
        self.assertEqual(f.decrypt(f.encrypt(b'roundtrip')),b'roundtrip')
    def test_wrong_fernet_key_and_tampering_are_denied(self):
        with self.assertRaises(InvalidToken):Fernet(Fernet.generate_key()).decrypt(CIPHER)
        with self.assertRaises(InvalidToken):Fernet(FERNET_KEY).decrypt(CIPHER[:-2]+b'AA')

if __name__=='__main__':unittest.main()
