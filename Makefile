VENV=.venv
PY=$(VENV)/bin/python
PIP=$(VENV)/bin/pip

.PHONY: help venv install run demo clean

help:
	@echo "make venv        - create venv"
	@echo "make install     - install python deps"
	@echo "make demo        - create demo challenge"
	@echo "make run DIR=... - solve challenge dir"
	@echo "make clean       - remove venv + artifacts"

venv:
	python3 -m venv $(VENV)
	$(PIP) install -U pip

install: venv
	$(PIP) install -r requirements.txt
	$(PIP) install -e .

demo:
	mkdir -p challenges/demo
	printf "Find the flag. No network needed.\n" > challenges/demo/README.txt
	$(PY) - << 'PY'
import base64, pathlib
flag = "flag{local_artifact_only}"
b64 = base64.b64encode(flag.encode()).decode()
pathlib.Path("challenges/demo/encoded.txt").write_text(b64+"\n", encoding="utf-8")
PY

run:
	@[ -n "$(DIR)" ] || (echo "Usage: make run DIR=challenges/demo" && exit 2)
	$(PY) -m ctf_agent solve "$(DIR)" --out artifacts/latest --work artifacts/work

clean:
	rm -rf $(VENV) artifacts
