.PHONY: bootstrap fetch native test examples verify list
PYTHON := .venv/bin/python
bootstrap:
	sh scripts/bootstrap.sh
fetch:
	python3 scripts/deps.py fetch all
native:
	python3 scripts/deps.py submodules su2
	python3 scripts/build.py eigen chrono jsbsim su2
test:
	$(PYTHON) -m unittest discover -s tests -v
examples:
	$(PYTHON) -m physim pipeline examples/atmosphere_pipeline.json --output artifacts/atmosphere.json
	$(PYTHON) -m physim run cantera --output artifacts/cantera.json
	$(PYTHON) -m physim run chrono --output artifacts/chrono.json
	$(PYTHON) -m physim run su2 --output artifacts/su2.json
verify:
	$(PYTHON) scripts/verify.py
list:
	$(PYTHON) -m physim list
