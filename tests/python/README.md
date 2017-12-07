Upgrading the third party modules required for unit testing
===========================================================

The Toolkit package embeds all libraries required for unit testing. If you wish to update the
version of any library, update the `requirements.txt` file and then run the `update_third_party.sh`
script.

The scripts will invoke the the 2.6 version of `python` and `pip` since Python 2.6 is missing
libraries that setuptools will install on behalf of some packages (ordereddict for mock for example.)

If you wish to use other executables to `pip install` packages and run validation on the new
libraries, you can invoke the upgrade script like this:

```
./update_third_party.sh /usr/local/bin/pip /usr/local/bin/python
```