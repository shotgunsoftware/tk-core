rm -rf 3rdParty 
pip install -r requirements.txt -t 3rdParty
git add 3rdParty
python - <<EOF

import sys
sys.path.insert(0, '3rdParty')

print("===================")
try:
    import mock
    import unittest2
    print("Upgrade succesfull!")
except:
    print("Upgrade failed!")
